"""
Unified Host Server for PMM Farm Feature Testing.

This script provides a centralized server that manages feature flag combinations
for automated testing workflows. It reads feature configurations from a YAML file,
generates permutations of feature flags, serves jobs to clients via REST API,
and optionally monitors SMT (Stack Management Tool) for new stack releases.

Dependencies:
    - flask: Web framework for REST API
    - pyyaml: YAML file parsing
    - requests: HTTP client for SMT API
    - requests_ntlm: NTLM authentication for SMT

Usage:
    python combined_server.py [OPTIONS]

Command-line Arguments:
    --yaml PATH       Path to YAML config file (default: enable_feature.yaml)
    --output DIR      Output directory for generated files (default: output)
    --port PORT       Server port number (default: 5000)
    --permute         Enable permutation mode (generate all combinations)
    --smt             Enable SMT monitoring for stack releases
    --username USER   Username for SMT authentication
    --password PASS   Password for SMT authentication
    --program NAME    Program name: GAINSBOROUGH, SOUNDWAVE, or CANIS

YAML Configuration Format:
    The YAML file should be organized by ISO week (YYYY-WNN format):
    
    2026-W21:
      - 
        feature.path.name: "value"    # Feature with specific value
        another.feature: null          # Feature flag (no value)
    
    Each week can have multiple feature groups. Features are extracted
    and combined based on the permutation mode setting.

API Endpoints:
    GET /get_next_afc_file
        Combined endpoint that gets the next afc file and returns its content.
        Records client IP on successful delivery.
        Response: {"status": "ok", "week": "2026-W21", "file": "feature.txt", "content": "..."}
                  or {"status": "empty"} if queue is empty
                  or {"status": "error", "reason": "file_not_found"} if file read fails
    
    GET /get_job (legacy)
        Returns the next job from the queue.
        Response: {"status": "ok", "week": "2026-W21", "file": "feature.txt"}
                  or {"status": "empty"} if queue is empty
    
    GET /get_file/<week>/<filename> (legacy)
        Returns the content of a specific job file.
        Response: {"status": "ok", "content": "feature1\\nfeature2"}
                  or {"status": "error"} if file not found

Architecture:
    - Main Thread: Flask server handling API requests
    - Monitor Thread: Periodically checks YAML for changes (every 30s)
    - SMT Thread: Periodically checks for new stack releases (every hour)

Author: xhoe@amd.com
"""

import yaml
import itertools
import hashlib
import time
from datetime import datetime, date
import os
import json
from queue import Queue
from flask import Flask, jsonify, request
import threading
import argparse
import requests
from requests_ntlm import HttpNtlmAuth
from enum import IntEnum


# =====================================================
# STATE FILE FOR PERSISTENCE
# =====================================================
# Use %LOCALAPPDATA% for Windows (standard location for per-user app data)
# Falls back to user home directory on other platforms
APP_NAME = "APEXScheduler"
if os.name == 'nt':  # Windows
    APP_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), APP_NAME)
else:  # Linux/Mac
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), f'.{APP_NAME.lower()}')

os.makedirs(APP_DATA_DIR, exist_ok=True)
STATE_FILE = os.path.join(APP_DATA_DIR, "server_state.json")


def load_persistent_state():
    """
    Load persistent state from the state file.
    
    Returns:
        dict: State dictionary, or empty dict if not found.
    """
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                print(f"📂 Loaded state from {STATE_FILE}")
                return state
    except Exception as e:
        print(f"⚠️ Could not load state file: {e}")
    return {}


def save_persistent_state(state_data):
    """
    Save state to the state file.
    
    Args:
        state_data (dict): State dictionary to save.
    """
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state_data, f, indent=2)
        print(f"💾 Saved state to {STATE_FILE}")
    except Exception as e:
        print(f"⚠️ Could not save state file: {e}")


# =====================================================
# PROGRAM ENUM
# =====================================================
class Program(IntEnum):
    """
    Enumeration of supported program IDs for SMT monitoring.
    
    Each program corresponds to a specific product line in the SMT system.
    The integer values are the internal SMT program identifiers.
    
    Attributes:
        GAINSBOROUGH: Program ID 1434 - Gainsborough product line
        SOUNDWAVE: Program ID 1427 - Soundwave product line
        CANIS: Program ID 1430 - Canis product line
    
    Note:
        MAGNUS (ID unknown) is not currently supported as it's not found in SMT.
    """
    # MAGNUS = 1 ## Magnus not found on SMT yet
    GAINSBOROUGH = 1434
    SOUNDWAVE = 1427
    CANIS = 1430


# =====================================================
# ARGUMENT PARSING
# =====================================================
# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser(description="Unified Host Server")

# File paths (default to relative paths from script directory)
parser.add_argument("--yaml", default=os.path.join(SCRIPT_DIR, "enable_feature.yaml"), 
                    help="Path to feature YAML config")
parser.add_argument("--stations", default=os.path.join(SCRIPT_DIR, "stations.yaml"),
                    help="Path to stations YAML config")
parser.add_argument("--output", default="output", help="Output directory")

# Server settings
parser.add_argument("--port", type=int, default=5000, help="Server port number")
parser.add_argument("--host", default="0.0.0.0", help="Server host address")

# Mode flags
parser.add_argument("--permute", action="store_true", help="Enable permutation mode (generate all combinations)")
parser.add_argument("--smt", action="store_true", help="Enable SMT monitoring for stack releases")

# SMT authentication
parser.add_argument("--username", default="", help="Username for SMT authentication")
parser.add_argument("--password", default="", help="Password for SMT authentication")
parser.add_argument("--program", default="SOUNDWAVE",
                    choices=[p.name for p in Program], help="Program name for SMT monitoring")

# URLs
parser.add_argument("--smt-url", default="http://atlstmapp01.amd.com:1234/api/getStacksForTimeline",
                    help="SMT API URL")
parser.add_argument("--apex-url", default="http://apexlegacy.amd.com/jobs",
                    help="APEX job scheduler URL")

# APEX job settings
parser.add_argument("--owner", default="xhoe@amd.com", help="APEX job owner email")
parser.add_argument("--priority", default="3", help="APEX job priority")
parser.add_argument("--setup-queue", default="Scheduler Test - Setup", help="APEX setup queue name")
parser.add_argument("--test-queue", default="Scheduler Test - Execute", help="APEX test queue name")
parser.add_argument("--execution-label", default="xhoe_scheduler_testing", help="APEX execution label")

# Timing intervals (in seconds)
parser.add_argument("--monitor-interval", type=int, default=30, help="YAML monitor check interval in seconds")
parser.add_argument("--smt-interval", type=int, default=3600, help="SMT check interval in seconds")

args = parser.parse_args()

# =====================================================
# GLOBAL CONFIG
# =====================================================
YAML_PATH = args.yaml
OUTPUT_BASE = args.output
STATIONS_YAML_PATH = args.stations
ENABLE_PERMUTATION_MODE = args.permute
RUN_SMT_MONITOR = args.smt

PROGRAM_ID = Program[args.program]
auth = HttpNtlmAuth(args.username, args.password)

SMT_URL = args.smt_url
APEX_URL = args.apex_url

HEADERS = {"Content-Type": "application/json"}

# =====================================================
# INIT
# =====================================================
app = Flask(__name__)

file_queue = Queue()  # Thread-safe queue holding (week, filename) tuples
queue_lock = threading.Lock()  # Lock for queue operations

# Load persistent state for hash and day tracking
_persistent_state = load_persistent_state()
last_hash = _persistent_state.get("last_hash")  # MD5 hash of last processed YAML data
if last_hash:
    print(f"📂 Restored last_hash: {last_hash}")

# List to track clients that have been served jobs: (timestamp, client_ip, filename)
served_clients = []
served_clients_lock = threading.Lock()  # Lock for thread-safe access

# Track current day for day change detection (load from persistent state)
_last_day_str = _persistent_state.get("last_processed_day")
if _last_day_str:
    try:
        current_day = date.fromisoformat(_last_day_str)
        print(f"📂 Restored last processed day: {current_day}")
    except Exception:
        current_day = datetime.now().date()
else:
    current_day = datetime.now().date()

# Global storage for current permutation names (populated by refresh_queue)
current_permutations = []
permutations_lock = threading.Lock()  # Lock for thread-safe access


# =====================================================
# TIME HELPERS
# =====================================================
def get_current_week():
    """
    Get the current ISO week string.
    
    Returns:
        str: Week string in format "YYYY-WNN" (e.g., "2026-W21").
    
    Example:
        >>> get_current_week()
        '2026-W21'
    """
    now = datetime.now()
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def get_today_start_timestamp():
    """
    Get the Unix timestamp (in milliseconds) for the start of today.
    
    Returns:
        int: Unix timestamp in milliseconds for 00:00:00 of the current day.
    
    Example:
        >>> get_today_start_timestamp()
        1747612800000  # Represents 2026-05-19 00:00:00
    """
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    return int(start.timestamp() * 1000)


def get_current_timestamp():
    """
    Get the current Unix timestamp in milliseconds.
    
    Returns:
        int: Current Unix timestamp in milliseconds.
    
    Example:
        >>> get_current_timestamp()
        1747638715000  # Represents current time
    """
    return int(datetime.now().timestamp() * 1000)


# =====================================================
# YAML + PERMUTATION
# =====================================================
def compute_hash(data):
    """
    Compute MD5 hash of data for change detection.
    
    Args:
        data: Any JSON-serializable data structure.
    
    Returns:
        str: MD5 hexdigest of the JSON-serialized data.
    
    Example:
        >>> compute_hash({"key": "value"})
        '9724c1e20e6e3e4d7f57ed25f9d4efb6'
    """
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


def load_yaml():
    """
    Load and parse the YAML configuration file.
    
    Returns:
        dict: Parsed YAML content, or empty dict if file is empty.
    
    Raises:
        FileNotFoundError: If YAML file does not exist.
        yaml.YAMLError: If YAML syntax is invalid.
    """
    with open(YAML_PATH, "r") as f:
        return yaml.safe_load(f) or {}


def load_stations_config():
    """
    Load and parse the stations YAML configuration file.
    
    The stations config maps IP addresses to station details including
    subscription_id and name for APEX job scheduling.
    
    Returns:
        dict: Parsed stations config, or empty dict if file is empty.
            Format: {
                "192.168.1.10": {"subscription_id": "4574", "name": "Station-A"},
                ...
            }
    
    Raises:
        FileNotFoundError: If stations YAML file does not exist.
        yaml.YAMLError: If YAML syntax is invalid.
    
    Example:
        >>> stations = load_stations_config()
        >>> stations["192.168.1.10"]["subscription_id"]
        '4574'
    """
    with open(STATIONS_YAML_PATH, "r") as f:
        return yaml.safe_load(f) or {}


def extract_pairs(groups):
    """
    Extract feature key-value pairs from YAML groups.
    
    Processes feature definitions from the YAML structure, extracting the
    final segment of dotted paths as the feature name. Features with values
    are formatted as "name=value", features without values (null) are just "name".
    
    Args:
        groups (list): List of dictionaries containing feature definitions.
            Each dict maps "path.to.feature" to a value or None.
    
    Returns:
        list: Sorted, deduplicated list of feature strings.
    
    Example:
        >>> groups = [{"test.adc": "0x00", "flag": None}]
        >>> extract_pairs(groups)
        ['adc=0x00', 'flag']
    """
    pairs = []
    for group in groups:
        for k, v in group.items():
            # Extract the last segment of the dotted path (e.g., "test.x.adc" -> "adc")
            key = k.split(".")[-1]
            # Format as "key=value" if value exists, otherwise just "key"
            pairs.append(key if v is None else f"{key}={v}")
    return sorted(set(pairs))


def generate_combinations(values):
    """
    Generate all possible combinations of the input values.
    
    Creates combinations of all lengths from 1 to len(values),
    representing all possible subsets of features to enable.
    
    Args:
        values (list): List of feature strings to combine.
    
    Returns:
        list: List of lists, each containing a combination of features.
    
    Example:
        >>> generate_combinations(['a', 'b', 'c'])
        [['a'], ['b'], ['c'], ['a', 'b'], ['a', 'c'], ['b', 'c'], ['a', 'b', 'c']]
    """
    results = []
    for r in range(1, len(values) + 1):
        results.extend(list(itertools.combinations(values, r)))
    return [list(r) for r in results]


def process_current_week(groups):
    """
    Process feature groups for the current week into job combinations.
    
    Extracts features from the YAML groups and either:
    - Returns each feature as a single-item list (permutation mode OFF)
    - Returns all possible combinations (permutation mode ON)
    
    Args:
        groups (list): Feature groups from the YAML for the current week.
    
    Returns:
        list: List of feature combinations, each combination is a list of strings.
    
    Example:
        With ENABLE_PERMUTATION_MODE=True and features ['adc', 'flag']:
        >>> process_current_week(groups)
        [['adc'], ['flag'], ['adc', 'flag']]
        
        With ENABLE_PERMUTATION_MODE=False:
        >>> process_current_week(groups)
        [['adc'], ['flag']]
    """
    pairs = extract_pairs(groups)

    if not ENABLE_PERMUTATION_MODE:
        return [[p] for p in pairs]

    return generate_combinations(pairs)


# =====================================================
# FILE GENERATION
# =====================================================
def write_files(week, combinations):
    """
    Write job files for each feature combination.
    
    Creates a directory for the week and writes one text file per combination.
    Each file contains the feature strings, one per line. Existing files in
    the week directory are deleted before writing new ones.
    
    Args:
        week (str): Week identifier (e.g., "2026-W21").
        combinations (list): List of feature combinations to write.
    
    Returns:
        list: List of generated filenames.
    
    Example:
        >>> write_files("2026-W21", [["adc", "flag"], ["y"]])
        ['adc-flag.txt', 'y.txt']
        
        File contents of 'adc-flag.txt':
            adc
            flag
    """
    base = os.path.join(OUTPUT_BASE, week)
    os.makedirs(base, exist_ok=True)

    # Cleanup: remove all existing files in the week directory
    for f in os.listdir(base):
        os.remove(os.path.join(base, f))

    files = []

    for combo in combinations:
        # Generate filename from feature names (strip values after '=')
        name = "-".join(c.split("=")[0] for c in combo)
        filename = f"{name}.txt"

        path = os.path.join(base, filename)

        with open(path, "w") as f:
            f.write("\n".join(combo))

        files.append(filename)

    return files


# =====================================================
# QUEUE MANAGEMENT
# =====================================================
def refresh_queue():
    """
    Refresh the job queue from the YAML configuration.
    
    Loads the YAML file, checks for changes using MD5 hash comparison,
    and if changed, regenerates all job files and repopulates the queue.
    Also stores the permutation names in the global current_permutations variable
    for use by schedule_permutations_to_stations().
    This function is called periodically by the monitor thread.
    
    The function:
    1. Loads the YAML configuration
    2. Checks if current week data exists
    3. Compares hash to detect changes
    4. If changed, generates combinations and writes files
    5. Clears and repopulates the job queue
    6. Stores permutation names in global current_permutations
    
    Global Variables Modified:
        last_hash: Updated to the new configuration hash
        file_queue: Cleared and repopulated with new jobs
        current_permutations: Updated with permutation names for APEX scheduling
    """
    global last_hash
    global current_permutations

    print("🔍 Checking YAML...")

    try:
        data = load_yaml()
    except Exception as e:
        print("❌ YAML error:", e)
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

    # Clear served clients list when rebuilding queue
    with served_clients_lock:
        served_clients.clear()
        print("🧹 Cleared served clients list")

    combos = process_current_week(groups)
    files = write_files(week, combos)

    # Store permutation names in global variable for APEX scheduling
    # Convert combinations to permutation names (strip values after '=')
    with permutations_lock:
        current_permutations = []
        for combo in combos:
            name = "-".join(c.split("=")[0] for c in combo)
            current_permutations.append(name)
        
        if ENABLE_PERMUTATION_MODE:
            print(f"🔀 Permutation mode ON: Generated {len(current_permutations)} combinations")
        else:
            print(f"📋 Permutation mode OFF: Using {len(current_permutations)} features directly from YAML")

    with queue_lock:
        # Clear existing queue
        while not file_queue.empty():
            file_queue.get()

        # Add new jobs
        for f in files:
            file_queue.put((week, f))

    last_hash = current_hash
    
    # Persist the new hash
    state = load_persistent_state()
    state["last_hash"] = current_hash
    state["last_generation_time"] = datetime.now().isoformat()
    state["last_generation_week"] = week
    state["permutation_count"] = len(current_permutations)
    save_persistent_state(state)

    print(f"✅ Jobs loaded: {file_queue.qsize()}")


def monitor_loop():
    """
    Background thread loop that monitors YAML for changes and day changes.
    
    Runs indefinitely, calling refresh_queue() every 30 seconds
    to check for configuration updates. Also detects day changes
    and triggers schedule_permutations_to_stations() when a new day begins.
    
    Note:
        This function is intended to run as a daemon thread and
        will terminate when the main program exits.
    """
    global current_day
    
    while True:
        # Always refresh queue first to ensure current_permutations is up-to-date
        refresh_queue()
        
        # Check for day change (after refresh to ensure permutations are current)
        today = datetime.now().date()
        if today != current_day:
            print(f"📆 Day changed: {current_day} → {today}")
            current_day = today
            # Persist the new day
            state = load_persistent_state()
            state["last_processed_day"] = today.isoformat()
            save_persistent_state(state)
            # Schedule all permutations to available stations
            schedule_permutations_to_stations()
        
        # Print served clients summary
        with served_clients_lock:
            if served_clients:
                print(f"📊 Served clients ({len(served_clients)} total):")
                for ts, ip, fn in served_clients:
                    print(f"   [{ts}] {ip} → {fn}")
            else:
                print("📊 No clients served yet")
        
        time.sleep(args.monitor_interval)


# =====================================================
# API ROUTES
# =====================================================
@app.route("/get_next_afc_file")
def get_next_afc_file():
    """
    Combined API endpoint to get the next job and return its content.
    
    This endpoint combines the functionality of get_job() and get_file()
    into a single request. It retrieves the next job from the queue,
    reads the file content, and records the client IP on success.
    
    Returns:
        JSON response:
            - {"status": "ok", "week": "<week>", "file": "<filename>", "content": "<content>"}
              on success (also records client IP)
            - {"status": "empty"} if queue is empty
            - {"status": "error", "reason": "file_not_found"} if file cannot be read
    
    Example:
        GET /get_next_afc_file
        Response: {
            "status": "ok",
            "week": "2026-W21",
            "file": "adc-flag.txt",
            "content": "adc=0x00\\nflag"
        }
    """
    # Get job from queue
    with queue_lock:
        if file_queue.empty():
            return jsonify({"status": "empty"})
        week, filename = file_queue.get()
    
    # Read file content
    path = os.path.join(OUTPUT_BASE, week, filename)
    
    if not os.path.exists(path):
        return jsonify({"status": "error", "reason": "file_not_found"})
    
    with open(path) as f:
        content = f.read()
    
    # Record client IP on successful delivery
    client_ip = request.remote_addr
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with served_clients_lock:
        served_clients.append((timestamp, client_ip, filename))
    
    print(f"📥 [{timestamp}] Job served: {filename} → {client_ip}")
    
    return jsonify({
        "status": "ok",
        "week": week,
        "file": filename,
        "content": content
    })


# =====================================================
# SMT MONITOR
# =====================================================
# APEX_ACTIVE_JOBS_URL = "http://apexlegacy.amd.com/farm/83/jobs/active"


# def check_apex_active_jobs():
#     """
#     Check if there are any active jobs in the APEX farm.
    
#     Queries the APEX active jobs page and parses the HTML response
#     to determine if any jobs are currently queued or running.
    
#     Returns:
#         bool: True if there are active jobs, False if the queue is empty.
#               Returns False on error (fails safe).
    
#     API Endpoint:
#         GET http://apexlegacy.amd.com/farm/83/jobs/active
    
#     Note:
#         The function checks for `<td>` elements in the HTML table.
#         If `<td>` elements exist, there are active jobs.
#         If only `<th>` elements exist, the table is empty.
    
#     Example:
#         >>> if not check_apex_active_jobs():
#         ...     schedule_apex_job()
#     """
#     try:
#         r = requests.get(APEX_ACTIVE_JOBS_URL, timeout=10)
#         html = r.text
        
#         # Check if table has data rows (contains <td> elements)
#         # Empty table only has <th> header elements
#         has_jobs = "<td>" in html
        
#         if has_jobs:
#             print("📋 APEX: Active jobs found")
#         else:
#             print("📋 APEX: No active jobs")
        
#         return has_jobs
        
#     except Exception as e:
#         print(f"⚠️ APEX check error: {e}")
#         return False  # Fail safe: assume no jobs on error


def schedule_apex_job(subscription_id, station_name, permutation_name, install_stack=False):
    """
    Schedule a new job on the APEX legacy system for a specific station and permutation.
    
    Creates and submits a new test job to the APEX job scheduler with
    dynamic subscription_id and station name based on the provided parameters.
    
    Args:
        subscription_id (str): The APEX subscription ID for the target station.
        station_name (str): The name of the station to run the job on.
        permutation_name (str): The name of the feature permutation being tested.
        install_stack (bool): Flag indicating if this is triggered by a stack release.
    
    Returns:
        bool: True if job was scheduled successfully (HTTP 200), False otherwise.
    
    API Endpoint:
        Uses APEX_URL from command-line arguments (default: http://apexlegacy.amd.com/jobs)
    
    Job Parameters:
        - name: "{station_name} - {permutation_name} - {timestamp}"
        - owner: From --owner argument
        - priority: From --priority argument
        - subscription_id: Dynamic based on station config
        - setup_queue: From --setup-queue argument
        - test_queue: From --test-queue argument
        - execution_label: From --execution-label argument
    
    Example:
        >>> schedule_apex_job("4574", "Station-A", "adc-flag")
        📤 APEX Job: Station-A - adc-flag - 2026-05-20 13:50:00 MYT → 200
        True
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S MYT')
    job_name = f"{station_name} - {permutation_name} - {timestamp}"

    data = {
        "name": job_name,
        "owner": args.owner,
        "priority": args.priority,
        "is_persistent": "false",
        "completion_criteria": "AllTestStations",
        "test_loops": "1",
        "subscription_id": subscription_id,
        "setup_queue": args.setup_queue,
        "test_queue": args.test_queue,
        "argument_overrides": "",
        "execution_label": args.execution_label
    }

    response = requests.post(APEX_URL, data=data)

    print(f"📤 APEX Job: {job_name} → {response.status_code}")
    
    return response.status_code == 200


def schedule_permutations_to_stations(install_stack=False):
    """
    Distribute feature permutations across available stations and schedule APEX jobs.
    
    This function implements the intelligent job distribution logic:
    1. Uses the global current_permutations (populated by refresh_queue)
    2. Gets available stations from stations.yaml
    3. Compares permutations count vs stations count
    4. If permutations <= stations: assigns one permutation per station
    5. If permutations > stations: distributes in round-robin fashion
       until all permutations are scheduled
    
    The function schedules jobs immediately in sequence. Each station
    receives jobs one at a time in round-robin order until all
    permutations are distributed.
    
    Example Distribution:
        3 permutations, 3 stations:
            Station-A → perm1
            Station-B → perm2
            Station-C → perm3
        
        7 permutations, 3 stations:
            Round 1: Station-A → perm1, Station-B → perm2, Station-C → perm3
            Round 2: Station-A → perm4, Station-B → perm5, Station-C → perm6
            Round 3: Station-A → perm7
    
    Args:
        install_stack (bool): Flag indicating if this is triggered by a stack release.
    
    Returns:
        dict: Summary of scheduling results with structure:
            {
                "total_permutations": int,
                "total_stations": int,
                "scheduled": int,
                "failed": int,
                "assignments": [(station_name, permutation_name, success), ...]
            }
    
    Global Variables Used:
        current_permutations: List of permutation names populated by refresh_queue()
    """
    print("🚀 Starting permutation distribution to stations...")
    
    # Use the global current_permutations (already processed by refresh_queue)
    with permutations_lock:
        permutations = list(current_permutations)  # Make a copy for thread safety
    
    if not permutations:
        print("⚠️ No permutations to schedule (run refresh_queue first)")
        return {
            "total_permutations": 0,
            "total_stations": 0,
            "scheduled": 0,
            "failed": 0,
            "assignments": []
        }
    
    # Get available stations
    try:
        stations = load_stations_config()
    except Exception as e:
        print(f"❌ Error loading stations config: {e}")
        return {
            "total_permutations": len(permutations),
            "total_stations": 0,
            "scheduled": 0,
            "failed": 0,
            "assignments": []
        }
    
    if not stations:
        print("⚠️ No stations configured")
        return {
            "total_permutations": len(permutations),
            "total_stations": 0,
            "scheduled": 0,
            "failed": 0,
            "assignments": []
        }
    
    # Convert stations dict to list for round-robin assignment
    station_list = [
        (ip, info["subscription_id"], info["name"])
        for ip, info in stations.items()
    ]
    
    num_permutations = len(permutations)
    num_stations = len(station_list)
    
    print(f"📊 Permutations: {num_permutations}, Stations: {num_stations}")
    
    # Determine scheduling strategy
    if num_permutations <= num_stations:
        print(f"✅ Permutations ({num_permutations}) ≤ Stations ({num_stations}): One job per station")
    else:
        print(f"⚠️ Permutations ({num_permutations}) > Stations ({num_stations}): Round-robin distribution")
    
    # Distribute permutations to stations in round-robin fashion
    assignments = []
    scheduled = 0
    failed = 0
    
    for i, perm_name in enumerate(permutations):
        # Round-robin: cycle through stations
        station_index = i % num_stations
        ip, subscription_id, station_name = station_list[station_index]
        
        print(f"📌 Assigning '{perm_name}' to {station_name} (IP: {ip})")
        
        # Schedule the job
        success = schedule_apex_job(subscription_id, station_name, perm_name, install_stack)
        
        if success:
            scheduled += 1
        else:
            failed += 1
        
        assignments.append((station_name, perm_name, success))
    
    # Print summary
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


def check_timeline():
    """
    Check SMT for new stack releases today.
    
    Queries the SMT API for stacks released between the start of today
    and the current time for the configured program. If releases are found,
    logs the detection (APEX job scheduling is currently disabled).
    
    Uses NTLM authentication with provided credentials.
    
    API Endpoint:
        POST http://atlstmapp01.amd.com:1234/api/getStacksForTimeline
    
    Payload Parameters:
        - startDate/endDate: Today's time range in milliseconds
        - programId: Target program ID from Program enum
        - Various filters set to "All"
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
        "programId": PROGRAM_ID,
        "qaType": "All",
        "dateType": "Released Between",
        "oem": "All"
    }

    # Example hardcoded payload for testing:
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

    try:
        r = requests.post(SMT_URL, json=payload, headers=HEADERS, auth=auth)
        data = r.json()

        info = data.get("info", [])

        if info:
            print("🚨 Stack release found")
            # Schedule all permutations to available stations when stack is released
            schedule_permutations_to_stations(install_stack=True)
        else:
            print("✅ No release")

    except Exception as e:
        print("⚠️ SMT error:", e)


def smt_loop():
    """
    Background thread loop that monitors SMT for stack releases.
    
    Runs indefinitely, calling check_timeline() every hour (3600 seconds)
    to check for new stack releases.
    
    Note:
        This function is intended to run as a daemon thread and
        will terminate when the main program exits.
        Only runs if RUN_SMT_MONITOR is True.
    """
    while True:
        print("🔍 SMT check...")
        check_timeline()
        time.sleep(args.smt_interval)


# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    print("🚀 Starting Server...")
    print(vars(args))

    # Initial queue population
    refresh_queue()

    # Start YAML monitor thread (checks every 30 seconds)
    threading.Thread(target=monitor_loop, daemon=True).start()

    # Start SMT monitor thread if enabled (checks every hour)
    if RUN_SMT_MONITOR:
        threading.Thread(target=smt_loop, daemon=True).start()

    # Start Flask server
    app.run(host=args.host, port=args.port, threaded=True)
