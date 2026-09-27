"""
batch_wizard_dialog.py - Interactive 4-step Batch Processing Wizard for EggSuite.
Allows users to construct reusable recipes and batch-process entire folders of data files.
"""

import os
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QProgressBar, QMessageBox,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QTabWidget, QWidget
)

from egg_suite.ui.theme import theme
from egg_suite.core.batch_processor import BatchRecipe, execute_batch_pipeline, BatchResult


class _BatchWorkerThread(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, input_folder, pattern, recipe, output_folder, x_col, y_col):
        super().__init__()
        self.input_folder = input_folder
        self.pattern = pattern
        self.recipe = recipe
        self.output_folder = output_folder
        self.x_col = x_col
        self.y_col = y_col
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            res = execute_batch_pipeline(
                input_folder=self.input_folder,
                file_pattern=self.pattern,
                recipe=self.recipe,
                output_folder=self.output_folder,
                x_col=self.x_col,
                y_col=self.y_col,
                progress_callback=lambda idx, total, fn: self.progress.emit(idx, total, fn),
                cancel_check=lambda: self._is_cancelled
            )
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class BatchWizardDialog(QDialog):
    """Multi-step wizard dialog for creating recipes and batch-processing folders."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Processing Wizard")
        self.resize(850, 600)
        self.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg};")

        self.recipe = BatchRecipe("Custom Batch Recipe")
        self.worker: Optional[_BatchWorkerThread] = None
        self.last_result: Optional[BatchResult] = None

        layout = QVBoxLayout(self)

        # Tabs for Wizard Steps
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {theme.border}; background: {theme.panel_bg}; border-radius: 4px; }}
            QTabBar::tab {{ background: {theme.bg}; color: {theme.fg}; padding: 8px 16px; border: 1px solid {theme.border}; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {theme.primary_bg}; color: {theme.primary_text}; font-weight: bold; }}
        """)
        layout.addWidget(self.tabs)

        self._build_step1_inputs()
        self._build_step2_recipe()
        self._build_step3_outputs()
        self._build_step4_execution()

        # Navigation Buttons
        btn_bar = QHBoxLayout()
        self.btn_back = QPushButton("◀ Back")
        self.btn_back.clicked.connect(self._prev_tab)
        self.btn_next = QPushButton("Next ▶")
        self.btn_next.setStyleSheet(f"font-weight: bold; background-color: {theme.primary_bg}; color: {theme.primary_text}; padding: 6px 15px;")
        self.btn_next.clicked.connect(self._next_tab)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)

        btn_bar.addWidget(self.btn_back)
        btn_bar.addWidget(self.btn_next)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_close)
        layout.addLayout(btn_bar)

        self._update_nav_buttons()

    def _build_step1_inputs(self):
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)

        title = QLabel("<b>Step 1: Select Input Directory & Column Mapping</b>")
        title.setStyleSheet(f"font-size: 15px; color: {theme.primary_text};")
        form.addRow(title)

        dir_lay = QHBoxLayout()
        self.in_dir_edit = QLineEdit()
        self.in_dir_edit.setPlaceholderText("Select folder containing data files...")
        btn_browse = QPushButton("📁 Browse")
        btn_browse.clicked.connect(self._browse_input_dir)
        dir_lay.addWidget(self.in_dir_edit)
        dir_lay.addWidget(btn_browse)
        form.addRow("Input Folder:", dir_lay)

        self.pattern_edit = QLineEdit("*.csv")
        form.addRow("File Filter Pattern:", self.pattern_edit)

        col_lay = QHBoxLayout()
        self.x_col_spin = QSpinBox()
        self.x_col_spin.setValue(0)
        self.y_col_spin = QSpinBox()
        self.y_col_spin.setValue(1)
        col_lay.addWidget(QLabel("X Column Index:"))
        col_lay.addWidget(self.x_col_spin)
        col_lay.addSpacing(20)
        col_lay.addWidget(QLabel("Y Column Index:"))
        col_lay.addWidget(self.y_col_spin)
        col_lay.addStretch()
        form.addRow("Column Mapping:", col_lay)

        self.tabs.addTab(tab, "1. Source Data")

    def _build_step2_recipe(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        title = QLabel("<b>Step 2: Build Processing Recipe</b>")
        title.setStyleSheet(f"font-size: 15px; color: {theme.primary_text};")
        layout.addWidget(title)

        h_split = QHBoxLayout()

        # Left: Operation Adder
        add_box = QGroupBox("Add Operation Block")
        add_box.setStyleSheet(f"QGroupBox {{ font-weight: bold; border: 1px solid {theme.border}; margin-top: 10px; padding: 10px; }}")
        add_form = QFormLayout(add_box)

        self.op_combo = QComboBox()
        self.op_combo.addItems([
            "Curve Fitting (Gaussian/Exp/Poly)",
            "Baseline Subtraction (ALS / Integration)",
            "Smoothing (Savitzky-Golay)",
            "Peak Finding",
            "Descriptive Statistics"
        ])
        add_form.addRow("Operation:", self.op_combo)

        self.param_model_combo = QComboBox()
        self.param_model_combo.addItems(["gaussian", "lorentzian", "exponential", "polynomial", "sine"])
        add_form.addRow("Fit Model:", self.param_model_combo)

        btn_add = QPushButton("➕ Add to Recipe")
        btn_add.setStyleSheet(f"background-color: {theme.primary_bg}; color: {theme.primary_text}; font-weight: bold; padding: 6px;")
        btn_add.clicked.connect(self._add_recipe_step)
        add_form.addRow(btn_add)
        h_split.addWidget(add_box, stretch=1)

        # Right: Recipe Step List
        list_box = QGroupBox("Active Recipe Pipeline")
        list_box.setStyleSheet(f"QGroupBox {{ font-weight: bold; border: 1px solid {theme.border}; margin-top: 10px; padding: 10px; }}")
        list_lay = QVBoxLayout(list_box)

        self.recipe_list = QListWidget()
        list_lay.addWidget(self.recipe_list)

        btn_recipe_bar = QHBoxLayout()
        btn_remove = QPushButton("✖ Remove Step")
        btn_remove.clicked.connect(self._remove_recipe_step)
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self._clear_recipe)
        btn_recipe_bar.addWidget(btn_remove)
        btn_recipe_bar.addWidget(btn_clear)
        list_lay.addLayout(btn_recipe_bar)

        h_split.addWidget(list_box, stretch=1)
        layout.addLayout(h_split)

        # Recipe Load/Save
        file_bar = QHBoxLayout()
        btn_save_recipe = QPushButton("💾 Save Recipe to JSON")
        btn_save_recipe.clicked.connect(self._save_recipe_file)
        btn_load_recipe = QPushButton("📂 Load Recipe from JSON")
        btn_load_recipe.clicked.connect(self._load_recipe_file)
        file_bar.addWidget(btn_save_recipe)
        file_bar.addWidget(btn_load_recipe)
        file_bar.addStretch()
        layout.addLayout(file_bar)

        # Pre-populate default steps
        self._add_default_recipe()
        self.tabs.addTab(tab, "2. Recipe Pipeline")

    def _build_step3_outputs(self):
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)

        title = QLabel("<b>Step 3: Configure Output Destinations</b>")
        title.setStyleSheet(f"font-size: 15px; color: {theme.primary_text};")
        form.addRow(title)

        sum_lay = QHBoxLayout()
        self.out_summary_edit = QLineEdit()
        self.out_summary_edit.setPlaceholderText("summary_results.csv")
        btn_browse_sum = QPushButton("Browse...")
        btn_browse_sum.clicked.connect(self._browse_summary_file)
        sum_lay.addWidget(self.out_summary_edit)
        sum_lay.addWidget(btn_browse_sum)
        form.addRow("Consolidated CSV Summary:", sum_lay)

        proc_lay = QHBoxLayout()
        self.out_proc_dir_edit = QLineEdit()
        self.out_proc_dir_edit.setPlaceholderText("Optional folder to export cleaned/processed files...")
        btn_browse_proc = QPushButton("Browse...")
        btn_browse_proc.clicked.connect(self._browse_processed_dir)
        proc_lay.addWidget(self.out_proc_dir_edit)
        proc_lay.addWidget(btn_browse_proc)
        form.addRow("Export Processed Data:", proc_lay)

        self.tabs.addTab(tab, "3. Outputs")

    def _build_step4_execution(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        title = QLabel("<b>Step 4: Execute Batch Process</b>")
        title.setStyleSheet(f"font-size: 15px; color: {theme.primary_text};")
        layout.addWidget(title)

        exec_bar = QHBoxLayout()
        self.btn_run = QPushButton("🚀 Run Batch Pipeline")
        self.btn_run.setStyleSheet(f"font-weight: bold; font-size: 14px; padding: 10px 20px; background-color: {theme.primary_bg}; color: {theme.primary_text}; border-radius: 4px;")
        self.btn_run.clicked.connect(self._start_batch)

        self.btn_cancel = QPushButton("⛔ Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_batch)

        exec_bar.addWidget(self.btn_run)
        exec_bar.addWidget(self.btn_cancel)
        exec_bar.addStretch()
        layout.addLayout(exec_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Ready to process.")
        layout.addWidget(self.status_lbl)

        layout.addWidget(QLabel("<b>Summary Results Preview:</b>"))
        self.results_table = QTableWidget()
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.results_table)

        self.tabs.addTab(tab, "4. Execution & Results")

    def _add_default_recipe(self):
        self.recipe.steps = []
        self.recipe.add_step("baseline_subtract", {"method": "endpoints"})
        self.recipe.add_step("fit_curve", {"model": "gaussian"})
        self.recipe.add_step("statistics", {})
        self._refresh_recipe_list()

    def _refresh_recipe_list(self):
        self.recipe_list.clear()
        for idx, step in enumerate(self.recipe.steps):
            stype = step["type"]
            params = step.get("params", {})
            param_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else "default"
            item_text = f"{idx + 1}. {stype.replace('_', ' ').title()} ({param_str})"
            self.recipe_list.addItem(QListWidgetItem(item_text))

    def _add_recipe_step(self):
        op_text = self.op_combo.currentText()
        if "Curve Fitting" in op_text:
            model = self.param_model_combo.currentText()
            self.recipe.add_step("fit_curve", {"model": model})
        elif "Baseline Subtraction" in op_text:
            self.recipe.add_step("baseline_subtract", {"method": "endpoints"})
        elif "Smoothing" in op_text:
            self.recipe.add_step("smooth", {"method": "savgol", "window_length": 11, "polyorder": 3})
        elif "Peak Finding" in op_text:
            self.recipe.add_step("find_peaks", {})
        elif "Descriptive Statistics" in op_text:
            self.recipe.add_step("statistics", {})
        self._refresh_recipe_list()

    def _remove_recipe_step(self):
        row = self.recipe_list.currentRow()
        if 0 <= row < len(self.recipe.steps):
            self.recipe.steps.pop(row)
            self._refresh_recipe_list()

    def _clear_recipe(self):
        self.recipe.steps.clear()
        self._refresh_recipe_list()

    def _browse_input_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Input Directory")
        if d:
            self.in_dir_edit.setText(d)
            if not self.out_summary_edit.text():
                self.out_summary_edit.setText(os.path.join(d, "batch_summary_report.csv"))

    def _browse_summary_file(self):
        f, _ = QFileDialog.getSaveFileName(self, "Save Consolidated Summary", "", "CSV Files (*.csv)")
        if f:
            self.out_summary_edit.setText(f)

    def _browse_processed_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Processed Output Directory")
        if d:
            self.out_proc_dir_edit.setText(d)

    def _save_recipe_file(self):
        f, _ = QFileDialog.getSaveFileName(self, "Save Recipe", "recipe.json", "JSON Recipe (*.json)")
        if f:
            self.recipe.save_to_file(f)
            QMessageBox.information(self, "Saved", f"Recipe saved to {os.path.basename(f)}")

    def _load_recipe_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load Recipe", "", "JSON Recipe (*.json)")
        if f:
            self.recipe = BatchRecipe.load_from_file(f)
            self._refresh_recipe_list()
            QMessageBox.information(self, "Loaded", f"Loaded recipe: {self.recipe.name}")

    def _prev_tab(self):
        curr = self.tabs.currentIndex()
        if curr > 0:
            self.tabs.setCurrentIndex(curr - 1)
        self._update_nav_buttons()

    def _next_tab(self):
        curr = self.tabs.currentIndex()
        if curr < self.tabs.count() - 1:
            self.tabs.setCurrentIndex(curr + 1)
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        curr = self.tabs.currentIndex()
        self.btn_back.setEnabled(curr > 0)
        self.btn_next.setEnabled(curr < self.tabs.count() - 1)

    def _start_batch(self):
        in_dir = self.in_dir_edit.text().strip()
        if not in_dir or not os.path.isdir(in_dir):
            QMessageBox.warning(self, "Input Error", "Please select a valid input directory in Step 1.")
            self.tabs.setCurrentIndex(0)
            return

        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Scanning files...")

        self.worker = _BatchWorkerThread(
            input_folder=in_dir,
            pattern=self.pattern_edit.text().strip() or "*.csv",
            recipe=self.recipe,
            output_folder=self.out_proc_dir_edit.text().strip() or None,
            x_col=self.x_col_spin.value(),
            y_col=self.y_col_spin.value()
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def _cancel_batch(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_lbl.setText("Cancelling batch execution...")

    def _on_worker_progress(self, current, total, filename):
        pct = int((current / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.status_lbl.setText(f"Processing ({current}/{total}): {filename}")

    def _on_worker_finished(self, result: BatchResult):
        self.last_result = result
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.status_lbl.setText(f"Complete! Processed {result.processed_count} files in {result.elapsed_seconds:.2f}s ({result.failed_count} errors).")

        df = result.to_dataframe()
        if not df.empty:
            # Export to summary CSV
            out_csv = self.out_summary_edit.text().strip()
            if out_csv:
                try:
                    result.export_summary_csv(out_csv)
                except Exception as e:
                    QMessageBox.warning(self, "Export Error", f"Could not write summary CSV:\n{e}")

            # Populate UI results table
            self.results_table.clear()
            self.results_table.setRowCount(len(df))
            self.results_table.setColumnCount(len(df.columns))
            self.results_table.setHorizontalHeaderLabels([str(c) for c in df.columns])

            for row_idx, row_data in df.iterrows():
                for col_idx, val in enumerate(row_data):
                    val_str = f"{val:.4g}" if isinstance(val, (float, np.floating)) else str(val)
                    self.results_table.setItem(int(row_idx), col_idx, QTableWidgetItem(val_str))

            QMessageBox.information(
                self, "Batch Complete",
                f"Successfully processed {result.processed_count} files!\n\nSummary saved to:\n{out_csv if out_csv else 'Preview table only.'}"
            )
        else:
            QMessageBox.warning(self, "No Results", "No files matched the pattern or all files failed.")

    def _on_worker_error(self, err_msg):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.status_lbl.setText("Error during batch execution.")
        QMessageBox.critical(self, "Batch Failed", f"An error occurred:\n{err_msg}")
