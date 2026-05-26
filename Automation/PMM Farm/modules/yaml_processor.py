"""
Feature YAML Processor Module.

Handles parsing feature YAML files and generating permutations.
"""

import hashlib
import itertools
import json
import os
from datetime import datetime
import yaml


# ===========================================
# Time Helpers
# ===========================================
def get_current_week():
    """
    Get the current ISO week string.
    
    Returns:
        str: Week string in format "YYYY-WNN" (e.g., "2026-W21").
    """
    now = datetime.now()
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


# ===========================================
# YAML Loading
# ===========================================
def load_yaml(yaml_path):
    """
    Load and parse the YAML configuration file.
    
    Args:
        yaml_path (str): Path to the YAML file.
    
    Returns:
        dict: Parsed YAML content, or empty dict if file is empty.
    """
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f) or {}


def load_stations_config(stations_path):
    """
    Load and parse the stations YAML configuration file.
    
    Args:
        stations_path (str): Path to stations YAML file.
    
    Returns:
        dict: Parsed stations config.
    """
    with open(stations_path, "r") as f:
        return yaml.safe_load(f) or {}


# ===========================================
# Hash Computation
# ===========================================
def compute_hash(data):
    """
    Compute MD5 hash of data for change detection.
    
    Args:
        data: Any JSON-serializable data structure.
    
    Returns:
        str: MD5 hexdigest of the JSON-serialized data.
    """
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


# ===========================================
# Feature Extraction
# ===========================================
def extract_pairs(groups):
    """
    Extract feature key-value pairs from YAML groups.
    
    Processes feature definitions from the YAML structure, keeping the full
    dotted path as the feature name. Features with values are formatted as 
    "name=value", features without values (null) are just "name".
    
    Args:
        groups (list): List of dictionaries containing feature definitions.
    
    Returns:
        list: Sorted, deduplicated list of feature strings.
    """
    pairs = []
    for group in groups:
        for k, v in group.items():
            pairs.append(k if v is None else f"{k}={v}")
    return sorted(set(pairs))


def generate_combinations(values):
    """
    Generate all possible combinations of the input values.
    
    Creates combinations of all lengths from 1 to len(values).
    
    Args:
        values (list): List of feature strings to combine.
    
    Returns:
        list: List of lists, each containing a combination of features.
    """
    results = []
    for r in range(1, len(values) + 1):
        results.extend(list(itertools.combinations(values, r)))
    return [list(r) for r in results]


def process_week_features(groups, permutation_mode=False):
    """
    Process feature groups for a week into job combinations.
    
    Args:
        groups (list): Feature groups from the YAML.
        permutation_mode (bool): If True, generate all combinations.
    
    Returns:
        list: List of feature combinations.
    """
    pairs = extract_pairs(groups)
    
    if not permutation_mode:
        return [[p] for p in pairs]
    
    return generate_combinations(pairs)


# ===========================================
# File Generation
# ===========================================
def write_files(output_dir, week, combinations):
    """
    Write job files for each feature combination.
    
    Creates a directory for the week and writes one text file per combination.
    
    Args:
        output_dir (str): Base output directory.
        week (str): Week identifier (e.g., "2026-W21").
        combinations (list): List of feature combinations to write.
    
    Returns:
        list: List of generated filenames.
    """
    base = os.path.join(output_dir, week)
    os.makedirs(base, exist_ok=True)

    # Cleanup existing files
    for f in os.listdir(base):
        os.remove(os.path.join(base, f))

    files = []
    for combo in combinations:
        name = "-".join(c.split("=")[0] for c in combo)
        filename = f"{name}.txt"
        path = os.path.join(base, filename)

        with open(path, "w") as f:
            f.write("\n".join(combo))

        files.append(filename)

    return files


def get_permutation_names(combinations):
    """
    Convert combinations to permutation names.
    
    Args:
        combinations (list): List of feature combinations.
    
    Returns:
        list: List of permutation name strings.
    """
    names = []
    for combo in combinations:
        name = "-".join(c.split("=")[0] for c in combo)
        names.append(name)
    return names
