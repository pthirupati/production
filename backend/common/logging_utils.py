"""
Structured JSON logging with PII masking for production deployments.

Logs are formatted as structured JSON for easy parsing by log aggregation
systems like ELK Stack, CloudWatch, or DataDog. Sensitive data is masked.

Example structured log output:
{
    "timestamp": "2024-01-15T10:30:45.123Z",
    "level": "INFO",
    "logger": "apps.accounts.views",
    "message": "User login successful",
    "user_id": 12345,
    "email": "us***@domain.com",
    "ip": "192.168.1.100",
    "request_id": "abc123xyz789",
    "path": "/api/auth/login",
    "method": "POST",
    "status": 200,
    "duration_ms": 245,
    "tags": ["auth", "security"],
}
"""

import json
import logging
import time
from datetime import datetime
from django.conf import settings
from .security import mask_pii


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    Masks PII automatically and includes request context.
    """
    
    def format(self, record):
        """Convert log record to structured JSON."""
        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Extract and mask request context if available
        if hasattr(record, 'request') and record.request:
            request = record.request
            log_data["request_id"] = getattr(request, 'id', None) or getattr(request, 'uuid', None)
            log_data["method"] = request.method
            log_data["path"] = request.path
            log_data["ip"] = self._get_client_ip(request)
            
            # Add user info if authenticated
            if hasattr(request, 'user') and request.user.is_authenticated:
                log_data["user_id"] = request.user.id
                log_data["email"] = mask_pii(request.user.email)
                log_data["username"] = request.user.username
        
        # Add custom fields from record (e.g., fields passed in extra={})
        if hasattr(record, 'fields'):
            for key, value in record.fields.items():
                if key in ['email', 'phone', 'ssn', 'card', 'passcode']:
                    value = mask_pii(str(value)) if value else None
                log_data[key] = value
        
        # Add structured fields if present
        if hasattr(record, 'structured'):
            for key, value in record.structured.items():
                if key in ['email', 'phone', 'ssn', 'card', 'passcode', 'password']:
                    value = mask_pii(str(value)) if value else None
                log_data[key] = value
        
        # Add tags if present
        if hasattr(record, 'tags'):
            log_data["tags"] = record.tags
        
        return json.dumps(log_data, default=str)
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request, accounting for proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class StructuredLogger:
    """
    Convenience wrapper around Python logger for structured logging.
    
    Usage:
        logger = StructuredLogger.get('myapp.mymodule')
        logger.info("Payment processed", user_id=123, amount=99.99)
        logger.warning("Suspicious login", email="user@domain.com", ip="192.168.1.1", tags=["security"])
        logger.error("Database error", error_code="CONN_TIMEOUT", severity="high")
    """
    
    _loggers = {}
    
    @classmethod
    def get(cls, name):
        """Get or create a structured logger."""
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            cls._loggers[name] = StructuredLoggerInstance(logger)
        return cls._loggers[name]


class StructuredLoggerInstance:
    """Instance of a structured logger with convenience methods."""
    
    def __init__(self, logger):
        self.logger = logger
    
    def _log(self, level, message, **kwargs):
        """Internal logging method with structured fields."""
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "(unknown file)", 0,
            message,
            (),
            None
        )
        
        # Attach structured fields
        record.structured = kwargs
        
        # Extract tags if provided
        record.tags = kwargs.pop('tags', [])
        
        self.logger.handle(record)
    
    def debug(self, message, **kwargs):
        """Log debug message with structured fields."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message, **kwargs):
        """Log info message with structured fields."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message, **kwargs):
        """Log warning message with structured fields."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message, **kwargs):
        """Log error message with structured fields."""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message, **kwargs):
        """Log critical message with structured fields."""
        self._log(logging.CRITICAL, message, **kwargs)
    
    # Aliases for common usage
    def warn(self, message, **kwargs):
        """Alias for warning()."""
        self.warning(message, **kwargs)
    
    def err(self, message, **kwargs):
        """Alias for error()."""
        self.error(message, **kwargs)


def get_structured_logger(name):
    """Convenience function to get a structured logger."""
    return StructuredLogger.get(name)
