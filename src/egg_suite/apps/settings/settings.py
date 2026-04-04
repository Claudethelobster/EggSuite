import os
import json
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
    QFormLayout, QLineEdit, QPushButton, QLabel, 
    QSlider, QFileDialog, QMessageBox, QComboBox, QApplication
)
from ui.theme import theme
from ui.custom_widgets import ToggleSwitch # Import the new switch!

class PreferencesDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.setWindowTitle("EggSuite Global Settings")
        self.setMinimumWidth(500)
        self.main_window = main_window
        self.settings = main_window.settings
        
        is_dark = self.settings.value("dark_mode", False, bool)
        dis_border = "#555555" if is_dark else "#cccccc"
        dis_text = "#777777" if is_dark else "#999999"
        dis_bg = "#2a2a2a" if is_dark else "#f0f0f0"
        
        # Removed all QCheckBox entries from the stylesheet
        self.setStyleSheet(f"""
            QDialog {{ background-color: {theme.bg}; color: {theme.fg}; }}
            QLabel {{ color: {theme.fg}; font-size: 13px; }}
            QLabel:disabled {{ color: {dis_text}; }}
            
            QTabWidget::pane {{ border: 1px solid {theme.border}; background: {theme.panel_bg}; border-radius: 4px; }}
            QTabBar::tab {{ background: {theme.bg}; color: {theme.fg}; padding: 8px 16px; border: 1px solid {theme.border}; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {theme.primary_bg}; font-weight: bold; border: 1px solid {theme.primary_border}; border-bottom: none; }}
            
            QComboBox, QSpinBox, QSlider, QLineEdit {{
                background-color: {theme.bg}; color: {theme.fg}; border: 1px solid {theme.border}; padding: 5px; border-radius: 3px;
            }}
            
            QComboBox:disabled, QSpinBox:disabled, QLineEdit:disabled {{
                background-color: {dis_bg}; color: {dis_text}; border: 1px solid {dis_border};
            }}
            
            QPushButton {{ background-color: {theme.bg}; border: 1px solid {theme.border}; border-radius: 4px; padding: 6px; color: {theme.fg}; }}
            QPushButton:hover {{ background-color: {theme.panel_bg}; }}
        """)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self._build_general_tab()
        self._build_ui_tab()
        self._build_advanced_tab()
        
        btn_box = QHBoxLayout()
        ok_btn = QPushButton("Save & Apply")
        ok_btn.setStyleSheet(f"font-weight: bold; background-color: {theme.primary_bg}; color: {theme.primary_text}; border: 1px solid {theme.primary_border}; padding: 6px 20px;")
        cancel_btn = QPushButton("Cancel")
        
        ok_btn.clicked.connect(self._on_save_clicked)
        cancel_btn.clicked.connect(self.reject)
        
        btn_box.addStretch()
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(ok_btn)
        layout.addLayout(btn_box)
        
        self.load_current_settings()

    def _build_general_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        
        self.mirror_subfolder = ToggleSwitch("Save Mirrors in /EggPlot_Output/ subfolder")
        form.addRow("File Management:", self.mirror_subfolder)
        
        form.addRow(QLabel("<hr style='border: 1px solid #ccc;'>"))
        
        profile_lay = QHBoxLayout()
        btn_export = QPushButton("Export Profile")
        btn_import = QPushButton("Import Profile")
        btn_export.clicked.connect(self.export_profile)
        btn_import.clicked.connect(self.import_profile)
        profile_lay.addWidget(btn_export)
        profile_lay.addWidget(btn_import)
        form.addRow("Settings Profile:", profile_lay)
        
        self.portable_mode = ToggleSwitch("Portable Mode (Save settings to local .ini file)")
        form.addRow("", self.portable_mode)
        
        form.addRow(QLabel("<hr style='border: 1px solid #ccc;'>"))
        
        btn_reset = QPushButton("Reset to Factory Defaults")
        btn_reset.setStyleSheet(f"color: {theme.danger_text}; font-weight: bold; border: 1px solid {theme.danger_border};")
        btn_reset.clicked.connect(self.factory_reset)
        form.addRow("Memory Wipe:", btn_reset)
        
        self.tabs.addTab(tab, "General & Data")
        
    def _on_save_clicked(self):
        current_dyn = self.dynamic_res_cb.isChecked()
        current_mon = self.monitor_combo.currentData()
        
        if not current_dyn and str(current_mon) != str(self.initial_monitor):
            ans = QMessageBox.question(
                self, "Restart Required", 
                "Changing the target monitor in Fixed Mode requires the suite to restart to apply the correct Windows scaling.\n\nWould you like to save and restart now?", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ans == QMessageBox.StandardButton.Yes:
                self.requires_restart = True
                self.accept()
            else:
                self.dynamic_res_cb.setChecked(self.initial_dynamic)
                idx_mon = self.monitor_combo.findData(self.initial_monitor)
                if idx_mon >= 0: self.monitor_combo.setCurrentIndex(idx_mon)
                return 
        else:
            self.requires_restart = False
            self.accept()
            
    def _toggle_res_ui(self):
        is_dynamic = self.dynamic_res_cb.isChecked()
        self.monitor_combo.setEnabled(not is_dynamic)
        self.resolution_combo.setEnabled(not is_dynamic)
        
        if hasattr(self, 'display_form'):
            lbl_mon = self.display_form.labelForField(self.monitor_combo)
            lbl_res = self.display_form.labelForField(self.resolution_combo)
            if lbl_mon: lbl_mon.setEnabled(not is_dynamic)
            if lbl_res: lbl_res.setEnabled(not is_dynamic)

    def _build_ui_tab(self):
        tab = QWidget()
        self.display_form = QFormLayout(tab) 
        
        self.dark_mode = ToggleSwitch("Enable Dark Mode Theme (Requires Restart)")
        self.display_form.addRow("Application Theme:", self.dark_mode)
        
        self.display_form.addRow(QLabel("<hr style='border: 1px solid #ccc;'>"))
        
        self.dynamic_res_cb = ToggleSwitch("Enable dynamic resolution & free dragging")
        self.dynamic_res_cb.stateChanged.connect(self._toggle_res_ui)
        self.display_form.addRow("Window Mode:", self.dynamic_res_cb)
        
        self.monitor_combo = QComboBox()
        self.screens = QApplication.screens()
        
        for i, screen in enumerate(self.screens):
            geom = screen.geometry()
            self.monitor_combo.addItem(f"Display {i + 1} ({geom.width()}x{geom.height()})", userData=i)
            
        self.resolution_combo = QComboBox()
        self.monitor_combo.currentIndexChanged.connect(self._update_resolutions)
        
        self.display_form.addRow("Target Monitor:", self.monitor_combo)
        self.display_form.addRow("Window Resolution:", self.resolution_combo)
        
        self.display_form.addRow(QLabel("<hr style='border: 1px solid #ccc;'>"))
        
        btn_restore_warnings = QPushButton("Restore all 'Are you sure?' warnings")
        btn_restore_warnings.clicked.connect(self.restore_warnings)
        self.display_form.addRow("Safety Nets:", btn_restore_warnings)
        
        self.tabs.addTab(tab, "UI & Experience")

    def _update_resolutions(self, index):
        self.resolution_combo.blockSignals(True) 
        self.resolution_combo.clear()
        
        if index < 0 or index >= len(self.screens): 
            self.resolution_combo.blockSignals(False)
            return
            
        target_screen = self.screens[index]
        avail_geom = target_screen.availableGeometry() 
        scale_factor = target_screen.devicePixelRatio()
        
        phys_w = int(avail_geom.width() * scale_factor)
        phys_h = int(avail_geom.height() * scale_factor)
        
        max_str = f"Maximise to Screen ({phys_w}x{phys_h})"
        self.resolution_combo.addItem(f"{max_str} (Recommended)", userData="MAX")
        
        standard_res = [
            (3840, 2160), (3440, 1440), (2560, 1600), (2560, 1440), 
            (2560, 1080), (1920, 1200), (1920, 1080), (1680, 1050), 
            (1600, 900),  (1440, 900),  (1366, 768),  (1280, 1024), 
            (1280, 800),  (1280, 720),  (1024, 768),  (800, 600)
        ]
        
        for w, h in standard_res:
            if w <= phys_w and h <= phys_h:
                self.resolution_combo.addItem(f"{w} x {h}", userData=f"{w}x{h}")
                
        saved_res = self.settings.value("target_resolution", "MAX")
        idx = self.resolution_combo.findData(saved_res)
        
        if idx >= 0:
            self.resolution_combo.setCurrentIndex(idx)
        else:
            self.resolution_combo.setCurrentIndex(0)
            
        self.resolution_combo.blockSignals(False)

    def _build_advanced_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        
        self.disable_opengl = ToggleSwitch("Disable Hardware Acceleration (OpenGL)")
        form.addRow("Graphics:", self.disable_opengl)
        
        poll_lay = QHBoxLayout()
        self.poll_slider = QSlider(Qt.Orientation.Horizontal)
        self.poll_slider.setRange(10, 120)
        self.poll_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.poll_slider.setTickInterval(10)
        
        self.poll_lbl = QLabel("60 Hz")
        self.poll_lbl.setFixedWidth(45)
        
        self.poll_slider.valueChanged.connect(lambda v: self.poll_lbl.setText(f"{v} Hz"))
        
        poll_lay.addWidget(self.poll_slider)
        poll_lay.addWidget(self.poll_lbl)
        form.addRow("Crosshair Polling Rate:", poll_lay)
        
        self.tabs.addTab(tab, "Advanced / Performance")

    # ... [The remaining methods (load_current_settings, factory_reset, etc.) stay exactly as they were] ...
    def load_current_settings(self):
        self.mirror_subfolder.setChecked(self.settings.value("mirror_subfolder", False, bool))
        self.portable_mode.setChecked(self.settings.value("portable_mode", False, bool))
        self.dark_mode.setChecked(self.settings.value("dark_mode", False, bool))
        self.disable_opengl.setChecked(self.settings.value("disable_opengl", False, bool))
        
        poll_rate = int(self.settings.value("crosshair_poll_rate", 60))
        self.poll_slider.setValue(poll_rate)
        
        try:
            self.initial_monitor = int(self.settings.value("target_monitor", 0))
        except (ValueError, TypeError):
            self.initial_monitor = 0
            
        if self.initial_monitor < self.monitor_combo.count():
            self.monitor_combo.setCurrentIndex(self.initial_monitor)
        else:
            self.monitor_combo.setCurrentIndex(0)
            self.initial_monitor = 0
            
        self._update_resolutions(self.monitor_combo.currentIndex())
        
        self.initial_resolution = self.settings.value("target_resolution", "MAX")
        idx = self.resolution_combo.findData(self.initial_resolution)
        if idx >= 0:
            self.resolution_combo.setCurrentIndex(idx)
        else:
            self.initial_resolution = "MAX"
            
        self.initial_dynamic = self.settings.value("dynamic_resolution", False, bool)
        self.dynamic_res_cb.setChecked(self.initial_dynamic)
        self._toggle_res_ui() 
        
        self.requires_restart = False

    def restore_warnings(self):
        self.settings.setValue("suppress_rename_warning", False)
        QMessageBox.information(self, "Restored", "All confirmation dialogs have been restored.")

    def factory_reset(self):
        ans = QMessageBox.warning(
            self, "Factory Reset", 
            "Are you sure you want to completely wipe all EggSuite settings, custom equations, and formatting defaults?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.settings.clear()
            QMessageBox.information(self, "Reset Complete", "Settings wiped. Please restart the suite.")
            self.accept()

    def export_profile(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Export Profile", "EggSuite_Profile.json", "JSON Files (*.json)")
        if not fname: return
        
        data = {key: self.settings.value(key) for key in self.settings.allKeys()}
        try:
            with open(fname, 'w') as f:
                json.dump(data, f, indent=4)
            QMessageBox.information(self, "Success", "Profile exported successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export profile:\n{e}")

    def import_profile(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Import Profile", "", "JSON Files (*.json)")
        if not fname: return
        
        try:
            with open(fname, 'r') as f:
                data = json.load(f)
            for key, val in data.items():
                self.settings.setValue(key, val)
            self.load_current_settings()
            QMessageBox.information(self, "Success", "Profile imported! Some changes may require a restart.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import profile:\n{e}")

    def get_results(self):
        return {
            "mirror_subfolder": self.mirror_subfolder.isChecked(),
            "portable_mode": self.portable_mode.isChecked(),
            "dark_mode": self.dark_mode.isChecked(),
            "disable_opengl": self.disable_opengl.isChecked(),
            "crosshair_poll_rate": self.poll_slider.value(),
            "target_monitor": self.monitor_combo.currentData(),
            "target_resolution": self.resolution_combo.currentData(),
            "dynamic_resolution": self.dynamic_res_cb.isChecked()
        }