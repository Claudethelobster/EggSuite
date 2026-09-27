"""
Unit tests for EggSuite Batch Processing and Recipe Engine.
"""

import os
import shutil
import tempfile
import unittest
import numpy as np
import pandas as pd

from egg_suite.core.batch_processor import BatchRecipe, execute_batch_pipeline, BatchResult


class TestBatchProcessor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.out_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.out_dir, exist_ok=True)

        # Create 3 synthetic CSV files
        self.x = np.linspace(0, 10, 100)
        for i in range(3):
            # Baseline + Gaussian peak
            y = 1.5 + (i + 1) * 3.0 * np.exp(-((self.x - (4.0 + i)) ** 2) / (2 * (0.8 ** 2)))
            df = pd.DataFrame({"Time_s": self.x, "Signal_mV": y})
            df.to_csv(os.path.join(self.temp_dir, f"sample_{i+1}.csv"), index=False)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recipe_serialization(self):
        recipe = BatchRecipe("Test Pipeline")
        recipe.add_step("smooth", {"method": "savgol", "window_length": 11})
        recipe.add_step("fit_curve", {"model": "gaussian"})
        
        json_str = recipe.to_json()
        loaded = BatchRecipe.from_json(json_str)
        
        self.assertEqual(loaded.name, "Test Pipeline")
        self.assertEqual(len(loaded.steps), 2)
        self.assertEqual(loaded.steps[0]["type"], "smooth")

    def test_batch_execution(self):
        recipe = BatchRecipe("Full Run")
        recipe.add_step("baseline_subtract", {"method": "endpoints"})
        recipe.add_step("fit_curve", {"model": "gaussian"})
        recipe.add_step("statistics", {})

        result = execute_batch_pipeline(
            input_folder=self.temp_dir,
            file_pattern="sample_*.csv",
            recipe=recipe,
            output_folder=self.out_dir,
            x_col=0,
            y_col=1
        )

        self.assertEqual(result.total_files, 3)
        self.assertEqual(result.processed_count, 3)
        self.assertEqual(result.failed_count, 0)

        df = result.to_dataframe()
        self.assertEqual(len(df), 3)
        self.assertIn("Fit_R2", df.columns)
        self.assertIn("Mean_Y", df.columns)

        # Check export
        summary_csv = os.path.join(self.out_dir, "summary.csv")
        result.export_summary_csv(summary_csv)
        self.assertTrue(os.path.exists(summary_csv))


if __name__ == "__main__":
    unittest.main()
