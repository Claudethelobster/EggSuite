"""
Unit test suite for EggSuite Analysis Engine and EggSuiteAPI.
"""

import unittest
import numpy as np
import pandas as pd

from egg_suite.core.analysis_engine import (
    fit_curve, find_peaks, compute_fft, smooth_data, integrate_area, compute_statistics
)
from egg_suite.core.workspace import GlobalWorkspace
from egg_suite.core.plugin_manager import EggSuiteAPI, PluginManager


class DummyTheme:
    bg = "#1e1e1e"
    fg = "#d4d4d4"
    panel_bg = "#252526"
    border = "#3e3e42"
    primary_bg = "#007acc"
    primary_text = "#ffffff"
    primary_border = "#0098ff"


class DummyHub:
    def __init__(self):
        self.toasts = []
        self.settings_store = {}

    def show_toast(self, title, message="", is_error=False):
        self.toasts.append((title, message, is_error))

    class SettingsProxy:
        def __init__(self, store):
            self.store = store

        def value(self, key, default=None):
            return self.store.get(key, default)

        def setValue(self, key, value):
            self.store[key] = value

    @property
    def settings(self):
        return DummyHub.SettingsProxy(self.settings_store)


class TestAnalysisEngine(unittest.TestCase):
    def test_polynomial_fit(self):
        x = np.linspace(-10, 10, 100)
        y = 3.0 + 2.0 * x - 0.5 * (x ** 2)
        res = fit_curve(x, y, model="polynomial", degree=2)
        self.assertTrue(res.success)
        self.assertAlmostEqual(res.r_squared, 1.0, places=4)
        self.assertAlmostEqual(res.parameters["c0"], 3.0, places=3)
        self.assertAlmostEqual(res.parameters["c1"], 2.0, places=3)
        self.assertAlmostEqual(res.parameters["c2"], -0.5, places=3)

    def test_gaussian_fit(self):
        x = np.linspace(-5, 5, 200)
        y = 10.0 * np.exp(-((x - 1.0) ** 2) / (2 * (0.8 ** 2))) + 2.0
        res = fit_curve(x, y, model="gaussian")
        self.assertTrue(res.success)
        self.assertAlmostEqual(res.r_squared, 1.0, places=3)
        self.assertAlmostEqual(res.parameters["amplitude"], 10.0, places=2)
        self.assertAlmostEqual(res.parameters["center"], 1.0, places=2)
        self.assertAlmostEqual(res.parameters["sigma"], 0.8, places=2)
        self.assertAlmostEqual(res.parameters["offset"], 2.0, places=2)

    def test_exponential_fit(self):
        x = np.linspace(0, 3, 100)
        y = 2.5 * np.exp(1.2 * x) + 1.0
        res = fit_curve(x, y, model="exponential")
        self.assertTrue(res.success)
        self.assertAlmostEqual(res.r_squared, 1.0, places=3)
        self.assertAlmostEqual(res.parameters["a"], 2.5, places=2)
        self.assertAlmostEqual(res.parameters["b"], 1.2, places=2)

    def test_peaks_and_fft(self):
        x = np.linspace(0, 10, 500)
        y = np.sin(2 * np.pi * 1.5 * x) + 0.5 * np.sin(2 * np.pi * 4.0 * x)
        peaks = find_peaks(y, x=x, height=0.8)
        self.assertTrue(len(peaks["indices"]) > 0)

        freqs, mags = compute_fft(y, sample_spacing=10.0/500)
        self.assertTrue(len(freqs) > 0)
        dominant_freq = freqs[np.argmax(mags[1:]) + 1]
        self.assertAlmostEqual(dominant_freq, 1.5, delta=0.2)

    def test_integration_and_stats(self):
        x = np.linspace(0, 4, 100)
        y = 2.0 * x
        res = integrate_area(x, y, baseline_method="zero")
        # Area of triangle base 4, height 8 = 16
        self.assertAlmostEqual(res["net_area"], 16.0, delta=0.2)

        stats = compute_statistics(y)
        self.assertAlmostEqual(stats["mean"], 4.0, delta=0.1)
        self.assertAlmostEqual(stats["min"], 0.0, places=3)
        self.assertAlmostEqual(stats["max"], 8.0, places=3)


class TestEggSuiteAPI(unittest.TestCase):
    def setUp(self):
        self.workspace = GlobalWorkspace()
        self.theme = DummyTheme()
        self.hub = DummyHub()
        self.api = EggSuiteAPI(self.workspace, self.theme, self.hub, "TestApp")

    def test_dataframe_management(self):
        df_in = pd.DataFrame({
            "Time": [0.0, 1.0, 2.0, 3.0],
            "Voltage": [10.5, 12.3, 14.1, 16.0]
        })
        self.api.add_dataframe("exp1.csv", df_in)

        names = self.api.get_dataset_names()
        self.assertIn("exp1.csv", names)

        cols = self.api.get_column_names("exp1.csv")
        self.assertEqual(cols, ["Time", "Voltage"])

        df_out = self.api.get_dataframe("exp1.csv")
        self.assertIsNotNone(df_out)
        self.assertEqual(list(df_out.columns), ["Time", "Voltage"])
        self.assertEqual(len(df_out), 4)

        col_arr = self.api.get_column_data("exp1.csv", "Voltage")
        np.testing.assert_array_equal(col_arr, [10.5, 12.3, 14.1, 16.0])

    def test_sandbox_settings(self):
        self.api.save_setting("test_key", "test_val")
        val = self.api.load_setting("test_key")
        self.assertEqual(val, "test_val")
        self.assertEqual(self.hub.settings_store["plugins/TestApp/test_key"], "test_val")

    def test_plugin_scanner(self):
        plugins = PluginManager.scan_plugins()
        plugin_names = [p["name"] for p in plugins]
        self.assertIn("Random Walk Simulator", plugin_names)
        self.assertIn("Live Curve Fitter", plugin_names)


if __name__ == "__main__":
    unittest.main()
