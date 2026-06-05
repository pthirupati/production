"""
Custom DRF throttles for resource-intensive operations.
"""
from rest_framework.throttling import UserRateThrottle


class LabStartThrottle(UserRateThrottle):
    """
    Limit lab starts to 5 per hour per authenticated user.
    Prevents abuse of container provisioning resources.
    """
    scope = "lab_start"
    rate = "5/hour"
