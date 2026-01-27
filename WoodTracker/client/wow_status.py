import time
from parse_savedvariables import load_sync_data

HEARTBEAT_TIMEOUT = 15  # secondes

def is_wow_alive_via_heartbeat():
    try:
        sync = load_sync_data()
        hb = sync.get("heartbeat")
        if not hb:
            return False
        return (time.time() - hb) < HEARTBEAT_TIMEOUT
    except Exception:
        return False
