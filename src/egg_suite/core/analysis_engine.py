"""
analysis_engine.py - Pure Python / NumPy / SciPy Mathematical and Analysis Engine for EggSuite.
This module is independent of GUI frameworks and can be used in headless scripts, notebooks,
and within the EggSuite plugin API.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
import scipy.optimize as opt
import scipy.signal as sig
import scipy.integrate as intg


# ==============================================================================
# 1. CURVE FITTING FUNCTIONS & MODELS
# ==============================================================================

def model_polynomial(x: np.ndarray, *coeffs: float) -> np.ndarray:
    """Evaluates polynomial with coefficients [c0, c1, c2, ...]: y = sum(ci * x^i)."""
    val = np.zeros_like(x, dtype=float)
    for power, c in enumerate(coeffs):
        val = val + c * (x ** power)
    return val

def model_gaussian(x: np.ndarray, amplitude: float, center: float, sigma: float, offset: float = 0.0) -> np.ndarray:
    """Gaussian curve: y = amplitude * exp(-((x - center)^2) / (2 * sigma^2)) + offset."""
    sigma = max(1e-15, abs(sigma))
    return amplitude * np.exp(-((x - center) ** 2) / (2 * (sigma ** 2))) + offset

def model_lorentzian(x: np.ndarray, amplitude: float, center: float, gamma: float, offset: float = 0.0) -> np.ndarray:
    """Lorentzian / Cauchy curve: y = amplitude * (gamma^2 / ((x - center)^2 + gamma^2)) + offset."""
    gamma = max(1e-15, abs(gamma))
    return amplitude * (gamma ** 2) / ((x - center) ** 2 + gamma ** 2) + offset

def model_exponential(x: np.ndarray, a: float, b: float, c: float = 0.0) -> np.ndarray:
    """Exponential curve: y = a * exp(b * x) + c."""
    # Clip exponent argument to prevent overflow
    arg = np.clip(b * x, -100, 100)
    return a * np.exp(arg) + c

def model_logarithmic(x: np.ndarray, a: float, b: float, c: float = 0.0) -> np.ndarray:
    """Logarithmic curve: y = a * ln(b * x) + c."""
    safe_x = np.where(b * x > 1e-15, b * x, 1e-15)
    return a * np.log(safe_x) + c

def model_sine(x: np.ndarray, amplitude: float, frequency: float, phase: float = 0.0, offset: float = 0.0) -> np.ndarray:
    """Sine wave: y = amplitude * sin(2 * pi * frequency * x + phase) + offset."""
    return amplitude * np.sin(2 * np.pi * frequency * x + phase) + offset

def model_power_law(x: np.ndarray, a: float, power: float, c: float = 0.0) -> np.ndarray:
    """Power law curve: y = a * (x ^ power) + c."""
    safe_x = np.where(x > 0, x, 1e-15)
    return a * (safe_x ** power) + c


class FitResult:
    """Container for curve fitting results with metrics and evaluation helpers."""
    def __init__(
        self,
        model_name: str,
        parameters: Dict[str, float],
        parameter_errors: Dict[str, float],
        r_squared: float,
        rmse: float,
        model_func: Callable,
        param_values: np.ndarray,
        pcov: Optional[np.ndarray] = None,
        success: bool = True,
        message: str = "Optimization converged successfully."
    ):
        self.model_name = model_name
        self.parameters = parameters
        self.parameter_errors = parameter_errors
        self.r_squared = r_squared
        self.rmse = rmse
        self.model_func = model_func
        self._param_values = param_values
        self.covariance = pcov
        self.success = success
        self.message = message

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        """Evaluates the fitted model at given x coordinates."""
        return self.model_func(x, *self._param_values)

    def summary(self) -> str:
        """Returns a formatted summary of fit parameters and quality metrics."""
        lines = [
            f"=== Fit Result: {self.model_name.capitalize()} ===",
            f"Status: {'Success' if self.success else 'Failed'} ({self.message})",
            f"R²: {self.r_squared:.6f}",
            f"RMSE: {self.rmse:.6g}",
            "Parameters:"
        ]
        for name, val in self.parameters.items():
            err = self.parameter_errors.get(name, 0.0)
            lines.append(f"  - {name}: {val:.6g} ± {err:.6g}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<FitResult model='{self.model_name}' r2={self.r_squared:.4f}>"


def fit_curve(
    x: Union[List[float], np.ndarray],
    y: Union[List[float], np.ndarray],
    model: str = "polynomial",
    degree: int = 1,
    p0: Optional[Union[List[float], Dict[str, float], np.ndarray]] = None,
    sigma: Optional[Union[List[float], np.ndarray]] = None,
    custom_func: Optional[Callable] = None,
    custom_param_names: Optional[List[str]] = None,
    max_evals: int = 20000
) -> FitResult:
    """
    Fits a mathematical model to data points (x, y).

    Parameters:
        x: Array-like 1D x-coordinates.
        y: Array-like 1D y-coordinates.
        model: Model name: 'polynomial', 'gaussian', 'lorentzian', 'exponential', 
               'logarithmic', 'sine', 'power_law', or 'custom'.
        degree: Degree for polynomial fitting (default: 1 for linear fit).
        p0: Optional initial parameter guesses.
        sigma: Optional 1D array of uncertainty/errors in y for weighted fitting.
        custom_func: Callable f(x, *params) if model='custom'.
        custom_param_names: Names for custom function parameters.
        max_evals: Maximum number of function evaluations for non-linear solver.

    Returns:
        FitResult containing fitted parameters, errors, R², RMSE, and evaluate method.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    # Filter out NaNs / Infs
    valid_mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    if sigma is not None:
        sigma_arr = np.asarray(sigma, dtype=float)
        valid_mask = valid_mask & np.isfinite(sigma_arr) & (sigma_arr > 0)
        sigma_clean = sigma_arr[valid_mask]
    else:
        sigma_clean = None

    x_clean = x_arr[valid_mask]
    y_clean = y_arr[valid_mask]

    if len(x_clean) < 2:
        raise ValueError("At least 2 valid finite data points are required for fitting.")

    model_lower = model.strip().lower()

    if model_lower == "polynomial" or model_lower == "linear":
        poly_deg = max(1, degree)
        if poly_deg == 1 and model_lower == "linear":
            poly_deg = 1

        # Analytical polynomial fit using numpy
        if sigma_clean is not None:
            weights = 1.0 / sigma_clean
            coeffs, cov = np.polyfit(x_clean, y_clean, poly_deg, w=weights, cov=True)
        else:
            coeffs, cov = np.polyfit(x_clean, y_clean, poly_deg, cov=True)

        # np.polyfit returns highest power first; reverse to match c0 + c1*x + ...
        rev_coeffs = coeffs[::-1]
        param_names = [f"c{i}" for i in range(len(rev_coeffs))]
        param_errors = np.sqrt(np.diag(cov))[::-1] if cov is not None else np.zeros_like(rev_coeffs)

        param_dict = {name: float(val) for name, val in zip(param_names, rev_coeffs)}
        error_dict = {name: float(err) for name, err in zip(param_names, param_errors)}

        y_pred = model_polynomial(x_clean, *rev_coeffs)
        ss_res = np.sum((y_clean - y_pred) ** 2)
        ss_tot = np.sum((y_clean - np.mean(y_clean)) ** 2)
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-15 else 1.0
        rmse = np.sqrt(np.mean((y_clean - y_pred) ** 2))

        return FitResult(
            model_name=f"polynomial_deg_{poly_deg}",
            parameters=param_dict,
            parameter_errors=error_dict,
            r_squared=float(r2),
            rmse=float(rmse),
            model_func=model_polynomial,
            param_values=rev_coeffs,
            pcov=cov,
            success=True
        )

    # Select non-linear function and default guesses
    if model_lower == "gaussian":
        func = model_gaussian
        param_names = ["amplitude", "center", "sigma", "offset"]
        if p0 is None:
            amp_guess = float(np.max(y_clean) - np.min(y_clean))
            center_guess = float(x_clean[np.argmax(y_clean)])
            sigma_guess = max(1e-6, float(np.std(x_clean) / 2.0))
            offset_guess = float(np.min(y_clean))
            init_guess = [amp_guess, center_guess, sigma_guess, offset_guess]
        else:
            init_guess = list(p0.values()) if isinstance(p0, dict) else list(p0)

    elif model_lower == "lorentzian":
        func = model_lorentzian
        param_names = ["amplitude", "center", "gamma", "offset"]
        if p0 is None:
            amp_guess = float(np.max(y_clean) - np.min(y_clean))
            center_guess = float(x_clean[np.argmax(y_clean)])
            gamma_guess = max(1e-6, float((np.max(x_clean) - np.min(x_clean)) / 10.0))
            offset_guess = float(np.min(y_clean))
            init_guess = [amp_guess, center_guess, gamma_guess, offset_guess]
        else:
            init_guess = list(p0.values()) if isinstance(p0, dict) else list(p0)

    elif model_lower == "exponential":
        func = model_exponential
        param_names = ["a", "b", "c"]
        if p0 is None:
            init_guess = [float(y_clean[0]), 0.01, float(np.min(y_clean))]
        else:
            init_guess = list(p0.values()) if isinstance(p0, dict) else list(p0)

    elif model_lower == "logarithmic":
        func = model_logarithmic
        param_names = ["a", "b", "c"]
        if p0 is None:
            init_guess = [1.0, 1.0, float(np.mean(y_clean))]
        else:
            init_guess = list(p0.values()) if isinstance(p0, dict) else list(p0)

    elif model_lower == "sine":
        func = model_sine
        param_names = ["amplitude", "frequency", "phase", "offset"]
        if p0 is None:
            amp_guess = float((np.max(y_clean) - np.min(y_clean)) / 2.0)
            offset_guess = float(np.mean(y_clean))
            # Rough FFT frequency estimation
            try:
                dt = float(np.mean(np.diff(x_clean)))
                if dt > 0:
                    fft_vals = np.abs(np.fft.rfft(y_clean - offset_guess))
                    freqs = np.fft.rfftfreq(len(y_clean), d=dt)
                    dominant_idx = np.argmax(fft_vals[1:]) + 1
                    freq_guess = float(freqs[dominant_idx])
                else:
                    freq_guess = 1.0
            except Exception:
                freq_guess = 1.0
            init_guess = [amp_guess, freq_guess, 0.0, offset_guess]
        else:
            init_guess = list(p0.values()) if isinstance(p0, dict) else list(p0)

    elif model_lower == "power_law":
        func = model_power_law
        param_names = ["a", "power", "c"]
        if p0 is None:
            init_guess = [1.0, 1.0, 0.0]
        else:
            init_guess = list(p0.values()) if isinstance(p0, dict) else list(p0)

    elif model_lower == "custom":
        if custom_func is None:
            raise ValueError("custom_func must be provided when model='custom'.")
        func = custom_func
        param_names = custom_param_names or [f"p{i}" for i in range(len(p0) if p0 is not None else 2)]
        if p0 is None:
            init_guess = [1.0] * len(param_names)
        else:
            init_guess = list(p0.values()) if isinstance(p0, dict) else list(p0)
    else:
        raise ValueError(f"Unknown fitting model: '{model}'. Supported: polynomial, gaussian, lorentzian, exponential, logarithmic, sine, power_law, custom.")

    try:
        if sigma_clean is not None:
            popt, pcov = opt.curve_fit(
                func, x_clean, y_clean,
                p0=init_guess, sigma=sigma_clean, absolute_sigma=True,
                maxfev=max_evals
            )
        else:
            popt, pcov = opt.curve_fit(
                func, x_clean, y_clean,
                p0=init_guess,
                maxfev=max_evals
            )
        success = True
        msg = "Converged successfully."
        errors = np.sqrt(np.diag(pcov)) if pcov is not None else np.zeros_like(popt)
    except Exception as e:
        success = False
        msg = f"Fitting failed: {str(e)}"
        popt = np.array(init_guess, dtype=float)
        errors = np.zeros_like(popt)
        pcov = None

    param_dict = {name: float(val) for name, val in zip(param_names, popt)}
    error_dict = {name: float(err) for name, err in zip(param_names, errors)}

    y_pred = func(x_clean, *popt)
    ss_res = np.sum((y_clean - y_pred) ** 2)
    ss_tot = np.sum((y_clean - np.mean(y_clean)) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-15 else 1.0
    rmse = np.sqrt(np.mean((y_clean - y_pred) ** 2))

    return FitResult(
        model_name=model_lower,
        parameters=param_dict,
        parameter_errors=error_dict,
        r_squared=float(r2),
        rmse=float(rmse),
        model_func=func,
        param_values=popt,
        pcov=pcov,
        success=success,
        message=msg
    )


# ==============================================================================
# 2. SIGNAL PROCESSING, PEAKS & INTEGRATION
# ==============================================================================

def find_peaks(
    y: Union[List[float], np.ndarray],
    x: Optional[Union[List[float], np.ndarray]] = None,
    height: Optional[float] = None,
    threshold: Optional[float] = None,
    distance: Optional[int] = None,
    prominence: Optional[float] = None,
    width: Optional[float] = None
) -> Dict[str, np.ndarray]:
    """
    Finds peaks in 1D signal with optional property filtering.

    Returns dictionary with:
      - 'indices': integer indices of peaks
      - 'x': x-coordinates of peaks (if x provided)
      - 'y': y-values of peaks
      - 'prominences': peak prominences (if calculated)
      - 'widths': peak widths (if calculated)
    """
    y_arr = np.asarray(y, dtype=float)
    peaks, properties = sig.find_peaks(
        y_arr, height=height, threshold=threshold,
        distance=distance, prominence=prominence, width=width
    )
    result = {
        "indices": peaks,
        "y": y_arr[peaks]
    }
    if x is not None:
        x_arr = np.asarray(x, dtype=float)
        result["x"] = x_arr[peaks]
    for k, v in properties.items():
        result[k] = v
    return result


def compute_fft(
    y: Union[List[float], np.ndarray],
    sample_spacing: float = 1.0,
    window: Optional[str] = "hann",
    one_sided: bool = True
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes Fast Fourier Transform (FFT) frequencies and magnitude spectrum.

    Parameters:
        y: Signal array.
        sample_spacing: Time/spatial difference between consecutive samples (dt).
        window: Windowing function ('hann', 'hamming', 'blackman', or None).
        one_sided: If True, returns only positive frequencies (rfft).

    Returns:
        (frequencies, magnitudes)
    """
    y_arr = np.asarray(y, dtype=float)
    n = len(y_arr)
    if n == 0:
        return np.array([]), np.array([])

    # Apply window
    if window:
        win = sig.get_window(window, n)
        y_win = (y_arr - np.mean(y_arr)) * win
    else:
        y_win = y_arr - np.mean(y_arr)

    if one_sided:
        freqs = np.fft.rfftfreq(n, d=sample_spacing)
        fft_vals = np.fft.rfft(y_win)
        magnitudes = (2.0 / n) * np.abs(fft_vals)
    else:
        freqs = np.fft.fftfreq(n, d=sample_spacing)
        fft_vals = np.fft.fft(y_win)
        magnitudes = (1.0 / n) * np.abs(fft_vals)

    return freqs, magnitudes


def smooth_data(
    y: Union[List[float], np.ndarray],
    method: str = "savgol",
    window_length: int = 11,
    polyorder: int = 3
) -> np.ndarray:
    """
    Smooths noisy 1D data using Savitzky-Golay filter or Moving Average.

    Parameters:
        y: Input signal.
        method: 'savgol' (Savitzky-Golay) or 'moving_average' (Boxcar convolution).
        window_length: Size of smoothing window (odd integer).
        polyorder: Polynomial order for savgol filter (must be < window_length).
    """
    y_arr = np.asarray(y, dtype=float)
    if len(y_arr) < 3:
        return y_arr.copy()

    # Ensure odd window length
    w_len = max(3, window_length)
    if w_len % 2 == 0:
        w_len += 1
    w_len = min(w_len, len(y_arr) if len(y_arr) % 2 != 0 else len(y_arr) - 1)

    if method.lower() == "savgol":
        order = min(polyorder, w_len - 1)
        return sig.savgol_filter(y_arr, window_length=w_len, polyorder=order)
    elif method.lower() in ("moving_average", "boxcar"):
        box = np.ones(w_len) / w_len
        return np.convolve(y_arr, box, mode="same")
    else:
        raise ValueError(f"Unknown smoothing method: {method}. Use 'savgol' or 'moving_average'.")


def integrate_area(
    x: Union[List[float], np.ndarray],
    y: Union[List[float], np.ndarray],
    baseline_method: str = "endpoints",
    custom_baseline_y: float = 0.0
) -> Dict[str, float]:
    """
    Calculates Area Under Curve with baseline subtraction.

    Parameters:
        x: 1D array of x-coordinates (must be monotonically sorted).
        y: 1D array of y-coordinates.
        baseline_method: 'endpoints' (linear slant between first & last point),
                         'min' (flat line at min y in range),
                         'zero' (y=0),
                         'custom' (flat line at custom_baseline_y).

    Returns:
        Dictionary with:
          - 'net_area': Area bounded between curve and baseline.
          - 'total_area': Raw integral without baseline subtraction.
          - 'baseline_area': Area of the baseline alone.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    if len(x_arr) < 2:
        return {"net_area": 0.0, "total_area": 0.0, "baseline_area": 0.0}

    # Ensure sorted by x
    sort_idx = np.argsort(x_arr)
    xs = x_arr[sort_idx]
    ys = y_arr[sort_idx]

    # Calculate baseline curve y_base
    if baseline_method == "endpoints":
        x0, x1 = xs[0], xs[-1]
        y0, y1 = ys[0], ys[-1]
        slope = (y1 - y0) / (x1 - x0) if (x1 - x0) != 0 else 0.0
        y_base = y0 + slope * (xs - x0)
    elif baseline_method == "min":
        y_base = np.full_like(ys, np.min(ys))
    elif baseline_method == "zero":
        y_base = np.zeros_like(ys)
    elif baseline_method == "custom":
        y_base = np.full_like(ys, custom_baseline_y)
    else:
        raise ValueError(f"Unknown baseline method: {baseline_method}")

    # Trapezoidal integration
    total_area = float(intg.trapezoid(ys, xs))
    base_area = float(intg.trapezoid(y_base, xs))
    net_area = float(intg.trapezoid(ys - y_base, xs))

    return {
        "net_area": net_area,
        "total_area": total_area,
        "baseline_area": base_area
    }


# ==============================================================================
# 3. STATISTICAL SUMMARIES
# ==============================================================================

def compute_statistics(data: Union[List[float], np.ndarray]) -> Dict[str, float]:
    """Computes comprehensive descriptive statistics on 1D numerical data."""
    arr = np.asarray(data, dtype=float)
    clean = arr[np.isfinite(arr)]
    if len(clean) == 0:
        return {
            "count": 0, "mean": np.nan, "std": np.nan, "var": np.nan,
            "min": np.nan, "q25": np.nan, "median": np.nan, "q75": np.nan,
            "max": np.nan, "skewness": np.nan, "kurtosis": np.nan
        }

    from scipy import stats
    return {
        "count": int(len(clean)),
        "mean": float(np.mean(clean)),
        "std": float(np.std(clean, ddof=1)) if len(clean) > 1 else 0.0,
        "var": float(np.var(clean, ddof=1)) if len(clean) > 1 else 0.0,
        "min": float(np.min(clean)),
        "q25": float(np.percentile(clean, 25)),
        "median": float(np.median(clean)),
        "q75": float(np.percentile(clean, 75)),
        "max": float(np.max(clean)),
        "skewness": float(stats.skew(clean)) if len(clean) > 2 else 0.0,
        "kurtosis": float(stats.kurtosis(clean)) if len(clean) > 3 else 0.0
    }
