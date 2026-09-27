"""
Unit tests for EggSuite Statistical Testing and Distribution Engine.
"""

import unittest
import numpy as np
import pandas as pd

from egg_suite.core.stats_engine import (
    test_two_sample_t, test_one_sample_t, test_one_way_anova,
    test_mann_whitney_u, test_normality, compute_correlation_matrix
)


class TestStatsEngine(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        self.group_a = np.random.normal(loc=10.0, scale=2.0, size=50)
        self.group_b = np.random.normal(loc=15.0, scale=2.0, size=50)

    def test_two_sample_t_test(self):
        res = test_two_sample_t(self.group_a, self.group_b, equal_var=True)
        self.assertTrue(res["is_significant_05"])
        self.assertTrue(res["is_significant_01"])
        self.assertLess(res["p_value"], 0.001)
        self.assertAlmostEqual(res["mean_a"], 10.0, delta=1.0)
        self.assertAlmostEqual(res["mean_b"], 15.0, delta=1.0)

    def test_one_way_anova(self):
        group_c = np.random.normal(loc=20.0, scale=2.0, size=50)
        res = test_one_way_anova(self.group_a, self.group_b, group_c)
        self.assertEqual(res["num_groups"], 3)
        self.assertTrue(res["is_significant_05"])
        self.assertLess(res["p_value"], 0.001)

    def test_mann_whitney_u(self):
        res = test_mann_whitney_u(self.group_a, self.group_b)
        self.assertTrue(res["is_significant_05"])
        self.assertLess(res["p_value"], 0.001)

    def test_normality(self):
        normal_data = np.random.normal(loc=0, scale=1, size=100)
        res = test_normality(normal_data)
        self.assertTrue(res["is_normal_05"])
        self.assertGreater(res["shapiro_p_value"], 0.05)

    def test_correlation_matrix(self):
        x = np.linspace(0, 10, 50)
        y = 2.0 * x + np.random.normal(0, 0.1, 50)
        z = -1.5 * x + np.random.normal(0, 0.1, 50)
        df = pd.DataFrame({"X": x, "Y": y, "Z": z})

        corr_mat, pval_mat = compute_correlation_matrix(df, method="pearson")
        self.assertEqual(corr_mat.shape, (3, 3))
        self.assertAlmostEqual(corr_mat.loc["X", "Y"], 1.0, delta=0.05)
        self.assertAlmostEqual(corr_mat.loc["X", "Z"], -1.0, delta=0.05)
        self.assertLess(pval_mat.loc["X", "Y"], 0.001)


if __name__ == "__main__":
    unittest.main()
