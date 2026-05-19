import yaml
import itertools
import hashlib
import time
from datetime import datetime
import os
import json

# =========================
# CONFIG
# =========================
file_path = r"C:\Users\xhoe\OneDrive - Advanced Micro Devices Inc\Documents\Sandbox\Automation\PMM Farm\enable_feature.yaml"

ENABLE_PERMUTATION_MODE = True
CHECK_INTERVAL = 60  # seconds

last_hash = None


# =========================
# Compute hash (only current week data)
# =========================
def compute_hash(data):
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


# =========================
# Get current week
# =========================
def get_current_week():
    now = datetime.now()
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


# =========================
# Load YAML
# =========================
def load_yaml():
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


# =========================
# Convert YAML groups → key=value pairs
# =========================
def extract_pairs(groups):
    all_pairs = []

    for group in groups:
        for k, v in group.items():
            # ✅ Take last part of key
            key_name = k.split(".")[-1]

            # ✅ Handle value / null
            if v is None:
                pair = f"{key_name}=0x01"
            else:
                pair = f"{key_name}={v}"

            all_pairs.append(pair)

    # ✅ Remove duplicates + keep stable order
    return sorted(set(all_pairs))


# =========================
# Generate combinations (1 → N)
# =========================
def generate_combinations(values):
    results = []

    for r in range(1, len(values) + 1):
        for combo in itertools.combinations(values, r):
            results.append(list(combo))

    return results


# =========================
# Process ONLY current week
# =========================
def process_current_week(groups):
    # ✅ Flatten ALL groups into single list
    all_pairs = extract_pairs(groups)

    results = []

    # ✅ Default mode (no permutations)
    if not ENABLE_PERMUTATION_MODE:
        for p in all_pairs:
            results.append([p])

    # ✅ Permutation mode
    else:
        results = generate_combinations(all_pairs)

    return results


# =========================
# Write output files
# =========================
def write_files(week, combinations):
    base_dir = os.path.join("output", week)
    os.makedirs(base_dir, exist_ok=True)

    # clean old files
    for f in os.listdir(base_dir):
        os.remove(os.path.join(base_dir, f))

    for combo in combinations:
        # ✅ extract only key (before '=')
        key_names = [c.split("=")[0] for c in combo]

        # ✅ filename uses only keys
        safe_name = "-".join(key_names)

        filename = os.path.join(base_dir, safe_name + ".txt")

        with open(filename, "w") as f:
            # ✅ content still full key=value
            f.write("\n".join(combo))

    print(f"✅ [{week}] Generated {len(combinations)} files")


# =========================
# Monitor loop
# =========================
def monitor():
    global last_hash

    print("🚀 Monitoring CURRENT WEEK only...")

    while True:
        try:
            data = load_yaml()

            if not data:
                print("⚠️ YAML empty or invalid")
                time.sleep(CHECK_INTERVAL)
                continue

            current_week = get_current_week()
            groups = data.get(current_week)

            if not groups:
                print(f"⚠️ No data for {current_week}")
                time.sleep(CHECK_INTERVAL)
                continue

            current_hash = compute_hash(groups)

            # ✅ Detect changes ONLY for current week
            if current_hash != last_hash:
                print(f"\n🔄 Change detected in {current_week}")

                results = process_current_week(groups)
                write_files(current_week, results)

                last_hash = current_hash
            else:
                print("⏳ No change in current week")

        except Exception as e:
            print("⚠️ Error:", e)

        time.sleep(CHECK_INTERVAL)


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    monitor()