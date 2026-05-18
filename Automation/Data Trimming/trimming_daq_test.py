import numpy as np
import statistics
import csv
import matplotlib.pyplot as plt
from openpyxl import load_workbook, Workbook
from openpyxl.chart import LineChart, Reference

csv_file = "0_daq_ddc96a15-5f79-4224-8e29-f9d4765f2fae.power.csv"
target_data = "APU_Total_P=APU_VDDCR_PCCX_P+APU_VDDCR_ECCX02_P+APU_VDDCR_ECCX13_P+APU_VDDCR_AIE_P+APU_VDDCR_GFX_P+APU_VDDCR_SOC_P+ROC_DRAM_Total_P"


column_index = None
start_row = None
rows = []

# Read CSV into memory
with open(csv_file, newline='', encoding='utf-8') as f:
    reader = list(csv.reader(f))
    rows = reader

# Find the cell containing target_data
for row_idx, row in enumerate(rows):
    for col_idx, cell in enumerate(row):
        if cell == target_data:
            column_index = col_idx
            start_row = row_idx + 2  # start BELOW the cell
            break
    if column_index is not None:
        break

# Pull values below that cell in the same column
data = []

if column_index is not None:
    for row_index, row in enumerate(rows[start_row:], start=start_row):
        if column_index < len(row) and row[column_index] != "":
            data.append((row_index, float(row[column_index])))


# def rate_of_change(y, t=None):
#     y = np.asarray(y, dtype=float)
#     if t is None:
#         t = np.arange(len(y), dtype=float)
#     else:
#         t = np.asarray(t, dtype=float)

#     if len(y) < 2:
#         return 0.0

#     return np.polyfit(t, y, 1)[0]


MIN_PASS_COUNT = 200
MAX_DROP_COUNT = 10   # allow small droops

pass_count = 0
drop_count = 0

peaks = []
stable_value = statistics.mean([t[1] for t in data[:1500]])

for row_index, val in enumerate(data):

    if val[1] > stable_value:
        pass_count += 1
        drop_count = 0

        if pass_count == 1:
            start = (row_index, val[1])

    else:
        if pass_count > 0:
            drop_count += 1

            if drop_count <= MAX_DROP_COUNT:
                # ignore short droop → still in high
                pass_count += 1
                continue

            # real break
            if pass_count > MIN_PASS_COUNT:
                peaks.append((start, (row_index, val[1])))

        pass_count = 0
        drop_count = 0

