"""Process-wide MongoClient.

PyMongo's guidance is one client per process, reused for every operation. A MongoClient
is not a cheap handle: each one opens its own connection pool and starts background
monitor threads, so building and closing one per request churns threads on every Alexa
turn and every dashboard poll for no benefit.

That churn is the leading suspect behind the recurring SIGSEGV in this service. The
crash surfaces in SQLAlchemy's session teardown, but a core dump showed a corrupted
pymalloc freelist, i.e. heap corruption written earlier by some C extension and only
tripped over later at an unrelated allocation.

Callers must not close what they get from here.
"""

import logging
import threading

from .config import mongodb_url, mongodb_client_kwargs

try:
    from pymongo import MongoClient
except ImportError:  # pymongo is optional at import time
    MongoClient = None

_client = None
_lock = threading.Lock()


def get_mongo_client():
    """Return the shared client, or None when pymongo is missing or unreachable."""
    global _client
    if MongoClient is None:
        return None
    if _client is None:
        with _lock:
            if _client is None:
                try:
                    _client = MongoClient(
                        mongodb_url,
                        **mongodb_client_kwargs,
                        serverSelectionTimeoutMS=3000,
                    )
                except Exception as exc:
                    logging.warning("Failed to create shared MongoDB client: %s", exc)
                    return None
    return _client
