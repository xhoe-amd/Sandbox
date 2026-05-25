"""
Weekend APEX Job Scheduler.

This script checks if it's Saturday or Sunday and schedules APEX jobs
on weekends for MRDC Weekly Stack Installation.

Usage:
    python weekend_scheduler.py [OPTIONS]

Command-line Arguments:
    --check-interval SEC   How often to check (default: 60 seconds)
    --apex-url URL         APEX job scheduler URL
    --owner EMAIL          APEX job owner email
    --priority NUM         APEX job priority (default: 3)
    --execution-label NAME APEX execution label

Author: xhoe@amd.com
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, date
import requests


# =========================
# Directory and file paths
# =========================
# Use %LOCALAPPDATA% for Windows (standard location for per-user app data)
# Falls back to user home directory on other platforms
APP_NAME = "APEXScheduler"
if os.name == 'nt':  # Windows
    APP_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), APP_NAME)
else:  # Linux/Mac
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), f'.{APP_NAME.lower()}')

os.makedirs(APP_DATA_DIR, exist_ok=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(APP_DATA_DIR, "scheduler_state.json")
LOG_FILE_APPDATA = os.path.join(APP_DATA_DIR, "stack_install_scheduler.log")
LOG_FILE_LOCAL = os.path.join(SCRIPT_DIR, "stack_install_scheduler.log")


# =========================
# Logging Setup
# =========================
def setup_logging(level=logging.INFO):
    """Configure logging to console and two files."""
    log_format = '%(asctime)s [ %(levelname)s ] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    log = logging.getLogger('scheduler')
    log.setLevel(level)
    
    if log.handlers:
        return log
    
    formatter = logging.Formatter(log_format, date_format)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)
    
    # File handler - AppData (persistent)
    appdata_handler = logging.FileHandler(LOG_FILE_APPDATA, encoding='utf-8')
    appdata_handler.setFormatter(formatter)
    log.addHandler(appdata_handler)
    
    # File handler - Local directory (convenient)
    local_handler = logging.FileHandler(LOG_FILE_LOCAL, encoding='utf-8')
    local_handler.setFormatter(formatter)
    log.addHandler(local_handler)
    
    return log


logger = setup_logging()

# =========================
# Subscription configurations
# =========================
SUBSCRIPTIONS = [
    {
        "subscription_id": "4600",
        "name_prefix": "SWV - MRDC Weekly Stack Installation",
        "test_queue": "SWV - Weekly Stack Installation"
    },
    # {
    #     "subscription_id": "4601",
    #     "name_prefix": "CNS - MRDC Weekly Stack Installation",
    #     "test_queue": "CNS - Weekly Stack Installation"
    # }
]

# =========================
# Argument parsing
# =========================
parser = argparse.ArgumentParser(description="Weekend APEX Job Scheduler")

parser.add_argument(
    "--check-interval",
    type=int,
    default=60,
    help="How often to check the day (in seconds, default: 60)"
)

parser.add_argument(
    "--apex-url",
    default="http://apexlegacy.amd.com/jobs",
    help="APEX job scheduler URL"
)

parser.add_argument(
    "--owner",
    default="xhoe@amd.com",
    help="APEX job owner email"
)

parser.add_argument(
    "--priority",
    default="3",
    help="APEX job priority"
)

parser.add_argument(
    "--execution-label",
    default="MRDC Weekly Stack Installation",
    help="APEX execution label"
)

args = parser.parse_args()


# =========================
# Schedule APEX job
# =========================
def schedule_apex_job(subscription_id, job_name, test_queue):
    """
    Schedule a new job on the APEX legacy system.
    
    Args:
        subscription_id (str): The APEX subscription ID.
        job_name (str): The full job name.
        test_queue (str): The test queue name for this subscription.
    
    Returns:
        bool: True if job was scheduled successfully, False otherwise.
    """
    data = {
        "name": job_name,
        "owner": args.owner,
        "priority": args.priority,
        "is_persistent": "false",
        "completion_criteria": "AllTestStations",
        "test_loops": "1",
        "subscription_id": subscription_id,
        "setup_queue": "",
        "test_queue": test_queue,
        "argument_overrides": "",
        "execution_label": args.execution_label
    }

    try:
        response = requests.post(args.apex_url, data=data, timeout=30)
        logger.info(f"APEX Job: {job_name} → {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error scheduling job: {e}")
        return False


# =========================
# Schedule weekend jobs
# =========================
def schedule_weekend_jobs():
    """
    Schedule APEX jobs for all configured subscriptions.
    
    Returns:
        bool: True if all jobs were scheduled successfully, False if any failed.
    """
    logger.info("Scheduling weekend jobs...")
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S MYT')
    scheduled = 0
    failed = 0
    
    for sub in SUBSCRIPTIONS:
        subscription_id = sub["subscription_id"]
        test_queue = sub["test_queue"]
        job_name = f"{sub['name_prefix']} {timestamp}"
        
        logger.info(f"Scheduling: {job_name} (Sub ID: {subscription_id}, Queue: {test_queue})")
        
        success = schedule_apex_job(subscription_id, job_name, test_queue)
        
        if success:
            scheduled += 1
        else:
            failed += 1
    
    logger.info("Scheduling Summary:")
    logger.info(f"  Successfully Scheduled: {scheduled}")
    if failed > 0:
        logger.warning(f"  Failed: {failed}")
    
    # Return True only if all jobs succeeded
    all_success = (failed == 0 and scheduled > 0)
    return all_success


# =========================
# Check if it's weekend
# =========================
def is_weekend():
    """Check if today is Saturday (5) or Sunday (6)."""
    return datetime.now().weekday() in (5, 6)


# =========================
# State persistence
# =========================
def load_last_scheduled_date():
    """
    Load the last scheduled date from the state file.
    
    Returns:
        date or None: The last scheduled date, or None if not found.
    """
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                date_str = state.get("last_scheduled_date")
                if date_str:
                    loaded_date = date.fromisoformat(date_str)
                    logger.debug(f"Loaded state: Last scheduled on {loaded_date}")
                    return loaded_date
    except Exception as e:
        logger.warning(f"Could not load state file: {e}")
    return None


def save_last_scheduled_date(scheduled_date):
    """
    Save the last scheduled date to the state file.
    
    Args:
        scheduled_date (date): The date to save.
    """
    try:
        state = {"last_scheduled_date": scheduled_date.isoformat()}
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved state: Last scheduled on {scheduled_date}")
    except Exception as e:
        logger.warning(f"Could not save state file: {e}")


# =========================
# Main loop
# =========================
def main():
    """
    Main loop that monitors for weekends and schedules jobs.
    Schedules once per weekend day when detected.
    """
    logger.info("Weekend Scheduler Started")
    logger.info(f"  Check interval: {args.check_interval} seconds")
    logger.info(f"  APEX URL: {args.apex_url}")
    logger.info("  Jobs to schedule:")
    for sub in SUBSCRIPTIONS:
        logger.info(f"    - {sub['subscription_id']}: {sub['name_prefix']} → {sub['test_queue']}")
    
    # Track if we've already scheduled for today (load from persistent state)
    last_scheduled_date = load_last_scheduled_date()
    
    while True:
        now = datetime.now()
        today = now.date()
        
        logger.debug(f"Checking day...")
        
        # Check if it's weekend
        if is_weekend():
            day_name = now.strftime("%A")
            logger.info(f"Today is {day_name} (Weekend)")
            
            # Schedule if we haven't scheduled today
            if last_scheduled_date != today:
                logger.info(f"It's {day_name}! Scheduling jobs...")
                success = schedule_weekend_jobs()
                
                if success:
                    last_scheduled_date = today
                    save_last_scheduled_date(today)
                    logger.info(f"Scheduled for {today}. Will not schedule again today.")
                else:
                    logger.error("Scheduling failed. Will retry on next check.")
            else:
                logger.debug(f"Already scheduled for today ({today})")
        else:
            day_name = now.strftime("%A")
            logger.debug(f"Today is {day_name} (Weekday - not scheduling)")
        
        time.sleep(args.check_interval)


# =========================
# Entry point
# =========================
if __name__ == "__main__":
    main()
