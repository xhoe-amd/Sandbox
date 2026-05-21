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
import time
from datetime import datetime
import requests

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
        "test_queue": test_queue,
        "argument_overrides": "",
        "execution_label": args.execution_label
    }

    try:
        response = requests.post(args.apex_url, data=data, timeout=30)
        print(f"📤 APEX Job: {job_name} → {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error scheduling job: {e}")
        return False


# =========================
# Schedule weekend jobs
# =========================
def schedule_weekend_jobs():
    """Schedule APEX jobs for both SWV (4600) and CNS (4601)."""
    print("🚀 Scheduling weekend jobs...")
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S MYT')
    scheduled = 0
    failed = 0
    
    for sub in SUBSCRIPTIONS:
        subscription_id = sub["subscription_id"]
        test_queue = sub["test_queue"]
        job_name = f"{sub['name_prefix']} {timestamp}"
        
        print(f"📌 Scheduling: {job_name} (Sub ID: {subscription_id}, Queue: {test_queue})")
        
        success = schedule_apex_job(subscription_id, job_name, test_queue)
        
        if success:
            scheduled += 1
        else:
            failed += 1
    
    print(f"\n📊 Scheduling Summary:")
    print(f"   Successfully Scheduled: {scheduled}")
    print(f"   Failed: {failed}")


# =========================
# Check if it's weekend
# =========================
def is_weekend():
    """Check if today is Saturday (5) or Sunday (6)."""
    return datetime.now().weekday() in (5, 6)


# =========================
# Main loop
# =========================
def main():
    """
    Main loop that monitors for weekends and schedules jobs.
    Schedules once per weekend day when detected.
    """
    print("🚀 Weekend Scheduler Started")
    print(f"   Check interval: {args.check_interval} seconds")
    print(f"   APEX URL: {args.apex_url}")
    print(f"   Jobs to schedule:")
    for sub in SUBSCRIPTIONS:
        print(f"      - {sub['subscription_id']}: {sub['name_prefix']} → {sub['test_queue']}")
    print("")
    
    # Track if we've already scheduled for today
    last_scheduled_date = None
    
    while True:
        now = datetime.now()
        today = now.date()
        
        print(f"⏰ [{now.strftime('%Y-%m-%d %H:%M:%S')}] Checking...")
        
        # Check if it's weekend
        if is_weekend():
            day_name = now.strftime("%A")
            print(f"📅 Today is {day_name} (Weekend)")
            
            # Schedule if we haven't scheduled today
            if last_scheduled_date != today:
                print(f"🚀 It's {day_name}! Scheduling jobs...")
                schedule_weekend_jobs()
                last_scheduled_date = today
                print(f"✅ Scheduled for {today}. Will not schedule again today.")
            else:
                print(f"⏳ Already scheduled for today ({today})")
        else:
            day_name = now.strftime("%A")
            print(f"📅 Today is {day_name} (Weekday - not scheduling)")
        
        print("")
        time.sleep(args.check_interval)


# =========================
# Entry point
# =========================
if __name__ == "__main__":
    main()
