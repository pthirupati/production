# Redis in FixitLab

Redis is used for **fast, in-memory operations** and real-time features.

## What Redis is used for
- Django Channels (WebSocket terminal)
- Session cache
- Rate limiting & abuse prevention
- Temporary lab/session state

## What Redis is NOT used for
- Persistent business data
- User records
- Scenario storage

Those are stored in PostgreSQL.

## Notes
- Redis data may be lost on restart (this is OK)
- PostgreSQL is the source of truth

