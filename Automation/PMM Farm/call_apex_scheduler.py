# import requests

# url = "http://apexlegacy.amd.com/jobs"

# data = {
#     "name": "SchedulerTest1",
#     "owner": "xhoe@amd.com",
#     "priority": "3",
#     "is_persistent": "false",
#     "completion_criteria": "AllTestStations",
#     "test_loops": "1",
#     "subscription_id": "4574",
#     "setup_queue": "Scheduler Test - Setup",
#     "test_queue": "Scheduler Test - Execute",
#     "argument_overrides": "",
#     "execution_label": "xhoe_scheduler_testing"
# }

# response = requests.post(url, data=data)

# print(response.status_code)
# print(response.text)

import requests
from requests_ntlm import HttpNtlmAuth
import json

# =========================
# CONFIGURATION
# =========================
USERNAME = "xhoe"
PASSWORD = "Vgt@19990703"

# If domain is required, use:
# USERNAME = "DOMAIN\\user"

auth = HttpNtlmAuth(USERNAME, PASSWORD)

# =========================
# 1. GET API (Program API)
# =========================
def get_program():
    url = "http://mkmsmtapp01.amd.com:8084/api/v1/program"
    params = {
        "name": "sampleprogram"
    }

    print("\n--- Calling GET API (Program) ---")

    try:
        response = requests.get(url, params=params, auth=auth)

        print("Status Code:", response.status_code)

        if response.ok:
            try:
                print(json.dumps(response.json(), indent=4))
            except:
                print(response.text)
        else:
            print("Error:", response.text)

    except requests.exceptions.RequestException as e:
        print("Request failed:", e)


# =========================
# 2. POST API (Timeline API)
# =========================
def get_timeline():
    url = "http://atlstmapp01.amd.com:1234/api/getStacksForTimeline"

    payload = {
        "weeklyOrMajor": "All",
        "intOrNDA": "All",
        "platform": "All",
        "sku": None,
        "state": "All",
        "startDate": "1778428800000",
        "endDate": "1778515200000",
        "label": None,
        "programId": 1427,
        "qaType": "All",
        "dateType": "Released Between",
        "oem": "All"
    }

    headers = {
        "Content-Type": "application/json"
    }

    print("\n--- Calling POST API (Timeline) ---")

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            auth=auth
        )

        print("Status Code:", response.status_code)

        if response.ok:
            try:
                print(json.dumps(response.json(), indent=4))
            except:
                print(response.text)
        else:
            print("Error:", response.text)

    except requests.exceptions.RequestException as e:
        print("Request failed:", e)


# =========================
# MAIN EXECUTION
# =========================
if __name__ == "__main__":
    get_program()
    get_timeline()