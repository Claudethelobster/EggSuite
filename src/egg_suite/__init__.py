"""
EggSuite - Data Analysis & Visualization Suite
"""

__version__ = "1.0.0"

# Expose mathematical analysis engine for programmatic / script use
from egg_suite.core import analysis_engine as analysis
from egg_suite.core.analysis_engine import (
    FitResult,
    fit_curve,
    find_peaks,
    compute_fft,
    smooth_data,
    integrate_area,
    compute_statistics
)

def load_dataset(filepath: str, delimiter: str = "auto", has_header: bool = True):
    """
    Loads a dataset from CSV or HDF5 into a pandas.DataFrame or dataset container
    without requiring the GUI to be running.
    """
    import pandas as pd
    import os
    
    if delimiter == "auto":
        delimiter = ","
        
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".csv", ".txt", ".dat"):
        return pd.read_csv(filepath, sep=delimiter, header=0 if has_header else None, comment='#', skipinitialspace=True)
    elif ext in (".h5", ".hdf5"):
        import h5py
        return h5py.File(filepath, 'r')
    else:
        return pd.read_csv(filepath, sep=delimiter, header=0 if has_header else None, comment='#')

def main():
    """Launches the EggSuite GUI application."""
    from egg_suite.__main__ import main as _main
    return _main()

run = main
egg_suite = main

__all__ = [
    "main",
    "run",
    "egg_suite",
    "__version__",
    "analysis",
    "FitResult",
    "fit_curve",
    "find_peaks",
    "compute_fft",
    "smooth_data",
    "integrate_area",
    "compute_statistics",
    "load_dataset"
]
