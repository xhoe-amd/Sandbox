import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def read_csv_generic(csv_path):
    """
    Reads normal CSV or Agilent datalogger CSV.

    For Agilent format:
      line 0 = #AGILENTDATALOGGER
      line 1 = real header
      line 2 = unit row
    """
    with open(csv_path, "r", errors="replace") as f:
        first_line = f.readline().strip()

    if first_line.startswith("#AGILENTDATALOGGER"):
        df = pd.read_csv(csv_path, skiprows=[0, 2], header=0)
    else:
        df = pd.read_csv(csv_path)

    df.columns = [str(c).lstrip("#").strip() for c in df.columns]
    return df


def base_col_name(col):
    """
    Converts:
      APU_Total_P=APU_VDDCR_PCCX_P+...
    into:
      APU_Total_P
    """
    return str(col).split("=", 1)[0].strip()


def resolve_column(df, column_name):
    """
    Supports:
      1. Exact full column name
      2. Short name before '='

    Example:
      User gives: APU_Total_P
      CSV has:   APU_Total_P=APU_VDDCR_PCCX_P+...
    """
    if column_name in df.columns:
        return column_name

    matches = [c for c in df.columns if base_col_name(c) == column_name]
    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        raise ValueError(
            f"Column name '{column_name}' is ambiguous. Matches: {matches}"
        )

    raise ValueError(
        f"Column '{column_name}' not found. Available short names include:\n"
        + "\n".join(sorted(set(base_col_name(c) for c in df.columns))[:80])
    )


def otsu_threshold(values, bins=256):
    """
    Auto threshold for separating idle and active data.
    Good for power logs where idle and active form two clusters.
    """
    values = pd.to_numeric(values, errors="coerce").dropna().to_numpy()

    if len(values) == 0:
        raise ValueError("No valid numeric values found for threshold calculation.")

    if np.nanmin(values) == np.nanmax(values):
        return float(np.nanmin(values))

    hist, bin_edges = np.histogram(values, bins=bins)
    centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    weight1 = np.cumsum(hist)
    weight2 = np.cumsum(hist[::-1])[::-1]

    mean1 = np.cumsum(hist * centers) / np.maximum(weight1, 1)
    mean2 = (
        np.cumsum((hist * centers)[::-1]) / np.maximum(weight2[::-1], 1)
    )[::-1]

    between_class_variance = (
        weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    )

    idx = np.argmax(between_class_variance)
    return float(centers[:-1][idx])


def remove_short_true_segments(mask, min_len):
    """
    Removes active segments shorter than min_len samples.
    """
    mask = pd.Series(mask).astype(bool).reset_index(drop=True)

    start = None
    for i, val in enumerate(mask):
        if val and start is None:
            start = i
        elif not val and start is not None:
            if i - start < min_len:
                mask.iloc[start:i] = False
            start = None

    if start is not None and len(mask) - start < min_len:
        mask.iloc[start:] = False

    return mask.to_numpy()


def fill_short_false_gaps(mask, max_gap):
    """
    Merges active sections separated by short idle gaps.
    """
    mask = pd.Series(mask).astype(bool).reset_index(drop=True)

    start = None
    for i, val in enumerate(mask):
        if not val and start is None:
            start = i
        elif val and start is not None:
            if i - start <= max_gap:
                mask.iloc[start:i] = True
            start = None

    return mask.to_numpy()


def trim_active_state(
    df,
    column_name,
    threshold="auto",
    smooth_samples=20,
    min_active_samples=40,
    merge_gap_samples=10,
):
    """
    Trims idle state and keeps active state only.

    threshold:
      "auto" uses Otsu threshold.
      numeric value uses manual threshold.

    smooth_samples:
      Rolling median window. Use around 0.5 sec if data is 25 ms/sample:
      0.5 sec / 0.025 sec = 20 samples.

    min_active_samples:
      Remove active spikes shorter than this.
      Example: 40 samples at 25 ms/sample = 1 sec.

    merge_gap_samples:
      Merge small idle gaps inside active state.
      Example: 10 samples at 25 ms/sample = 0.25 sec.
    """
    real_col = resolve_column(df, column_name)

    df = df.copy()
    df[real_col] = pd.to_numeric(df[real_col], errors="coerce")

    valid = df[real_col].notna()
    df_valid = df.loc[valid].copy()

    y = df_valid[real_col]

    y_smooth = (
        y.rolling(window=smooth_samples, center=True, min_periods=1)
        .median()
    )

    if threshold == "auto":
        active_threshold = otsu_threshold(y_smooth)
    else:
        active_threshold = float(threshold)

    active_mask = y_smooth > active_threshold

    active_mask = fill_short_false_gaps(active_mask, merge_gap_samples)
    active_mask = remove_short_true_segments(active_mask, min_active_samples)

    active_df = df_valid.loc[active_mask].copy()

    return active_df, real_col, active_threshold


def choose_x_axis(df, x_col=None):
    """
    Uses user-selected x-axis if provided.
    Otherwise prefers Seconds, Timestamp, Time, then index.
    """
    if x_col is not None:
        if x_col not in df.columns:
            raise ValueError(f"x_col '{x_col}' not found in CSV.")
        return df[x_col], x_col

    for candidate in ["Seconds", "Timestamp", "Time", "time", "timestamp"]:
        if candidate in df.columns:
            return df[candidate], candidate

    return df.index, "Index"


def plot_active(active_df, column, original_df=None, x_col=None, output_png=None):
    x, x_label = choose_x_axis(active_df, x_col)

    plt.figure(figsize=(12, 5))

    if original_df is not None:
        original_x, _ = choose_x_axis(original_df, x_col)
        original_y = pd.to_numeric(original_df[column], errors="coerce")
        plt.plot(
            original_x,
            original_y,
            color="red",
            linewidth=0.8,
            alpha=0.55,
            label="Original data",
        )

    plt.plot(x, active_df[column], linewidth=1.2, label="Active state only")
    plt.xlabel(x_label)
    plt.ylabel(base_col_name(column))
    plt.title(f"Original and Active State: {base_col_name(column)}")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    if output_png:
        plt.savefig(output_png, dpi=150)

    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Trim idle states from CSV and plot active-state data."
    )

    parser.add_argument("--csv", required=True, help="Input CSV file path")
    parser.add_argument(
        "--column",
        required=True,
        help="Column to analyze. Example: APU_Total_P",
    )
    parser.add_argument(
        "--threshold",
        default="auto",
        help="Use 'auto' or a numeric threshold. Example: auto or 9.0",
    )
    parser.add_argument(
        "--x-col",
        default=None,
        help="Optional x-axis column. Example: Seconds or Timestamp",
    )
    parser.add_argument(
        "--smooth-samples",
        type=int,
        default=20,
        help="Rolling median smoothing window in samples",
    )
    parser.add_argument(
        "--min-active-samples",
        type=int,
        default=40,
        help="Remove active segments shorter than this many samples",
    )
    parser.add_argument(
        "--merge-gap-samples",
        type=int,
        default=10,
        help="Merge idle gaps shorter than this many samples",
    )
    parser.add_argument(
        "--out-csv",
        default="active_only.csv",
        help="Output CSV containing active-state rows only",
    )
    parser.add_argument(
        "--out-png",
        default="active_plot.png",
        help="Output plot image",
    )

    args = parser.parse_args()

    df = read_csv_generic(args.csv)

    active_df, real_col, used_threshold = trim_active_state(
        df=df,
        column_name=args.column,
        threshold=args.threshold,
        smooth_samples=args.smooth_samples,
        min_active_samples=args.min_active_samples,
        merge_gap_samples=args.merge_gap_samples,
    )

    active_df.to_csv(args.out_csv, index=False)

    print(f"Resolved column : {real_col}")
    print(f"Threshold used  : {used_threshold:.6f}")
    print(f"Original rows   : {len(df)}")
    print(f"Active rows     : {len(active_df)}")
    print(f"Saved CSV       : {args.out_csv}")
    print(f"Saved plot      : {args.out_png}")

    plot_active(
        active_df=active_df,
        column=real_col,
        original_df=df,
        x_col=args.x_col,
        output_png=args.out_png,
    )


if __name__ == "__main__":
    main()
