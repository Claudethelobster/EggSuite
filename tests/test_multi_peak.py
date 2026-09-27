"""
Unit tests for EggSuite Multi-Peak Deconvolution Engine.
"""

import unittest
import numpy as np

from egg_suite.core.multi_peak_engine import PeakItem, fit_multi_peaks, MultiPeakFitResult


class TestMultiPeakEngine(unittest.TestCase):
    def setUp(self):
        self.x = np.linspace(0, 20, 300)
        # Construct true overlapping doublet: Peak 1 at x=7, Peak 2 at x=12
        p1 = 5.0 * np.exp(-((self.x - 7.0) ** 2) / (2 * (1.2 ** 2)))
        p2 = 3.5 * np.exp(-((self.x - 12.0) ** 2) / (2 * (1.0 ** 2)))
        self.baseline = 1.0 + 0.05 * self.x
        self.y = self.baseline + p1 + p2

    def test_multi_gaussian_fit(self):
        initial_guesses = [
            PeakItem(peak_type="gaussian", center=6.5, amplitude=4.0, width=2.5),
            PeakItem(peak_type="gaussian", center=12.5, amplitude=3.0, width=2.0)
        ]

        result = fit_multi_peaks(self.x, self.y, initial_guesses, fit_baseline=True)

        self.assertTrue(result.success)
        self.assertGreater(result.r_squared, 0.99)
        self.assertEqual(len(result.peaks), 2)

        # Centers should be close to 7.0 and 12.0
        self.assertAlmostEqual(result.peaks[0].center, 7.0, delta=0.2)
        self.assertAlmostEqual(result.peaks[1].center, 12.0, delta=0.2)

        # Amplitudes should be close to 5.0 and 3.5
        self.assertAlmostEqual(result.peaks[0].amplitude, 5.0, delta=0.3)
        self.assertAlmostEqual(result.peaks[1].amplitude, 3.5, delta=0.3)

        # Check summary table structure
        summary = result.summary_table()
        self.assertEqual(len(summary), 2)
        self.assertIn("Integrated_Area", summary[0])

    def test_composite_evaluation(self):
        peaks = [
            PeakItem(peak_type="gaussian", center=5.0, amplitude=2.0, width=1.5),
            PeakItem(peak_type="lorentzian", center=10.0, amplitude=3.0, width=1.0)
        ]
        result = MultiPeakFitResult(
            peaks=peaks,
            baseline_offset=0.5,
            baseline_slope=0.0,
            r_squared=0.99,
            rmse=0.01
        )

        x_eval = np.array([5.0, 10.0])
        y_eval = result.evaluate_composite(x_eval)
        self.assertEqual(len(y_eval), 2)
        self.assertGreater(y_eval[0], 2.0) # Baseline + Peak 1


if __name__ == "__main__":
    unittest.main()
