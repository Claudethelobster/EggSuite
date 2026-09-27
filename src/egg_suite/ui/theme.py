"""
theme.py - Dynamic Theme Engine and Palette Manager for EggSuite.
Supports real-time theme switching without restarting the application.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication


class ThemeManager(QObject):
    """Manages the global color palette and broadcasts real-time theme change signals."""
    theme_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.is_dark = False
        self._set_colors(False)

    def _set_colors(self, is_dark: bool):
        self.is_dark = is_dark
        if is_dark:
            # Dark Mode Palette
            self.bg = "#353535"
            self.fg = "#ffffff"
            self.panel_bg = "#222222"
            self.border = "#555555"
            
            self.primary_text = "#66a3ff"  # Brighter blue for dark backgrounds
            self.primary_bg = "#1a3355"
            self.primary_border = "#336699"
            
            self.danger_text = "#ff6666"   # Brighter red
            self.danger_bg = "#4d1a1a"
            self.danger_border = "#993333"
            
            self.success_text = "#50c878"  # Brighter green
            self.success_bg = "#1a4026"
            self.success_border = "#2d7344"
            
            self.warning_text = "#ffcc00"
            self.warning_bg = "#4d3d00"
            self.warning_border = "#997a00"
        else:
            # Light Mode Palette
            self.bg = "#f5f5f5"
            self.fg = "#000000"
            self.panel_bg = "#ffffff"
            self.border = "#8a8a8a"
            
            self.primary_text = "#0055ff"
            self.primary_bg = "#d0e8ff"
            self.primary_border = "#0055ff"
            
            self.danger_text = "#d90000"
            self.danger_bg = "#ffe6e6"
            self.danger_border = "#d90000"
            
            self.success_text = "#2ca02c"
            self.success_bg = "#e6f5e6"
            self.success_border = "#2ca02c"
            
            self.warning_text = "#ffaa00"
            self.warning_bg = "#fff0d0"
            self.warning_border = "#ffaa00"

    def apply_to_application(self, app: QApplication = None):
        """Pushes current theme palette and pyqtgraph configuration to Qt application."""
        if app is None:
            app = QApplication.instance()
        if not app:
            return

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(self.bg))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(self.fg))
        palette.setColor(QPalette.ColorRole.Base, QColor(self.panel_bg))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(self.bg))
        palette.setColor(QPalette.ColorRole.Text, QColor(self.fg))
        palette.setColor(QPalette.ColorRole.Button, QColor(self.panel_bg))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(self.fg))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(self.primary_bg))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(self.primary_text))

        strong_border = QColor("#AAAAAA") if self.is_dark else QColor("#222222")
        palette.setColor(QPalette.ColorRole.Dark, strong_border)
        palette.setColor(QPalette.ColorRole.Shadow, strong_border)
        palette.setColor(QPalette.ColorRole.Mid, strong_border)

        app.setPalette(palette)

        # Update pyqtgraph if loaded
        try:
            import pyqtgraph as pg
            pg.setConfigOption('background', self.panel_bg)
            pg.setConfigOption('foreground', self.fg)
        except Exception:
            pass

    def update(self, is_dark: bool):
        """Updates the theme colors, applies palette globally, and emits theme_changed signal."""
        self._set_colors(is_dark)
        self.apply_to_application()
        self.theme_changed.emit(is_dark)


# Global singleton so all windows and dialogs read from and bind to the same instance
theme = ThemeManager()
