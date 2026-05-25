"""
APEX Job Scheduler Module.

Handles scheduling APEX jobs for weekly stack installations and daily runs.
"""

from datetime import datetime
import requests

from .config_loader import config, get_config


# ===========================================
# APEX Job Scheduling
# ===========================================
def schedule_single_apex_job(apex_url, owner, subscription_id, job_name, priority, setup_queue, test_queue):
    """
    Schedule a single APEX job with specific parameters.
    
    Args:
        apex_url (str): The APEX API endpoint URL.
        owner (str): Job owner email.
        subscription_id (str): The APEX subscription ID for the target station.
        job_name (str): The full job name.
        priority (str): Job priority (1=highest, 5=lower).
        setup_queue (str): The setup queue name.
        test_queue (str): The test queue name.
    
    Returns:
        bool: True if job was scheduled successfully (HTTP 200), False otherwise.
    """
    data = {
        "name": job_name,
        "owner": owner,
        "priority": priority,
        "is_persistent": "false",
        "completion_criteria": "AllTestStations",
        "test_loops": "1",
        "subscription_id": subscription_id,
        "setup_queue": setup_queue,
        "test_queue": test_queue,
        "argument_overrides": "",
        "execution_label": get_config(config, "apex", "execution_label", "xhoe_scheduler_testing")
    }

    try:
        response = requests.post(apex_url, data=data, timeout=30)
        print(f"📤 APEX Job: {job_name} → {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error scheduling job: {e}")
        return False


def schedule_apex_job(apex_url, owner, subscription_id, station_name, permutation_name, install_stack=False):
    """
    Schedule APEX jobs for a station based on the run type (weekly or daily).
    
    For each station/permutation, schedules TWO jobs:
    1. Baseline job: Stack installation (weekly) or BIOS reset (daily) + baseline workloads
    2. Feature job: Feature enablement (with pmm_client.py) + feature workloads
    
    Each job type has its own priority:
    - Weekly: baseline=1, feature=2
    - Daily: baseline=4, feature=5
    
    Args:
        apex_url (str): The APEX API endpoint URL.
        owner (str): Job owner email.
        subscription_id (str): The APEX subscription ID for the target station.
        station_name (str): The name of the station to run the job on.
        permutation_name (str): The name of the feature permutation being tested.
        install_stack (bool): True = Weekly new stack, False = Daily run
    
    Returns:
        bool: True if all jobs were scheduled successfully, False if any failed.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S MYT')
    
    # Get config for weekly or daily run
    apex_config = config.get("apex", {})
    run_type = "weekly" if install_stack else "daily"
    run_config = apex_config.get(run_type, {})
    
    baseline_config = run_config.get("baseline", {})
    feature_config = run_config.get("feature", {})
    
    run_label = "Weekly Stack" if install_stack else "Daily"
    print(f"📋 Scheduling {run_label} jobs for {station_name} - {permutation_name}")
    
    all_success = True
    
    # Job 1: Baseline (stack install or BIOS reset + baseline workloads)
    baseline_job_name = f"{station_name} - Baseline - {timestamp}"
    baseline_priority = baseline_config.get("priority", "4")
    baseline_setup = baseline_config.get("setup_queue", "")
    baseline_test = baseline_config.get("test_queue", "")
    
    print(f"   📌 Job 1 (Baseline, P{baseline_priority}): {baseline_setup} → {baseline_test}")
    success = schedule_single_apex_job(
        apex_url, owner, subscription_id, baseline_job_name, baseline_priority, baseline_setup, baseline_test
    )
    if not success:
        all_success = False
    
    # Job 2: Feature (feature enablement with pmm_client + workloads)
    feature_job_name = f"{station_name} - {permutation_name} - {timestamp}"
    feature_priority = feature_config.get("priority", "5")
    feature_setup = feature_config.get("setup_queue", "")
    feature_test = feature_config.get("test_queue", "")
    
    print(f"   📌 Job 2 (Feature, P{feature_priority}): {feature_setup} → {feature_test}")
    success = schedule_single_apex_job(
        apex_url, owner, subscription_id, feature_job_name, feature_priority, feature_setup, feature_test
    )
    if not success:
        all_success = False
    
    return all_success


def schedule_permutations_to_stations(apex_url, owner, stations, permutations, install_stack=False):
    """
    Distribute feature permutations across available stations and schedule APEX jobs.
    
    Implements round-robin distribution of permutations to stations.
    
    Args:
        apex_url (str): The APEX API endpoint URL.
        owner (str): Job owner email.
        stations (dict): Stations config from stations.yaml.
        permutations (list): List of permutation names to schedule.
        install_stack (bool): True = Weekly new stack, False = Daily run
    
    Returns:
        dict: Summary of scheduling results.
    """
    print("🚀 Starting permutation distribution to stations...")
    
    if not permutations:
        print("⚠️ No permutations to schedule")
        return {"total_permutations": 0, "total_stations": 0, "scheduled": 0, "failed": 0, "assignments": []}
    
    if not stations:
        print("⚠️ No stations configured")
        return {"total_permutations": len(permutations), "total_stations": 0, "scheduled": 0, "failed": 0, "assignments": []}
    
    # Convert stations dict to list for round-robin assignment
    station_list = [
        (ip, info["subscription_id"], info["name"])
        for ip, info in stations.items()
    ]
    
    num_permutations = len(permutations)
    num_stations = len(station_list)
    
    print(f"📊 Permutations: {num_permutations}, Stations: {num_stations}")
    
    if num_permutations <= num_stations:
        print(f"✅ Permutations ({num_permutations}) ≤ Stations ({num_stations}): One job per station")
    else:
        print(f"⚠️ Permutations ({num_permutations}) > Stations ({num_stations}): Round-robin distribution")
    
    # Distribute permutations to stations in round-robin fashion
    assignments = []
    scheduled = 0
    failed = 0
    
    for i, perm_name in enumerate(permutations):
        station_index = i % num_stations
        ip, subscription_id, station_name = station_list[station_index]
        
        print(f"📌 Assigning '{perm_name}' to {station_name} (IP: {ip})")
        
        success = schedule_apex_job(apex_url, owner, subscription_id, station_name, perm_name, install_stack)
        
        if success:
            scheduled += 1
        else:
            failed += 1
        
        assignments.append((station_name, perm_name, success))
    
    print(f"\n📊 Scheduling Summary:")
    print(f"   Total Permutations: {num_permutations}")
    print(f"   Total Stations: {num_stations}")
    print(f"   Successfully Scheduled: {scheduled}")
    print(f"   Failed: {failed}")
    
    return {
        "total_permutations": num_permutations,
        "total_stations": num_stations,
        "scheduled": scheduled,
        "failed": failed,
        "assignments": assignments
    }
