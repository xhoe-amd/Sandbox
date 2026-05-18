import numpy as np
import matplotlib.pyplot as plt

# === Load data from file ===
file_path = r"C:\Users\xhoe\Downloads\APU_Total_P=APU_VDDCR_PCCX_P+APU_VD.txt"

data = []
with open(file_path, 'r') as f:
    for line in f:
        try:
            # Keep only numeric values
            val = float(line.strip())
            data.append(val)
        except:
            continue

signal = np.array(data)

# === Define logic-high threshold ===
# Adjust this depending on your signal behavior
threshold = 9.0   # <- tweak if needed (e.g. 6.0 / 7.0 / 12.0 depending on region)

# === Extract contiguous logic-high segments ===
logic_mask = signal >= threshold

segments = []
current_segment = []

for val, is_high in zip(signal, logic_mask):
    if is_high:
        current_segment.append(val)
    else:
        if current_segment:
            segments.append(current_segment)
            current_segment = []

# Catch last segment
if current_segment:
    segments.append(current_segment)

# === Concatenate all logic-high segments ===
if segments:
    trimmed_signal = np.concatenate(segments)
else:
    trimmed_signal = np.array([])

print(segments)

# # === Plot results ===
# plt.figure(figsize=(14, 5))

# # Before trimming
# plt.subplot(1, 2, 1)
# plt.plot(signal)
# plt.title("Original Signal")
# plt.xlabel("Sample Index")
# plt.ylabel("Amplitude")

# # After trimming (logic-high only)
# plt.subplot(1, 2, 2)
# plt.plot(trimmed_signal)
# plt.title("Concatenated Logic-High Segments")
# plt.xlabel("Sample Index")
# plt.ylabel("Amplitude")

# plt.tight_layout()
# plt.show()


# # === Optional debug info ===
# print(f"Total samples: {len(signal)}")
# print(f"Number of logic-high segments: {len(segments)}")
# print(f"Trimmed samples: {len(trimmed_signal)}")