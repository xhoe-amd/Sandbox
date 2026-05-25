"""
PMM Farm SUT Client.

This client connects to the PMM Farm host server and retrieves job files
for processing. It uses the combined /get_next_afc_file API endpoint to fetch
both job metadata and file content in a single request.

Usage:
    python pmm_client.py [OPTIONS]

Command-line Arguments:
    --host HOST       Host IP address (default: 10.148.34.147)
    --port PORT       Host port number (default: 5000)
    --name NAME       SUT identifier name (default: SUT)
    --interval SEC    Retry interval in seconds (default: 5)

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


# =========================
# Directory paths
# =========================
APP_NAME = "APEXScheduler"
if os.name == 'nt':  # Windows
    APP_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), APP_NAME)
else:  # Linux/Mac
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), f'.{APP_NAME.lower()}')

os.makedirs(APP_DATA_DIR, exist_ok=True)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# =========================
# Parse CLI arguments (before logging setup)
# =========================
parser = argparse.ArgumentParser(description="SUT Client")

parser.add_argument(
    "--host",
    help="Host IP (e.g. 192.168.1.10)",
    default="10.148.216.73" # Harris Host
    # default="localhost" # localhost for testing
)

parser.add_argument(
    "--port",
    type=int,
    default=5000,
    help="Host port number (default: 5000)"
)

parser.add_argument(
    "--name",
    default="SUT",
    help="SUT identifier name (default: SUT)"
)

parser.add_argument(
    "--interval",
    type=int,
    default=5,
    help="Retry interval in seconds (default: 5)"
)

parser.add_argument(
    "--save-dir",
    default="received",
    help="Directory to save received files (default: received)"
)

parser.add_argument(
    "--timeout",
    type=int,
    default=10,
    help="Request timeout in seconds (default: 10)"
)

parser.add_argument(
    "--output-file",
    default="enable_pmm_features.txt",
    help="Output filename (default: enable_pmm_features.txt)"
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
            - reason: Error reason (if status is "error")
    """
    try:
        r = requests.get(f"{HOST}/get_next_afc_file", timeout=args.timeout)
        return r.json()
    except Exception as e:
        logger.warning(f"[{SUT_NAME}] Error connecting to host: {e}")
        return {"status": "error"}


# =========================
# Main loop
# =========================
def main():
    """
    Main client loop.
    
    Continuously polls the server for jobs until the queue is empty.
    For each job received, saves the file content locally.
    """
    logger.info(f"[{SUT_NAME}] Connected to {HOST}")

    while True:
        # Fetch next job (includes file content)
        job = get_next_afc_file()

        if job["status"] == "empty":
            logger.info(f"[{SUT_NAME}] No more jobs, exiting")
            break

        if job["status"] == "error":
            reason = job.get("reason", "unknown")
            logger.warning(f"[{SUT_NAME}] Error: {reason}, retrying...")
            time.sleep(args.interval)
            continue

        if job["status"] != "ok":
            logger.warning(f"[{SUT_NAME}] Unexpected response, retrying...")
            time.sleep(args.interval)
            continue

        week = job["week"]
        filename = job["file"]
        content = job["content"]

        logger.info(f"[{SUT_NAME}] Received job: {week}/{filename}")

        # Save locally with configured filename
        local_path = os.path.join(SAVE_DIR, args.output_file)

        with open(local_path, "w") as f:
            f.write(content)

        logger.info(f"[{SUT_NAME}] Saved: {local_path}")

        break


# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    main()
