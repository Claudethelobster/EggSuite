# apps/data_inspector/inspector_window.py
import os
import pandas as pd
import numpy as np
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QItemSelectionModel, pyqtSignal, QSettings
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QTableView, QMenu, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QSplitter, QTextEdit, QDialog
)
from PyQt6.QtGui import QAction
from ui.theme import theme
from ui.custom_widgets import ToastNotification
from apps.data_inspector.uncertainty_window import UncertaintyCalculatorDialog
from core.history_engine import EggCommand

class DropNaNCommand(EggCommand):
    """Encapsulates the Drop NaN logic so it can be safely undone and redone."""
    def __init__(self, inspector, col_name):
        super().__init__(f"Drop NaNs in '{col_name}'")
        self.inspector = inspector
        self.col_name = col_name
        self.dataset_path = inspector.current_dataset.filename
        
        # Capture the mask and the dropped rows before execution
        self.mask = self.inspector.df[col_name].isna().to_numpy()
        self.dropped_rows = self.inspector.df[self.mask].copy()
        self.dropped_count = len(self.dropped_rows)

    def execute(self):
        self.inspector.df = self.inspector.df.dropna(subset=[self.col_name]).reset_index(drop=True)
        self._sync()

    def undo(self):
        import pandas as pd
        import numpy as np
        
        current_data = self.inspector.df.to_numpy()
        dropped_data = self.dropped_rows.to_numpy()
        
        woven_data = np.empty((len(self.mask), current_data.shape[1]), dtype=object)
        
        woven_data[self.mask] = dropped_data
        woven_data[~self.mask] = current_data
        
        # Rebuild the DataFrame and let Pandas automatically fix the data types!
        self.inspector.df = pd.DataFrame(woven_data, columns=self.inspector.df.columns).infer_objects()
        self._sync()

    def _sync(self):
        """A helper method to ensure the disk, RAM, and UI all reflect the current DataFrame."""
        target_file = self.dataset_path
        
        # 1. Update Disk
        self.inspector.df.to_csv(target_file, index=False, encoding='utf-8-sig')
        
        # 2. Update RAM
        self.inspector.current_dataset.data = self.inspector.df.to_numpy()
        self.inspector.current_dataset.num_points = len(self.inspector.df)
        
        # 3. Update the UI Table
        self.inspector.table_model.set_dataframe(self.inspector.df)
        self.inspector.stats_label.setText(f"Rows: {len(self.inspector.df):,} | Columns: {len(self.inspector.df.columns)}")
        
        # Refresh the sidebar statistics if a column is currently selected
        idx = self.inspector.table_view.selectionModel().currentIndex()
        if idx.isValid():
            self.inspector._on_column_selected(idx, None)

class PandasTableModel(QAbstractTableModel):
    """ A lightning-fast bridge between a Pandas DataFrame and a PyQt TableView. """
    def __init__(self, df=pd.DataFrame()):
        super().__init__()
        self._df = df

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
            
        if role == Qt.ItemDataRole.DisplayRole:
            val = self._df.iat[index.row(), index.column()]
            if pd.isna(val):
                return ""
            if isinstance(val, (float, np.floating)):
                # Format floats cleanly, but leave integers/strings alone
                if val.is_integer():
                    return str(int(val))
                return f"{val:.6g}"
            return str(val)
            
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._df.columns[section])
            else:
                return str(section)
        return None
        
    def set_dataframe(self, df):
        self.beginResetModel()
        self._df = df
        self.endResetModel()


class DataInspectorWindow(QMainWindow):
    home_requested = pyqtSignal()
    def __init__(self, workspace=None, is_popout=False):
        super().__init__()
        self.workspace = workspace
        self.is_popout = is_popout  # Store the flag
        self.current_dataset = None
        self.df = pd.DataFrame()
        
        self.setWindowTitle("EggSuite - Data Inspector")
        self.resize(1200, 800)
        
        # --- UI SKELETON ---
        # 1. Fetch Display Mode from settings
        self.settings = QSettings("BadgerLoop", "QtPlotter") # Ensure settings access
        self.display_mode = self.settings.value("display_mode", "Windowed")
        
        # 2. Apply Window Flags for Borderless Mode
        if self.display_mode == "Borderless Windowed" and not self.is_popout:
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        self._build_menubar()
        self._build_toolbar()
        self._build_table_view()
        
        # --- WORKSPACE LISTENER ---
        if self.workspace:
            self.workspace.dataset_added.connect(self._on_workspace_updated)
            self.workspace.dataset_removed.connect(self._on_workspace_updated)
            self._on_workspace_updated()
        
        if not self.is_popout:
            if self.display_mode == "Fullscreen":
                self.showFullScreen()
            elif self.display_mode == "Borderless Windowed":
                self.showMaximized()
            else:
                self.showNormal()

    def _build_menubar(self):
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet(f"background-color: {theme.panel_bg}; color: {theme.fg}; border-bottom: 1px solid {theme.border};")

        # --- FIX: Elevate to ApplicationShortcut to prevent focus stealing ---
        self.edit_menu = menu_bar.addMenu("Edit")
        
        self.action_undo = QAction("Undo", self)
        self.action_undo.setShortcut("Ctrl+Z")
        self.action_undo.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut) # <--- UPDATED
        self.action_undo.triggered.connect(self._trigger_undo)
        self.addAction(self.action_undo)
        
        self.action_redo = QAction("Redo", self)
        self.action_redo.setShortcut("Ctrl+Y")
        self.action_redo.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut) # <--- UPDATED
        self.action_redo.triggered.connect(self._trigger_redo)
        self.addAction(self.action_redo)
        
        self.edit_menu.addAction(self.action_undo)
        self.edit_menu.addAction(self.action_redo)
        # -------------------------------------------------------------------

        # Build the 'Calculate' Menu
        self.calc_menu = menu_bar.addMenu("Calculate")

        # Add the Error Propagation Action
        self.action_error_prop = QAction("Error Propagation...", self)
        self.action_error_prop.setShortcut("Ctrl+E") 
        self.action_error_prop.setEnabled(False) # Disabled until a dataset is loaded
        self.action_error_prop.triggered.connect(self._open_uncertainty_calculator)
        
        self.calc_menu.addAction(self.action_error_prop)
        
    def _trigger_undo(self):
        """Safely calls undo on the currently active file's history tree."""
        if self.current_dataset and self.current_dataset.filename in self.workspace.datasets:
            try:
                history = self.workspace.datasets[self.current_dataset.filename]["history"]
                if history.undo():
                    self.show_toast("Undo Successful", "The previous action has been reverted.")
                else:
                    self.show_toast("History Empty", "There is nothing to undo.", is_error=True)
            except Exception as e:
                self.show_toast("Undo Error", str(e), is_error=True)

    def _trigger_redo(self):
        """Safely calls redo on the currently active file's history tree."""
        if self.current_dataset and self.current_dataset.filename in self.workspace.datasets:
            try:
                history = self.workspace.datasets[self.current_dataset.filename]["history"]
                if history.redo():
                    self.show_toast("Redo Successful", "The action has been reapplied.")
                else:
                    self.show_toast("Timeline End", "There is nothing to redo.", is_error=True)
            except Exception as e:
                self.show_toast("Redo Error", str(e), is_error=True)

    def _build_toolbar(self):
        toolbar_layout = QHBoxLayout()
        
        # --- NEW: Conditionally render the Home Button ---
        if not self.is_popout:
            self.btn_home = QPushButton("🏠 Home")
            self.btn_home.setStyleSheet(f"font-weight: bold; background-color: {theme.panel_bg}; color: {theme.fg}; padding: 6px 15px; border: 1px solid {theme.border}; border-radius: 4px;")
            self.btn_home.clicked.connect(self._go_home)
            toolbar_layout.addWidget(self.btn_home)
            
            # Add a little breathing room between Home and the file selector
            toolbar_layout.addSpacing(15)
        # ------------------------------------------------
        
        # --- WORKSPACE SWITCHER ---
        toolbar_layout.addWidget(QLabel("<b>Active File:</b>"))
        
        self.workspace_btn = QPushButton("No Workspace File Selected ▾")
        self.workspace_btn.setStyleSheet(f"text-align: left; background-color: {theme.panel_bg}; font-weight: bold; padding: 6px; border: 1px solid {theme.border}; border-radius: 4px;")
        
        self.workspace_menu = QMenu(self)
        self.workspace_menu.setStyleSheet(f"QMenu {{ background-color: {theme.panel_bg}; border: 1px solid {theme.border}; }}")
        
        self.workspace_tree = QTreeWidget()
        self.workspace_tree.setHeaderHidden(True)
        self.workspace_tree.setMinimumWidth(350)
        self.workspace_tree.setMinimumHeight(250)
        self.workspace_tree.setStyleSheet(f"QTreeWidget {{ background-color: {theme.panel_bg}; color: {theme.fg}; border: none; outline: none; font-size: 13px; }} QTreeWidget::item:selected {{ background-color: {theme.primary_bg}; color: {theme.primary_text}; }}")
        
        from PyQt6.QtWidgets import QWidgetAction
        tree_action = QWidgetAction(self)
        tree_action.setDefaultWidget(self.workspace_tree)
        self.workspace_menu.addAction(tree_action)
        
        self.workspace_btn.setMenu(self.workspace_menu)
        self.workspace_tree.itemClicked.connect(self._on_workspace_tree_clicked)
        
        toolbar_layout.addWidget(self.workspace_btn)
        # ------------------------------------------------
        
        # Stretch the layout to push everything to the left
        toolbar_layout.addStretch()

        # --- NEW: Smart Quit Button ---
        if not self.is_popout and self.display_mode in ["Borderless Windowed", "Fullscreen"]:
            self.btn_quit = QPushButton("✖")
            self.btn_quit.setFixedSize(30, 30)
            self.btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_quit.setToolTip("Exit Data Inspector")
            self.btn_quit.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: transparent; color: {theme.fg}; 
                    font-weight: bold; font-size: 16px; border: none; 
                }}
                QPushButton:hover {{ 
                    background-color: {theme.danger_bg}; color: {theme.danger_text}; 
                    border-radius: 4px; 
                }}
            """)
            self.btn_quit.clicked.connect(self.close)
            toolbar_layout.addWidget(self.btn_quit)
        # ------------------------------
        
        self.main_layout.addLayout(toolbar_layout)
        
    def _go_home(self):
        """Returns to the main Hub Dashboard and closes the Inspector."""
        self.home_requested.emit()
        self.close()
        
    def show_toast(self, title, message="", is_error=False):
        """Spawns a non-blocking notification in the bottom-right corner."""
        if hasattr(self, 'active_toast') and self.active_toast:
            try: self.active_toast.deleteLater()
            except: pass
            
        self.active_toast = ToastNotification(self, title, message, is_error=is_error)
        self.active_toast.show_toast()
        
    def _open_uncertainty_calculator(self):
        if not self.current_dataset or self.df.empty:
            return
            
        dlg = UncertaintyCalculatorDialog(self.current_dataset, self)
        
        # We will add the actual data handling logic inside this block later
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pass

    def _build_table_view(self):
        # 1. Create a resizable splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter, 1)

        # 2. LEFT SIDE: The Massive Table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table_view = QTableView()
        self.table_model = PandasTableModel(self.df)
        self.table_view.setModel(self.table_model)
        
        # Styling for massive data sets
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setStyleSheet(f"alternate-background-color: {theme.bg}; background-color: {theme.panel_bg}; color: {theme.fg}; gridline-color: {theme.border};")
        
        font = self.table_view.font()
        font.setFamily("Consolas, DejaVu Sans Mono, Menlo, Courier New")
        font.setPointSize(10)
        self.table_view.setFont(font)
        
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultSectionSize(120)
        header.setStyleSheet(f"QHeaderView::section {{ background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border}; padding: 4px; font-weight: bold; }}")
        
        v_header = self.table_view.verticalHeader()
        v_header.setStyleSheet(f"QHeaderView::section {{ background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border}; padding: 4px; }}")
        
        # Connect the column click listener!
        self.table_view.selectionModel().currentColumnChanged.connect(self._on_column_selected)
        
        table_layout.addWidget(self.table_view)
        
        # Bottom Stats Bar
        self.stats_label = QLabel("Rows: 0 | Columns: 0")
        self.stats_label.setStyleSheet(f"color: {theme.fg}; font-size: 11px;")
        table_layout.addWidget(self.stats_label)
        
        self.splitter.addWidget(table_container)

        # 3. RIGHT SIDE: The Inspector Sidebar
        self.sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 0, 0, 0)
        
        lbl = QLabel("<b>Column Diagnostics</b>")
        lbl.setStyleSheet(f"font-size: 16px; color: {theme.primary_text};")
        sidebar_layout.addWidget(lbl)
        
        self.col_stats_view = QTextEdit()
        self.col_stats_view.setReadOnly(True)
        self.col_stats_view.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg}; border: 1px solid {theme.border}; border-radius: 4px; font-family: Consolas, monospace; font-size: 13px; padding: 10px;")
        self.col_stats_view.setHtml("<span style='color: #888;'>Select a column header to view statistics.</span>")
        sidebar_layout.addWidget(self.col_stats_view)
        
        self.btn_drop_nan = QPushButton("🗑️ Drop NaNs in Column")
        self.btn_drop_nan.setStyleSheet(f"padding: 6px; border: 1px solid {theme.border}; border-radius: 4px;")
        self.btn_drop_nan.setEnabled(False)
        self.btn_drop_nan.clicked.connect(self._drop_nans)
        sidebar_layout.addWidget(self.btn_drop_nan)
        
        self.splitter.addWidget(self.sidebar)
        
        # Set default proportions (Table gets 80% of space, Sidebar gets 20%)
        self.splitter.setSizes([850, 350])
        
    def _drop_nans(self):
        from PyQt6.QtWidgets import QMessageBox
        import os
        import glob
        import re
        import shutil

        # 1. Figure out which column the user is currently looking at
        selected_indexes = self.table_view.selectionModel().selectedColumns()
        if not selected_indexes: return
        
        col_idx = selected_indexes[0].column()
        col_name = self.df.columns[col_idx]
        
        # 2. Confirm the destructive action
        ans = QMessageBox.question(
            self, 
            "Confirm Drop", 
            f"Are you sure you want to drop all rows where '{col_name}' is missing (NaN)?\n\nThis will remove the entire row across ALL columns to keep your data aligned.", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans != QMessageBox.StandardButton.Yes: return
        
        # 3. Create Mirror File path if we aren't already working on one
        fname = self.current_dataset.filename
        orig_name = os.path.basename(fname)
        directory = os.path.dirname(fname)
        
        target_file = fname
        if not orig_name.startswith("MIRROR_"):
            name_only, ext = os.path.splitext(orig_name)
            search_pattern = os.path.join(directory, f"MIRROR_{name_only}*{ext}")
            existing_mirrors = [os.path.basename(p) for p in glob.glob(search_pattern)]
            
            max_num = max([int(m.group(1)) for m in [re.search(r'\((\d+)\)', x) for x in existing_mirrors] if m] + [1 if f"MIRROR_{orig_name}" in existing_mirrors else 0])
            mirror_name = f"MIRROR_{name_only} ({max_num + 1}){ext}" if existing_mirrors else f"MIRROR_{orig_name}"
            target_file = os.path.join(directory, mirror_name)
            
            QMessageBox.information(self, "Mirror Created", f"To protect original data, a Mirror file has been automatically created:\n{mirror_name}")
            
            # --- CRITICAL FIX: Save the RAW, unedited data into the mirror file FIRST ---
            self.df.to_csv(target_file, index=False, encoding='utf-8-sig')
            
            import copy
            new_dataset = copy.deepcopy(self.current_dataset)
            new_dataset.filename = target_file
            
            if hasattr(self.workspace, 'add_single_file'):
                self.workspace.add_single_file(target_file, new_dataset)
            else:
                from core.history_engine import HistoryTree
                self.workspace.datasets[target_file] = {
                    "name": os.path.basename(target_file), "type": "file", 
                    "parent": None, "children": [], "dataset": new_dataset,
                    "history": HistoryTree()
                }
                
            self.current_dataset = new_dataset
            self.workspace_btn.setText(f"Active: {os.path.basename(target_file)} ▾")
            self.workspace.dataset_added.emit(target_file)
            
        # 4. DELEGATE TO THE COMMAND ENGINE
        # We do not manually call self.df.dropna() anymore. 
        # The command must do it, so it can snapshot the rows being destroyed!
        command = DropNaNCommand(self, col_name)
        
        # Prevent adding empty actions to the timeline if there were no NaNs to begin with
        if command.dropped_count == 0:
            self.show_toast("No Action Taken", f"No missing values found in '{col_name}'.")
            return
            
        # Execute the command (this automatically drops the rows and syncs the UI)
        self.workspace.datasets[target_file]["history"].execute_command(command)
        
        QMessageBox.information(self, "Success", f"Successfully dropped {command.dropped_count} corrupted rows.")
        
    def _on_column_selected(self, current, previous):
        if not current.isValid() or self.df.empty:
            self.col_stats_view.setHtml("<span style='color: #888;'>Select a column to view statistics.</span>")
            self.btn_drop_nan.setEnabled(False)
            return
            
        col_idx = current.column()
        col_name = self.df.columns[col_idx]
        col_data = self.df.iloc[:, col_idx]
        
        # Calculate stats instantly with Pandas
        total_rows = len(col_data)
        nan_count = col_data.isna().sum()
        nan_percent = (nan_count / total_rows) * 100 if total_rows > 0 else 0
        
        html = f"<b style='color: {theme.primary_text}; font-size: 14px;'>{col_name}</b><br><hr style='border: 0; border-top: 1px solid {theme.border};'>"
        html += f"<b>Data Type:</b> {col_data.dtype}<br>"
        
        # Colour code the missing values red if there are any
        if nan_count > 0:
            html += f"<b>Missing (NaN):</b> <span style='color: {theme.danger_text}; font-weight: bold;'>{nan_count:,} ({nan_percent:.1f}%)</span><br><br>"
        else:
            html += f"<b>Missing (NaN):</b> 0 (0%)<br><br>"
        
        if pd.api.types.is_numeric_dtype(col_data):
            # Use Pandas vectorised math to grab stats instantly
            html += f"<b>Minimum:</b> {col_data.min():.6g}<br>"
            html += f"<b>Maximum:</b> {col_data.max():.6g}<br>"
            html += f"<b>Mean:</b>&nbsp;&nbsp;&nbsp;&nbsp;{col_data.mean():.6g}<br>"
            html += f"<b>Std Dev:</b>&nbsp; {col_data.std():.6g}<br>"
        else:
            html += f"<b>Unique Values:</b> {col_data.nunique()}<br>"
            
        self.col_stats_view.setHtml(html)
        
        # Cast the NumPy boolean to a native Python boolean for PyQt6
        has_nans = bool(nan_count > 0)
        
        # Only enable the "Drop NaN" button if there are actually missing values
        self.btn_drop_nan.setEnabled(has_nans)
        
        if has_nans:
            self.btn_drop_nan.setStyleSheet(f"font-weight: bold; background-color: {theme.danger_bg}; color: {theme.danger_text}; border: 1px solid {theme.danger_border}; padding: 6px; border-radius: 4px;")
        else:
            self.btn_drop_nan.setStyleSheet(f"padding: 6px; background-color: {theme.panel_bg}; border: 1px solid {theme.border}; border-radius: 4px; color: {theme.fg};")

    # ==========================================
    # WORKSPACE SYNC ENGINE
    # ==========================================
    def _on_workspace_updated(self, filename=None):
        self.workspace_tree.blockSignals(True)
        self.workspace_tree.clear()
        
        for path, info in self.workspace.datasets.items():
            if info["parent"] is None:
                item = QTreeWidgetItem([f"📁 {info['name']}" if info["type"] == "folder" else f"📄 {info['name']}"])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                
                if info["type"] == "folder":
                    for child_path in info["children"]:
                        child_info = self.workspace.get_item_info(child_path)
                        if child_info:
                            child_item = QTreeWidgetItem([f"📄 {child_info['name']}"])
                            child_item.setData(0, Qt.ItemDataRole.UserRole, child_path)
                            item.addChild(child_item)
                            
                self.workspace_tree.addTopLevelItem(item)
                
        self.workspace_tree.expandAll()
        self.workspace_tree.blockSignals(False)

        # Auto-select if nothing is active
        if not self.current_dataset and self.workspace.datasets:
            first_item = self.workspace_tree.topLevelItem(0)
            if first_item:
                self._on_workspace_tree_clicked(first_item, 0)
        elif not self.workspace.datasets:
            self.workspace_btn.setText("No Workspace File Selected ▾")
            self._load_dataset_into_view(None)

    def _on_workspace_tree_clicked(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path: return
        
        self.workspace_menu.hide() 
        self.workspace_btn.setText(f"Active: {item.text(0).replace('📁 ', '').replace('📄 ', '')} ▾")
        
        info = self.workspace.get_item_info(path)
        if not info: return
        
        # Note: If it's a child file that hasn't been loaded, we might need the lazy-load logic here later.
        # For now, we assume the dataset exists in RAM.
        ds = self.workspace.get_dataset(path)
        self._load_dataset_into_view(ds)

    def _load_dataset_into_view(self, dataset):
        self.current_dataset = dataset
        
        if not dataset:
            self.df = pd.DataFrame()
            self.table_model.set_dataframe(self.df)
            if hasattr(self, 'stats_label'):
                self.stats_label.setText("Rows: 0 | Columns: 0")
            
            # Disable the menu item when no data is loaded
            if hasattr(self, 'action_error_prop'):
                self.action_error_prop.setEnabled(False)
            return

        # Dynamically build the column headers from the dataset's dictionary
        num_cols = dataset.num_inputs + getattr(dataset, 'num_outputs', 0)
        cols = [dataset.column_names.get(i, f"Column {i}") for i in range(num_cols)]
        
        # --- FIX: Safely route the data extraction based on the file format! ---
        data_array = None
        if hasattr(dataset, 'data') and dataset.data is not None:
            data_array = dataset.data
        elif hasattr(dataset, 'sweeps') and len(dataset.sweeps) > 0:
            data_array = dataset.sweeps[0].data
            
        if data_array is None:
            data_array = [] # Absolute failsafe for empty arrays
        # -----------------------------------------------------------------------
        
        # Convert the massive NumPy array into a Pandas DataFrame instantly
        self.df = pd.DataFrame(data_array, columns=cols)
        
        # Push it to the UI
        self.table_model.set_dataframe(self.df)
        if hasattr(self, 'stats_label'):
            self.stats_label.setText(f"Rows: {len(self.df):,} | Columns: {len(self.df.columns)}")
        
        # Enable the menu item now that data is ready
        if hasattr(self, 'action_error_prop'):
            self.action_error_prop.setEnabled(True)
            
        if hasattr(self, 'table_view'):
            self.table_view.clearSelection()