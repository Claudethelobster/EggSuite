import os
import random
import csv
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QFrame, QFileDialog, QMessageBox, QProgressDialog,
    QDialog
)

from ui.theme import theme
from ui.custom_widgets import ToggleSwitch
from core.data_loader import DataLoaderThread
from ui.dialogs.data_mgmt import FileImportDialog, CopyableErrorDialog, TemplateSelectionDialog, BatchImportDialog

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

        # --- UPGRADED: Tree Widget ---
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderHidden(True)
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

        btn_h2 = QHBoxLayout()
        self.btn_remove = QPushButton("✖ Remove Selected")
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
        self.tile_inspect.launch_requested.connect(lambda popout: QMessageBox.information(self, "Coming Soon", "The Spreadsheet Data Inspector is currently in development!"))
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

    # ==========================================
    # FILE LOADING ENGINE
    # ==========================================
    def _load_data_file(self):
        fnames, _ = QFileDialog.getOpenFileNames(self, "Open Data File(s)", "", "All supported files (*.txt *.csv *.h5 *.hdf5);;CSV files (*.csv);;HDF5 files (*.h5 *.hdf5);;All files (*)")
        if not fnames: return

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
        # 1. Use getExistingDirectory so the OS lets them pick a folder!
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder with CSVs")
        if not folder_path: return

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
        item = self.file_tree.currentItem()
        if item:
            # We extract the exact filepath stored hidden in the UserRole
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self.workspace.remove_dataset(path)

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
        """Dynamically enables the merge button only if a parent folder is selected."""
        item = self.file_tree.currentItem()
        if not item:
            self.btn_merge_folder.setEnabled(False)
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        info = self.workspace.get_item_info(path)

        # The stylesheet will automatically un-grey the button when this is set to True
        if info and info["type"] == "folder":
            self.btn_merge_folder.setEnabled(True)
        else:
            self.btn_merge_folder.setEnabled(False)

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