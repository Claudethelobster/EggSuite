"""
batch_processor.py - High-performance batch processing and recipe execution engine for EggSuite.
Executes automated data pipelines across directories of files and outputs consolidated reports.
"""

import os
import glob
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from egg_suite.core.analysis_engine import (
    fit_curve, find_peaks, compute_fft, smooth_data, integrate_area, compute_statistics
)


class BatchRecipe:
    """Represents an ordered pipeline of processing operations to apply per file."""
    def __init__(self, name: str = "Default Recipe", steps: Optional[List[Dict[str, Any]]] = None):
        self.name = name
        self.steps = steps or []

    def add_step(self, op_type: str, params: Optional[Dict[str, Any]] = None):
        self.steps.append({
            "type": op_type,
            "params": params or {}
        })

    def to_json(self, indent: int = 4) -> str:
        return json.dumps({
            "recipe_name": self.name,
            "steps": self.steps
        }, indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "BatchRecipe":
        data = json.loads(json_str)
        return cls(name=data.get("recipe_name", "Loaded Recipe"), steps=data.get("steps", []))

    def save_to_file(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load_from_file(cls, filepath: str) -> "BatchRecipe":
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())


class BatchResult:
    """Stores the aggregated results of a batch execution run."""
    def __init__(self, total_files: int):
        self.total_files = total_files
        self.processed_count = 0
        self.failed_count = 0
        self.file_records: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, str]] = []
        self.start_time = time.time()
        self.elapsed_seconds = 0.0

    def add_record(self, record: Dict[str, Any]):
        self.file_records.append(record)
        self.processed_count += 1

    def add_error(self, filename: str, error_msg: str):
        self.errors.append({"filename": filename, "error": error_msg})
        self.failed_count += 1
        self.processed_count += 1

    def to_dataframe(self) -> pd.DataFrame:
        if not self.file_records:
            return pd.DataFrame()
        return pd.DataFrame(self.file_records)

    def export_summary_csv(self, output_path: str):
        df = self.to_dataframe()
        if not df.empty:
            df.to_csv(output_path, index=False, encoding="utf-8-sig")


def execute_batch_pipeline(
    input_folder: str,
    file_pattern: str = "*.csv",
    recipe: Optional[BatchRecipe] = None,
    output_folder: Optional[str] = None,
    x_col: int = 0,
    y_col: int = 1,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> BatchResult:
    """
    Executes a BatchRecipe over all matching files in input_folder.

    Parameters:
        input_folder: Path to directory containing source files.
        file_pattern: Glob pattern to filter files (e.g. '*.csv').
        recipe: The BatchRecipe containing sequential operation steps.
        output_folder: Optional folder to save processed files/plots.
        x_col: Column index for x-coordinates (default: 0).
        y_col: Column index for y-coordinates (default: 1).
        progress_callback: Callback func(current_idx, total_count, filename).
        cancel_check: Optional function returning True if user cancelled execution.

    Returns:
        BatchResult containing metric summary table and execution statistics.
    """
    search_path = os.path.join(input_folder, file_pattern)
    matched_files = sorted(glob.glob(search_path))
    
    if not matched_files:
        search_path = os.path.join(input_folder, "**", file_pattern)
        matched_files = sorted(glob.glob(search_path, recursive=True))

    total_files = len(matched_files)
    result = BatchResult(total_files=total_files)

    if total_files == 0:
        return result

    if output_folder and not os.path.exists(output_folder):
        os.makedirs(output_folder, exist_ok=True)

    recipe_steps = recipe.steps if recipe else []

    for idx, filepath in enumerate(matched_files):
        if cancel_check and cancel_check():
            break

        fname = os.path.basename(filepath)
        if progress_callback:
            progress_callback(idx + 1, total_files, fname)

        try:
            # 1. Load data
            ext = os.path.splitext(filepath)[1].lower()
            if ext in (".csv", ".txt", ".dat"):
                df = pd.read_csv(filepath, comment="#", skipinitialspace=True)
            elif ext in (".h5", ".hdf5"):
                import h5py
                with h5py.File(filepath, "r") as hf:
                    keys = list(hf.keys())
                    data_dict = {k: np.array(hf[k]).flatten() for k in keys if isinstance(hf[k], h5py.Dataset)}
                    df = pd.DataFrame(data_dict)
            else:
                df = pd.read_csv(filepath, comment="#")

            if df.empty or len(df.columns) < 2:
                result.add_error(fname, "File contains insufficient columns for 2D analysis.")
                continue

            # Resolve X and Y arrays
            cols = list(df.columns)
            x_name = cols[x_col] if x_col < len(cols) else cols[0]
            y_name = cols[y_col] if y_col < len(cols) else cols[1]

            x = df[x_name].to_numpy(dtype=float)
            y = df[y_name].to_numpy(dtype=float)

            # Drop non-finite rows
            valid = np.isfinite(x) & np.isfinite(y)
            x = x[valid]
            y = y[valid]

            file_metrics: Dict[str, Any] = {
                "Filename": fname,
                "File_Path": filepath,
                "Original_Points": len(df),
                "Valid_Points": len(x)
            }

            # 2. Execute Recipe Steps sequentially
            current_x = x.copy()
            current_y = y.copy()

            for step in recipe_steps:
                stype = step.get("type", "").lower()
                params = step.get("params", {})

                if stype == "slice_range":
                    x_min = params.get("x_min", -np.inf)
                    x_max = params.get("x_max", np.inf)
                    mask = (current_x >= x_min) & (current_x <= x_max)
                    current_x = current_x[mask]
                    current_y = current_y[mask]

                elif stype == "smooth":
                    method = params.get("method", "savgol")
                    w_len = int(params.get("window_length", 11))
                    poly = int(params.get("polyorder", 3))
                    current_y = smooth_data(current_y, method=method, window_length=w_len, polyorder=poly)

                elif stype == "baseline_subtract":
                    b_method = params.get("method", "endpoints")
                    area_info = integrate_area(current_x, current_y, baseline_method=b_method)
                    file_metrics["Net_Integrated_Area"] = area_info["net_area"]
                    file_metrics["Baseline_Area"] = area_info["baseline_area"]
                    file_metrics["Total_Area"] = area_info["total_area"]

                elif stype == "fit_curve":
                    model = params.get("model", "gaussian")
                    fit_res = fit_curve(current_x, current_y, model=model)
                    file_metrics[f"Fit_Model"] = model
                    file_metrics[f"Fit_R2"] = fit_res.r_squared
                    file_metrics[f"Fit_RMSE"] = fit_res.rmse
                    file_metrics[f"Fit_Success"] = fit_res.success
                    for pname, pval in fit_res.parameters.items():
                        file_metrics[f"Fit_Param_{pname}"] = pval
                    for pname, perr in fit_res.parameter_errors.items():
                        file_metrics[f"Fit_Err_{pname}"] = perr

                elif stype == "find_peaks":
                    height = params.get("min_height")
                    dist = params.get("min_distance")
                    peaks = find_peaks(current_y, x=current_x, height=height, distance=dist)
                    peak_indices = peaks["indices"]
                    file_metrics["Num_Peaks_Found"] = len(peak_indices)
                    if len(peak_indices) > 0:
                        file_metrics["Primary_Peak_X"] = float(peaks["x"][0])
                        file_metrics["Primary_Peak_Y"] = float(peaks["y"][0])

                elif stype == "statistics":
                    stats = compute_statistics(current_y)
                    file_metrics["Mean_Y"] = stats["mean"]
                    file_metrics["Std_Y"] = stats["std"]
                    file_metrics["Min_Y"] = stats["min"]
                    file_metrics["Max_Y"] = stats["max"]
                    file_metrics["Median_Y"] = stats["median"]

            # Save processed data file if output folder specified
            if output_folder:
                out_csv = os.path.join(output_folder, f"PROCESSED_{fname}")
                out_df = pd.DataFrame({f"{x_name}_Processed": current_x, f"{y_name}_Processed": current_y})
                out_df.to_csv(out_csv, index=False)

            result.add_record(file_metrics)

        except Exception as e:
            result.add_error(fname, str(e))

    result.elapsed_seconds = time.time() - result.start_time
    return result
