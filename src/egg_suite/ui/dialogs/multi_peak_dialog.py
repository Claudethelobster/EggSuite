"""
multi_peak_dialog.py - Interactive Multi-Peak Deconvolution Dialog for Plot & Stats.
Provides click-to-place peak anchors, simultaneous profile optimization, and decomposed curve visualization.
"""

from typing import List, Optional
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QCheckBox, QMessageBox, QFileDialog, QWidget, QSplitter
)

from egg_suite.ui.theme import theme
from egg_suite.core.multi_peak_engine import PeakItem, fit_multi_peaks, MultiPeakFitResult


PEAK_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe"
]


class MultiPeakDeconvolutionDialog(QDialog):
    """Interactive dialog for placing peak markers and executing multi-peak deconvolution."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Multi-Peak Deconvolution & Fitting")
        self.resize(900, 550)
        self.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg};")

        # Extract active x and y data from main window
        self.x, self.y = self._extract_data()
        self.initial_peaks: List[PeakItem] = []
        self.fit_result: Optional[MultiPeakFitResult] = None

        # Phantom items on the plot
        self.phantom_items = []

        layout = QVBoxLayout(self)

        header_lbl = QLabel("<b>Interactive Multi-Peak Deconvolution</b>")
        header_lbl.setStyleSheet(f"font-size: 16px; color: {theme.primary_text};")
        layout.addWidget(header_lbl)

        info_lbl = QLabel("Add peaks manually below or click <i>'Auto-Detect Peaks'</i> to find initial estimates, then click <b>Fit Model</b>.")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        # Peak Control Table
        self.peak_table = QTableWidget()
        self.peak_table.setColumnCount(4)
        self.peak_table.setHorizontalHeaderLabels(["Model", "Center Guess", "Height Guess", "FWHM Guess"])
        self.peak_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.peak_table.setStyleSheet(f"background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border};")
        layout.addWidget(self.peak_table)

        # Action Buttons for Peak Table
        btn_row1 = QHBoxLayout()
        btn_add_peak = QPushButton("➕ Add Peak")
        btn_add_peak.clicked.connect(self._add_peak_row)
        btn_auto_detect = QPushButton("✨ Auto-Detect Peaks")
        btn_auto_detect.clicked.connect(self._auto_detect_peaks)
        btn_remove_peak = QPushButton("✖ Remove Selected")
        btn_remove_peak.clicked.connect(self._remove_selected_peak)

        btn_row1.addWidget(btn_add_peak)
        btn_row1.addWidget(btn_auto_detect)
        btn_row1.addWidget(btn_remove_peak)
        btn_row1.addStretch()

        self.cb_baseline = QCheckBox("Fit Linear Baseline")
        self.cb_baseline.setChecked(True)
        btn_row1.addWidget(self.cb_baseline)
        layout.addLayout(btn_row1)

        # Results Summary Table
        layout.addWidget(QLabel("<b>Deconvolved Peak Results:</b>"))
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels(["Peak #", "Type", "Center", "Amplitude", "FWHM", "Area", "% Area"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setStyleSheet(f"background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border};")
        layout.addWidget(self.results_table)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        self.btn_fit = QPushButton("⚡ Fit Multi-Peak Model")
        self.btn_fit.setStyleSheet(f"font-weight: bold; font-size: 14px; padding: 8px 18px; background-color: {theme.primary_bg}; color: {theme.primary_text}; border-radius: 4px;")
        self.btn_fit.clicked.connect(self.run_fit)

        self.btn_export = QPushButton("💾 Export CSV Table")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_csv)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)

        bottom_bar.addWidget(self.btn_fit)
        bottom_bar.addWidget(self.btn_export)
        bottom_bar.addStretch()
        bottom_bar.addWidget(btn_close)
        layout.addLayout(bottom_bar)

        # Initial auto-detection
        self._auto_detect_peaks()

    def _extract_data(self):
        if hasattr(self.main_window, "get_active_xy"):
            return self.main_window.get_active_xy()
        elif hasattr(self.main_window, "x") and hasattr(self.main_window, "y"):
            return self.main_window.x, self.main_window.y
        return np.linspace(0, 10, 100), np.zeros(100)

    def _auto_detect_peaks(self):
        from egg_suite.core.analysis_engine import find_peaks
        self.peak_table.setRowCount(0)
        x, y = self.x, self.y
        if len(x) < 3:
            return

        y_range = float(np.max(y) - np.min(y))
        peaks = find_peaks(y, x=x, height=float(np.min(y) + y_range * 0.2), distance=max(5, len(y) // 30))
        indices = peaks["indices"]

        if len(indices) == 0:
            # Fallback single peak at center
            self._add_peak_row(center=float(np.mean(x)), amp=float(y_range), fwhm=float((np.max(x) - np.min(x)) / 5.0))
        else:
            for idx in indices[:6]: # Limit to first 6 peaks initially
                cen = float(x[idx])
                amp = float(y[idx] - np.min(y))
                fwhm = float((np.max(x) - np.min(x)) / 15.0)
                self._add_peak_row(center=cen, amp=amp, fwhm=fwhm)

    def _add_peak_row(self, center=None, amp=None, fwhm=None):
        row = self.peak_table.rowCount()
        self.peak_table.insertRow(row)

        model_combo = QComboBox()
        model_combo.addItems(["Gaussian", "Lorentzian", "Pseudo-Voigt"])
        self.peak_table.setCellWidget(row, 0, model_combo)

        cen_val = center if center is not None else float(np.mean(self.x))
        amp_val = amp if amp is not None else float(np.ptp(self.y) / 2.0)
        fwhm_val = fwhm if fwhm is not None else float(np.ptp(self.x) / 10.0)

        self.peak_table.setItem(row, 1, QTableWidgetItem(f"{cen_val:.4g}"))
        self.peak_table.setItem(row, 2, QTableWidgetItem(f"{amp_val:.4g}"))
        self.peak_table.setItem(row, 3, QTableWidgetItem(f"{fwhm_val:.4g}"))

    def _remove_selected_peak(self):
        row = self.peak_table.currentRow()
        if row >= 0:
            self.peak_table.removeRow(row)

    def run_fit(self):
        rows = self.peak_table.rowCount()
        if rows == 0:
            QMessageBox.warning(self, "No Peaks", "Please add at least one peak.")
            return

        initial_peaks = []
        for r in range(rows):
            combo = self.peak_table.cellWidget(r, 0)
            ptype = combo.currentText().lower() if combo else "gaussian"
            try:
                cen = float(self.peak_table.item(r, 1).text())
                amp = float(self.peak_table.item(r, 2).text())
                fwhm = float(self.peak_table.item(r, 3).text())
            except (ValueError, AttributeError):
                QMessageBox.warning(self, "Value Error", f"Invalid numerical values in row {r + 1}.")
                return
            initial_peaks.append(PeakItem(peak_type=ptype, center=cen, amplitude=amp, width=fwhm))

        try:
            self.fit_result = fit_multi_peaks(self.x, self.y, initial_peaks, fit_baseline=self.cb_baseline.isChecked())
            self._update_results_table()
            self._draw_overlay()
            self.btn_export.setEnabled(True)
            QMessageBox.information(self, "Fit Complete", f"Multi-Peak Fit Converged!\nR² = {self.fit_result.r_squared:.4f}")
        except Exception as e:
            QMessageBox.critical(self, "Fitting Error", str(e))

    def _update_results_table(self):
        if not self.fit_result:
            return
        summary = self.fit_result.summary_table()
        self.results_table.setRowCount(len(summary))

        for row_idx, row_dict in enumerate(summary):
            self.results_table.setItem(row_idx, 0, QTableWidgetItem(str(row_dict["Peak_Index"])))
            self.results_table.setItem(row_idx, 1, QTableWidgetItem(str(row_dict["Type"])))
            self.results_table.setItem(row_idx, 2, QTableWidgetItem(f"{row_dict['Center']:.4g}"))
            self.results_table.setItem(row_idx, 3, QTableWidgetItem(f"{row_dict['Amplitude']:.4g}"))
            self.results_table.setItem(row_idx, 4, QTableWidgetItem(f"{row_dict['FWHM']:.4g}"))
            self.results_table.setItem(row_idx, 5, QTableWidgetItem(f"{row_dict['Integrated_Area']:.4g}"))
            self.results_table.setItem(row_idx, 6, QTableWidgetItem(str(row_dict["Area_Percent"])))

    def _draw_overlay(self):
        """Draws individual dashed peak curves and composite fit line on main plot."""
        if not self.fit_result or not hasattr(self.main_window, "plot_widget"):
            return

        self._clear_phantom_items()
        pw = self.main_window.plot_widget
        x_dense = np.linspace(np.min(self.x), np.max(self.x), 500)

        # 1. Composite Curve (Thick Solid Line)
        y_composite = self.fit_result.evaluate_composite(x_dense)
        composite_item = pg.PlotCurveItem(x_dense, y_composite, pen=pg.mkPen(color=theme.primary_bg, width=3))
        pw.addItem(composite_item)
        self.phantom_items.append(composite_item)

        # 2. Individual Peaks (Dashed Lines)
        base_dense = self.fit_result.evaluate_baseline(x_dense)
        for idx, pk in enumerate(self.fit_result.peaks):
            color = PEAK_COLORS[idx % len(PEAK_COLORS)]
            y_pk = base_dense + pk.evaluate(x_dense)
            pk_item = pg.PlotCurveItem(x_dense, y_pk, pen=pg.mkPen(color=color, width=2, style=Qt.PenStyle.DashLine))
            pw.addItem(pk_item)
            self.phantom_items.append(pk_item)

    def _clear_phantom_items(self):
        if hasattr(self.main_window, "plot_widget"):
            for item in self.phantom_items:
                try:
                    self.main_window.plot_widget.removeItem(item)
                except Exception:
                    pass
        self.phantom_items.clear()

    def export_csv(self):
        if not self.fit_result:
            return
        f, _ = QFileDialog.getSaveFileName(self, "Export Deconvolution Results", "multi_peak_results.csv", "CSV Files (*.csv)")
        if f:
            import pandas as pd
            df = pd.DataFrame(self.fit_result.summary_table())
            df.to_csv(f, index=False)
            QMessageBox.information(self, "Exported", f"Results exported to {f}")

    def closeEvent(self, event):
        self._clear_phantom_items()
        super().closeEvent(event)

    def reject(self):
        self._clear_phantom_items()
        super().reject()
