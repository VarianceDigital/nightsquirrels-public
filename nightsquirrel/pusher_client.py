import os
import logging

log = logging.getLogger(__name__)

_pusher_instance = None


def get_pusher():
    """Return a singleton pusher.Pusher instance, or None if not configured."""
    global _pusher_instance

    if _pusher_instance is not None:
        return _pusher_instance

    app_id = os.environ.get("PUSHER_APP_ID")
    key = os.environ.get("PUSHER_KEY")
    secret = os.environ.get("PUSHER_SECRET")
    cluster = os.environ.get("PUSHER_CLUSTER")

    if not all([app_id, key, secret, cluster]):
        log.warning("Pusher env vars not set; real-time comments disabled")
        return None

    import pusher
    _pusher_instance = pusher.Pusher(
        app_id=app_id,
        key=key,
        secret=secret,
        cluster=cluster,
        ssl=True,
    )
    return _pusher_instance


def get_pusher_key():
    """Return the PUSHER_KEY (needed client-side), or empty string."""
    return os.environ.get("PUSHER_KEY", "")


def get_pusher_cluster():
    """Return the PUSHER_CLUSTER (needed client-side), or empty string."""
    return os.environ.get("PUSHER_CLUSTER", "")
