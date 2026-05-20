import requests

url = "http://apexlegacy.amd.com/jobs"

data = {
    "name": "SchedulerTest1",
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