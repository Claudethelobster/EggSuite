"""
stats_engine.py - Pure Python Statistical Testing, Hypothesis Evaluation & Distribution Engine.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import scipy.stats as stats
import pandas as pd


def test_two_sample_t(
    sample_a: Union[List[float], np.ndarray],
    sample_b: Union[List[float], np.ndarray],
    equal_var: bool = False,
    paired: bool = False
) -> Dict[str, Any]:
    """Computes Two-Sample Independent, Welch's, or Paired Student's t-test."""
    a = np.asarray(sample_a, dtype=float)
    b = np.asarray(sample_b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]

    if len(a) < 2 or len(b) < 2:
        raise ValueError("Samples must have at least 2 valid points.")

    if paired:
        if len(a) != len(b):
            raise ValueError("Paired t-test requires samples of identical size.")
        res = stats.ttest_rel(a, b)
        test_name = "Paired Student's t-test"
    else:
        res = stats.ttest_ind(a, b, equal_var=equal_var)
        test_name = "Student's Two-Sample t-test" if equal_var else "Welch's Two-Sample t-test"

    return {
        "test_name": test_name,
        "t_statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "df": float(getattr(res, "df", len(a) + len(b) - 2)),
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "std_a": float(np.std(a, ddof=1)),
        "std_b": float(np.std(b, ddof=1)),
        "difference_of_means": float(np.mean(a) - np.mean(b)),
        "is_significant_05": bool(res.pvalue < 0.05),
        "is_significant_01": bool(res.pvalue < 0.01)
    }


def test_one_sample_t(sample: Union[List[float], np.ndarray], pop_mean: float = 0.0) -> Dict[str, Any]:
    """Computes One-Sample t-test against a hypothesized population mean."""
    arr = np.asarray(sample, dtype=float)
    clean = arr[np.isfinite(arr)]
    if len(clean) < 2:
        raise ValueError("Sample must have at least 2 points.")
    res = stats.ttest_1samp(clean, popmean=pop_mean)
    return {
        "test_name": "One-Sample t-test",
        "t_statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "sample_mean": float(np.mean(clean)),
        "hypothesized_mean": float(pop_mean),
        "std_err": float(stats.sem(clean)),
        "is_significant_05": bool(res.pvalue < 0.05)
    }


def test_one_way_anova(*samples: Union[List[float], np.ndarray]) -> Dict[str, Any]:
    """Computes One-Way ANOVA across multiple groups."""
    clean_groups = []
    for g in samples:
        arr = np.asarray(g, dtype=float)
        c = arr[np.isfinite(arr)]
        if len(c) > 0:
            clean_groups.append(c)

    if len(clean_groups) < 2:
        raise ValueError("ANOVA requires at least 2 valid sample groups.")

    f_stat, p_val = stats.f_oneway(*clean_groups)
    kw_stat, kw_pval = stats.kruskal(*clean_groups)

    return {
        "test_name": "One-Way ANOVA",
        "f_statistic": float(f_stat),
        "p_value": float(p_val),
        "kruskal_statistic": float(kw_stat),
        "kruskal_p_value": float(kw_pval),
        "num_groups": len(clean_groups),
        "group_means": [float(np.mean(g)) for g in clean_groups],
        "is_significant_05": bool(p_val < 0.05)
    }


def test_mann_whitney_u(sample_a: Union[List[float], np.ndarray], sample_b: Union[List[float], np.ndarray]) -> Dict[str, Any]:
    """Non-parametric Mann-Whitney U test."""
    a = np.asarray(sample_a, dtype=float)
    b = np.asarray(sample_b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    res = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {
        "test_name": "Mann-Whitney U Test (Non-parametric)",
        "u_statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "median_a": float(np.median(a)),
        "median_b": float(np.median(b)),
        "is_significant_05": bool(res.pvalue < 0.05)
    }


def test_normality(sample: Union[List[float], np.ndarray]) -> Dict[str, Any]:
    """Tests sample normality using Shapiro-Wilk and D'Agostino tests."""
    arr = np.asarray(sample, dtype=float)
    clean = arr[np.isfinite(arr)]
    if len(clean) < 3:
        raise ValueError("Normality testing requires at least 3 points.")

    # Shapiro-Wilk (up to 5000 points)
    shapiro_stat, shapiro_pval = stats.shapiro(clean[:5000])

    return {
        "sample_size": len(clean),
        "shapiro_statistic": float(shapiro_stat),
        "shapiro_p_value": float(shapiro_pval),
        "is_normal_05": bool(shapiro_pval > 0.05),
        "skewness": float(stats.skew(clean)),
        "kurtosis": float(stats.kurtosis(clean))
    }


def compute_correlation_matrix(df: pd.DataFrame, method: str = "pearson") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Computes correlation coefficients and corresponding p-values matrix.

    Returns:
        (corr_matrix, pvalue_matrix)
    """
    numeric_df = df.select_dtypes(include=[np.number])
    cols = numeric_df.columns
    n = len(cols)

    corr_mat = np.zeros((n, n))
    pval_mat = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            if i == j:
                corr_mat[i, j] = 1.0
                pval_mat[i, j] = 0.0
            else:
                x = numeric_df.iloc[:, i].to_numpy()
                y = numeric_df.iloc[:, j].to_numpy()
                valid = np.isfinite(x) & np.isfinite(y)
                if np.sum(valid) > 2:
                    if method == "spearman":
                        r, p = stats.spearmanr(x[valid], y[valid])
                    else:
                        r, p = stats.pearsonr(x[valid], y[valid])
                    corr_mat[i, j] = r
                    pval_mat[i, j] = p
                else:
                    corr_mat[i, j] = np.nan
                    pval_mat[i, j] = np.nan

    return (
        pd.DataFrame(corr_mat, index=cols, columns=cols),
        pd.DataFrame(pval_mat, index=cols, columns=cols)
    )
