import os
import time

import psutil


def get_uptime(round_to: int = 2) -> float:
    """Get uptime of the current process."""
    now = time.time()
    p = psutil.Process(os.getpid())
    return round(now - p.create_time(), round_to)
