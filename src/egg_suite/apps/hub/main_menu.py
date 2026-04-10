import os
import random
import csv
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QUrl, QPoint, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QFrame, QFileDialog, QMessageBox, QProgressDialog,
    QDialog, QGraphicsBlurEffect, QLineEdit
)

from ui.theme import theme
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

class AppTile(QFrame):
    launch_requested = pyqtSignal(bool) 

    def __init__(self, title, description, icon="📊", parent=None):
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
        
        self.popout_cb = ToggleSwitch("Open in separate window")
        
        font = self.popout_cb.font()
        font.setPixelSize(12)
        font.setBold(True)
        self.popout_cb.setFont(font)
        
        layout.addWidget(self.popout_cb)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.popout_cb.geometry().contains(event.pos()):
                self.launch_requested.emit(self.popout_cb.isChecked())
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

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(30)

        # --- LEFT PANEL: Active Workspace ---
        left_panel = QVBoxLayout()
        ws_title = QLabel("Active Workspace")
        ws_title.setStyleSheet("font-size: 20px; font-weight: bold;")
        left_panel.addWidget(ws_title)

        # --- NEW: Workspace Search Bar ---
        self.workspace_search = QLineEdit()
        self.workspace_search.setPlaceholderText("🔍 Search files...")
        self.workspace_search.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg}; border: 1px solid {theme.border}; padding: 5px; border-radius: 4px;")
        self.workspace_search.textChanged.connect(self._filter_workspace_tree)
        left_panel.addWidget(self.workspace_search)
        # ---------------------------------

        # --- UPGRADED: Tree Widget ---
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

        # --- BUTTON STYLESHEETS ---
        primary_btn_style = f"""
            QPushButton {{ 
                font-weight: bold; background-color: {theme.primary_bg}; color: {theme.primary_text}; 
                padding: 8px; border: 1px solid {theme.primary_border}; border-radius: 4px; 
            }}
            QPushButton:hover {{ 
                border: 1px solid {theme.primary_text}; 
            }}
            QPushButton:disabled {{ 
                background-color: transparent; color: #777777; border: 1px dashed #777777; 
            }}
        """
        
        secondary_btn_style = f"""
            QPushButton {{ 
                padding: 8px; background-color: {theme.panel_bg}; border: 1px solid {theme.border}; 
                border-radius: 4px; color: {theme.fg}; 
            }}
            QPushButton:hover {{ 
                background-color: {theme.primary_bg}; border: 1px solid {theme.primary_border}; color: {theme.primary_text}; 
            }}
            QPushButton:disabled {{ 
                background-color: transparent; color: #777777; border: 1px dashed #777777; 
            }}
        """

        # --- NEW FOLDER BUTTON ---
        btn_h1 = QHBoxLayout()
        self.btn_load_file = QPushButton("📄 Load File")
        self.btn_load_file.setStyleSheet(secondary_btn_style) # Swapped to secondary
        self.btn_load_file.clicked.connect(self._load_data_file)
        
        self.btn_load_folder = QPushButton("📁 Load Folder")
        self.btn_load_folder.setStyleSheet(secondary_btn_style) # Swapped to secondary
        self.btn_load_folder.clicked.connect(self._load_data_folder)
        
        btn_h1.addWidget(self.btn_load_file)
        btn_h1.addWidget(self.btn_load_folder)
        left_panel.addLayout(btn_h1)

        # --- NEW: RECENT FILES BUTTON ---
        self.btn_recent_files = QPushButton("🕒 Recent Files")
        self.btn_recent_files.setStyleSheet(secondary_btn_style)
        self.btn_recent_files.clicked.connect(self._open_recent_files_dialog)
        left_panel.addWidget(self.btn_recent_files)

        btn_h2 = QHBoxLayout()
        self.btn_remove = QPushButton("✖ Remove Selected")
        # ... [rest of existing code] ...
        self.btn_remove.setStyleSheet(secondary_btn_style)
        self.btn_remove.clicked.connect(self._remove_selected_file)
        
        # Keep the Merge button as primary so it boldly announces when it becomes active
        self.btn_merge_folder = QPushButton("🔗 Merge Folder")
        self.btn_merge_folder.setStyleSheet(secondary_btn_style)
        self.btn_merge_folder.setEnabled(False) 
        self.btn_merge_folder.clicked.connect(self._merge_selected_folder)
        
        btn_h2.addWidget(self.btn_remove)
        btn_h2.addWidget(self.btn_merge_folder)
        left_panel.addLayout(btn_h2)

        # Hook up a listener to the tree selection
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

        # Plotter Tile
        self.tile_plot = AppTile("Plot & Statistics", "Visualize data, apply mathematical fits, and run topological analysis.", icon="📈")
        self.tile_plot.launch_requested.connect(self._launch_plot_app)
        grid.addWidget(self.tile_plot, 0, 0)

        # Inspector Tile
        self.tile_inspect = AppTile("Data Inspector", "View raw arrays, sanitize anomalies, and edit dataset tables.", icon="🧮")
        self.tile_inspect.launch_requested.connect(self._launch_inspector_app)
        grid.addWidget(self.tile_inspect, 0, 1)

        # Settings Tile
        self.tile_settings = AppTile("Global Settings", "Configure themes, hardware limits, and suite behavior.", icon="⚙️")
        self.tile_settings.launch_requested.connect(self._launch_settings_app)
        grid.addWidget(self.tile_settings, 1, 0)

        right_panel.addLayout(grid)
        right_panel.addStretch()
        main_layout.addLayout(right_panel)

        self.workspace.dataset_added.connect(self._refresh_file_tree)
        self.workspace.dataset_removed.connect(self._refresh_file_tree)
        
        # --- NEW: Drag and Drop Spotlight Setup ---
        self.setAcceptDrops(True)
        self.window_dimmer = WindowDimmer(self.centralWidget())
        self.drop_overlay = DropOverlay(self.centralWidget())
        # ----------------------------------------

        # --- RESTORE SESSION MEMORY ---
        geom = self.settings.value("hub_geometry")
        if geom:
            self.restoreGeometry(geom)
            
        state = self.settings.value("hub_state")
        if state:
            self.restoreState(state)
        # ------------------------------
        
        # --- NEW: Initialise Telemetry ---
        self._setup_status_bar()
        
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
        # Note: We no longer trigger a UI refresh here since the UI is now a popup!

    def _open_recent_files_dialog(self):
        dlg = RecentFilesDialog(self.settings, self)
        # If the user clicks a file, we hijack the Drag and Drop router to load it perfectly!
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_path:
            self._process_dropped_items([dlg.selected_path])

    # ==========================================
    # FILE LOADING ENGINE
    # ==========================================
    def _load_data_file(self):
        # Read the last used directory (default to empty string if it doesn't exist yet)
        last_dir = self.settings.value("last_load_directory", "")
        
        # Pass last_dir into the dialogue
        fnames, _ = QFileDialog.getOpenFileNames(self, "Open Data File(s)", last_dir, "All supported files (*.txt *.csv *.h5 *.hdf5);;CSV files (*.csv);;HDF5 files (*.h5 *.hdf5);;All files (*)")
        if not fnames: return
        
        # Save the new directory for next time!
        self.settings.setValue("last_load_directory", os.path.dirname(fnames[0]))

        # --- ROUTE 1: Single File Selected (Classic Logic) ---
        if len(fnames) == 1:
            is_badgerloop_actual, is_hdf5_actual = False, False
            detected_type = "CSV" 
            try:
                with open(fnames[0], 'rb') as f:
                    header_bytes = f.read(2000)
                    if header_bytes.startswith(b'\x89HDF\r\n\x1a\n'):
                        is_hdf5_actual, detected_type = True, "HDF5" # <-- Fixed unpacking!
                    else:
                        text_chunk = header_bytes.decode('utf-8', errors='ignore')
                        if "###OUTPUTS" in text_chunk or "###INPUTS" in text_chunk or "###DATA" in text_chunk:
                            is_badgerloop_actual, detected_type = True, "BadgerLoop" # <-- Fixed unpacking!
            except Exception: pass

            dlg = FileImportDialog(self, detected_type=detected_type)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                opts = dlg.get_options()
                
                # Restore the original format mismatch shields
                if opts["type"] == "HDF5" and not is_hdf5_actual:
                    QMessageBox.critical(self, "Format Mismatch", "This file does not appear to be a valid HDF5 binary.")
                    return
                if opts["type"] == "CSV" and is_badgerloop_actual:
                    QMessageBox.critical(self, "Format Mismatch", "This appears to be a native BadgerLoop file. Please select 'BadgerLoop'.")
                    return
                    
                opts["filepath"] = fnames[0]
                self.load_queue = [opts]
            else:
                return # User cancelled
                
        # --- ROUTE 2: Multiple Files Selected (Batch Logic) ---
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

        # Pop the entire dictionary containing both the filepath and the options
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
        # Read the last used directory
        last_dir = self.settings.value("last_load_directory", "")
        
        # Pass last_dir into the dialogue
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder with CSVs", last_dir)
        if not folder_path: return
        
        # Save the new directory for next time!
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
        
        # 2. Signature Validation
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

        # 3. Template Selection (if mixed files found)
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

        # 4. Dispatch the Loader Thread
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
            
        if hasattr(self, 'drop_overlay') and hasattr(self, 'file_tree'):
            # Calculate exactly where the file_tree is currently sitting on the screen
            top_left = self.file_tree.mapTo(self.centralWidget(), QPoint(0, 0))
            self.drop_overlay.setGeometry(top_left.x(), top_left.y(), self.file_tree.width(), self.file_tree.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay_positions()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
            # Snap overlays to current layout positions
            self._update_overlay_positions()
            
            # 1. Grey out the entire window
            self.window_dimmer.raise_()
            self.window_dimmer.show()
            
            # 2. Blur ONLY the file tree underneath the dimmer
            blur = QGraphicsBlurEffect()
            blur.setBlurRadius(12)
            self.file_tree.setGraphicsEffect(blur)
            
            # 3. Illuminate the drop zone
            self.drop_overlay.raise_()
            self.drop_overlay.show()

    def dragLeaveEvent(self, event):
        # Cleanly remove the blur and hide the spotlights if they drag away
        self.file_tree.setGraphicsEffect(None)
        self.window_dimmer.hide()
        self.drop_overlay.hide()

    def dropEvent(self, event):
        # Snap the UI back to normal
        self.file_tree.setGraphicsEffect(None)
        self.window_dimmer.hide()
        self.drop_overlay.hide()
        
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        
        if paths:
            # Send the paths to the master Sorting Hat router!
            self._process_dropped_items(paths)
            
    def _process_dropped_items(self, paths):
        loose_files = []
        folders = []
        valid_exts = ('.csv', '.txt', '.h5', '.hdf5')

        # 1. Sort the drop contents securely
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

        # ==========================================
        # PHASE 1: UI GATHERING (The Sequential Approach)
        # ==========================================
        
        # A. Handle Loose Files
        if loose_files:
            if len(loose_files) == 1:
                # Re-use your Route 1 logic for a single file
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
                # Re-use your Route 2 logic for batches
                dlg = BatchImportDialog(loose_files, self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self.load_queue.extend(dlg.get_options_list())

        # B. Handle Folders
        if folders:
            # We process them sequentially. If they dropped 3 folders, they get 3 dialogs.
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
                    
                    # Quick signature scan
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
                            continue # User skipped this folder
                            
                    opts["type"] = "MultiCSV"
                    opts["file_list"] = signatures[target_sig]
                    opts["filepath"] = folder_path # We hijack filepath to store the folder name for the loader
                    self.load_queue.append(opts)

        # ==========================================
        # PHASE 2: EXECUTION
        # ==========================================
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
        # Register the file into the workspace memory bank
        if getattr(dataset, 'file_list', None) is not None and len(dataset.file_list) > 1:
            self.workspace.add_folder(fname, dataset)
        else:
            self.workspace.add_single_file(fname, dataset)
            
        # --- NEW: Save to Recent Files and notify user ---
        self._add_to_recents(fname)
        self.statusBar().showMessage(f"Successfully loaded: {os.path.basename(fname)}", 5000)
        # ------------------------------------------------
            
        # Automatically trigger the next file in the queue
        self._process_next_file_in_queue()

    def _on_load_error(self, err_msg):
        # Clear the queue so one corrupted file stops the batch from continuing
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

        # Collect all the unique paths the user highlighted
        paths_to_remove = []
        for item in selected_items:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path and path not in paths_to_remove:
                paths_to_remove.append(path)

        if not paths_to_remove:
            return

        # Optional: Ask for confirmation if they are deleting a massive batch
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

        # Tell the workspace to wipe them from memory
        for path in paths_to_remove:
            # Assuming your workspace has a remove_dataset or remove_item method
            if hasattr(self.workspace, 'remove_dataset'):
                self.workspace.remove_dataset(path)

        # Refresh the UI
        self._refresh_file_tree()
        self.btn_remove.clearFocus()

    def _refresh_file_tree(self):
        self.file_tree.clear()
        
        # Iterate over all registered paths in the workspace
        for path, info in self.workspace.datasets.items():
            
            # Only generate top-level UI items (files and parent folders)
            if info["parent"] is None:
                item = QTreeWidgetItem([info["name"]])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                
                if info["type"] == "folder":
                    item.setText(0, f"📁 {info['name']}")
                    
                    # Fetch all children belonging to this folder and nest them
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

        # Default save path: directory containing the folder, with a sensible name
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

                # Extract headers directly from the dataset memory
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

            # Instantly load the brand-new concatenated file into the workspace!
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
        """Dynamically enables the merge button only if a single parent folder is selected."""
        selected_items = self.file_tree.selectedItems()
        
        # If exactly one item is selected, check if it is a folder
        if len(selected_items) == 1:
            path = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
            info = self.workspace.get_item_info(path)

            if info and info["type"] == "folder":
                self.btn_merge_folder.setEnabled(True)
            else:
                self.btn_merge_folder.setEnabled(False)
        else:
            # Zero items, or multiple items selected: lock the button!
            self.btn_merge_folder.setEnabled(False)

    # ==========================================
    # APP LAUNCHERS
    # ==========================================
    def _launch_plot_app(self, popout):
        if not self.workspace.datasets:
            QMessageBox.warning(self, "Workspace Empty", "Please load a Data File into the Workspace before launching the Plotter.")
            return

        # --- NEW: Identify the Active File from the Tree ---
        active_file = None
        selected = self.file_tree.selectedItems()
        if selected:
            active_file = selected[0].data(0, Qt.ItemDataRole.UserRole)
        elif self.workspace.datasets:
            # Fallback to the first loaded dataset if nothing is highlighted
            active_file = list(self.workspace.datasets.keys())[0]
        # ---------------------------------------------------

        from apps.plot_and_stats.main_window import BadgerLoopQtGraph
        # Pass the active file directly into the constructor!
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

        # Pass the popout flag here!
        inspector_window = DataInspectorWindow(self.workspace, is_popout=popout)
        
        if popout:
            # Spawn independently, leave Hub visible (No Home Button)
            inspector_window.show()
            self.open_apps.append(inspector_window)
        else:
            # Wire up the return signal, hide Hub, show Inspector (Has Home Button)
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
                
            QMessageBox.information(self, "Settings Saved", "Preferences updated successfully.\nSome changes (like Theme or Global Scalers) may require restarting the Suite to fully take effect.")