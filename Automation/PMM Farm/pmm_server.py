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
    config, get_config, SCRIPT_DIR,
    load_persistent_state, save_persistent_state
)
from modules.scheduler import schedule_permutations_to_stations
from modules.smt_monitor import Program, check_timeline
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

# SMT settings
parser.add_argument("--username", default=get_config(config, "smt", "username", ""))
parser.add_argument("--password", default=get_config(config, "smt", "password", ""))
parser.add_argument("--program", default=get_config(config, "smt", "program", "SOUNDWAVE"),
                    choices=[p.name for p in Program])
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

# Load persistent state
_state = load_persistent_state()
last_hash = _state.get("last_hash")
current_permutations = []
served_clients = []

# Day tracking
_last_day_str = _state.get("last_processed_day")
current_day = date.fromisoformat(_last_day_str) if _last_day_str else datetime.now().date()


# ===========================================
# Queue Management
# ===========================================
def refresh_queue():
    """Refresh job queue from YAML configuration."""
    global last_hash, current_permutations

    print("🔍 Checking YAML...")
    
    try:
        data = load_yaml(args.yaml)
    except Exception as e:
        print(f"❌ YAML error: {e}")
        return

    week = get_current_week()
    groups = data.get(week)
    print(f"📅 Current week: {week}")

    if not groups:
        print("⚠️ No data for current week")
        return

    current_hash = compute_hash(groups)
    if current_hash == last_hash:
        print("⏳ No change")
        return

    print("🔄 Rebuilding job queue...")
    
    with served_clients_lock:
        served_clients.clear()

    combos = process_week_features(groups, args.permute)
    files = write_files(args.output, week, combos)

    with permutations_lock:
        current_permutations = get_permutation_names(combos)
        mode = "ON" if args.permute else "OFF"
        print(f"🔀 Permutation mode {mode}: {len(current_permutations)} items")

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

    print(f"✅ Jobs loaded: {file_queue.qsize()}")


def trigger_scheduling(install_stack=False):
    """Trigger job scheduling to all stations."""
    with permutations_lock:
        perms = list(current_permutations)
    
    try:
        stations = load_stations_config(args.stations)
    except Exception as e:
        print(f"❌ Error loading stations: {e}")
        return
    
    schedule_permutations_to_stations(args.apex_url, args.owner, stations, perms, install_stack)


# ===========================================
# Monitor Threads
# ===========================================
def monitor_loop():
    """Monitor YAML for changes and detect day changes."""
    global current_day
    
    while True:
        refresh_queue()
        
        today = datetime.now().date()
        if today != current_day:
            print(f"📆 Day changed: {current_day} → {today}")
            current_day = today
            state = load_persistent_state()
            state["last_processed_day"] = today.isoformat()
            save_persistent_state(state)
            trigger_scheduling(install_stack=False)
        
        with served_clients_lock:
            if served_clients:
                print(f"📊 Served clients: {len(served_clients)}")
        
        time.sleep(args.monitor_interval)


def smt_loop():
    """Monitor SMT for stack releases."""
    program_id = Program[args.program]
    
    while True:
        print("🔍 SMT check...")
        if check_timeline(args.smt_url, args.username, args.password, program_id):
            trigger_scheduling(install_stack=True)
        time.sleep(args.smt_interval)


# ===========================================
# API Routes
# ===========================================
@app.route("/get_next_afc_file")
def get_next_afc_file():
    """Get next job from queue and return its content."""
    with queue_lock:
        if file_queue.empty():
            return jsonify({"status": "empty"})
        week, filename = file_queue.get()
    
    path = os.path.join(args.output, week, filename)
    if not os.path.exists(path):
        return jsonify({"status": "error", "reason": "file_not_found"})
    
    with open(path) as f:
        content = f.read()
    
    client_ip = request.remote_addr
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with served_clients_lock:
        served_clients.append((timestamp, client_ip, filename))
    
    print(f"📥 [{timestamp}] Job served: {filename} → {client_ip}")
    
    return jsonify({"status": "ok", "week": week, "file": filename, "content": content})


# ===========================================
# Main
# ===========================================
if __name__ == "__main__":
    print("🚀 Starting PMM Server...")
    print(f"   Port: {args.port}")
    print(f"   Permutation mode: {args.permute}")
    print(f"   SMT monitor: {args.smt}")
    
    refresh_queue()
    
    threading.Thread(target=monitor_loop, daemon=True).start()
    
    if args.smt:
        threading.Thread(target=smt_loop, daemon=True).start()
    
    app.run(host=args.host, port=args.port, threaded=True)
