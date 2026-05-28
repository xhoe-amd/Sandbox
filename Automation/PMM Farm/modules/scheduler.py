"""
APEX Job Scheduler Module.

Handles scheduling APEX jobs for weekly stack installations and daily runs.
"""

from datetime import datetime
import requests

from .config_loader import config, get_config, logger


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
    # Get job defaults from config
    apex_config = config.get("apex", {})
    job_defaults = apex_config.get("job_defaults", {})
    
    data = {
        "name": job_name,
        "owner": owner,
        "priority": priority,
        "is_persistent": job_defaults.get("is_persistent", "false"),
        "completion_criteria": job_defaults.get("completion_criteria", "AllTestStations"),
        "test_loops": job_defaults.get("test_loops", "1"),
        "subscription_id": subscription_id,
        "setup_queue": setup_queue,
        "test_queue": test_queue,
        "argument_overrides": job_defaults.get("argument_overrides", ""),
        "execution_label": apex_config.get("execution_label", "xhoe_scheduler_testing")
    }

    # Get timeout from config
    timeout = get_config(config, "intervals", "apex_timeout", 30)

    try:
        response = requests.post(apex_url, data=data, timeout=timeout)
        logger.info(f"APEX Job: {job_name} → {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error scheduling job: {e}")
        return False


def schedule_permutations_to_stations(apex_url, owner, stations, permutations, install_stack=False, weekly_permutations=False, program="SOUNDWAVE", preschedule_mode=True):
    """
    Schedule APEX jobs to stations.
    
    Flow:
    - Weekly (install_stack=True): Baseline only (unless weekly_permutations=True)
    - Daily (install_stack=False): Baseline + all feature permutations
    
    Args:
        apex_url (str): The APEX API endpoint URL.
        owner (str): Job owner email.
        stations (dict): Stations config from stations.yaml.
        permutations (list): List of permutation names to schedule.
        install_stack (bool): True = Weekly new stack, False = Daily run
        weekly_permutations (bool): If True, run permutations on weekly runs too
        program (str): Program name (SOUNDWAVE, GAINSBOROUGH, CANIS)
        preschedule_mode (bool): If True, assign permutations to specific stations (IP-based).
                                 If False, generic scheduling (no station-specific assignments).
    
    Returns:
        dict: Summary of scheduling results including 'station_assignments' 
              mapping station IPs to their assigned permutation names (only when preschedule_mode=True).
    """
    logger.info("Starting job scheduling...")
    logger.info(f"Program: {program}")
    
    if not stations:
        logger.warning("No stations configured")
        return {"baseline_scheduled": False, "feature_scheduled": 0, "failed": 0}
    
    # Get config for program and run type
    apex_config = config.get("apex", {})
    programs_config = apex_config.get("programs", {})
    program_config = programs_config.get(program, {})
    
    if not program_config:
        logger.warning(f"No config found for program: {program}")
        return {"baseline_scheduled": False, "feature_scheduled": 0, "failed": 0}
    
    run_type = "weekly" if install_stack else "daily"
    run_config = program_config.get(run_type, {})
    
    baseline_config = run_config.get("baseline", {})
    feature_config = run_config.get("feature", {})
    
    run_label = "Weekly Stack" if install_stack else "Daily"
    logger.info(f"Run type: {run_label}")
    logger.info(f"Preschedule mode: {'ON' if preschedule_mode else 'OFF'}")
    
    # Convert stations dict to list
    station_list = [
        (ip, info["subscription_id"], info["name"])
        for ip, info in stations.items()
    ]
    num_stations = len(station_list)
    
    # Get timestamp format from config
    timestamp_format = config.get("apex", {}).get("timestamp_format", "%Y-%m-%d %H:%M:%S MYT")
    timestamp = datetime.now().strftime(timestamp_format)
    baseline_success = True
    feature_scheduled = 0
    failed = 0
    
    # =========================================
    # Step 1: Schedule ONE baseline job
    # =========================================
    logger.info("Step 1: Scheduling baseline job (ONCE)")
    baseline_priority = baseline_config.get("priority", "4")
    baseline_setup = baseline_config.get("setup_queue", "")
    baseline_test = baseline_config.get("test_queue", "")
    
    # Use first station for baseline job
    ip, subscription_id, station_name = station_list[0]
    baseline_job_name = f"Baseline - {timestamp}"
    
    logger.info(f"  Baseline (P{baseline_priority}): {baseline_setup} → {baseline_test}")
    baseline_success = schedule_single_apex_job(
        apex_url, owner, subscription_id, baseline_job_name, baseline_priority, baseline_setup, baseline_test
    )
    
    if not baseline_success:
        logger.error("  Baseline job failed")
    
    # =========================================
    # Step 2: Schedule feature jobs for each permutation
    # =========================================
    # Track station assignments: IP -> list of assigned permutation names (only for preschedule mode)
    station_assignments = {ip: [] for ip, _, _ in station_list} if preschedule_mode else {}
    
    # Skip permutations for weekly unless weekly_permutations flag is enabled
    skip_permutations = install_stack and not weekly_permutations
    
    if skip_permutations:
        logger.info("Weekly run: Skipping permutations (baseline only)")
        logger.info("  Set weekly_permutations=true in config to enable")
    elif not permutations:
        logger.warning("No permutations to schedule feature jobs")
    else:
        logger.info(f"Step 2: Scheduling feature jobs ({len(permutations)} permutations)")
        feature_priority = feature_config.get("priority", "5")
        feature_setup = feature_config.get("setup_queue", "")
        feature_test = feature_config.get("test_queue", "")
        
        for i, perm_name in enumerate(permutations):
            # Round-robin distribution across stations
            station_index = i % num_stations
            ip, subscription_id, station_name = station_list[station_index]
            
            # Track assignment for this station (only in preschedule mode)
            if preschedule_mode:
                station_assignments[ip].append(perm_name)
                # Job name includes permutation name (tied to specific station)
                feature_job_name = f"{station_name} - {perm_name} - {timestamp}"
                logger.info(f"  {perm_name} → {station_name} ({ip}) (P{feature_priority})")
            else:
                # Job name does NOT include permutation name (free-for-all mode)
                feature_job_name = f"{station_name} - Feature Job {i+1} - {timestamp}"
                logger.info(f"  Job {i+1} → {station_name} (P{feature_priority})")
            
            success = schedule_single_apex_job(
                apex_url, owner, subscription_id, feature_job_name, feature_priority, feature_setup, feature_test
            )
            if success:
                feature_scheduled += 1
            else:
                failed += 1
    
    # =========================================
    # Summary
    # =========================================
    logger.info("Scheduling Summary:")
    logger.info(f"  Baseline job: {'Success' if baseline_success else 'Failed'}")
    logger.info(f"  Feature jobs scheduled: {feature_scheduled}/{len(permutations) if permutations else 0}")
    if failed > 0:
        logger.warning(f"  Failed: {failed}")
    
    # Log station assignments (only for preschedule mode)
    if preschedule_mode:
        logger.info("Station Assignments:")
        for ip, assigned_perms in station_assignments.items():
            station_name = next((name for i, _, name in station_list if i == ip), ip)
            logger.info(f"  {station_name} ({ip}): {len(assigned_perms)} permutations")
    else:
        logger.info("Free-for-all mode: No station-specific assignments")
    
    return {
        "baseline_scheduled": baseline_success,
        "feature_scheduled": feature_scheduled,
        "total_permutations": len(permutations) if permutations else 0,
        "failed": failed,
        "station_assignments": station_assignments
    }
