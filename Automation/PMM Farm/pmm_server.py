"""
PMM Server - Feature Testing Automation Server.

A REST API server that manages feature flag combinations for automated testing.
Monitors YAML config for changes and optionally monitors SMT for stack releases.

Usage:
    python pmm_server.py [OPTIONS]

Author: xhoe@amd.com
"""

import argparse
import os
import threading
import time
from datetime import datetime, date
from queue import Queue

from flask import Flask, jsonify, request

from modules.config_loader import (
    config, get_config, SCRIPT_DIR, logger,
    load_persistent_state, save_persistent_state
)
from modules.constants import Program
from modules.scheduler import schedule_permutations_to_stations
from modules.smt_monitor import check_timeline
from modules.yaml_processor import (
    get_current_week, load_yaml, load_stations_config,
    compute_hash, process_week_features, write_files, get_permutation_names
)


# ===========================================
# Argument Parsing
# ===========================================
parser = argparse.ArgumentParser(description="PMM Server - Feature Testing Automation")

# File paths
parser.add_argument("--yaml", 
                    default=os.path.join(SCRIPT_DIR, get_config(config, "paths", "feature_yaml", "enable_feature.yaml")))
parser.add_argument("--stations",
                    default=os.path.join(SCRIPT_DIR, get_config(config, "paths", "stations_yaml", "stations.yaml")))
parser.add_argument("--output", default=get_config(config, "paths", "output_dir", "output"))

# Server settings
parser.add_argument("--port", type=int, default=get_config(config, "server", "port", 5000))
parser.add_argument("--host", default=get_config(config, "server", "host", "0.0.0.0"))

# Mode flags
parser.add_argument("--permute", action="store_true", default=get_config(config, "modes", "permutation", False))
parser.add_argument("--smt", action="store_true", default=get_config(config, "modes", "smt_monitor", False))
parser.add_argument("--weekly-permutations", action="store_true", 
                    default=get_config(config, "modes", "weekly_permutations", False),
                    help="Run permutations on weekly stack runs (default: baseline only)")
parser.add_argument("--preschedule", action="store_true",
                    default=get_config(config, "modes", "preschedule", True),
                    help="Preschedule mode: assign files to specific stations (IP-based). "
                         "If off, free-for-all mode where any client can get any file.")

# Program selection (global setting)
parser.add_argument("--program", default=config.get("program", "SOUNDWAVE"),
                    choices=[p.name for p in Program],
                    help="Program: SOUNDWAVE, GAINSBOROUGH, CANIS")

# SMT settings (env vars: PMM_USERNAME, PMM_PASSWORD)
parser.add_argument("--username", 
                    default=os.environ.get("PMM_USERNAME", get_config(config, "smt", "username", "")))
parser.add_argument("--password", 
                    default=os.environ.get("PMM_PASSWORD", get_config(config, "smt", "password", "")))
parser.add_argument("--smt-url", default=get_config(config, "smt", "url", ""))

# APEX settings
parser.add_argument("--apex-url", default=get_config(config, "apex", "url", "http://apexlegacy.amd.com/jobs"))
parser.add_argument("--owner", default=get_config(config, "apex", "owner", "xhoe@amd.com"))

# Intervals
parser.add_argument("--monitor-interval", type=int, default=get_config(config, "intervals", "yaml_monitor", 30))
parser.add_argument("--smt-interval", type=int, default=get_config(config, "intervals", "smt_check", 3600))

args = parser.parse_args()


# ===========================================
# Global State
# ===========================================
app = Flask(__name__)
file_queue = Queue()
queue_lock = threading.Lock()
permutations_lock = threading.Lock()
served_clients_lock = threading.Lock()
station_assignments_lock = threading.Lock()

# Load persistent state
_state = load_persistent_state()
last_hash = _state.get("last_hash")
current_permutations = []
served_clients = []

# Station assignments: IP -> {"daily": [files], "weekly": [files]}
# Each station has separate queues for daily and weekly jobs
# Files are served in order: weekly first (higher priority), then daily
station_assignments = _state.get("station_assignments", {})

# Day tracking - track both current day and last scheduled day
_last_day_str = _state.get("last_processed_day")
_last_scheduled_str = _state.get("last_scheduled_day")
current_day = date.fromisoformat(_last_day_str) if _last_day_str else datetime.now().date()
last_scheduled_day = date.fromisoformat(_last_scheduled_str) if _last_scheduled_str else None


# ===========================================
# Queue Management
# ===========================================
def refresh_queue():
    """Refresh job queue from YAML configuration."""
    global last_hash, current_permutations

    logger.debug("Checking YAML...")
    
    try:
        data = load_yaml(args.yaml)
    except Exception as e:
        logger.error(f"YAML error: {e}")
        return

    week = get_current_week()
    groups = data.get(week)
    logger.debug(f"Current week: {week}")

    if not groups:
        logger.warning("No data for current week")
        return

    # Include permutation mode in hash so mode changes trigger regeneration
    current_hash = compute_hash({"groups": groups, "permute": args.permute})
    if current_hash == last_hash:
        logger.debug("No change in YAML or mode")
        return

    logger.info("Rebuilding job queue...")
    
    with served_clients_lock:
        served_clients.clear()

    combos = process_week_features(groups, args.permute)
    files = write_files(args.output, week, combos)

    with permutations_lock:
        current_permutations = get_permutation_names(combos)
        mode = "ON" if args.permute else "OFF"
        logger.info(f"Permutation mode {mode}: {len(current_permutations)} items")

    with queue_lock:
        while not file_queue.empty():
            file_queue.get()
        for f in files:
            file_queue.put((week, f))

    last_hash = current_hash
    
    # Persist state
    state = load_persistent_state()
    state["last_hash"] = current_hash
    state["last_generation_time"] = datetime.now().isoformat()
    save_persistent_state(state)

    logger.info(f"Jobs loaded: {file_queue.qsize()}")


def trigger_scheduling(install_stack=False):
    """
    Trigger job scheduling to all stations and store assignments.
    
    Daily and weekly jobs are tracked separately:
    - Weekly jobs are added to "weekly" queue
    - Daily jobs are added to "daily" queue
    - Jobs coexist - weekly doesn't overwrite daily and vice versa
    """
    global station_assignments
    
    schedule_type = "weekly" if install_stack else "daily"
    logger.info(f"Scheduling type: {schedule_type.upper()}")
    
    # =========================================
    # Check for leftover files of SAME type
    # =========================================
    if args.preschedule:
        with station_assignments_lock:
            leftover_count = 0
            leftover_details = []
            
            for ip, queues in station_assignments.items():
                type_files = queues.get(schedule_type, [])
                if type_files:
                    leftover_count += len(type_files)
                    leftover_details.append(f"  {ip}: {len(type_files)} {schedule_type} files remaining")
            
            if leftover_count > 0:
                logger.warning(f"⚠️  LEFTOVER {schedule_type.upper()} FILES: {leftover_count} files not retrieved by clients!")
                for detail in leftover_details:
                    logger.warning(detail)
                logger.warning(f"    New {schedule_type} scheduling will overwrite previous {schedule_type} assignments.")
    
    # =========================================
    # Proceed with scheduling
    # =========================================
    with permutations_lock:
        perms = list(current_permutations)
    
    try:
        stations = load_stations_config(args.stations)
    except Exception as e:
        logger.error(f"Error loading stations: {e}")
        return
    
    result = schedule_permutations_to_stations(
        args.apex_url, args.owner, stations, perms, 
        install_stack, args.weekly_permutations, args.program,
        preschedule_mode=args.preschedule
    )
    
    # Store station assignments for client file serving (only in preschedule mode)
    if args.preschedule and result and "station_assignments" in result:
        new_assignments = result["station_assignments"]
        
        with station_assignments_lock:
            # Merge new assignments with existing (don't overwrite other type)
            for ip, new_files in new_assignments.items():
                if ip not in station_assignments:
                    station_assignments[ip] = {"daily": [], "weekly": []}
                
                # Replace only the current schedule type, keep the other
                station_assignments[ip][schedule_type] = new_files
            
            logger.info(f"Updated {schedule_type} assignments for {len(new_assignments)} stations")
            
            # Log combined status
            total_daily = sum(len(q.get("daily", [])) for q in station_assignments.values())
            total_weekly = sum(len(q.get("weekly", [])) for q in station_assignments.values())
            logger.info(f"  Total pending: {total_daily} daily, {total_weekly} weekly")
            
            # Persist station assignments
            state = load_persistent_state()
            state["station_assignments"] = station_assignments
            save_persistent_state(state)
    elif not args.preschedule:
        # In free-for-all mode, no assignments are tracked
        logger.info("Free-for-all mode: No station-specific assignments")


# ===========================================
# Monitor Threads
# ===========================================
def monitor_loop():
    """Monitor YAML for changes and detect day changes."""
    global current_day, last_scheduled_day
    
    while True:
        refresh_queue()
        
        today = datetime.now().date()
        
        # Check if we need to schedule today (day changed OR not scheduled yet today)
        should_schedule = False
        
        if today != current_day:
            logger.info(f"Day changed: {current_day} → {today}")
            current_day = today
            should_schedule = True
        elif last_scheduled_day != today:
            # Server restarted but today not scheduled yet
            logger.info(f"Server restarted, checking if scheduling needed for {today}")
            should_schedule = True
        
        if should_schedule and last_scheduled_day != today:
            logger.info(f"Triggering daily scheduling for {today}")
            trigger_scheduling(install_stack=False)
            
            # Update both day tracking and scheduled day
            last_scheduled_day = today
            state = load_persistent_state()
            state["last_processed_day"] = today.isoformat()
            state["last_scheduled_day"] = today.isoformat()
            save_persistent_state(state)
            logger.info(f"Scheduling completed and saved for {today}")
        
        with served_clients_lock:
            if served_clients:
                logger.debug(f"Served clients: {len(served_clients)}")
        
        time.sleep(args.monitor_interval)


def smt_loop():
    """Monitor SMT for stack releases."""
    program_id = Program[args.program]
    
    while True:
        logger.debug("Checking SMT for stack releases...")
        if check_timeline(args.smt_url, args.username, args.password, program_id):
            trigger_scheduling(install_stack=True)
        time.sleep(args.smt_interval)


# ===========================================
# API Routes
# ===========================================
@app.route("/get_next_afc_file")
def get_next_afc_file():
    """
    Get next job for the requesting client.
    
    Behavior depends on preschedule mode:
    - Preschedule ON: Only serve files to registered stations with remaining assignments.
                      Weekly files are served first (higher priority), then daily.
                      Returns error if IP not registered or no files remaining.
    - Preschedule OFF: Free-for-all, any client can get next file from queue.
    """
    client_ip = request.remote_addr
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    week = get_current_week()
    filename = None
    job_type = None
    
    if args.preschedule:
        # =========================================
        # PRESCHEDULE MODE: IP-based assignments
        # =========================================
        with station_assignments_lock:
            # Check if client IP is registered
            if client_ip not in station_assignments:
                logger.warning(f"Rejected: {client_ip} not in preschedule list")
                return jsonify({
                    "status": "error",
                    "reason": "ip_not_registered",
                    "message": f"IP {client_ip} is not registered in the preschedule list"
                }), 403
            
            client_queues = station_assignments[client_ip]
            weekly_files = client_queues.get("weekly", [])
            daily_files = client_queues.get("daily", [])
            
            # Check if there are any files remaining for this client
            if not weekly_files and not daily_files:
                logger.info(f"No more files for {client_ip}")
                return jsonify({
                    "status": "empty",
                    "reason": "no_files_remaining",
                    "message": f"No more files assigned to IP {client_ip}"
                })
            
            # Serve weekly files first (higher priority), then daily
            if weekly_files:
                perm_name = weekly_files.pop(0)
                job_type = "weekly"
                remaining = f"{len(weekly_files)} weekly, {len(daily_files)} daily"
            else:
                perm_name = daily_files.pop(0)
                job_type = "daily"
                remaining = f"{len(weekly_files)} weekly, {len(daily_files)} daily"
            
            filename = f"{perm_name}.txt"
            
            # Persist updated assignments
            state = load_persistent_state()
            state["station_assignments"] = station_assignments
            save_persistent_state(state)
            
            logger.info(f"[{job_type.upper()}] {filename} → {client_ip} ({remaining} remaining)")
    else:
        # =========================================
        # FREE-FOR-ALL MODE: Any client can get files
        # =========================================
        with queue_lock:
            if file_queue.empty():
                return jsonify({"status": "empty"})
            week, filename = file_queue.get()
        job_type = "queue"
        logger.info(f"Queue job: {filename} → {client_ip} (free-for-all mode)")
    
    path = os.path.join(args.output, week, filename)
    if not os.path.exists(path):
        return jsonify({"status": "error", "reason": "file_not_found", "file": filename}), 404
    
    with open(path) as f:
        content = f.read()
    
    with served_clients_lock:
        served_clients.append((timestamp, client_ip, filename, job_type))
    
    return jsonify({
        "status": "ok", 
        "week": week, 
        "file": filename, 
        "content": content,
        "job_type": job_type
    })


# ===========================================
# Main
# ===========================================
if __name__ == "__main__":
    logger.info("Starting PMM Server...")
    logger.info(f"  Program: {args.program}")
    logger.info(f"  Port: {args.port}")
    logger.info(f"  Permutation mode: {args.permute}")
    logger.info(f"  Preschedule mode: {args.preschedule}")
    logger.info(f"  SMT monitor: {args.smt}")
    logger.info(f"  Weekly permutations: {args.weekly_permutations}")
    
    refresh_queue()
    
    threading.Thread(target=monitor_loop, daemon=True).start()
    
    if args.smt:
        threading.Thread(target=smt_loop, daemon=True).start()
    
    app.run(host=args.host, port=args.port, threaded=True)
