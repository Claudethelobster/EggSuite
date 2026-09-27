"""
main.py - Live Curve Fitter Plugin Example
Demonstrates EggSuite's modernized DataFrame API, Analysis Bridge, UI helpers, and Event Hooks.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QComboBox, QPushButton, QLabel, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt


class LiveCurveFitterApp(QMainWindow):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.colours = self.api.get_theme_colours()

        self.setWindowTitle("Live Curve Fitter (Modern API Demo)")
        self.resize(950, 650)
        self.api.ui.apply_theme(self)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Left Control Panel
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        left_panel.addWidget(QLabel("<b>1. Active Dataset:</b>"))
        self.dataset_combo = QComboBox()
        self.dataset_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 6px; background-color: {self.colours['panel_bg']};
                color: {self.colours['fg']}; border: 1px solid {self.colours['border']}; border-radius: 4px;
            }}
        """)
        self._refresh_datasets()
        left_panel.addWidget(self.dataset_combo)

        # Synthetic generator button for quick testing
        self.btn_gen_synth = self.api.ui.create_button("🎲 Generate Test Gaussian", is_primary=False)
        self.btn_gen_synth.clicked.connect(self._generate_synthetic_data)
        left_panel.addWidget(self.btn_gen_synth)

        left_panel.addSpacing(10)
        left_panel.addWidget(QLabel("<b>2. Fitting Model:</b>"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gaussian", "lorentzian", "exponential", "polynomial", "sine"])
        self.model_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 6px; background-color: {self.colours['panel_bg']};
                color: {self.colours['fg']}; border: 1px solid {self.colours['border']}; border-radius: 4px;
            }}
        """)
        left_panel.addWidget(self.model_combo)

        self.btn_fit = self.api.ui.create_button("⚡ Fit Model to Data", is_primary=True)
        self.btn_fit.clicked.connect(self.execute_fit)
        left_panel.addWidget(self.btn_fit)

        left_panel.addSpacing(10)
        left_panel.addWidget(QLabel("<b>3. Fit Summary & Metrics:</b>"))
        self.summary_box = QTextEdit()
        self.summary_box.setReadOnly(True)
        self.summary_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.colours['panel_bg']}; color: {self.colours['fg']};
                border: 1px solid {self.colours['border']}; font-family: Consolas, monospace; font-size: 12px;
            }}
        """)
        left_panel.addWidget(self.summary_box, stretch=1)

        main_layout.addLayout(left_panel, stretch=1)

        # Right Plot Area
        self.plot_widget = self.api.ui.create_plot_widget(title="Data Points & Fitted Curve")
        self.data_scatter = pg.ScatterPlotItem(pen=pg.mkPen(None), brush=pg.mkBrush(200, 200, 200, 180), size=7)
        self.fit_curve_line = pg.PlotCurveItem(pen=pg.mkPen(color=self.colours['primary_bg'], width=2.5))
        self.plot_widget.addItem(self.data_scatter)
        self.plot_widget.addItem(self.fit_curve_line)

        main_layout.addWidget(self.plot_widget, stretch=2)

        # Subscribe to workspace event hooks
        self.api.events.on_dataset_added(self._on_workspace_updated)
        self.api.events.on_dataset_removed(self._on_workspace_updated)

        # Initial check
        if self.dataset_combo.count() == 0:
            self._generate_synthetic_data()

    def _refresh_datasets(self):
        current = self.dataset_combo.currentText()
        self.dataset_combo.clear()
        names = self.api.get_dataset_names()
        self.dataset_combo.addItems(names)
        if current in names:
            self.dataset_combo.setCurrentText(current)

    def _on_workspace_updated(self, filepath):
        self._refresh_datasets()

    def _generate_synthetic_data(self):
        """Generates noisy Gaussian synthetic data using DataFrame API."""
        import pandas as pd
        x = np.linspace(-5, 5, 200)
        true_y = 12.5 * np.exp(-((x - 0.5) ** 2) / (2 * (1.2 ** 2))) + 3.0
        noise = np.random.normal(0, 0.4, size=len(x))
        y = true_y + noise

        df = pd.DataFrame({"X_Position": x, "Signal_Intensity": y})
        dataset_name = "Synthetic_Peak_Sample"
        self.api.add_dataframe(dataset_name, df, notes="Generated synthetic Gaussian peak.")
        self._refresh_datasets()
        self.dataset_combo.setCurrentText(dataset_name)
        self.api.ui.show_notification("Dataset Generated", f"Registered '{dataset_name}' in workspace.")
        self.execute_fit()

    def execute_fit(self):
        target = self.dataset_combo.currentText()
        if not target:
            self.api.ui.show_notification("No Dataset", "Please select or generate a dataset.", is_error=True)
            return

        # Fetch as clean DataFrame
        df = self.api.get_dataframe(target)
        if df is None or len(df.columns) < 2:
            self.api.ui.show_notification("Invalid Dataset", "Dataset must contain at least 2 numerical columns.", is_error=True)
            return

        x = df.iloc[:, 0].to_numpy()
        y = df.iloc[:, 1].to_numpy()
        model_name = self.model_combo.currentText()

        # Execute pure Python fit via analysis engine
        try:
            fit_result = self.api.analysis.fit_curve(x, y, model=model_name)
            self.summary_box.setPlainText(fit_result.summary())

            # Update Plot
            self.data_scatter.setData(x, y)
            x_dense = np.linspace(np.min(x), np.max(x), 400)
            y_dense = fit_result.evaluate(x_dense)
            self.fit_curve_line.setData(x_dense, y_dense)

            self.api.ui.show_notification("Fit Complete", f"{model_name.capitalize()} fit converged (R² = {fit_result.r_squared:.4f}).")
        except Exception as e:
            self.api.ui.show_error_dialog("Fitting Failed", str(e))


def run_app(api):
    return LiveCurveFitterApp(api)
