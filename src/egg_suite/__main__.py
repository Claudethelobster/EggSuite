import sys
import os
import warnings
import ctypes
from PyQt6.QtGui import QIcon
# --- THE SPYDER CACHE ASSASSIN ---
os.environ.pop("QT_API", None)
os.environ.pop("QT_PLUGIN_PATH", None)
os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)

for module_name in list(sys.modules.keys()):
    if module_name.startswith("pyqtgraph"):
        del sys.modules[module_name]
# ---------------------------------

# --- GLOBAL WARNING SUPPRESSION ---
warnings.simplefilter("ignore")
warnings.filterwarnings("ignore", category=RuntimeWarning)
# ----------------------------------

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QPalette, QColor

# Import Theme and new Core architecture
from ui.theme import theme
from core.workspace import GlobalWorkspace
from apps.hub.main_menu import HubWindow

def main():
    # --- FIX: Tell Windows this is a unique application, not just a Python script ---
    # This forces the taskbar to use our custom icon instead of the default Python one
    try:
        app_id = 'badgerloop.eggsuite.suite.1_0' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except AttributeError:
        pass # Fails silently if the user is on macOS or Linux
    # --------------------------------------------------------------------------------

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        
    # --- NEW: Set the Global Application Icon ---
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons", "app_icon.png")
    app.setWindowIcon(QIcon(icon_path))
    # ------------------------------------------
    
    # --- Force the Fusion rendering engine ---
    app.setStyle("Fusion")
    # ----------------------------------------------
    
    # 1. Boot Theme Engine
    local_ini = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "settings.ini")
    if os.path.exists(local_ini):
        settings = QSettings(local_ini, QSettings.Format.IniFormat)
    else:
        settings = QSettings("BadgerLoop", "QtPlotter")
        
    is_dark = settings.value("dark_mode", False, bool)
    theme.update(is_dark)
    
    # --- NEW: SYNCHRONISE FUSION WITH YOUR THEME ---
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme.bg))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.fg))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme.panel_bg))      # Inside of the checkbox
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.bg))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme.fg))              # Colour of the tick!
    palette.setColor(QPalette.ColorRole.Button, QColor(theme.panel_bg))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.fg))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.primary_bg))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.primary_text))
    
    # --- FIX: High-contrast checkbox borders ---
    strong_border = QColor("#AAAAAA") if is_dark else QColor("#222222")
    
    palette.setColor(QPalette.ColorRole.Dark, strong_border)
    palette.setColor(QPalette.ColorRole.Shadow, strong_border)
    palette.setColor(QPalette.ColorRole.Mid, strong_border)
    # -------------------------------------------
    
    app.setPalette(palette)
    # -----------------------------------------------
    
    # 2. Initialise the Global Memory
    workspace = GlobalWorkspace()
    
    # 3. Launch the Hub Dashboard
    hub = HubWindow(workspace)
    hub.show()
    
    # Use app.exec() without sys.exit() to prevent Spyder from forcefully killing the console
    app.exec()

if __name__ == '__main__':
    main()