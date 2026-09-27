"""
stats_dialog.py - Interactive Statistical Testing & Distribution Analysis Suite for Plot & Stats.
"""

from typing import List, Optional
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QWidget, QGroupBox, QFormLayout, QTextEdit,
    QCheckBox, QSplitter, QMessageBox
)

from egg_suite.ui.theme import theme
from egg_suite.core.stats_engine import (
    test_two_sample_t, test_one_sample_t, test_one_way_anova,
    test_mann_whitney_u, test_normality, compute_correlation_matrix
)


class StatisticalAnalysisDialog(QDialog):
    """Integrated Statistical Testing & Distribution Suite Dialog."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Statistical Testing & Distribution Analysis")
        self.resize(950, 620)
        self.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg};")

        self.df = self._extract_dataframe()

        layout = QVBoxLayout(self)

        header_lbl = QLabel("<b>Statistical Testing & Inferential Analysis Suite</b>")
        header_lbl.setStyleSheet(f"font-size: 16px; color: {theme.primary_text};")
        layout.addWidget(header_lbl)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {theme.border}; background: {theme.panel_bg}; border-radius: 4px; }}
            QTabBar::tab {{ background: {theme.bg}; color: {theme.fg}; padding: 8px 16px; border: 1px solid {theme.border}; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {theme.primary_bg}; color: {theme.primary_text}; font-weight: bold; }}
        """)
        layout.addWidget(self.tabs)

        self._build_hypothesis_tab()
        self._build_normality_tab()
        self._build_correlation_tab()

        btn_bar = QHBoxLayout()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_bar.addStretch()
        btn_bar.addWidget(btn_close)
        layout.addLayout(btn_bar)

    def _extract_dataframe(self) -> pd.DataFrame:
        if hasattr(self.main_window, "dataset") and self.main_window.dataset:
            ds = self.main_window.dataset
            data = getattr(ds, "data", None)
            if data is not None and data.size > 0:
                cols = [ds.column_names.get(i, f"Column_{i}") for i in range(data.shape[1] if data.ndim > 1 else 1)]
                return pd.DataFrame(data, columns=cols)
        # Fallback synthetic demo
        return pd.DataFrame({
            "Control_Group": np.random.normal(10, 2, 100),
            "Treatment_A": np.random.normal(12.5, 2.2, 100),
            "Treatment_B": np.random.normal(14.0, 1.8, 100)
        })

    def _build_hypothesis_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # Left Controls
        left_box = QGroupBox("Configure Hypothesis Test")
        left_box.setStyleSheet(f"QGroupBox {{ font-weight: bold; border: 1px solid {theme.border}; padding: 10px; }}")
        left_form = QFormLayout(left_box)

        self.test_type_combo = QComboBox()
        self.test_type_combo.addItems([
            "Independent Two-Sample t-test (Welch's)",
            "Student's Two-Sample t-test (Equal Variance)",
            "Paired Student's t-test",
            "Mann-Whitney U Test (Non-parametric)",
            "One-Way ANOVA (All numeric columns)",
            "One-Sample t-test vs 0"
        ])
        left_form.addRow("Test Type:", self.test_type_combo)

        cols = list(self.df.columns)
        self.col_a_combo = QComboBox()
        self.col_a_combo.addItems(cols)
        left_form.addRow("Group A (Sample 1):", self.col_a_combo)

        self.col_b_combo = QComboBox()
        self.col_b_combo.addItems(cols)
        if len(cols) > 1:
            self.col_b_combo.setCurrentIndex(1)
        left_form.addRow("Group B (Sample 2):", self.col_b_combo)

        btn_run = QPushButton("⚡ Execute Hypothesis Test")
        btn_run.setStyleSheet(f"font-weight: bold; padding: 8px; background-color: {theme.primary_bg}; color: {theme.primary_text}; border-radius: 4px;")
        btn_run.clicked.connect(self._run_hypothesis_test)
        left_form.addRow(btn_run)

        layout.addWidget(left_box, stretch=1)

        # Right Summary Panel
        right_box = QGroupBox("Test Results & Significance")
        right_box.setStyleSheet(f"QGroupBox {{ font-weight: bold; border: 1px solid {theme.border}; padding: 10px; }}")
        right_lay = QVBoxLayout(right_box)

        self.test_output = QTextEdit()
        self.test_output.setReadOnly(True)
        self.test_output.setStyleSheet(f"background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border}; font-family: Consolas, monospace; font-size: 13px;")
        right_lay.addWidget(self.test_output)

        layout.addWidget(right_box, stretch=2)
        self.tabs.addTab(tab, "🧪 Hypothesis Tests")

    def _run_hypothesis_test(self):
        col_a_name = self.col_a_combo.currentText()
        col_b_name = self.col_b_combo.currentText()
        test_idx = self.test_type_combo.currentIndex()

        a = self.df[col_a_name].to_numpy(dtype=float)
        b = self.df[col_b_name].to_numpy(dtype=float)

        try:
            if test_idx == 0: # Welch
                res = test_two_sample_t(a, b, equal_var=False)
            elif test_idx == 1: # Student
                res = test_two_sample_t(a, b, equal_var=True)
            elif test_idx == 2: # Paired
                res = test_two_sample_t(a, b, paired=True)
            elif test_idx == 3: # Mann-Whitney
                res = test_mann_whitney_u(a, b)
            elif test_idx == 4: # ANOVA
                numeric_cols = [self.df[c].to_numpy(dtype=float) for c in self.df.columns]
                res = test_one_way_anova(*numeric_cols)
            else: # One-sample
                res = test_one_sample_t(a, pop_mean=0.0)

            # Format results output
            lines = [
                f"==================================================",
                f" Test: {res.get('test_name', 'Statistical Test')}",
                f"==================================================",
            ]
            if "t_statistic" in res:
                lines.append(f"  t-Statistic: {res['t_statistic']:.5f}")
            if "f_statistic" in res:
                lines.append(f"  F-Statistic: {res['f_statistic']:.5f}")
            if "u_statistic" in res:
                lines.append(f"  U-Statistic: {res['u_statistic']:.5f}")

            p_val = res.get("p_value", 1.0)
            sig_flag = "★★★ Statistically Significant (p < 0.001)" if p_val < 0.001 else \
                       "★★ Statistically Significant (p < 0.01)" if p_val < 0.01 else \
                       "★ Statistically Significant (p < 0.05)" if p_val < 0.05 else \
                       "✖ NOT Statistically Significant (p >= 0.05)"

            lines.append(f"  p-Value:     {p_val:.6g}")
            lines.append(f"  Conclusion:  {sig_flag}")
            lines.append("--------------------------------------------------")

            if "mean_a" in res and "mean_b" in res:
                lines.append(f"  Mean ({col_a_name}): {res['mean_a']:.4g} (Std: {res['std_a']:.4g})")
                lines.append(f"  Mean ({col_b_name}): {res['mean_b']:.4g} (Std: {res['std_b']:.4g})")
                lines.append(f"  Difference of Means: {res['difference_of_means']:.4g}")

            self.test_output.setPlainText("\n".join(lines))

        except Exception as e:
            self.test_output.setPlainText(f"Test calculation failed:\n{e}")

    def _build_normality_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)

        left_box = QGroupBox("Select Variable")
        left_box.setStyleSheet(f"QGroupBox {{ font-weight: bold; border: 1px solid {theme.border}; padding: 10px; }}")
        left_form = QFormLayout(left_box)

        self.norm_col_combo = QComboBox()
        self.norm_col_combo.addItems(list(self.df.columns))
        left_form.addRow("Column:", self.norm_col_combo)

        btn_norm = QPushButton("🔍 Check Normality")
        btn_norm.setStyleSheet(f"font-weight: bold; padding: 6px; background-color: {theme.primary_bg}; color: {theme.primary_text};")
        btn_norm.clicked.connect(self._run_normality_test)
        left_form.addRow(btn_norm)

        self.norm_summary_lbl = QLabel("")
        self.norm_summary_lbl.setWordWrap(True)
        left_form.addRow(self.norm_summary_lbl)
        layout.addWidget(left_box, stretch=1)

        # Plot Preview
        self.norm_plot = pg.PlotWidget(title="Distribution Histogram")
        self.norm_plot.setBackground(theme.panel_bg)
        self.norm_plot.showGrid(x=True, y=True, alpha=0.3)
        layout.addWidget(self.norm_plot, stretch=2)

        self.tabs.addTab(tab, "📐 Normality & Distributions")
        self._run_normality_test()

    def _run_normality_test(self):
        col_name = self.norm_col_combo.currentText()
        if not col_name or col_name not in self.df.columns:
            return
        data = self.df[col_name].to_numpy(dtype=float)
        clean = data[np.isfinite(data)]
        if len(clean) < 3:
            return

        res = test_normality(clean)
        p_val = res["shapiro_p_value"]
        is_normal = res["is_normal_05"]

        msg = (
            f"<b>Shapiro-Wilk Test:</b><br>"
            f"W-Statistic: <code>{res['shapiro_statistic']:.4f}</code><br>"
            f"p-Value: <code>{p_val:.6g}</code><br>"
            f"Distribution: <b style='color: {'#51cf66' if is_normal else '#ff6b6b'};'>"
            f"{'Likely Normal (p > 0.05)' if is_normal else 'Non-Normal (p < 0.05)'}</b><br><br>"
            f"Skewness: <code>{res['skewness']:.4f}</code><br>"
            f"Kurtosis: <code>{res['kurtosis']:.4f}</code>"
        )
        self.norm_summary_lbl.setText(msg)

        # Draw histogram
        self.norm_plot.clear()
        y_hist, x_edges = np.histogram(clean, bins=min(30, max(5, len(clean) // 5)))
        x_centers = (x_edges[:-1] + x_edges[1:]) / 2.0
        bar = pg.BarGraphItem(x0=x_edges[:-1], x1=x_edges[1:], height=y_hist, brush=pg.mkBrush(theme.primary_bg))
        self.norm_plot.addItem(bar)

    def _build_correlation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ctrl_bar = QHBoxLayout()
        self.corr_method_combo = QComboBox()
        self.corr_method_combo.addItems(["Pearson (Linear Correlation)", "Spearman (Rank Correlation)"])
        self.corr_method_combo.currentIndexChanged.connect(self._refresh_correlation)
        ctrl_bar.addWidget(QLabel("Correlation Method:"))
        ctrl_bar.addWidget(self.corr_method_combo)
        ctrl_bar.addStretch()
        layout.addLayout(ctrl_bar)

        self.corr_table = QTableWidget()
        self.corr_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.corr_table.setStyleSheet(f"background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border};")
        layout.addWidget(self.corr_table)

        self.tabs.addTab(tab, "📊 Correlation Matrix")
        self._refresh_correlation()

    def _refresh_correlation(self):
        method = "spearman" if "Spearman" in self.corr_method_combo.currentText() else "pearson"
        corr_df, pval_df = compute_correlation_matrix(self.df, method=method)

        cols = list(corr_df.columns)
        self.corr_table.setRowCount(len(cols))
        self.corr_table.setColumnCount(len(cols))
        self.corr_table.setHorizontalHeaderLabels(cols)
        self.corr_table.setVerticalHeaderLabels(cols)

        for i, row_col in enumerate(cols):
            for j, col_col in enumerate(cols):
                r_val = corr_df.iloc[i, j]
                p_val = pval_df.iloc[i, j]
                item_str = f"{r_val:.3f}\n(p={p_val:.3f})" if not np.isnan(r_val) else "N/A"
                item = QTableWidgetItem(item_str)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Color cell by correlation strength
                if not np.isnan(r_val) and i != j:
                    if abs(r_val) > 0.7:
                        item.setBackground(pg.mkColor(theme.primary_bg))
                        item.setForeground(pg.mkColor(theme.primary_text))
                self.corr_table.setItem(i, j, item)
