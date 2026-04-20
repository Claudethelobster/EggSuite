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
    QDialog, QGraphicsBlurEffect, QLineEdit, QStackedWidget, QListWidget, QListWidgetItem, QFormLayout,
    QCompleter
)

from ui.theme import theme
from ui.custom_widgets import ToastNotification
from apps.data_inspector.inspector_window import DataInspectorWindow
from ui.custom_widgets import ToggleSwitch
from core.data_loader import DataLoaderThread
from core.plugin_manager import PluginManager
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
        
        self.author_edit = QLineEdit("User")
        self.version_edit = QLineEdit("1.0.0")
        
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("e.g., quantum_simulator")
        self.folder_edit.textChanged.connect(self._validate)
        
        # --- NEW: Dependency Staging Area ---
        self.dep_input = QLineEdit()
        self.dep_input.setPlaceholderText("e.g., scipy (press Enter to add)")
        
        # Fetch installed packages and attach the auto-completer
        installed_pkgs = self._get_installed_packages()
        completer = QCompleter(installed_pkgs, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.dep_input.setCompleter(completer)
        
        self.dep_add_btn = QPushButton("➕ Add")
        self.dep_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dep_add_btn.clicked.connect(self._add_dependency)
        self.dep_input.returnPressed.connect(self._add_dependency)
        
        dep_lay = QHBoxLayout()
        dep_lay.addWidget(self.dep_input)
        dep_lay.addWidget(self.dep_add_btn)
        
        self.dep_list = QListWidget()
        self.dep_list.setFixedHeight(80) # Keep it compact
        
        self.dep_remove_btn = QPushButton("➖ Remove Selected")
        self.dep_remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dep_remove_btn.clicked.connect(self._remove_dependency)
        
        # Styling
        input_style = f"background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border}; border-radius: 4px; padding: 6px;"
        btn_style = f"padding: 6px; background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border}; border-radius: 4px;"
        
        self.name_edit.setStyleSheet(input_style)
        self.desc_edit.setStyleSheet(input_style)
        self.icon_edit.setStyleSheet(input_style)
        self.author_edit.setStyleSheet(input_style)
        self.version_edit.setStyleSheet(input_style)
        self.folder_edit.setStyleSheet(input_style)
        self.dep_input.setStyleSheet(input_style)
        self.dep_list.setStyleSheet(f"background-color: {theme.bg}; color: {theme.fg}; border: 1px solid {theme.border}; border-radius: 4px;")
        self.dep_add_btn.setStyleSheet(btn_style)
        self.dep_remove_btn.setStyleSheet(btn_style)
        
        # Add to form
        form.addRow("App Name:", self.name_edit)
        form.addRow("Description:", self.desc_edit)
        form.addRow("Icon (Emoji):", self.icon_edit)
        form.addRow("Author:", self.author_edit)
        form.addRow("Version:", self.version_edit)
        form.addRow("Folder Name:", self.folder_edit)
        form.addRow("Dependencies:", dep_lay)
        form.addRow("", self.dep_list)
        form.addRow("", self.dep_remove_btn)
        # ------------------------------------
        
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
        # Extract the list items
        dependencies = [self.dep_list.item(i).text() for i in range(self.dep_list.count())]
        
        return {
            "name": self.name_edit.text().strip(),
            "description": self.desc_edit.text().strip() or "A custom EggSuite plugin.",
            "icon": self.icon_edit.text().strip() or "🧩",
            "author": self.author_edit.text().strip() or "Unknown", 
            "version": self.version_edit.text().strip() or "1.0.0",   
            "folder": self.folder_edit.text(),
            "dependencies": dependencies # <--- ADD THIS TO THE RETURN DICT
        }

    def _auto_fill_folder(self, text):
        # Only auto-fill if the user hasn't manually modified the folder box yet
        if not self.folder_edit.isModified():
            clean_name = text.lower().strip()
            clean_name = re.sub(r'[^a-z0-9_]', '_', clean_name) # Strip invalid chars
            clean_name = re.sub(r'_+', '_', clean_name)         # Remove double underscores
            self.folder_edit.setText(clean_name)
        self._validate()
        
    def _get_installed_packages(self):
        """Silently fetches a list of all installed Python libraries for the completer."""
        try:
            # We use a set comprehension to strip out duplicates
            return sorted(list({dist.metadata['Name'] for dist in importlib.metadata.distributions() if dist.metadata['Name']}))
        except Exception:
            return [] # Fallback to empty list if importlib fails, user can still type manually

    def _add_dependency(self):
        """Moves text from the input box into the staging list."""
        dep = self.dep_input.text().strip()
        if not dep:
            return
            
        # Prevent duplicates in the list
        existing = [self.dep_list.item(i).text() for i in range(self.dep_list.count())]
        if dep not in existing:
            self.dep_list.addItem(dep)
            
        self.dep_input.clear()

    def _remove_dependency(self):
        """Removes the highlighted dependency from the staging list."""
        for item in self.dep_list.selectedItems():
            self.dep_list.takeItem(self.dep_list.row(item))

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

    def __init__(self, title, description, icon="📊", show_toggle=True, unpin_callback=None, parent=None):
        super().__init__(parent)
        from PyQt6.QtGui import QFontMetrics
        
        self.setStyleSheet(f"""
            QFrame {{ background-color: {theme.panel_bg}; border: 2px solid {theme.border}; border-radius: 12px; }}
            QFrame:hover {{ background-color: {theme.primary_bg}; border: 2px solid {theme.primary_border}; }}
        """)
        self.setFixedSize(220, 220)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.full_description = description # Save the full text for the pop-up

        layout = QVBoxLayout(self)
        
        # --- Top Row (Icon & Unpin) ---
        top_lay = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 40px; border: none; background: transparent;")
        top_lay.addWidget(icon_lbl)
        top_lay.addStretch()
        
        if unpin_callback:
            unpin_btn = QPushButton("📌 Unpin")
            unpin_btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 10px; font-weight: bold; color: {theme.fg};
                    background-color: transparent; border: 1px solid {theme.border}; border-radius: 4px; padding: 4px;
                }}
                QPushButton:hover {{ background-color: {theme.danger_border}; color: white; border: 1px solid red; }}
            """)
            unpin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            unpin_btn.clicked.connect(unpin_callback)
            top_lay.addWidget(unpin_btn, alignment=Qt.AlignmentFlag.AlignTop)
            
        layout.addLayout(top_lay)
        layout.addStretch()

        # --- Title and Info Button Row ---
        title_lay = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; border: none; background: transparent; color: {theme.primary_text};")
        title_lay.addWidget(title_lbl, stretch=1)
        
        # Build the info button but hide it by default
        self.info_btn = QPushButton("ℹ️")
        self.info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_btn.setStyleSheet("border: none; background: transparent; font-size: 16px;")
        self.info_btn.clicked.connect(self._show_info_popup)
        self.info_btn.hide() 
        title_lay.addWidget(self.info_btn, alignment=Qt.AlignmentFlag.AlignTop)
        
        layout.addLayout(title_lay)
        
        # --- Description & Dynamic Truncation ---
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"font-size: 12px; border: none; background: transparent; color: {theme.fg};")
        
        # Mathematically calculate if the text will fit inside ~3 lines (approx 45 pixels)
        font_metrics = desc_lbl.fontMetrics()
        target_width = 190 # 220px tile width minus margins
        rect = font_metrics.boundingRect(0, 0, target_width, 1000, Qt.TextFlag.TextWordWrap, description)
        
        if rect.height() > 45: 
            # The text is too long! Reveal the info button.
            self.info_btn.show()
            
            # Chop the string down until it fits the boundary
            short_desc = description
            while font_metrics.boundingRect(0, 0, target_width, 1000, Qt.TextFlag.TextWordWrap, short_desc + "...").height() > 45 and len(short_desc) > 0:
                short_desc = short_desc[:-5] # Chop 5 chars at a time for efficiency
            desc_lbl.setText(short_desc.strip() + "...")
            
        layout.addWidget(desc_lbl)
        layout.addSpacing(10)
        
        # --- Bottom Toggle ---
        self.popout_cb = None
        if show_toggle:
            self.popout_cb = ToggleSwitch("Open in separate window")
            font = self.popout_cb.font()
            font.setPixelSize(12)
            font.setBold(True)
            self.popout_cb.setFont(font)
            layout.addWidget(self.popout_cb)
        else:
            layout.addSpacing(24)

    def _show_info_popup(self):
        """Spawns a styled dialog showing the complete application description."""
        msg = QMessageBox(self)
        msg.setWindowTitle("App Information")
        msg.setText(self.full_description)
        # Apply the suite theme to the popup
        msg.setStyleSheet(f"""
            QMessageBox {{ background-color: {theme.bg}; color: {theme.fg}; }}
            QLabel {{ color: {theme.fg}; font-size: 13px; }}
            QPushButton {{
                padding: 6px 15px; background-color: {theme.panel_bg}; 
                color: {theme.fg}; border: 1px solid {theme.border}; border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {theme.primary_bg}; color: {theme.primary_text}; }}
        """)
        msg.exec()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Safely catch clicks so they don't trigger a launch if clicking a button
            child = self.childAt(event.pos())
            if isinstance(child, QPushButton) or (self.popout_cb and self.popout_cb.geometry().contains(event.pos())):
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

        # --- RIGHT PANEL: Scrollable App Grid ---
        right_panel = QVBoxLayout()
        
        header_lay = QHBoxLayout()
        header_lbl = QLabel("EggSuite")
        header_lbl.setStyleSheet(f"font-size: 36px; font-weight: bold; color: {theme.primary_text}; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;")
        header_lay.addWidget(header_lbl)
        header_lay.addStretch()
        
        # --- NEW: The dedicated External Apps button ---
        self.btn_external_apps = QPushButton("🧩 Browse Plugins")
        self.btn_external_apps.setStyleSheet(f"""
            QPushButton {{
                font-weight: bold; font-size: 14px; padding: 10px 20px; 
                background-color: {theme.panel_bg}; color: {theme.primary_text}; 
                border: 2px solid {theme.primary_border}; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {theme.primary_bg}; }}
        """)
        self.btn_external_apps.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_external_apps.clicked.connect(self._show_app_browser)
        header_lay.addWidget(self.btn_external_apps, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        right_panel.addLayout(header_lay)
        
        EGG_FACTS = [
            "A standard chef's hat has 100 folds, representing 100 ways to cook an egg.",
            "The colour of an eggshell is determined purely by the breed of the hen."
            # (You can leave your big list of facts here, I've truncated it for brevity!)
        ]
        random_fact = random.choice(EGG_FACTS)
        
        subtitle_lbl = QLabel(f"Select an application to begin.<br><br><span style='color: #888;'><i>{random_fact}</i></span>")
        subtitle_lbl.setWordWrap(True)
        subtitle_lbl.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
        right_panel.addWidget(subtitle_lbl)

        # --- NEW: Scroll Area for Apps ---
        from PyQt6.QtWidgets import QScrollArea
        self.app_scroll_area = QScrollArea()
        self.app_scroll_area.setWidgetResizable(True)
        self.app_scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.app_grid_container = QWidget()
        self.app_grid_container.setStyleSheet("background: transparent;")
        self.app_grid_layout = QGridLayout(self.app_grid_container)
        self.app_grid_layout.setSpacing(20)
        self.app_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.app_scroll_area.setWidget(self.app_grid_container)
        right_panel.addWidget(self.app_scroll_area, stretch=1)
        
        main_layout.addLayout(right_panel)
        
        # Populate the grid initially
        self._refresh_main_app_grid()

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
        
    def _refresh_main_app_grid(self):
        """Clears and redraws the scrollable main menu grid, including pinned apps."""
        # Clear existing tiles
        while self.app_grid_layout.count():
            item = self.app_grid_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        apps_to_draw = []
        
        # 1. Native Apps (Always present)
        plot_tile = AppTile("Plot & Statistics", "Visualize data, apply mathematical fits, and run topological analysis.", icon="📈")
        plot_tile.launch_requested.connect(self._launch_plot_app)
        apps_to_draw.append(plot_tile)
        
        inspect_tile = AppTile("Data Inspector", "View raw arrays, sanitize anomalies, and edit dataset tables.", icon="🧮")
        inspect_tile.launch_requested.connect(self._launch_inspector_app)
        apps_to_draw.append(inspect_tile)
        
        settings_tile = AppTile("Global Settings", "Configure themes, hardware limits, and suite behavior.", icon="⚙️")
        settings_tile.launch_requested.connect(self._launch_settings_app)
        apps_to_draw.append(settings_tile)
        
        # 2. External Pinned Apps
        base_dir = os.path.dirname(os.path.abspath(__file__))
        apps_dir = os.path.abspath(os.path.join(base_dir, "../../external_apps"))
        plugins = PluginManager.scan_plugins(apps_dir)
        
        for p in plugins:
            if p.get("pinned", False):
                # We use a lambda default argument (folder=p["folder_path"]) to prevent late-binding loop bugs
                unpin_func = lambda _, folder=p["folder_path"]: self._toggle_pin(folder, False)
                
                custom_tile = AppTile(
                    title=p["name"], 
                    description=p["description"], 
                    icon=p["icon"], 
                    unpin_callback=unpin_func
                )
                
                # Check for missing dependencies so we don't let them launch broken pinned apps
                if p.get("missing_deps"):
                    custom_tile.setEnabled(False)
                    custom_tile.setToolTip(f"Missing dependencies: {', '.join(p['missing_deps'])}")
                    custom_tile.setStyleSheet(f"QFrame {{ background-color: {theme.panel_bg}; border: 2px dashed #777; opacity: 0.5; }}")
                else:
                    launch_func = lambda popout, n=p["name"], f=p["folder_path"], e=p["entry_file"]: self._launch_external_app(n, f, e)
                    custom_tile.launch_requested.connect(launch_func)
                    
                apps_to_draw.append(custom_tile)
                
        # 3. Draw them into the grid, wrapping every 3 columns
        columns = 3
        for index, tile in enumerate(apps_to_draw):
            row = index // columns
            col = index % columns
            self.app_grid_layout.addWidget(tile, row, col)

    def _toggle_pin(self, folder_path, state):
        """Changes the pin state in the JSON and instantly refreshes both UIs."""
        if PluginManager.set_pinned_state(folder_path, state):
            self._refresh_main_app_grid()
            if self.stacked_widget.currentIndex() == 1:
                self._scan_external_apps() # Refresh the browser if we are looking at it
            self.show_toast("Success", "App pinned to Hub." if state else "App unpinned from Hub.")
        
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
                manifest = {
                    "name": data["name"],
                    "description": data["description"],
                    "author": data["author"],
                    "version": data["version"],
                    "icon": data["icon"],
                    "entry_point": "main.py",
                    "dependencies": data["dependencies"] # <--- WRITE IT TO THE JSON
                }
                with open(os.path.join(folder_path, "manifest.json"), "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=4)
                    
                # 3. Write Boilerplate main.py
                class_name = data["name"].replace(" ", "").replace("-", "") + "Window"
                
                boilerplate = f'''import pyqtgraph as pg
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QLabel

class {class_name}(QMainWindow):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.colours = api.get_theme_colours()
        
        self.setWindowTitle("{data["name"]}")
        self.resize(800, 600)
        
        # Apply the EggSuite theme securely via the API
        self.setStyleSheet(f"background-color: {{self.colours['bg']}}; color: {{self.colours['fg']}};")
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        title = QLabel("Welcome to {data["name"]}!")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {{self.colours['primary_text']}};")
        layout.addWidget(title)
        
        desc = QLabel("Your plugin is connected to EggSuite via the secure API.\\nCheck the terminal to see your loaded datasets.")
        desc.setStyleSheet(f"font-size: 14px; color: {{self.colours['fg']}};")
        layout.addWidget(desc)
        layout.addStretch()
        
        # Test the API
        loaded_files = self.api.get_dataset_names()
        print(f"Plugin connected safely. Loaded datasets: {{loaded_files}}")
        
        # Test the Toast notification API
        self.api.show_notification("Plugin Ready", "The API connection is working smoothly.")

# --- MANDATORY ENTRY POINT ---
def run_app(api):
    """Called by the EggSuite PluginManager when the user clicks 'Launch'."""
    window = {class_name}(api)
    return window
'''
                with open(os.path.join(folder_path, "main.py"), "w", encoding="utf-8") as f:
                    f.write(boilerplate)
                    
                self.show_toast("App Created", f"'{data['name']}' has been scaffolded successfully!")
                
                self._scan_external_apps() 
                
            except Exception as e:
                CopyableErrorDialog("Creation Failed", "Failed to generate the plugin files.", str(e), self).exec()

    # --- FIX: Added missing_deps parameter ---
    def _add_app_to_list(self, name, description, icon="🧩", author="Unknown", version="1.0", app_folder_path=None, entry_file=None, missing_deps=None, pinned=False):
        if missing_deps is None:
            missing_deps = []
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
        
        text_lay.addLayout(header_lay)
        text_lay.addWidget(desc_box)
        
        # --- NEW: Dependency Warning Label ---
        if missing_deps:
            warning_lbl = QLabel(f"⚠️ Missing Requirements: {', '.join(missing_deps)}")
            # Assuming your theme has a danger_text colour. If not, use a hardcoded red like '#ff4444' for now.
            danger_colour = getattr(theme, 'danger_text', '#ff4444') 
            warning_lbl.setStyleSheet(f"color: {danger_colour}; font-weight: bold; font-size: 12px; border: none; background: transparent;")
            text_lay.addWidget(warning_lbl)
            
            # If the card has a warning, it needs a bit more height
            calculated_height += 20 
        # --------------------------------------
        
        text_lay.addStretch() 
        
        # --- FIX: Wrap the buttons in a transparent QWidget so we can align them ---
        btn_container = QWidget()
        btn_container.setStyleSheet("background: transparent; border: none;")
        btn_lay = QVBoxLayout(btn_container)
        btn_lay.setContentsMargins(0, 0, 0, 0)
        btn_lay.setSpacing(10)
        
        launch_btn = QPushButton("🚀 Launch App")
        launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if missing_deps:
            launch_btn.setText("🔒 Unavailable")
            launch_btn.setEnabled(False)
            launch_btn.setStyleSheet(f"font-weight: bold; font-size: 14px; padding: 12px 24px; background-color: transparent; color: #777777; border: 2px dashed #777777; border-radius: 6px;")
        else:
            launch_btn.setStyleSheet(f"""
                QPushButton {{ font-weight: bold; font-size: 14px; padding: 12px 24px; background-color: {theme.bg}; color: {theme.primary_text}; border: 2px solid {theme.primary_border}; border-radius: 6px; }}
                QPushButton:hover {{ background-color: {theme.primary_border}; color: white; }}
            """)
            if app_folder_path and entry_file:
                launch_btn.clicked.connect(lambda: self._launch_external_app(name, app_folder_path, entry_file))
                
        btn_lay.addWidget(launch_btn)

        # --- NEW: Pin/Unpin Button ---
        if app_folder_path:
            pin_btn = QPushButton("❌ Unpin from Hub" if pinned else "📌 Pin to Hub")
            pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            pin_btn.setStyleSheet(f"""
                QPushButton {{ font-size: 12px; font-weight: bold; padding: 8px; background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border}; border-radius: 6px; }}
                QPushButton:hover {{ background-color: {theme.primary_bg}; }}
            """)
            pin_btn.clicked.connect(lambda _, f=app_folder_path, s=not pinned: self._toggle_pin(f, s))
            btn_lay.addWidget(pin_btn)
        # -----------------------------
        
        layout.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_lay, stretch=1)
        
        # --- FIX: Now we use addWidget, which accepts the alignment flag! ---
        layout.addWidget(btn_container, alignment=Qt.AlignmentFlag.AlignVCenter) 
        
        widget.layout().update()
        widget.adjustSize()
        hint = widget.sizeHint()
        hint.setHeight(hint.height() + 15) 
        item.setSizeHint(hint)
        
        self.app_list.setItemWidget(item, widget)
        
    def _launch_external_app(self, app_name, folder_path, entry_file):
        """Passes execution to the PluginManager for safe loading."""
        self.show_toast("Launching", f"Starting {app_name}...")
        
        # Let the external module handle the dangerous injection
        plugin_window = PluginManager.launch(app_name, folder_path, entry_file, self.workspace, theme, self)
        
        if plugin_window:
            self.open_apps.append(plugin_window)
            plugin_window.show()

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
        """Uses the PluginManager to discover apps and builds their UI cards."""
        self.app_list.clear()
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        apps_dir = os.path.abspath(os.path.join(base_dir, "../../external_apps"))
        
        # --- FIX: Ask the manager for the list of plugins ---
        plugins = PluginManager.scan_plugins(apps_dir)
        
        # --- FIX: Loop through the returned dictionaries and pass the missing dependencies ---
        for p in plugins:
            self._add_app_to_list(
                p["name"], 
                p["description"], 
                icon=p["icon"], 
                author=p["author"], 
                version=p["version"], 
                app_folder_path=p["folder_path"], 
                entry_file=p["entry_file"],
                missing_deps=p.get("missing_deps", []),
                pinned=p.get("pinned", False) # Pass the pinned state
            )

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