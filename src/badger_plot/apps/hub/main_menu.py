import os
import random
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QListWidget, QFrame, QFileDialog, QMessageBox, QProgressDialog,
    QCheckBox, QDialog
)

from ui.theme import theme
from core.data_loader import DataLoaderThread
from ui.dialogs.data_mgmt import FileImportDialog, CopyableErrorDialog

class AppTile(QFrame):
    """A custom clickable square tile for launching suite applications."""
    launch_requested = pyqtSignal(bool) # Emits True if 'Open in separate window' is checked

    def __init__(self, title, description, icon="📊", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{ background-color: {theme.panel_bg}; border: 2px solid {theme.border}; border-radius: 12px; }}
            QFrame:hover {{ background-color: {theme.primary_bg}; border: 2px solid {theme.primary_border}; }}
        """)
        self.setFixedSize(220, 220)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        
        # Top: Just the Icon now
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 40px; border: none; background: transparent;")
        layout.addWidget(icon_lbl)

        layout.addStretch()

        # Middle: Text Elements
        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; border: none; background: transparent; color: {theme.primary_text};")
        
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"font-size: 12px; border: none; background: transparent; color: {theme.fg};")
        
        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)
        
        layout.addSpacing(10)
        
        # Bottom: The Popout Checkbox (Native Styling ensures the tick is visible)
        self.popout_cb = QCheckBox("Open in separate window")
        self.popout_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popout_cb.setStyleSheet(f"""
            QCheckBox {{ font-size: 12px; font-weight: bold; color: {theme.fg}; background: transparent; border: none; }}
        """)
        layout.addWidget(self.popout_cb)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # If the user clicked the actual frame (and not the checkbox), launch the app!
            if not self.popout_cb.geometry().contains(event.pos()):
                self.launch_requested.emit(self.popout_cb.isChecked())
        super().mousePressEvent(event)


class HubWindow(QMainWindow):
    def __init__(self, workspace):
        super().__init__()
        self.workspace = workspace
        self.setWindowTitle("EggSuite - Main Menu")
        self.resize(1000, 700)
        self.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg};")

        # --- FIX: INITIALIZE QSETTINGS FOR THE HUB ---
        local_ini = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../settings.ini")
        settings_target = local_ini if os.path.exists(local_ini) else "BadgerLoop"
        self.settings = QSettings(settings_target, QSettings.Format.IniFormat) if os.path.exists(local_ini) else QSettings("BadgerLoop", "QtPlotter")
        # ---------------------------------------------

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

        self.file_list = QListWidget()
        
        # Stylized Horizontal Scrollbar
        scroll_css = f"""
            QScrollBar:horizontal {{ border: 1px solid {theme.border}; background: {theme.bg}; height: 14px; margin: 0px; border-radius: 6px; }}
            QScrollBar::handle:horizontal {{ background: {theme.primary_border}; min-width: 30px; border-radius: 5px; margin: 1px; }}
            QScrollBar::handle:horizontal:hover {{ background: {theme.primary_bg}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
        """
        self.file_list.setStyleSheet(f"QListWidget {{ background-color: {theme.panel_bg}; border: 1px solid {theme.border}; border-radius: 6px; font-size: 14px; padding: 5px; }} {scroll_css}")
        
        left_panel.addWidget(self.file_list)

        btn_h = QHBoxLayout()
        self.btn_load = QPushButton("➕ Load Data File")
        self.btn_load.setStyleSheet(f"font-weight: bold; background-color: {theme.primary_bg}; color: {theme.primary_text}; padding: 8px; border: 1px solid {theme.primary_border}; border-radius: 4px;")
        self.btn_load.clicked.connect(self._load_data_file)
        
        self.btn_remove = QPushButton("✖ Remove")
        self.btn_remove.setStyleSheet(f"padding: 8px; border: 1px solid {theme.border}; border-radius: 4px;")
        self.btn_remove.clicked.connect(self._remove_selected_file)

        btn_h.addWidget(self.btn_load)
        btn_h.addWidget(self.btn_remove)
        left_panel.addLayout(btn_h)

        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setFixedWidth(300)
        main_layout.addWidget(left_widget)

        # --- RIGHT PANEL: App Grid ---
        right_panel = QVBoxLayout()
        
        header_lbl = QLabel("EggSuite")
        header_lbl.setStyleSheet(f"font-size: 36px; font-weight: bold; color: {theme.primary_text}; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;")
        right_panel.addWidget(header_lbl)
        
        # --- RESTORED EGG FACTS ---
        # Replace this array with the full list from your old splash screen!
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
        # --------------------------

        grid = QGridLayout()
        grid.setSpacing(20)

        # Plotter Tile
        self.tile_plot = AppTile("Plot & Statistics", "Visualize data, apply mathematical fits, and run topological analysis.", icon="📈")
        self.tile_plot.launch_requested.connect(self._launch_plot_app)
        grid.addWidget(self.tile_plot, 0, 0)

        # Inspector Tile
        self.tile_inspect = AppTile("Data Inspector", "View raw arrays, sanitize anomalies, and edit dataset tables.", icon="🧮")
        self.tile_inspect.launch_requested.connect(lambda popout: QMessageBox.information(self, "Coming Soon", "The Spreadsheet Data Inspector is currently in development!"))
        grid.addWidget(self.tile_inspect, 0, 1)

        # Settings Tile
        self.tile_settings = AppTile("Global Settings", "Configure themes, hardware limits, and suite behavior.", icon="⚙️")
        self.tile_settings.launch_requested.connect(self._launch_settings_app)
        grid.addWidget(self.tile_settings, 1, 0)

        right_panel.addLayout(grid)
        right_panel.addStretch()
        main_layout.addLayout(right_panel)

        self.workspace.dataset_added.connect(self._refresh_file_list)
        self.workspace.dataset_removed.connect(self._refresh_file_list)

    # ==========================================
    # FILE LOADING ENGINE
    # ==========================================
    def _load_data_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open Data File", "", "All supported files (*.txt *.csv *.h5 *.hdf5);;CSV files (*.csv);;HDF5 files (*.h5 *.hdf5);;All files (*)")
        if not fname: return

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
                QMessageBox.critical(self, "Format Mismatch", "This file does not appear to be a valid HDF5 binary.")
                return
            if opts["type"] == "CSV" and is_badgerloop_actual:
                QMessageBox.critical(self, "Format Mismatch", "This appears to be a native BadgerLoop file. Please select 'BadgerLoop'.")
                return

            self.progress_dialog = QProgressDialog("Loading Data into Workspace...", "Cancel", 0, 100, self)
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setCancelButton(None)
            self.progress_dialog.show()

            self.loader_thread = DataLoaderThread(fname, opts)
            self.loader_thread.progress.connect(self._update_progress_ui)
            self.loader_thread.finished.connect(lambda ds: self._on_load_finished(fname, ds))
            self.loader_thread.error.connect(self._on_load_error)
            self.loader_thread.start()

    def _update_progress_ui(self, percent, text):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setLabelText(text)
            self.progress_dialog.setValue(percent)

    def _on_load_finished(self, fname, dataset):
        if hasattr(self, 'progress_dialog'): self.progress_dialog.accept()
        self.workspace.add_dataset(fname, dataset)

    def _on_load_error(self, err_msg):
        if hasattr(self, 'progress_dialog'): self.progress_dialog.accept()
        CopyableErrorDialog("Loading Error", "An error occurred while loading the data.", err_msg, self).exec()

    def _remove_selected_file(self):
        item = self.file_list.currentItem()
        if item:
            for fname in list(self.workspace.datasets.keys()):
                if os.path.basename(fname) == item.text():
                    self.workspace.remove_dataset(fname)
                    break

    def _refresh_file_list(self):
        self.file_list.clear()
        for filename in self.workspace.datasets.keys():
            self.file_list.addItem(os.path.basename(filename))


    # ==========================================
    # APP LAUNCHERS
    # ==========================================
    def _launch_plot_app(self, popout):
        if not self.workspace.datasets:
            QMessageBox.warning(self, "Workspace Empty", "Please load a Data File into the Workspace before launching the Plotter.")
            return

        from apps.plot_and_stats.main_window import BadgerLoopQtGraph
        plot_window = BadgerLoopQtGraph(self.workspace, is_popout=popout)
        
        if popout:
            plot_window.show()
            self.open_apps.append(plot_window)
        else:
            plot_window.home_requested.connect(self.show)
            self.hide()
            plot_window.show()
            self.open_apps.append(plot_window)

    def _launch_settings_app(self, popout):
        from apps.settings.settings import PreferencesDialog
        
        dlg = PreferencesDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_settings = dlg.get_results()
            for key, val in new_settings.items():
                self.settings.setValue(key, val)
                
            QMessageBox.information(self, "Settings Saved", "Preferences updated successfully.\nSome changes (like Theme or Global Scalers) may require restarting the Suite to fully take effect.")