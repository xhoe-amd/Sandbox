"""
SMT Stack Release Monitor Module.

Monitors the Stack Management Tool (SMT) for new stack releases.
"""

from datetime import datetime
from enum import IntEnum
import requests
from requests_ntlm import HttpNtlmAuth

from .config_loader import logger


# ===========================================
# Program Enum
# ===========================================
class Program(IntEnum):
    """
    Enumeration of supported program IDs for SMT monitoring.
    """
    MAGNUS = 1            # Placeholder - ID TBD
    GAINSBOROUGH = 1434
    SOUNDWAVE = 1427
    CANIS = 1430


# ===========================================
# Time Helpers
# ===========================================
def get_today_start_timestamp():
    """Get Unix timestamp (ms) for start of today."""
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    return int(start.timestamp() * 1000)


def get_current_timestamp():
    """Get current Unix timestamp in milliseconds."""
    return int(datetime.now().timestamp() * 1000)


# ===========================================
# SMT API
# ===========================================
def check_timeline(smt_url, username, password, program_id):
    """
    Check SMT for new stack releases today.
    
    Queries the SMT API for stacks released between the start of today
    and the current time for the configured program.
    
    Args:
        smt_url (str): SMT API URL.
        username (str): Username for NTLM auth.
        password (str): Password for NTLM auth.
        program_id (int): Program ID from Program enum.
    
    Returns:
        bool: True if stack releases found, False otherwise.
    """
    payload = {
        "weeklyOrMajor": "All",
        "intOrNDA": "All",
        "platform": "All",
        "sku": None,
        "state": "All",
        "startDate": str(get_today_start_timestamp()),
        "endDate": str(get_current_timestamp()),
        "label": None,
        "programId": program_id,
        "qaType": "All",
        "dateType": "Released Between",
        "oem": "All"
    }

    headers = {"Content-Type": "application/json"}
    auth = HttpNtlmAuth(username, password)

    try:
        r = requests.post(smt_url, json=payload, headers=headers, auth=auth, timeout=30)
        data = r.json()
        info = data.get("info", [])

        if info:
            logger.info("Stack release found!")
            return True
        else:
            logger.debug("No stack release")
            return False

    except Exception as e:
        logger.warning(f"SMT error: {e}")
        return False
