"""
multi_peak_engine.py - Advanced Multi-Peak Deconvolution & Composite Fitting Engine.
Solves overlapping Gaussian, Lorentzian, and Voigt peak profiles simultaneously with baseline.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
import scipy.optimize as opt


def peak_gaussian(x: np.ndarray, amplitude: float, center: float, sigma: float) -> np.ndarray:
    """Gaussian single peak component."""
    sigma = max(1e-12, abs(sigma))
    return amplitude * np.exp(-((x - center) ** 2) / (2.0 * (sigma ** 2)))


def peak_lorentzian(x: np.ndarray, amplitude: float, center: float, gamma: float) -> np.ndarray:
    """Lorentzian single peak component."""
    gamma = max(1e-12, abs(gamma))
    return amplitude * (gamma ** 2) / ((x - center) ** 2 + gamma ** 2)


def peak_pseudo_voigt(x: np.ndarray, amplitude: float, center: float, width: float, eta: float = 0.5) -> np.ndarray:
    """Pseudo-Voigt linear combination of Gaussian and Lorentzian."""
    eta = np.clip(eta, 0.0, 1.0)
    g = peak_gaussian(x, amplitude, center, width / 2.35482)
    l = peak_lorentzian(x, amplitude, center, width / 2.0)
    return eta * l + (1.0 - eta) * g


class PeakItem:
    """Represents an individual peak in a multi-peak composite model."""
    def __init__(self, peak_type: str = "gaussian", center: float = 0.0, amplitude: float = 1.0, width: float = 1.0):
        self.peak_type = peak_type.lower()
        self.center = float(center)
        self.amplitude = float(amplitude)
        self.width = max(1e-6, float(width))
        self.area = 0.0
        self.fwhm = 0.0
        self.relative_area_pct = 0.0

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        if self.peak_type == "gaussian":
            return peak_gaussian(x, self.amplitude, self.center, self.width / 2.35482)
        elif self.peak_type == "lorentzian":
            return peak_lorentzian(x, self.amplitude, self.center, self.width / 2.0)
        elif self.peak_type in ("voigt", "pseudo_voigt"):
            return peak_pseudo_voigt(x, self.amplitude, self.center, self.width)
        return peak_gaussian(x, self.amplitude, self.center, self.width)


class MultiPeakFitResult:
    """Encapsulates the complete multi-peak deconvolution solution."""
    def __init__(
        self,
        peaks: List[PeakItem],
        baseline_offset: float,
        baseline_slope: float,
        r_squared: float,
        rmse: float,
        success: bool = True,
        message: str = "Deconvolution converged successfully."
    ):
        self.peaks = peaks
        self.baseline_offset = baseline_offset
        self.baseline_slope = baseline_slope
        self.r_squared = r_squared
        self.rmse = rmse
        self.success = success
        self.message = message

    def evaluate_composite(self, x: np.ndarray) -> np.ndarray:
        """Evaluates baseline + sum of all individual peaks."""
        y = self.baseline_offset + self.baseline_slope * x
        for p in self.peaks:
            y = y + p.evaluate(x)
        return y

    def evaluate_baseline(self, x: np.ndarray) -> np.ndarray:
        return self.baseline_offset + self.baseline_slope * x

    def summary_table(self) -> List[Dict[str, Any]]:
        rows = []
        for idx, p in enumerate(self.peaks):
            rows.append({
                "Peak_Index": idx + 1,
                "Type": p.peak_type.capitalize(),
                "Center": p.center,
                "Amplitude": p.amplitude,
                "FWHM": p.fwhm,
                "Integrated_Area": p.area,
                "Area_Percent": f"{p.relative_area_pct:.2f}%"
            })
        return rows


def fit_multi_peaks(
    x: Union[List[float], np.ndarray],
    y: Union[List[float], np.ndarray],
    initial_peaks: List[PeakItem],
    fit_baseline: bool = True
) -> MultiPeakFitResult:
    """
    Fits a composite multi-peak model with baseline to experimental data.

    Parameters:
        x: 1D array of x coordinates.
        y: 1D array of y coordinates.
        initial_peaks: List of PeakItem objects with initial guess centers and widths.
        fit_baseline: If True, includes offset and linear slope in parameter optimization.

    Returns:
        MultiPeakFitResult with individual deconvolved peaks and goodness of fit metrics.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    valid = np.isfinite(x_arr) & np.isfinite(y_arr)
    xs = x_arr[valid]
    ys = y_arr[valid]

    num_peaks = len(initial_peaks)
    if num_peaks == 0 or len(xs) < 3 * num_peaks:
        raise ValueError("At least 1 peak and sufficient data points are required.")

    # Flatten initial parameters: [c_base, m_base, amp1, center1, width1, amp2, center2, width2, ...]
    p0 = []
    bounds_lower = []
    bounds_upper = []

    # Baseline guesses
    base_offset = float(np.min(ys))
    base_slope = 0.0
    p0.extend([base_offset, base_slope])
    bounds_lower.extend([-np.inf, -np.inf] if fit_baseline else [base_offset - 1e-6, -1e-6])
    bounds_upper.extend([np.inf, np.inf] if fit_baseline else [base_offset + 1e-6, 1e-6])

    x_span = max(1e-6, float(np.max(xs) - np.min(xs)))

    for p in initial_peaks:
        p0.extend([p.amplitude, p.center, p.width])
        # Amplitudes > 0, Centers bounded by data range, Widths > 0
        bounds_lower.extend([0.0, float(np.min(xs)) - x_span * 0.1, 1e-6])
        bounds_upper.extend([np.inf, float(np.max(xs)) + x_span * 0.1, x_span])

    peak_types = [p.peak_type for p in initial_peaks]

    def composite_model(x_eval, *params):
        offset, slope = params[0], params[1]
        y_val = offset + slope * x_eval
        for i in range(num_peaks):
            amp = params[2 + 3 * i]
            cen = params[3 + 3 * i]
            wid = params[4 + 3 * i]
            ptype = peak_types[i]
            if ptype == "gaussian":
                y_val = y_val + peak_gaussian(x_eval, amp, cen, wid / 2.35482)
            elif ptype == "lorentzian":
                y_val = y_val + peak_lorentzian(x_eval, amp, cen, wid / 2.0)
            elif ptype in ("voigt", "pseudo_voigt"):
                y_val = y_val + peak_pseudo_voigt(x_eval, amp, cen, wid)
            else:
                y_val = y_val + peak_gaussian(x_eval, amp, cen, wid)
        return y_val

    try:
        popt, _ = opt.curve_fit(
            composite_model, xs, ys,
            p0=p0,
            bounds=(bounds_lower, bounds_upper),
            maxfev=30000
        )
        success = True
        msg = "Deconvolution converged."
    except Exception as e:
        popt = np.array(p0)
        success = False
        msg = f"Deconvolution warning: {str(e)}"

    fitted_offset, fitted_slope = popt[0], popt[1]
    fitted_peaks: List[PeakItem] = []
    total_area = 0.0

    for i in range(num_peaks):
        amp = float(popt[2 + 3 * i])
        cen = float(popt[3 + 3 * i])
        wid = float(popt[4 + 3 * i])
        ptype = peak_types[i]

        pk = PeakItem(peak_type=ptype, center=cen, amplitude=amp, width=wid)
        pk.fwhm = wid

        # Analytical area formulas
        if ptype == "gaussian":
            sigma = wid / 2.35482
            pk.area = float(amp * sigma * np.sqrt(2 * np.pi))
        elif ptype == "lorentzian":
            gamma = wid / 2.0
            pk.area = float(amp * np.pi * gamma)
        else: # Pseudo-voigt
            pk.area = float(0.5 * amp * (wid / 2.0) * np.pi + 0.5 * amp * (wid / 2.35482) * np.sqrt(2 * np.pi))

        total_area += pk.area
        fitted_peaks.append(pk)

    for pk in fitted_peaks:
        pk.relative_area_pct = (pk.area / total_area * 100.0) if total_area > 0 else 0.0

    # R2 and RMSE metrics
    y_pred = composite_model(xs, *popt)
    ss_res = np.sum((ys - y_pred) ** 2)
    ss_tot = np.sum((ys - np.mean(ys)) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-15 else 1.0
    rmse = np.sqrt(np.mean((ys - y_pred) ** 2))

    return MultiPeakFitResult(
        peaks=fitted_peaks,
        baseline_offset=float(fitted_offset),
        baseline_slope=float(fitted_slope),
        r_squared=float(r2),
        rmse=float(rmse),
        success=success,
        message=msg
    )
