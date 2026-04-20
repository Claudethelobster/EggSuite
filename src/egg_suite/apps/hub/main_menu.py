import os
import random
import csv
import json
import importlib.util
import sys
import re
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QUrl, QPoint, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QFrame, QFileDialog, QMessageBox, QProgressDialog,
    QDialog, QGraphicsBlurEffect, QLineEdit, QStackedWidget, QListWidget, QListWidgetItem, QFormLayout
)

from ui.theme import theme
from ui.custom_widgets import ToastNotification
from apps.data_inspector.inspector_window import DataInspectorWindow
from ui.custom_widgets import ToggleSwitch
from core.data_loader import DataLoaderThread
from ui.dialogs.data_mgmt import FileImportDialog, CopyableErrorDialog, TemplateSelectionDialog, BatchImportDialog

class RecentFilesDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.selected_path = None
        
        self.setWindowTitle("Recent Files")
        self.setMinimumWidth(400)
        self.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg};")
        
        self.main_layout = QVBoxLayout(self)
        self._build_ui()
        
    def _build_ui(self):
        # Clear layout if rebuilding (used when the cache is cleared)
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget(): sub.widget().deleteLater()
            
        import json
        import os
        recents_str = self.settings.value("recent_files", "[]")
        try: recents = json.loads(recents_str)
        except Exception: recents = []
        
        if not recents:
            lbl = QLabel("<i>No recent files found in the cache.</i>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {theme.fg}; font-size: 14px; padding: 20px;")
            self.main_layout.addWidget(lbl)
        else:
            lbl = QLabel("<b>Select a recent file or folder to load:</b>")
            lbl.setStyleSheet("font-size: 14px;")
            self.main_layout.addWidget(lbl)
            self.main_layout.addSpacing(10)
            
            for path in recents:
                if not os.path.exists(path): continue
                
                icon = "📁" if os.path.isdir(path) else "📄"
                btn = QPushButton(f"{icon} {os.path.basename(path)}")
                btn.setToolTip(path) # Hovering shows the full file path!
                btn.setStyleSheet(f"""
                    QPushButton {{ 
                        text-align: left; padding: 10px; background-color: {theme.panel_bg}; 
                        border: 1px solid {theme.border}; border-radius: 4px; 
                        color: {theme.primary_text}; font-weight: bold; font-size: 13px;
                    }}
                    QPushButton:hover {{ 
                        background-color: {theme.primary_bg}; border: 1px solid {theme.primary_border}; 
                    }}
                """)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, p=path: self._select_file(p))
                self.main_layout.addWidget(btn)
                
        self.main_layout.addSpacing(15)
        
        # Bottom controls
        bottom_lay = QHBoxLayout()
        
        clear_btn = QPushButton("🗑️ Clear Cache")
        clear_btn.setStyleSheet(f"padding: 6px 12px; color: {theme.danger_text}; border: 1px solid {theme.danger_border}; border-radius: 4px; background-color: {theme.bg};")
        clear_btn.clicked.connect(self._clear_cache)
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"padding: 6px 15px; border: 1px solid {theme.border}; border-radius: 4px; background-color: {theme.bg}; color: {theme.fg};")
        close_btn.clicked.connect(self.reject)
        
        bottom_lay.addWidget(clear_btn)
        bottom_lay.addStretch()
        bottom_lay.addWidget(close_btn)
        
        self.main_layout.addLayout(bottom_lay)
        
    def _select_file(self, path):
        self.selected_path = path
        self.accept()
        
    def _clear_cache(self):
        import json
        self.settings.setValue("recent_files", json.dumps([]))
        self._build_ui() # Instantly refreshes the window to show it is empty
        
class AppCreatorDialog(QDialog):
    """A safe, validating form for users to scaffold new EggSuite plugins."""
    def __init__(self, apps_dir, parent=None):
        super().__init__(parent)
        self.apps_dir = apps_dir
        self.setWindowTitle("Create New Plugin")
        self.setMinimumWidth(450)
        self.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg};")
        
        self.layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Quantum Simulator")
        self.name_edit.textChanged.connect(self._auto_fill_folder)
        
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Brief description of what it does...")
        
        self.icon_edit = QLineEdit("🧩")
        self.icon_edit.setMaxLength(2) 
        
        # --- NEW: Author and Version Inputs ---
        self.author_edit = QLineEdit("User")
        self.version_edit = QLineEdit("1.0.0")
        # --------------------------------------
        
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("e.g., quantum_simulator")
        self.folder_edit.textChanged.connect(self._validate)
        
        input_style = f"background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border}; border-radius: 4px; padding: 6px;"
        self.name_edit.setStyleSheet(input_style)
        self.desc_edit.setStyleSheet(input_style)
        self.icon_edit.setStyleSheet(input_style)
        self.author_edit.setStyleSheet(input_style) # Style the new inputs
        self.version_edit.setStyleSheet(input_style) # Style the new inputs
        self.folder_edit.setStyleSheet(input_style)
        
        form.addRow("App Name:", self.name_edit)
        form.addRow("Description:", self.desc_edit)
        form.addRow("Icon (Emoji):", self.icon_edit)
        form.addRow("Author:", self.author_edit)   # Add to layout
        form.addRow("Version:", self.version_edit) # Add to layout
        form.addRow("Folder Name:", self.folder_edit)
        
        self.layout.addLayout(form)
        
        self.warning_lbl = QLabel("")
        self.warning_lbl.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 12px;")
        self.warning_lbl.hide()
        self.layout.addWidget(self.warning_lbl)
        
        btn_box = QHBoxLayout()
        self.create_btn = QPushButton("Create Plugin")
        self.create_btn.setStyleSheet(f"font-weight: bold; padding: 8px 15px; background-color: {theme.primary_bg}; color: {theme.primary_text}; border: 1px solid {theme.primary_border}; border-radius: 4px;")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"padding: 8px 15px; background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border}; border-radius: 4px;")
        cancel_btn.clicked.connect(self.reject)
        
        btn_box.addStretch()
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(self.create_btn)
        self.layout.addLayout(btn_box)

    # (Keep your _auto_fill_folder, _validate, and _set_warning methods exactly the same)
        
    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "description": self.desc_edit.text().strip() or "A custom EggSuite plugin.",
            "icon": self.icon_edit.text().strip() or "🧩",
            "author": self.author_edit.text().strip() or "Unknown", # Capture Author
            "version": self.version_edit.text().strip() or "1.0.0",   # Capture Version
            "folder": self.folder_edit.text()
        }

    def _auto_fill_folder(self, text):
        # Only auto-fill if the user hasn't manually modified the folder box yet
        if not self.folder_edit.isModified():
            clean_name = text.lower().strip()
            clean_name = re.sub(r'[^a-z0-9_]', '_', clean_name) # Strip invalid chars
            clean_name = re.sub(r'_+', '_', clean_name)         # Remove double underscores
            self.folder_edit.setText(clean_name)
        self._validate()

    def _validate(self):
        folder = self.folder_edit.text()
        name = self.name_edit.text().strip()
        
        if not name:
            self._set_warning("App Name cannot be empty.")
            return
        if not folder:
            self._set_warning("Folder Name cannot be empty.")
            return
        if not re.match(r"^[a-z0-9_]+$", folder):
            self._set_warning("Folder Name can only contain lowercase letters, numbers, and underscores.")
            return
            
        target_path = os.path.join(self.apps_dir, folder)
        if os.path.exists(target_path):
            self._set_warning("A folder with this name already exists in external_apps!")
            return
            
        self.warning_lbl.hide()
        self.create_btn.setEnabled(True)
        
    def _set_warning(self, msg):
        self.warning_lbl.setText(msg)
        self.warning_lbl.show()
        self.create_btn.setEnabled(False)
        

class AppTile(QFrame):
    launch_requested = pyqtSignal(bool) 

    # --- ADDED: show_toggle parameter ---
    def __init__(self, title, description, icon="📊", show_toggle=True, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{ background-color: {theme.panel_bg}; border: 2px solid {theme.border}; border-radius: 12px; }}
            QFrame:hover {{ background-color: {theme.primary_bg}; border: 2px solid {theme.primary_border}; }}
        """)
        self.setFixedSize(220, 220)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 40px; border: none; background: transparent;")
        layout.addWidget(icon_lbl)

        layout.addStretch()

        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; border: none; background: transparent; color: {theme.primary_text};")
        
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"font-size: 12px; border: none; background: transparent; color: {theme.fg};")
        
        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)
        layout.addSpacing(10)
        
        # --- NEW: Only build the toggle if requested ---
        self.popout_cb = None
        if show_toggle:
            self.popout_cb = ToggleSwitch("Open in separate window")
            font = self.popout_cb.font()
            font.setPixelSize(12)
            font.setBold(True)
            self.popout_cb.setFont(font)
            layout.addWidget(self.popout_cb)
        else:
            layout.addSpacing(24) # Keep the height balanced when toggle is missing

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Safely check if the toggle exists and was clicked
            if self.popout_cb and self.popout_cb.geometry().contains(event.pos()):
                pass 
            else:
                popout_state = self.popout_cb.isChecked() if self.popout_cb else False
                self.launch_requested.emit(popout_state)
        super().mousePressEvent(event)

class WindowDimmer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Greys out the entire application
        self.setStyleSheet("background-color: rgba(0, 0, 0, 140);")
        self.hide()

class DropOverlay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Adds a slight blue tint, thick dashed border, and matches the tree's rounded corners
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(66, 135, 245, 30); 
                border: 4px dashed {theme.primary_bg}; 
                border-radius: 6px; 
            }}
        """)
        
        layout = QVBoxLayout(self)
        
        label = QLabel("➕\nDrop files to load")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {theme.primary_text}; font-size: 26px; font-weight: bold; border: none; background: transparent;")
        
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        
        self.hide()

class HubWindow(QMainWindow):
    def __init__(self, workspace):
        super().__init__()
        self.workspace = workspace
        self.setWindowTitle("EggSuite - Main Menu")
        self.resize(1000, 700)
        self.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg};")

        local_ini = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../settings.ini")
        settings_target = local_ini if os.path.exists(local_ini) else "BadgerLoop"
        self.settings = QSettings(settings_target, QSettings.Format.IniFormat) if os.path.exists(local_ini) else QSettings("BadgerLoop", "QtPlotter")

        self.open_apps = [] 

        # ==========================================
        # STACKED WIDGET ARCHITECTURE
        # ==========================================
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # --- PAGE 0: Main Menu ---
        self.main_page = QWidget()
        main_layout = QHBoxLayout(self.main_page)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(30)

        # --- LEFT PANEL: Active Workspace ---
        left_panel = QVBoxLayout()
        ws_title = QLabel("Active Workspace")
        ws_title.setStyleSheet("font-size: 20px; font-weight: bold;")
        left_panel.addWidget(ws_title)

        self.workspace_search = QLineEdit()
        self.workspace_search.setPlaceholderText("🔍 Search files...")
        self.workspace_search.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg}; border: 1px solid {theme.border}; padding: 5px; border-radius: 4px;")
        self.workspace_search.textChanged.connect(self._filter_workspace_tree)
        left_panel.addWidget(self.workspace_search)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderHidden(True)
        from PyQt6.QtWidgets import QAbstractItemView
        self.file_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_tree.setIndentation(15)
        
        scroll_css = f"""
            QScrollBar:horizontal {{ border: 1px solid {theme.border}; background: {theme.bg}; height: 14px; margin: 0px; border-radius: 6px; }}
            QScrollBar::handle:horizontal {{ background: {theme.primary_border}; min-width: 30px; border-radius: 5px; margin: 1px; }}
            QScrollBar::handle:horizontal:hover {{ background: {theme.primary_bg}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
            
            QTreeWidget::item {{ padding: 4px; }}
            QTreeWidget::item:selected {{ background-color: {theme.primary_bg}; color: {theme.primary_text}; border-radius: 4px; }}
        """
        self.file_tree.setStyleSheet(f"QTreeWidget {{ background-color: {theme.panel_bg}; border: 1px solid {theme.border}; border-radius: 6px; font-size: 14px; padding: 5px; outline: none; }} {scroll_css}")
        
        left_panel.addWidget(self.file_tree)

        # BUTTON STYLESHEETS
        primary_btn_style = f"""
            QPushButton {{ 
                font-weight: bold; background-color: {theme.primary_bg}; color: {theme.primary_text}; 
                padding: 8px; border: 1px solid {theme.primary_border}; border-radius: 4px; 
            }}
            QPushButton:hover {{ border: 1px solid {theme.primary_text}; }}
            QPushButton:disabled {{ background-color: transparent; color: #777777; border: 1px dashed #777777; }}
        """
        
        secondary_btn_style = f"""
            QPushButton {{ 
                padding: 8px; background-color: {theme.panel_bg}; border: 1px solid {theme.border}; 
                border-radius: 4px; color: {theme.fg}; 
            }}
            QPushButton:hover {{ background-color: {theme.primary_bg}; border: 1px solid {theme.primary_border}; color: {theme.primary_text}; }}
            QPushButton:disabled {{ background-color: transparent; color: #777777; border: 1px dashed #777777; }}
        """

        btn_h1 = QHBoxLayout()
        self.btn_load_file = QPushButton("📄 Load File")
        self.btn_load_file.setStyleSheet(secondary_btn_style) 
        self.btn_load_file.clicked.connect(self._load_data_file)
        
        self.btn_load_folder = QPushButton("📁 Load Folder")
        self.btn_load_folder.setStyleSheet(secondary_btn_style) 
        self.btn_load_folder.clicked.connect(self._load_data_folder)
        
        btn_h1.addWidget(self.btn_load_file)
        btn_h1.addWidget(self.btn_load_folder)
        left_panel.addLayout(btn_h1)

        self.btn_recent_files = QPushButton("🕒 Recent Files")
        self.btn_recent_files.setStyleSheet(secondary_btn_style)
        self.btn_recent_files.clicked.connect(self._open_recent_files_dialog)
        left_panel.addWidget(self.btn_recent_files)

        btn_h2 = QHBoxLayout()
        self.btn_remove = QPushButton("✖ Remove Selected")
        self.btn_remove.setStyleSheet(secondary_btn_style)
        self.btn_remove.clicked.connect(self._remove_selected_file)
        
        self.btn_merge_folder = QPushButton("🔗 Merge Folder")
        self.btn_merge_folder.setStyleSheet(secondary_btn_style)
        self.btn_merge_folder.setEnabled(False) 
        self.btn_merge_folder.clicked.connect(self._merge_selected_folder)
        
        btn_h2.addWidget(self.btn_remove)
        btn_h2.addWidget(self.btn_merge_folder)
        left_panel.addLayout(btn_h2)

        self.file_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)

        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setFixedWidth(300)
        main_layout.addWidget(left_widget)

        # --- RIGHT PANEL: App Grid ---
        right_panel = QVBoxLayout()
        
        header_lbl = QLabel("EggSuite")
        header_lbl.setStyleSheet(f"font-size: 36px; font-weight: bold; color: {theme.primary_text}; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;")
        right_panel.addWidget(header_lbl)
        
        EGG_FACTS = [
            "A standard chef's hat has 100 folds, representing 100 ways to cook an egg.",
            "The colour of an eggshell is determined purely by the breed of the hen.",
            "To tell if an egg is raw or hard-boiled, spin it. Raw eggs wobble, boiled ones spin cleanly.",
            "Eggs age more in one day at room temperature than in one week in the fridge.",
            "The stringy white bits keeping the yolk in the centre are called chalazae.",
            "As a hen ages, she lays larger eggs with much thinner shells.",
            "Kiwi birds lay the largest egg in relation to their body size of any bird.",
            "Ostrich eggs are the largest bird eggs, but the smallest in relation to the mother's size.",
            "Double-yolk eggs are typically laid by young hens whose reproductive systems haven't fully matured.",
            "The word 'yolk' derives from the Old English word 'geoloca', simply meaning 'yellow'.",
            "An average eggshell has up to 17,000 tiny microscopic pores over its surface.",
            "A hen turns her egg nearly 50 times a day to keep the yolk from sticking to the side.",
            "It takes a hen roughly 24 to 26 hours to produce a single egg.",
            "The UK consumes over 13 billion eggs every single year.",
            "Araucana hens are famous for laying natural pale blue or green eggs.",
            "Harriet, a hen from the UK, laid a record-breaking egg measuring 9.1 inches in diameter in 2010.",
            "Egg yolks are one of the few foods that naturally contain Vitamin D.",
            "If an egg sinks in a bowl of water, it is fresh. If it floats, it has gone bad.",
            "Blood spots in an egg do not mean it is fertilised; they are just a ruptured blood vessel.",
            "Cloudy egg whites are a sign that the egg is incredibly fresh.",
            "To peel a hard-boiled egg easily, plunge it into ice water immediately after cooking.",
            "The Guinness World Record for making an omelette is 427 in just 30 minutes.",
            "An eggshell is made almost entirely of calcium carbonate, the same material as chalk and limestone.",
            "The yolk and the white contain roughly the same amount of protein.",
            "Hens with white earlobes generally lay white eggs, whilst hens with red earlobes lay brown ones.",
            "A hen can lay unfertilised eggs without a cockerel being present.",
            "The thickest part of an eggshell is at the pointy end.",
            "Brown eggs are generally more expensive because the hens that lay them are larger and require more feed.",
            "A 'pullet' is a young hen under one year old, and their eggs are highly prized by pastry chefs.",
            "Eggs absorb odours easily because of their porous shells, which is why they are best kept in their cartons.",
            "The longest recorded flight of a tossed fresh egg without breaking is a staggering 98.51 metres.",
            "Quail eggs have a distinctly higher yolk-to-white ratio than chicken eggs, making them much richer in flavour.",
            "Fake eggs were once a serious counterfeit industry in the late 19th and early 20th centuries.",
            "The yolk colour is influenced entirely by a hen's diet; more marigold petals or maize means a deeper orange.",
            "To perfectly poach an egg, adding a splash of vinegar to the water helps coagulate the white faster.",
            "Hummingbird eggs can be as tiny as a baked bean.",
            "There is no nutritional difference whatsoever between brown and white eggs.",
            "A hen requires roughly 14 hours of daylight to trigger the egg-laying process.",
            "The phrase 'walking on eggshells' originated in the mid-19th century to describe acting with extreme caution.",
            "An egg will spin significantly faster if it is hard-boiled compared to a raw one because the liquid centre absorbs the momentum."
        ]
        
        random_fact = random.choice(EGG_FACTS)
        
        subtitle_lbl = QLabel(f"Select an application to begin.<br><br><span style='color: #888;'><i>{random_fact}</i></span>")
        subtitle_lbl.setWordWrap(True)
        subtitle_lbl.setStyleSheet("font-size: 14px; margin-bottom: 20px;")
        right_panel.addWidget(subtitle_lbl)

        grid = QGridLayout()
        grid.setSpacing(20)

        # Tile 1: Plotter
        self.tile_plot = AppTile("Plot & Statistics", "Visualize data, apply mathematical fits, and run topological analysis.", icon="📈")
        self.tile_plot.launch_requested.connect(self._launch_plot_app)
        grid.addWidget(self.tile_plot, 0, 0)

        # Tile 2: Inspector
        self.tile_inspect = AppTile("Data Inspector", "View raw arrays, sanitize anomalies, and edit dataset tables.", icon="🧮")
        self.tile_inspect.launch_requested.connect(self._launch_inspector_app)
        grid.addWidget(self.tile_inspect, 0, 1)

        # Tile 3: Settings
        self.tile_settings = AppTile("Global Settings", "Configure themes, hardware limits, and suite behavior.", icon="⚙️")
        self.tile_settings.launch_requested.connect(self._launch_settings_app)
        grid.addWidget(self.tile_settings, 1, 0)

        # --- NEW Tile 4: External Apps ---
        self.tile_plugins = AppTile("External Apps", "Browse and launch custom user-built plugins from the external_apps directory.", icon="🧩", show_toggle=False)
        # Popout flag is ignored for the browser; it's a built-in page.
        self.tile_plugins.launch_requested.connect(lambda _: self._show_app_browser())
        grid.addWidget(self.tile_plugins, 1, 1)
        # ---------------------------------

        right_panel.addLayout(grid)
        right_panel.addStretch()
        main_layout.addLayout(right_panel)

        self.stacked_widget.addWidget(self.main_page)

        # --- PAGE 1: External App Browser ---
        self._build_app_browser_ui()
        # ------------------------------------

        self.workspace.dataset_added.connect(self._refresh_file_tree)
        self.workspace.dataset_removed.connect(self._refresh_file_tree)
        
        self.setAcceptDrops(True)
        self.window_dimmer = WindowDimmer(self.stacked_widget)
        self.drop_overlay = DropOverlay(self.stacked_widget)

        geom = self.settings.value("hub_geometry")
        if geom: self.restoreGeometry(geom)
            
        state = self.settings.value("hub_state")
        if state: self.restoreState(state)
        
        self._setup_status_bar()
        
    def _build_app_browser_ui(self):
        """Constructs the elegant app browser page for external modules."""
        self.browser_page = QWidget()
        layout = QVBoxLayout(self.browser_page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        # --- Top Bar: Back Button, Title, Refresh & Create ---
        header_lay = QHBoxLayout()
        back_btn = QPushButton("🔙 Back to Hub")
        back_btn.setStyleSheet(f"""
            QPushButton {{
                font-weight: bold; font-size: 14px; padding: 8px 15px; 
                background-color: {theme.panel_bg}; color: {theme.fg}; 
                border: 1px solid {theme.border}; border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.primary_bg}; color: {theme.primary_text}; 
                border: 1px solid {theme.primary_border};
            }}
        """)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # --- ADDED: Back button now also refreshes the list in the background ---
        back_btn.clicked.connect(lambda: (self.stacked_widget.setCurrentIndex(0), self._scan_external_apps()))
        
        title = QLabel("External Applications")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {theme.primary_text};")

        # --- ADDED: Manual Refresh Button ---
        refresh_btn = QPushButton("🔄 Refresh List")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                font-weight: bold; font-size: 14px; padding: 8px 15px; 
                background-color: {theme.panel_bg}; color: {theme.fg}; 
                border: 1px solid {theme.border}; border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.primary_bg}; color: {theme.primary_text}; 
                border: 1px solid {theme.primary_border};
            }}
        """)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # --- FIX: Added a lambda to trigger both the scan and the toast ---
        refresh_btn.clicked.connect(lambda: (self._scan_external_apps(), self.show_toast("Refreshed", "The application list has been updated.")))
        
        create_btn = QPushButton("➕ Create New App")
        create_btn.setStyleSheet(f"""
            QPushButton {{
                font-weight: bold; font-size: 14px; padding: 8px 15px; 
                background-color: {theme.primary_bg}; color: {theme.primary_text}; 
                border: 1px solid {theme.primary_border}; border-radius: 4px;
            }}
            QPushButton:hover {{ border: 1px solid white; }}
        """)
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.clicked.connect(self._open_app_creator)
        
        header_lay.addWidget(back_btn)
        header_lay.addStretch()
        header_lay.addWidget(title)
        header_lay.addStretch()
        header_lay.addWidget(refresh_btn) # Add the refresh button
        header_lay.addWidget(create_btn)  
        # ---------------------------------------------------
        
        layout.addLayout(header_lay)
        layout.addSpacing(10)
        
        # ... (Keep the rest of your Search Bar and List Widget code exactly as it is) ...

        # Search Bar
        self.app_search_bar = QLineEdit()
        self.app_search_bar.setPlaceholderText("🔍 Search installed applications by name or description...")
        self.app_search_bar.setStyleSheet(f"""
            QLineEdit {{
                font-size: 14px; padding: 12px; background-color: {theme.panel_bg}; 
                color: {theme.fg}; border: 1px solid {theme.border}; border-radius: 6px;
            }}
            QLineEdit:focus {{ border: 1px solid {theme.primary_border}; }}
        """)
        self.app_search_bar.textChanged.connect(self._filter_app_list)
        layout.addWidget(self.app_search_bar)

        # Auto-Alphabetising List
        self.app_list = QListWidget()
        self.app_list.setSortingEnabled(True) # MAGIC: This keeps everything alphabetical!
        self.app_list.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Removes ugly dotted selection line
        self.app_list.setStyleSheet(f"""
            QListWidget {{
                background-color: transparent; border: none; outline: none;
            }}
            QListWidget::item {{
                background-color: transparent; border: none; 
                margin-bottom: 12px; padding: 0px;
            }}
            QListWidget::item:selected {{
                background-color: transparent;
            }}
            
            QScrollBar:vertical {{ border: none; background: transparent; width: 10px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: {theme.border}; min-height: 30px; border-radius: 5px; }}
            QScrollBar::handle:vertical:hover {{ background: {theme.primary_bg}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        layout.addWidget(self.app_list)

        self.stacked_widget.addWidget(self.browser_page)
        
        self._scan_external_apps()

    def _show_app_browser(self):
        """Transitions the UI smoothly to the External Apps browser."""
        self.app_search_bar.clear()
        # --- ADDED: Force a scan just before showing the page ---
        self._scan_external_apps() 
        self.stacked_widget.setCurrentIndex(1)
        
    def _open_app_creator(self):
        """Spawns the dialog and generates the boilerplate files if accepted."""
        import json
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        apps_dir = os.path.abspath(os.path.join(base_dir, "../../external_apps"))
        if not os.path.exists(apps_dir):
            os.makedirs(apps_dir)
            
        dlg = AppCreatorDialog(apps_dir, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            folder_path = os.path.join(apps_dir, data["folder"])
            
            try:
                # 1. Create Directory
                os.makedirs(folder_path)
                
                # 2. Write manifest.json
                # --- FIX: Use the data from the dialog! ---
                manifest = {
                    "name": data["name"],
                    "description": data["description"],
                    "author": data["author"],   # Changed from "User"
                    "version": data["version"], # Changed from "1.0"
                    "icon": data["icon"],
                    "entry_point": "main.py"
                }
                with open(os.path.join(folder_path, "manifest.json"), "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=4)
                    
                # 3. Write Boilerplate main.py
                # We dynamically inject their app name into the class name!
                class_name = data["name"].replace(" ", "").replace("-", "") + "Window"
                
                boilerplate = f'''import pyqtgraph as pg
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QLabel

class {class_name}(QMainWindow):
    def __init__(self, workspace, current_theme):
        super().__init__()
        self.workspace = workspace
        self.theme = current_theme
        
        self.setWindowTitle("{data["name"]}")
        self.resize(800, 600)
        self.setStyleSheet(f"background-color: {{self.theme.bg}}; color: {{self.theme.fg}};")
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        title = QLabel("Welcome to {data["name"]}!")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {{self.theme.primary_text}};")
        layout.addWidget(title)
        
        desc = QLabel("Your workspace memory is connected.\\nCheck the terminal to see how many datasets are currently loaded.")
        desc.setStyleSheet(f"font-size: 14px; color: {{self.theme.fg}};")
        layout.addWidget(desc)
        layout.addStretch()
        
        print(f"Plugin connected successfully. Loaded datasets: {{len(self.workspace.datasets)}}")

# --- MANDATORY ENTRY POINT ---
def run_app(workspace, current_theme):
    """Called by the EggSuite Hub when the user clicks 'Launch'."""
    window = {class_name}(workspace, current_theme)
    return window
'''
                with open(os.path.join(folder_path, "main.py"), "w", encoding="utf-8") as f:
                    f.write(boilerplate)
                    
                self.show_toast("App Created", f"'{data['name']}' has been scaffolded successfully!")
                
                self._scan_external_apps() 
                
            except Exception as e:
                CopyableErrorDialog("Creation Failed", "Failed to generate the plugin files.", str(e), self).exec()

    # --- FIX: Updated signature to accept author and version ---
    def _add_app_to_list(self, name, description, icon="🧩", author="Unknown", version="1.0", app_folder_path=None, entry_file=None):
        """Builds a beautiful, properly padded card for a single app."""
        from PyQt6.QtWidgets import QTextEdit
        from PyQt6.QtGui import QFontMetrics
        
        item = QListWidgetItem(self.app_list)
        
        widget = QFrame()
        widget.setStyleSheet(f"""
            QFrame {{ 
                background-color: {theme.panel_bg}; 
                border: 2px solid {theme.border}; 
                border-radius: 12px; 
            }}
            QFrame:hover {{ 
                background-color: {theme.primary_bg}; 
                border: 2px solid {theme.primary_border}; 
            }}
        """)
        
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(25, 20, 25, 20) 
        layout.setSpacing(20)
        
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 36px; padding-right: 15px; border: none; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignTop) 
        
        text_lay = QVBoxLayout()
        text_lay.setSpacing(6)
        
        # --- NEW: Title and Metadata Layout ---
        # We put the title and the author/version badge on the same horizontal line
        header_lay = QHBoxLayout()
        title_lbl = QLabel(name)
        title_lbl.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {theme.primary_text}; border: none; background: transparent;")
        
        # --- ADD THESE TWO LINES ---
        title_lbl.setObjectName("app_title")
        title_lbl.setProperty("original_text", name)
        # ---------------------------
        
        meta_lbl = QLabel(f"v{version} • by {author}")
        meta_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {theme.primary_bg}; border: none; background: transparent;")
        
        header_lay.addWidget(title_lbl)
        header_lay.addWidget(meta_lbl)
        header_lay.addStretch() # Push metadata to stick close to the title
        # --------------------------------------
        
        desc_box = QTextEdit()
        desc_box.setPlainText(description)
        desc_box.setReadOnly(True)
        desc_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        desc_box.setFrameStyle(QFrame.Shape.NoFrame)
        
        # --- ADD THESE TWO LINES ---
        desc_box.setObjectName("app_desc")
        desc_box.setProperty("original_text", description)
        # ---------------------------
        
        desc_box.setStyleSheet(f"""
            QTextEdit {{
                font-size: 13px; color: {theme.fg}; border: none; background: transparent;
            }}
            QScrollBar:vertical {{ 
                border: none; background: transparent; width: 8px; margin: 0px; 
            }}
            QScrollBar::handle:vertical {{ 
                background: {theme.border}; border-radius: 4px; 
            }}
            QScrollBar::handle:vertical:hover {{ background: {theme.primary_text}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        
        font = desc_box.font()
        font_metrics = QFontMetrics(font)
        line_height = font_metrics.lineSpacing()
        
        estimated_width = 600 
        chars_per_line = estimated_width / font_metrics.averageCharWidth()
        estimated_lines = max(1, len(description) / chars_per_line)
        
        calculated_height = int((estimated_lines + 1) * line_height)
        
        min_height = 25 
        max_height = 80 
        
        optimal_height = max(min_height, min(calculated_height, max_height))
        desc_box.setFixedHeight(optimal_height)
        
        if calculated_height > max_height:
            desc_box.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            desc_box.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # --- FIX: Add the new header layout instead of just the title ---
        text_lay.addLayout(header_lay)
        text_lay.addWidget(desc_box)
        text_lay.addStretch() 
        
        launch_btn = QPushButton("🚀 Launch App")
        launch_btn.setStyleSheet(f"""
            QPushButton {{
                font-weight: bold; font-size: 14px; padding: 12px 24px; 
                background-color: {theme.bg}; color: {theme.primary_text}; 
                border: 2px solid {theme.primary_border}; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {theme.primary_border}; color: white; }}
        """)
        launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if app_folder_path and entry_file:
            launch_btn.clicked.connect(lambda: self._launch_external_app(name, app_folder_path, entry_file))
        else:
            launch_btn.clicked.connect(lambda: self.show_toast("Mock Launch", f"Preparing to inject '{name}' into memory..."))
        
        layout.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_lay, stretch=1)
        layout.addWidget(launch_btn, alignment=Qt.AlignmentFlag.AlignVCenter) 
        
        widget.layout().update()
        widget.adjustSize()
        hint = widget.sizeHint()
        hint.setHeight(hint.height() + 15) 
        item.setSizeHint(hint)
        
        self.app_list.setItemWidget(item, widget)
        
    def _launch_external_app(self, app_name, folder_path, entry_file):
        """Dynamically imports and executes an external plugin."""
        main_path = os.path.join(folder_path, entry_file)
        
        # 1. Create a dynamic module specification
        spec = importlib.util.spec_from_file_location(f"plugin_{app_name.replace(' ', '_')}", main_path)
        plugin_module = importlib.util.module_from_spec(spec)
        
        # 2. Temporarily add the app's folder to the system path
        # This allows the app to import its own internal files cleanly
        sys.path.insert(0, folder_path)
        
        try:
            self.show_toast("Launching", f"Starting {app_name}...")
            
            # 3. Execute the code into memory
            spec.loader.exec_module(plugin_module)
            
            # 4. Fire the entry function, passing the live workspace!
            # We expect every plugin to have a 'run_app(workspace, theme)' function
            plugin_window = plugin_module.run_app(self.workspace, theme)
            
            # Keep a reference so it isn't garbage collected
            self.open_apps.append(plugin_window)
            plugin_window.show()
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            CopyableErrorDialog("Plugin Crash", f"Failed to launch {app_name}.", f"{e}\n\n{error_details}", self).exec()
        finally:
            # 5. Clean up the system path
            if folder_path in sys.path:
                sys.path.remove(folder_path)

    def _filter_app_list(self, text):
        """Hides apps that do not match and highlights the search term in the ones that do."""
        import re
        from PyQt6.QtWidgets import QLabel, QTextEdit
        
        query = text.strip()
        
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            widget = self.app_list.itemWidget(item)
            
            # 1. Find our specific text widgets using the names we gave them
            title_lbl = widget.findChild(QLabel, "app_title")
            desc_box = widget.findChild(QTextEdit, "app_desc")
            
            if not title_lbl or not desc_box:
                continue
                
            # 2. Retrieve the pure, unformatted original text
            orig_title = title_lbl.property("original_text")
            orig_desc = desc_box.property("original_text")
            
            # 3. If the search bar is empty, restore the original text and unhide
            if not query:
                title_lbl.setText(orig_title)
                desc_box.setPlainText(orig_desc)
                item.setHidden(False)
                continue
                
            # 4. Case-insensitive search
            match_title = query.lower() in orig_title.lower()
            match_desc = query.lower() in orig_desc.lower()
            
            if match_title or match_desc:
                item.setHidden(False)
                
                # --- HIGHLIGHT LOGIC ---
                # re.escape makes sure special characters in the search don't break the regex
                escaped_query = re.escape(query)
                # re.IGNORECASE finds the word regardless of capitalisation
                pattern = re.compile(f"({escaped_query})", re.IGNORECASE)
                
                # We wrap the matched word in a span using your primary theme colour
                highlight_span = f"<span style='background-color: {theme.primary_bg}; color: #ffffff;'>\\1</span>"
                
                # Apply to Title
                highlighted_title = pattern.sub(highlight_span, orig_title)
                title_lbl.setText(highlighted_title)
                
                # Apply to Description (Convert \n to <br> so HTML renders line breaks correctly)
                desc_html = orig_desc.replace('\n', '<br>')
                highlighted_desc = pattern.sub(highlight_span, desc_html)
                # Wrap the whole thing in a span to ensure the font size/colour isn't lost when switching to HTML mode
                desc_box.setHtml(f"<span style='color: {theme.fg}; font-size: 13px;'>{highlighted_desc}</span>")
                
            else:
                item.setHidden(True)

    def _scan_external_apps(self):
        """Scans the external_apps directory for valid plugins and builds their UI cards."""
        self.app_list.clear()
        
        # Define the path to the external_apps folder (relative to this script)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        apps_dir = os.path.abspath(os.path.join(base_dir, "../../external_apps"))
        
        if not os.path.exists(apps_dir):
            os.makedirs(apps_dir) # Create it if it doesn't exist
            return
            
        # Scan for folders containing a manifest.json
        for item in os.listdir(apps_dir):
            app_path = os.path.join(apps_dir, item)
            if not os.path.isdir(app_path): continue
                
            manifest_path = os.path.join(app_path, "manifest.json")
            if not os.path.exists(manifest_path): continue
                
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                    
                name = manifest.get("name", "Unknown App")
                desc = manifest.get("description", "No description provided.")
                icon = manifest.get("icon", "🧩")
                
                # --- NEW: Read Author and Version ---
                author = manifest.get("author", "Unknown Author")
                version = manifest.get("version", "1.0")
                # ------------------------------------
                
                entry_file = manifest.get("entry_point", "main.py")
                
                entry_path = os.path.join(app_path, entry_file)
                if not os.path.exists(entry_path):
                    print(f"Plugin Error: {name} is missing its entry point: {entry_file}")
                    continue
                    
                # --- FIX: Pass author and version to the UI builder ---
                self._add_app_to_list(name, desc, icon, author, version, app_path, entry_file)
                
            except Exception as e:
                print(f"Failed to load plugin manifest in {item}: {e}")

    def show_toast(self, title, message="", is_error=False):
        """Spawns a non-blocking notification in the bottom-right corner."""
        if hasattr(self, 'active_toast') and self.active_toast:
            try: self.active_toast.deleteLater()
            except: pass
            
        self.active_toast = ToastNotification(self, title, message, is_error=is_error)
        self.active_toast.show_toast()
        
    def closeEvent(self, event):
        """Saves the window size and position when the app is closed."""
        self.settings.setValue("hub_geometry", self.saveGeometry())
        self.settings.setValue("hub_state", self.saveState())
        super().closeEvent(event)
        
    def _setup_status_bar(self):
        self.statusBar().setStyleSheet(f"background-color: {theme.panel_bg}; color: {theme.fg}; border-top: 1px solid {theme.border};")
        
        self.ram_label = QLabel("RAM: -- MB")
        self.ram_label.setStyleSheet(f"color: {theme.primary_text}; font-weight: bold; font-family: Consolas, monospace; padding-right: 15px;")
        
        self.statusBar().addPermanentWidget(self.ram_label)
        self.statusBar().showMessage("Ready", 5000)
        
        self.ram_timer = QTimer(self)
        self.ram_timer.timeout.connect(self._update_ram_usage)
        self.ram_timer.start(2000) 
        self._update_ram_usage()

    def _update_ram_usage(self):
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_mb = process.memory_info().rss / (1024 * 1024)
            self.ram_label.setText(f"RAM: {mem_mb:.1f} MB")
        except ImportError:
            self.ram_label.setText("RAM: [psutil missing]")

    def _add_to_recents(self, filepath):
        import json
        recents_str = self.settings.value("recent_files", "[]")
        try: recents = json.loads(recents_str)
        except Exception: recents = []
        
        if filepath in recents: recents.remove(filepath)
        recents.insert(0, filepath)
        recents = recents[:5] 
        
        self.settings.setValue("recent_files", json.dumps(recents))

    def _open_recent_files_dialog(self):
        dlg = RecentFilesDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_path:
            self._process_dropped_items([dlg.selected_path])

    # ==========================================
    # FILE LOADING ENGINE
    # ==========================================
    def _load_data_file(self):
        last_dir = self.settings.value("last_load_directory", "")
        fnames, _ = QFileDialog.getOpenFileNames(self, "Open Data File(s)", last_dir, "All supported files (*.txt *.csv *.h5 *.hdf5);;CSV files (*.csv);;HDF5 files (*.h5 *.hdf5);;All files (*)")
        if not fnames: return
        
        self.settings.setValue("last_load_directory", os.path.dirname(fnames[0]))

        if len(fnames) == 1:
            is_badgerloop_actual, is_hdf5_actual = False, False
            detected_type = "CSV" 
            try:
                with open(fnames[0], 'rb') as f:
                    header_bytes = f.read(2000)
                    if header_bytes.startswith(b'\x89HDF\r\n\x1a\n'):
                        is_hdf5_actual, detected_type = True, "HDF5" 
                    else:
                        text_chunk = header_bytes.decode('utf-8', errors='ignore')
                        if "###OUTPUTS" in text_chunk or "###INPUTS" in text_chunk or "###DATA" in text_chunk:
                            is_badgerloop_actual, detected_type = True, "BadgerLoop" 
            except Exception: pass

            dlg = FileImportDialog(self, detected_type=detected_type)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                opts = dlg.get_options()
                
                if opts["type"] == "HDF5" and not is_hdf5_actual:
                    QMessageBox.critical(self, "Format Mismatch", "This file does not appear to be a valid HDF5 binary.")
                    return
                if opts["type"] == "CSV" and is_badgerloop_actual:
                    QMessageBox.critical(self, "Format Mismatch", "This appears to be a native BadgerLoop file. Please select 'BadgerLoop'.")
                    return
                    
                opts["filepath"] = fnames[0]
                self.load_queue = [opts]
            else:
                return 
                
        else:
            dlg = BatchImportDialog(fnames, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.load_queue = dlg.get_options_list()
            else:
                return

        if not hasattr(self, 'load_queue') or not self.load_queue:
            return

        self.progress_dialog = QProgressDialog("Initializing Load...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.show()

        self._process_next_file_in_queue()

    def _process_next_file_in_queue(self):
        if not hasattr(self, 'load_queue') or not self.load_queue:
            if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
                self.progress_dialog.accept()
                self.progress_dialog.deleteLater()
                self.progress_dialog = None
            return

        current_job = self.load_queue.pop(0)
        current_file = current_job["filepath"]
        
        if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
            self.progress_dialog.setLabelText(f"Loading: {os.path.basename(current_file)}")
            self.progress_dialog.setValue(0)

        self.loader_thread = DataLoaderThread(current_file, current_job)
        self.loader_thread.progress.connect(self._update_progress_ui)
        self.loader_thread.finished.connect(lambda ds, f=current_file: self._on_load_finished(f, ds))
        self.loader_thread.error.connect(self._on_load_error)
        self.loader_thread.start()

    def _load_data_folder(self):
        last_dir = self.settings.value("last_load_directory", "")
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder with CSVs", last_dir)
        if not folder_path: return
        
        self.settings.setValue("last_load_directory", folder_path)

        all_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.csv')]
        if not all_files:
            QMessageBox.warning(self, "No CSVs Found", "No CSV files were found in the selected folder.")
            return
        all_files.sort()

        dlg = FileImportDialog(self)
        dlg.file_type.setCurrentText("CSV")
        dlg.file_type.setEnabled(False) 
        
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        opts = dlg.get_options()
        
        delim = opts["delimiter"]
        if delim == "auto": delim = "," 
        
        signatures = {}
        errors = []
        
        self.progress_dialog = QProgressDialog("Scanning folder signatures...", "Cancel", 0, len(all_files), self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()
        
        for i, fname in enumerate(all_files):
            if self.progress_dialog.wasCanceled(): return
            self.progress_dialog.setValue(i)
            
            full_path = os.path.join(folder_path, fname)
            try:
                with open(full_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    first_line = ""
                    for line in f:
                        if line.strip() and not line.strip().startswith('#'):
                            first_line = line.strip()
                            break
                    
                    if not first_line:
                        errors.append((fname, "Empty or comments only"))
                        continue
                        
                    row = next(csv.reader([first_line], delimiter=delim))
                    sig = tuple(row) if opts["has_header"] else len(row)
                    
                    if sig not in signatures:
                        signatures[sig] = []
                    signatures[sig].append(full_path)
            except Exception as e:
                errors.append((fname, str(e)))

        self.progress_dialog.setValue(len(all_files))
        
        if not signatures:
            QMessageBox.critical(self, "Validation Failed", "No valid data found in the CSV files.")
            return

        target_sig = None
        if len(signatures) == 1:
            target_sig = list(signatures.keys())[0] 
        else:
            sel_dlg = TemplateSelectionDialog(signatures, self)
            if sel_dlg.exec() != QDialog.DialogCode.Accepted: return
            target_sig = sel_dlg.get_selected_signature()
            
        valid_files = signatures[target_sig]
        rejected_count = len(all_files) - len(valid_files)
        
        if rejected_count > 0:
            msg = f"Loaded {len(valid_files)} files matching the selected template.\nIgnored {rejected_count} mismatched/junk files.\n\n"
            if errors:
                msg += "Some files had read errors:\n"
                for r in errors[:5]: msg += f"- {r[0]}: {r[1]}\n"
                if len(errors) > 5: msg += "..."
            QMessageBox.information(self, "Validation Summary", msg)

        opts["type"] = "MultiCSV"
        opts["file_list"] = valid_files
        
        self.progress_dialog.setLabelText("Stitching files in memory...")
        self.progress_dialog.setValue(0)
        
        self.loader_thread = DataLoaderThread(folder_path, opts)
        self.loader_thread.progress.connect(self._update_progress_ui)
        self.loader_thread.finished.connect(lambda ds: self._on_load_finished(folder_path, ds))
        self.loader_thread.error.connect(self._on_load_error)
        self.loader_thread.start()
        
    def _update_overlay_positions(self):
        """Ensures the spotlight overlays perfectly track the UI layout."""
        if hasattr(self, 'window_dimmer') and self.centralWidget():
            self.window_dimmer.resize(self.centralWidget().size())
            
        # Only snap the drop overlay to the tree if we are actually looking at the main page
        if hasattr(self, 'drop_overlay') and hasattr(self, 'file_tree') and self.stacked_widget.currentIndex() == 0:
            top_left = self.file_tree.mapTo(self.centralWidget(), QPoint(0, 0))
            self.drop_overlay.setGeometry(top_left.x(), top_left.y(), self.file_tree.width(), self.file_tree.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay_positions()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._update_overlay_positions()
            self.window_dimmer.raise_()
            self.window_dimmer.show()
            
            # Only blur the file tree if we are on the main page
            if self.stacked_widget.currentIndex() == 0:
                blur = QGraphicsBlurEffect()
                blur.setBlurRadius(12)
                self.file_tree.setGraphicsEffect(blur)
                self.drop_overlay.raise_()
                self.drop_overlay.show()

    def dragLeaveEvent(self, event):
        self.file_tree.setGraphicsEffect(None)
        self.window_dimmer.hide()
        self.drop_overlay.hide()

    def dropEvent(self, event):
        self.file_tree.setGraphicsEffect(None)
        self.window_dimmer.hide()
        self.drop_overlay.hide()
        
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        
        if paths:
            self._process_dropped_items(paths)
            
    def _process_dropped_items(self, paths):
        # We can accept files globally, so if they dropped them while on the App page, 
        # instantly jump back to the Hub so they can see the load progress!
        if self.stacked_widget.currentIndex() != 0:
            self.stacked_widget.setCurrentIndex(0)
            
        loose_files = []
        folders = []
        valid_exts = ('.csv', '.txt', '.h5', '.hdf5')

        for p in paths:
            if os.path.isfile(p) and p.lower().endswith(valid_exts):
                loose_files.append(p)
            elif os.path.isdir(p):
                folders.append(p)

        if not loose_files and not folders:
            QMessageBox.warning(self, "Invalid Files", "No supported files (CSV, TXT, HDF5) or folders were detected in the drop.")
            return

        if not hasattr(self, 'load_queue') or self.load_queue is None:
            self.load_queue = []

        if loose_files:
            if len(loose_files) == 1:
                fname = loose_files[0]
                is_badgerloop_actual, is_hdf5_actual = False, False
                detected_type = "CSV" 
                try:
                    with open(fname, 'rb') as f:
                        header_bytes = f.read(2000)
                        if header_bytes.startswith(b'\x89HDF\r\n\x1a\n'):
                            is_hdf5_actual, detected_type = True, "HDF5"
                        else:
                            text_chunk = header_bytes.decode('utf-8', errors='ignore')
                            if "###OUTPUTS" in text_chunk or "###INPUTS" in text_chunk or "###DATA" in text_chunk:
                                is_badgerloop_actual, detected_type = True, "BadgerLoop"
                except Exception: pass

                dlg = FileImportDialog(self, detected_type=detected_type)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    opts = dlg.get_options()
                    if opts["type"] == "HDF5" and not is_hdf5_actual:
                        QMessageBox.critical(self, "Format Mismatch", "File is not a valid HDF5 binary.")
                    elif opts["type"] == "CSV" and is_badgerloop_actual:
                        QMessageBox.critical(self, "Format Mismatch", "This appears to be a native BadgerLoop file.")
                    else:
                        opts["filepath"] = fname
                        self.load_queue.append(opts)
            else:
                dlg = BatchImportDialog(loose_files, self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self.load_queue.extend(dlg.get_options_list())

        if folders:
            for folder_path in folders:
                all_files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)]
                if not all_files: continue
                all_files.sort()

                dlg = FileImportDialog(self)
                dlg.file_type.setCurrentText("CSV")
                dlg.file_type.setEnabled(False) 
                
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    opts = dlg.get_options()
                    delim = opts["delimiter"]
                    if delim == "auto": delim = "," 
                    
                    signatures = {}
                    for fname in all_files:
                        full_path = os.path.join(folder_path, fname)
                        try:
                            with open(full_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                                first_line = ""
                                for line in f:
                                    if line.strip() and not line.strip().startswith('#'):
                                        first_line = line.strip()
                                        break
                                if not first_line: continue
                                row = next(csv.reader([first_line], delimiter=delim))
                                sig = tuple(row) if opts["has_header"] else len(row)
                                if sig not in signatures: signatures[sig] = []
                                signatures[sig].append(full_path)
                        except Exception: pass

                    if not signatures: continue

                    target_sig = list(signatures.keys())[0]
                    if len(signatures) > 1:
                        sel_dlg = TemplateSelectionDialog(signatures, self)
                        if sel_dlg.exec() == QDialog.DialogCode.Accepted:
                            target_sig = sel_dlg.get_selected_signature()
                        else:
                            continue 
                            
                    opts["type"] = "MultiCSV"
                    opts["file_list"] = signatures[target_sig]
                    opts["filepath"] = folder_path 
                    self.load_queue.append(opts)

        if self.load_queue:
            if not hasattr(self, 'progress_dialog') or self.progress_dialog is None:
                self.progress_dialog = QProgressDialog("Initializing Load...", "Cancel", 0, 100, self)
                self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                self.progress_dialog.setCancelButton(None)
                self.progress_dialog.show()

            self._process_next_file_in_queue()

    def _update_progress_ui(self, percent, text):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setLabelText(text)
            self.progress_dialog.setValue(percent)

    def _on_load_finished(self, fname, dataset):
        if getattr(dataset, 'file_list', None) is not None and len(dataset.file_list) > 1:
            self.workspace.add_folder(fname, dataset)
        else:
            self.workspace.add_single_file(fname, dataset)
            
        self._add_to_recents(fname)
        self.statusBar().showMessage(f"Successfully loaded: {os.path.basename(fname)}", 5000)
            
        self._process_next_file_in_queue()

    def _on_load_error(self, err_msg):
        self.load_queue = []
        if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
            self.progress_dialog.accept()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
        CopyableErrorDialog("Loading Error", "An error occurred while loading the data.", err_msg, self).exec()

    def _remove_selected_file(self):
        selected_items = self.file_tree.selectedItems()
        if not selected_items:
            return

        paths_to_remove = []
        for item in selected_items:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path and path not in paths_to_remove:
                paths_to_remove.append(path)

        if not paths_to_remove:
            return

        if len(paths_to_remove) > 1:
            from PyQt6.QtWidgets import QMessageBox
            ans = QMessageBox.question(
                self, 
                "Confirm Batch Removal", 
                f"Are you sure you want to remove {len(paths_to_remove)} items from the workspace?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        for path in paths_to_remove:
            if hasattr(self.workspace, 'remove_dataset'):
                self.workspace.remove_dataset(path)

        self._refresh_file_tree()
        self.btn_remove.clearFocus()

    def _refresh_file_tree(self):
        self.file_tree.clear()
        
        for path, info in self.workspace.datasets.items():
            if info["parent"] is None:
                item = QTreeWidgetItem([info["name"]])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                
                if info["type"] == "folder":
                    item.setText(0, f"📁 {info['name']}")
                    for child_path in info["children"]:
                        child_info = self.workspace.get_item_info(child_path)
                        if child_info:
                            child_item = QTreeWidgetItem([f"📄 {child_info['name']}"])
                            child_item.setData(0, Qt.ItemDataRole.UserRole, child_path)
                            item.addChild(child_item)
                else:
                    item.setText(0, f"📄 {info['name']}")
                    
                self.file_tree.addTopLevelItem(item)
                
        self.file_tree.expandAll()
        
    def _filter_workspace_tree(self, text):
        query = text.lower()
        for i in range(self.file_tree.topLevelItemCount()):
            parent_item = self.file_tree.topLevelItem(i)
            parent_visible = query in parent_item.text(0).lower()
            
            any_child_visible = False
            for j in range(parent_item.childCount()):
                child = parent_item.child(j)
                if query in child.text(0).lower() or parent_visible:
                    child.setHidden(False)
                    any_child_visible = True
                else:
                    child.setHidden(True)
            
            parent_item.setHidden(not (parent_visible or any_child_visible))
        
    def _merge_selected_folder(self):
        item = self.file_tree.currentItem()
        if not item: return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        info = self.workspace.get_item_info(path)

        if not info or info["type"] != "folder": return

        dataset = info["dataset"]
        if not dataset: return

        parent_dir = os.path.dirname(path)
        default_name = f"Merged_{os.path.basename(path)}.csv"
        default_path = os.path.join(parent_dir, default_name)

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Concatenated CSV", default_path, "CSV files (*.csv)")
        if not save_path: return
        if not save_path.lower().endswith('.csv'): save_path += '.csv'

        try:
            self.progress_dialog = QProgressDialog("Concatenating files...", "Cancel", 0, len(dataset.file_list), self)
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.show()

            with open(save_path, 'w', encoding='utf-8-sig', newline='') as out_f:
                out_f.write("# Format: ConcatenatedCSV\n")
                out_f.write("# Is Mirror File: Yes\n")
                out_f.write(f"# Concatenated from folder: {os.path.basename(dataset.filename)}\n")

                header_line = ",".join([dataset.column_names[i] for i in range(dataset.num_inputs)])
                out_f.write(header_line + "\n")

                for i, filepath in enumerate(dataset.file_list):
                    if self.progress_dialog.wasCanceled():
                        out_f.close()
                        os.remove(save_path)
                        return
                        
                    self.progress_dialog.setValue(i)
                    out_f.write(f"# --- Sweep {i} (File: {os.path.basename(filepath)}) ---\n")

                    with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as in_f:
                        lines = in_f.readlines()

                    header_skipped = False
                    for line in lines:
                        clean_line = line.strip()
                        if not clean_line or clean_line.startswith("#"): continue
                        if not header_skipped:
                            header_skipped = True
                            continue
                        out_f.write(clean_line + "\n")

            self.progress_dialog.setValue(len(dataset.file_list))

            opts = {"type": "ConcatenatedCSV", "delimiter": ",", "has_header": True}
            
            self.progress_dialog.setLabelText("Loading concatenated file into memory...")
            self.progress_dialog.setValue(0)

            self.loader_thread = DataLoaderThread(save_path, opts)
            self.loader_thread.progress.connect(self._update_progress_ui)
            self.loader_thread.finished.connect(lambda ds: self._on_load_finished(save_path, ds))
            self.loader_thread.error.connect(self._on_load_error)
            self.loader_thread.start()

        except Exception as e:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.accept()
                self.progress_dialog.deleteLater()
                self.progress_dialog = None
            QMessageBox.critical(self, "Concatenation Error", f"Failed to concatenate files:\n{e}")
        
    def _on_tree_selection_changed(self):
        selected_items = self.file_tree.selectedItems()
        if len(selected_items) == 1:
            path = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
            info = self.workspace.get_item_info(path)

            if info and info["type"] == "folder":
                self.btn_merge_folder.setEnabled(True)
            else:
                self.btn_merge_folder.setEnabled(False)
        else:
            self.btn_merge_folder.setEnabled(False)

    # ==========================================
    # APP LAUNCHERS
    # ==========================================
    def _launch_plot_app(self, popout):
        if not self.workspace.datasets:
            QMessageBox.warning(self, "Workspace Empty", "Please load a Data File into the Workspace before launching the Plotter.")
            return

        active_file = None
        selected = self.file_tree.selectedItems()
        if selected:
            active_file = selected[0].data(0, Qt.ItemDataRole.UserRole)
        elif self.workspace.datasets:
            active_file = list(self.workspace.datasets.keys())[0]

        from apps.plot_and_stats.main_window import BadgerLoopQtGraph
        plot_window = BadgerLoopQtGraph(self.workspace, is_popout=popout, initial_file=active_file)
        
        if popout:
            plot_window.show()
            self.open_apps.append(plot_window)
        else:
            plot_window.home_requested.connect(self.show)
            self.hide()
            plot_window.show()
            self.open_apps.append(plot_window)
            
    def _launch_inspector_app(self, popout):
        if not self.workspace.datasets:
            QMessageBox.warning(self, "Workspace Empty", "Please load a Data File into the Workspace before launching the Inspector.")
            return

        inspector_window = DataInspectorWindow(self.workspace, is_popout=popout)
        
        if popout:
            inspector_window.show()
            self.open_apps.append(inspector_window)
        else:
            inspector_window.home_requested.connect(self.show)
            self.hide()
            inspector_window.show()
            self.open_apps.append(inspector_window)

    def _launch_settings_app(self, popout):
        from apps.settings.settings import PreferencesDialog
        
        dlg = PreferencesDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_settings = dlg.get_results()
            for key, val in new_settings.items():
                self.settings.setValue(key, val)
                
            self.show_toast("Settings Applied", "Global preferences updated successfully.")