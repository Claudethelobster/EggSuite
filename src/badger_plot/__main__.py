import sys
import os
import warnings

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

# Import Theme and new Core architecture
from ui.theme import theme
from core.workspace import GlobalWorkspace
from apps.hub.main_menu import HubWindow

def main():
    app = QApplication(sys.argv)
    
    # 1. Boot Theme Engine
    local_ini = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "settings.ini")
    if os.path.exists(local_ini):
        settings = QSettings(local_ini, QSettings.Format.IniFormat)
    else:
        settings = QSettings("BadgerLoop", "QtPlotter")
        
    is_dark = settings.value("dark_mode", False, bool)
    theme.update(is_dark)
    
    # 2. Initialize the Global Memory
    workspace = GlobalWorkspace()
    
    # 3. Launch the Hub Dashboard
    hub = HubWindow(workspace)
    hub.show()
    
    # We will hook up the tile clicks in the next step!
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()