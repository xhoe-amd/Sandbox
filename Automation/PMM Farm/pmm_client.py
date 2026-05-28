"""
PMM Farm SUT Client.

This client connects to the PMM Farm host server and retrieves job files
for processing. It uses the combined /get_next_afc_file API endpoint to fetch
both job metadata and file content in a single request.

Usage:
    python pmm_client.py [OPTIONS]

Command-line Arguments:
    --host HOST       Host IP address (default: from config or 10.148.216.73)
    --port PORT       Host port number (default: from config or 5000)
    --name NAME       SUT identifier name (default: SUT)
    --interval SEC    Retry interval in seconds (default: from config or 5)

Example:
    python pmm_client.py --host 192.168.1.10 --port 5000 --name SUT1

Author: xhoe@amd.com
"""

import argparse
import logging
import os
import time
from datetime import datetime

import requests
import yaml


# =========================
# Directory paths and config loading
# =========================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config_client.yaml")


def load_config():
    """Load configuration from YAML file. Returns empty dict if not found."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


# Load config for defaults (optional - uses hardcoded fallbacks if not found)
config = load_config()

# Get app settings from config or use defaults
APP_NAME = config.get("app", {}).get("name", "APEXScheduler")
PERMS_DIRNAME = config.get("app", {}).get("perms_dirname", "pmm_farm_perms")

# Get connection settings from config
connection_config = config.get("connection", {})
DEFAULT_HOST = connection_config.get("host", "10.148.216.73")
DEFAULT_PORT = connection_config.get("port", 5000)

# Get timing settings from config
timing_config = config.get("timing", {})
DEFAULT_INTERVAL = timing_config.get("retry_interval", 5)
DEFAULT_TIMEOUT = timing_config.get("request_timeout", 10)

# Get output settings from config
output_config = config.get("output", {})
DEFAULT_OUTPUT_FILE = output_config.get("filename", "enable_pmm_features.txt")

# Setup directories
if os.name == 'nt':  # Windows
    APP_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), APP_NAME)
else:  # Linux/Mac
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), f'.{APP_NAME.lower()}')

os.makedirs(APP_DATA_DIR, exist_ok=True)
PERMS_DIR = os.path.join(APP_DATA_DIR, PERMS_DIRNAME)


# =========================
# Parse CLI arguments (before logging setup)
# =========================
parser = argparse.ArgumentParser(description="SUT Client")

parser.add_argument(
    "--host",
    help=f"Host IP (default: {DEFAULT_HOST})",
    default=DEFAULT_HOST
)

parser.add_argument(
    "--port",
    type=int,
    default=DEFAULT_PORT,
    help=f"Host port number (default: {DEFAULT_PORT})"
)

parser.add_argument(
    "--name",
    default="SUT",
    help="SUT identifier name (default: SUT)"
)

parser.add_argument(
    "--interval",
    type=int,
    default=DEFAULT_INTERVAL,
    help=f"Retry interval in seconds (default: {DEFAULT_INTERVAL})"
)

parser.add_argument(
    "--save-dir",
    default=PERMS_DIR,
    help=f"Directory to save received files (default: {PERMS_DIR})"
)

parser.add_argument(
    "--timeout",
    type=int,
    default=DEFAULT_TIMEOUT,
    help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})"
)

parser.add_argument(
    "--output-file",
    default=DEFAULT_OUTPUT_FILE,
    help=f"Output filename (default: {DEFAULT_OUTPUT_FILE})"
)

args = parser.parse_args()

HOST = f"http://{args.host}:{args.port}"
SAVE_DIR = args.save_dir
SUT_NAME = args.name

os.makedirs(SAVE_DIR, exist_ok=True)


# =========================
# Logging Setup (after args parsed for dynamic filename)
# =========================
def setup_logging(sut_name):
    """Configure logging to console and two files with dynamic name."""
    log_format = '%(asctime)s | %(levelname)-7s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    log = logging.getLogger(f'pmm_client_{sut_name}')
    log.setLevel(logging.INFO)
    
    if log.handlers:
        return log
    
    formatter = logging.Formatter(log_format, date_format)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"pmm_client_{sut_name}_{timestamp}.log"
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)
    
    # File handler - AppData (persistent)
    appdata_handler = logging.FileHandler(
        os.path.join(APP_DATA_DIR, log_filename), encoding='utf-8'
    )
    appdata_handler.setFormatter(formatter)
    log.addHandler(appdata_handler)
    
    # File handler - Local directory (convenient)
    local_handler = logging.FileHandler(
        os.path.join(SCRIPT_DIR, log_filename), encoding='utf-8'
    )
    local_handler.setFormatter(formatter)
    log.addHandler(local_handler)
    
    return log


logger = setup_logging(SUT_NAME)


# =========================
# Get next job (combined API)
# =========================
def get_next_afc_file():
    """
    Fetch the next job from the host server.
    
    Uses the combined /get_next_afc_file API endpoint which returns
    both job metadata (week, filename) and file content in a single request.
    
    Returns:
        dict: Response JSON with keys:
            - status: "ok", "empty", or "error"
            - week: Week identifier (if status is "ok")
            - file: Filename (if status is "ok")
            - content: File content (if status is "ok")
            - job_type: "weekly", "daily", or "queue" (if status is "ok")
            - reason: Error reason (if status is "error")
            - message: Human-readable error message (if status is "error")
            - http_status: HTTP status code from response
    """
    try:
        r = requests.get(f"{HOST}/get_next_afc_file", timeout=args.timeout)
        response = r.json()
        response["http_status"] = r.status_code
        return response
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[{SUT_NAME}] Connection failed: Unable to reach server at {HOST}")
        return {"status": "error", "reason": "connection_failed", "message": str(e)}
    except requests.exceptions.Timeout as e:
        logger.error(f"[{SUT_NAME}] Request timed out after {args.timeout}s")
        return {"status": "error", "reason": "timeout", "message": str(e)}
    except requests.exceptions.JSONDecodeError as e:
        logger.error(f"[{SUT_NAME}] Invalid JSON response from server")
        return {"status": "error", "reason": "invalid_response", "message": str(e)}
    except Exception as e:
        logger.error(f"[{SUT_NAME}] Unexpected error: {e}")
        return {"status": "error", "reason": "unknown", "message": str(e)}


# =========================
# Main loop
# =========================
def main():
    """
    Main client loop.
    
    Continuously polls the server for jobs until the queue is empty.
    For each job received, saves the file content locally.
    
    Exit codes:
        0 - Success (job received and saved, or no more jobs)
        1 - Fatal error (IP not registered, unrecoverable error)
        2 - Temporary error (will retry)
    """
    logger.info(f"[{SUT_NAME}] Connecting to {HOST}")

    while True:
        # Fetch next job (includes file content)
        job = get_next_afc_file()
        status = job.get("status")
        reason = job.get("reason", "")
        message = job.get("message", "")

        # ===========================================
        # Handle "empty" status - no more jobs
        # ===========================================
        if status == "empty":
            if reason == "no_files_remaining":
                # Preschedule mode: no more files assigned to this IP
                logger.info(f"[{SUT_NAME}] No more files assigned to this station")
                if message:
                    logger.info(f"[{SUT_NAME}] {message}")
            else:
                # Free-for-all mode: queue is empty
                logger.info(f"[{SUT_NAME}] Queue is empty, no more jobs available")
            break

        # ===========================================
        # Handle "error" status
        # ===========================================
        if status == "error":
            # --- Fatal errors (no retry) ---
            if reason == "ip_not_registered":
                logger.error(f"[{SUT_NAME}] FATAL: This station's IP is not registered in the preschedule list")
                if message:
                    logger.error(f"[{SUT_NAME}] {message}")
                logger.error(f"[{SUT_NAME}] Contact administrator to add this station to stations.yaml")
                exit(1)
            
            if reason == "file_not_found":
                file_name = job.get("file", "unknown")
                logger.error(f"[{SUT_NAME}] Server error: File '{file_name}' not found on server")
                logger.error(f"[{SUT_NAME}] This may indicate a server configuration issue")
                exit(1)
            
            # --- Retryable errors ---
            if reason == "connection_failed":
                logger.warning(f"[{SUT_NAME}] Cannot connect to server, retrying in {args.interval}s...")
                time.sleep(args.interval)
                continue
            
            if reason == "timeout":
                logger.warning(f"[{SUT_NAME}] Request timed out, retrying in {args.interval}s...")
                time.sleep(args.interval)
                continue
            
            if reason == "invalid_response":
                logger.warning(f"[{SUT_NAME}] Invalid response from server, retrying in {args.interval}s...")
                time.sleep(args.interval)
                continue
            
            # --- Unknown errors ---
            logger.warning(f"[{SUT_NAME}] Error: {reason}")
            if message:
                logger.warning(f"[{SUT_NAME}] Details: {message}")
            logger.warning(f"[{SUT_NAME}] Retrying in {args.interval}s...")
            time.sleep(args.interval)
            continue

        # ===========================================
        # Handle unexpected status
        # ===========================================
        if status != "ok":
            logger.warning(f"[{SUT_NAME}] Unexpected response status: {status}")
            logger.warning(f"[{SUT_NAME}] Retrying in {args.interval}s...")
            time.sleep(args.interval)
            continue

        # ===========================================
        # Handle "ok" status - success
        # ===========================================
        week = job.get("week", "unknown")
        filename = job.get("file", "unknown")
        content = job.get("content", "")
        job_type = job.get("job_type", "unknown")

        # Log with job type for clarity
        job_type_label = job_type.upper() if job_type else "UNKNOWN"
        logger.info(f"[{SUT_NAME}] Received [{job_type_label}] job: {week}/{filename}")

        # Save locally with configured filename
        local_path = os.path.join(SAVE_DIR, args.output_file)

        try:
            with open(local_path, "w") as f:
                f.write(content)
            logger.info(f"[{SUT_NAME}] Saved: {local_path}")
        except Exception as e:
            logger.error(f"[{SUT_NAME}] Failed to save file: {e}")
            exit(1)

        break
    
    logger.info(f"[{SUT_NAME}] Client finished")


# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    main()
