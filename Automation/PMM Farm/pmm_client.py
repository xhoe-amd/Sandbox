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

import requests
import time
import os
import argparse

# =========================
# Parse CLI arguments
# =========================
parser = argparse.ArgumentParser(description="SUT Client")

parser.add_argument(
    "--host",
    help="Host IP (e.g. 192.168.1.10)",
    default="10.148.34.147"
)

parser.add_argument(
    "--port",
    default="5000",
    help="Port (default: 5000)"
)

parser.add_argument(
    "--name",
    default="SUT",
    help="SUT name (optional)"
)

parser.add_argument(
    "--interval",
    type=int,
    default=5,
    help="Retry interval in seconds"
)

args = parser.parse_args()

HOST = f"http://{args.host}:{args.port}"
SAVE_DIR = "received"
SUT_NAME = args.name

os.makedirs(SAVE_DIR, exist_ok=True)


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
        r = requests.get(f"{HOST}/get_next_afc_file", timeout=10)
        return r.json()
    except Exception as e:
        print(f"⚠️ [{SUT_NAME}] Error connecting to host:", e)
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
    print(f"🚀 [{SUT_NAME}] Connected to {HOST}")

    while True:
        # Fetch next job (includes file content)
        job = get_next_afc_file()

        if job["status"] == "empty":
            print(f"✅ [{SUT_NAME}] No more jobs, exiting")
            break

        if job["status"] == "error":
            reason = job.get("reason", "unknown")
            print(f"⚠️ [{SUT_NAME}] Error: {reason}, retrying...")
            time.sleep(args.interval)
            continue

        if job["status"] != "ok":
            print(f"⚠️ [{SUT_NAME}] Unexpected response, retrying...")
            time.sleep(args.interval)
            continue

        week = job["week"]
        filename = job["file"]
        content = job["content"]

        print(f"📥 [{SUT_NAME}] Received job: {week}/{filename}")

        # Save locally
        local_path = os.path.join(SAVE_DIR, filename)

        with open(local_path, "w") as f:
            f.write(content)

        print(f"💾 [{SUT_NAME}] Saved: {local_path}")

        break


# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    main()
