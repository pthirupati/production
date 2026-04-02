# RabbitMQ in FixitLab

RabbitMQ is used as the **message broker** for Celery.

## What RabbitMQ is used for
- Async lab provisioning
- Lab cleanup & expiry jobs
- Background validation tasks
- Periodic jobs via Celery Beat

## What RabbitMQ is NOT used for
- Real-time WebSockets (Redis does that)
- Caching
- Persistent storage

## Management UI
Access at:
http://localhost:15672

(Default credentials: guest / guest)

