import requests
from requests_ntlm import HttpNtlmAuth
import json
import time
from datetime import datetime, timedelta
import requests

from enum import IntEnum

class Program(IntEnum):
    # MAGNUS = 1 ## Magnus not found on SMT yet
    GAINSBOROUGH = 1434
    SOUNDWAVE = 1427
    CANIS = 1430

# =========================
# CONFIGURATION
# =========================
USERNAME = ""
PASSWORD = ""
PROGRAM_ID = Program.SOUNDWAVE

auth = HttpNtlmAuth(USERNAME, PASSWORD)

URL = "http://atlstmapp01.amd.com:1234/api/getStacksForTimeline"

HEADERS = {
    "Content-Type": "application/json"
}

def schedule_apex_farm_job():
    url = "http://apexlegacy.amd.com/jobs"

    data = {
        "name": f"SchedulerTest - {datetime.now().strftime('%Y-%m-%d %H:%M:%S MYT')}",
        "owner": "xhoe@amd.com",
        "priority": "3",
        "is_persistent": "false",
        "completion_criteria": "AllTestStations",
        "test_loops": "1",
        "subscription_id": "4574",
        "setup_queue": "Scheduler Test - Setup",
        "test_queue": "Scheduler Test - Execute",
        "argument_overrides": "",
        "execution_label": "xhoe_scheduler_testing"
    }

    response = requests.post(url, data=data)

    print(response.status_code)
    print(response.text)

# =========================
# TIME HELPER
# =========================
def get_today_start_timestamp():
    now = datetime.now()
    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
    return int(start_of_day.timestamp() * 1000)  # milliseconds


def get_current_timestamp():
    return int(datetime.now().timestamp() * 1000)

# =========================
# API CALL
# =========================
def check_timeline():
    start_ts = get_today_start_timestamp()
    end_ts = get_current_timestamp()

    payload = {
        "weeklyOrMajor": "All",
        "intOrNDA": "All",
        "platform": "All",
        "sku": None,
        "state": "All",
        "startDate": str(start_ts),
        "endDate": str(end_ts),
        "label": None,
        "programId": PROGRAM_ID,
        "qaType": "All",
        "dateType": "Released Between",
        "oem": "All"
    }

    # payload = {
    #     "weeklyOrMajor": "All",
    #     "intOrNDA": "All",
    #     "platform": "All",
    #     "sku": None,
    #     "state": "All",
    #     "startDate": "1778428800000",
    #     "endDate": "1778515200000",
    #     "label": None,
    #     "programId": 1427,
    #     "qaType": "All",
    #     "dateType": "Released Between",
    #     "oem": "All"
    # }

    print(f"\n[{datetime.now()}] Checking data...")
    print(f"Start: {start_ts}, End: {end_ts}")

    try:
        response = requests.post(
            URL,
            headers=HEADERS,
            json=payload,
            auth=auth,
            timeout=60
        )

        print("Status Code:", response.status_code)
        print("Response Body:", response.text)

        if response.ok:
            data = response.json()

            info = data.get("info", [])

            if info:
                print("🚨 STACK RELEASE FOUND!")
                print(json.dumps(info, indent=4))
                schedule_apex_farm_job()

                # 👉 Optional: save to file
                with open("alert_log.json", "a") as f:
                    f.write(json.dumps(info) + "\n")

            else:
                print("✅ No Stack Release Found.")

        else:
            print("❌ Error:", response.text)

    except Exception as e:
        print("⚠️ Request failed:", str(e))


# =========================
# MAIN LOOP (24/7)
# =========================
def run_forever():
    print("🚀 Starting 24/7 monitoring (every hour)...")

    while True:
        check_timeline()

        print("⏳ Sleeping for 1 hour...\n")
        time.sleep(3600)  # 1 hour


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    run_forever()