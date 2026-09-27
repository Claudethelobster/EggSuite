"""
plugin_manager.py - Plugin management and modern EggSuiteAPI bridge.
Provides a comprehensive, secure, and typed API for external plugins to interact
with datasets, analysis engines, themes, and UI widgets in EggSuite.
"""

import os
import sys
import importlib.util
import traceback
import json
from typing import Any, Callable, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from PyQt6.QtWidgets import QFileDialog, QPushButton, QWidget
from PyQt6.QtCore import QObject, pyqtSignal

from egg_suite.ui.dialogs.data_mgmt import CopyableErrorDialog
import egg_suite.core.analysis_engine as analysis_engine


class _AnalysisBridge:
    """Namespace for mathematical fitting, signal processing, and statistics."""
    fit_curve = staticmethod(analysis_engine.fit_curve)
    find_peaks = staticmethod(analysis_engine.find_peaks)
    compute_fft = staticmethod(analysis_engine.compute_fft)
    smooth_data = staticmethod(analysis_engine.smooth_data)
    integrate_area = staticmethod(analysis_engine.integrate_area)
    compute_statistics = staticmethod(analysis_engine.compute_statistics)


class _UIBridge:
    """Namespace for UI helpers, styling, and widget builders."""
    def __init__(self, theme, hub_window):
        self._theme = theme
        self._hub = hub_window

    def get_theme_colours(self) -> Dict[str, str]:
        """Returns active UI theme color dictionary."""
        return {
            "bg": self._theme.bg,
            "fg": self._theme.fg,
            "panel_bg": self._theme.panel_bg,
            "border": self._theme.border,
            "primary_bg": self._theme.primary_bg,
            "primary_text": self._theme.primary_text,
            "primary_border": self._theme.primary_border,
            "danger_bg": getattr(self._theme, "danger_bg", "#dc3545"),
            "danger_text": getattr(self._theme, "danger_text", "#ff6b6b"),
            "success_bg": getattr(self._theme, "success_bg", "#28a745"),
            "success_text": getattr(self._theme, "success_text", "#51cf66"),
        }

    def apply_theme(self, widget: QWidget):
        """Applies global dark/light palette to a widget."""
        c = self.get_theme_colours()
        widget.setStyleSheet(f"background-color: {c['bg']}; color: {c['fg']};")

    def create_button(self, text: str, is_primary: bool = False, parent: Optional[QWidget] = None) -> QPushButton:
        """Creates a styled QPushButton matching the suite's theme."""
        c = self.get_theme_colours()
        btn = QPushButton(text, parent)
        if is_primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-weight: bold; padding: 8px 16px;
                    background-color: {c['primary_bg']}; color: {c['primary_text']};
                    border: 1px solid {c['primary_border']}; border-radius: 4px;
                }}
                QPushButton:hover {{ border: 1px solid white; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 8px 16px;
                    background-color: {c['panel_bg']}; color: {c['fg']};
                    border: 1px solid {c['border']}; border-radius: 4px;
                }}
                QPushButton:hover {{ border: 1px solid {c['primary_border']}; color: {c['primary_text']}; }}
            """)
        return btn

    def create_plot_widget(self, title: str = "", show_grid: bool = True, parent: Optional[QWidget] = None):
        """Creates a pre-themed pyqtgraph PlotWidget."""
        try:
            import pyqtgraph as pg
            c = self.get_theme_colours()
            pw = pg.PlotWidget(parent=parent, title=title if title else None)
            pw.setBackground(c['panel_bg'])
            if show_grid:
                pw.showGrid(x=True, y=True, alpha=0.3)
            return pw
        except ImportError:
            raise ImportError("pyqtgraph is required to create plot widgets.")

    def show_notification(self, title: str, message: str, is_error: bool = False):
        """Spawns a native EggSuite toast notification in the Hub."""
        if self._hub and hasattr(self._hub, 'show_toast'):
            self._hub.show_toast(title, message, is_error)

    def show_error_dialog(self, title: str, message: str, details: str = ""):
        """Spawns the native copyable error dialog."""
        CopyableErrorDialog(title, message, details, self._hub).exec()


class _EventBridge:
    """Namespace for subscribing to workspace signals."""
    def __init__(self, workspace):
        self._workspace = workspace

    def on_dataset_added(self, callback: Callable[[str], None]):
        """Connects callback to dataset_added(filepath) signal."""
        if hasattr(self._workspace, 'dataset_added'):
            self._workspace.dataset_added.connect(callback)

    def on_dataset_removed(self, callback: Callable[[str], None]):
        """Connects callback to dataset_removed(filepath) signal."""
        if hasattr(self._workspace, 'dataset_removed'):
            self._workspace.dataset_removed.connect(callback)

    def on_data_modified(self, callback: Callable[[str], None]):
        """Connects callback to data_modified(filepath) signal."""
        if hasattr(self._workspace, 'data_modified'):
            self._workspace.data_modified.connect(callback)


class _DataContainer:
    """Generic dataset container for wrapping user-created DataFrames or arrays."""
    def __init__(self, name: str, data_array: np.ndarray, column_names: Dict[int, str], notes: str = ""):
        self.filename = name
        self.name = name
        self.data = data_array
        self.column_names = column_names
        self.num_points = data_array.shape[0] if data_array.ndim > 0 and data_array.size > 0 else 0
        self.num_inputs = data_array.shape[1] if data_array.ndim > 1 else (1 if data_array.size > 0 else 0)
        self.num_outputs = 0
        self.notes = notes
        self.sweeps = []


class EggSuiteAPI:
    """The modern bridge between external plugins and the EggSuite core."""

    def __init__(self, workspace, theme, hub_window, app_name: str):
        self._workspace = workspace
        self._theme = theme
        self._hub = hub_window
        self._app_name = app_name

        # Sub-interfaces
        self.analysis = _AnalysisBridge()
        self.ui = _UIBridge(theme, hub_window)
        self.events = _EventBridge(workspace)

    # ==========================================
    # 1. DATA MANAGEMENT & DATAFRAME GETTERS
    # ==========================================
    def get_dataset_names(self) -> List[str]:
        """Returns a list of all dataset keys currently loaded in the Hub."""
        if not self._workspace or not hasattr(self._workspace, 'datasets'):
            return []
        return list(self._workspace.datasets.keys())

    def get_dataset(self, name: str) -> Any:
        """Returns the raw dataset object for a given name/path."""
        if not self._workspace:
            return None
        info = self._workspace.get_item_info(name)
        return info["dataset"] if info else None

    def get_dataframe(self, name: str) -> Optional[pd.DataFrame]:
        """
        Retrieves the specified dataset as a clean, standardized pandas.DataFrame.
        Automatically resolves column headers and multi-sweep concatenation.
        """
        ds = self.get_dataset(name)
        if ds is None:
            return None

        # Extract data array
        data_arr = getattr(ds, 'data', None)
        if data_arr is None and hasattr(ds, 'sweeps') and ds.sweeps:
            valid_sweeps = [s.data for s in ds.sweeps if getattr(s, 'data', None) is not None]
            if valid_sweeps:
                data_arr = np.vstack(valid_sweeps)

        if data_arr is None:
            return None

        # Resolve column names
        col_names = getattr(ds, 'column_names', {})
        num_cols = data_arr.shape[1] if data_arr.ndim > 1 else 1
        headers = [col_names.get(i, f"Column_{i}") for i in range(num_cols)]

        if data_arr.ndim == 1:
            data_arr = data_arr.reshape(-1, 1)

        return pd.DataFrame(data_arr, columns=headers)

    def get_column_names(self, name: str) -> List[str]:
        """Returns the list of column header strings for a dataset."""
        ds = self.get_dataset(name)
        if ds is None:
            return []
        if hasattr(ds, 'column_names') and ds.column_names:
            return [ds.column_names.get(i, f"Column_{i}") for i in range(len(ds.column_names))]
        df = self.get_dataframe(name)
        return list(df.columns) if df is not None else []

    def get_column_data(self, name: str, column: Union[str, int]) -> Optional[np.ndarray]:
        """
        Returns a 1D NumPy array for a specific column in a dataset.
        Column can be specified by index (int) or column name (str).
        """
        df = self.get_dataframe(name)
        if df is None:
            return None
        if isinstance(column, int):
            if 0 <= column < len(df.columns):
                return df.iloc[:, column].to_numpy()
            return None
        elif isinstance(column, str):
            if column in df.columns:
                return df[column].to_numpy()
            return None
        return None

    def add_dataset(self, name: str, dataset_object: Any):
        """Allows a plugin to push a raw dataset object into the main EggSuite workspace."""
        if self._workspace:
            self._workspace.add_single_file(name, dataset_object)

    def add_dataframe(self, name: str, df: pd.DataFrame, notes: str = ""):
        """
        Allows a plugin to push a pandas.DataFrame directly into the EggSuite workspace.
        Automatically wraps it into a native compatible dataset container.
        """
        col_map = {i: str(col) for i, col in enumerate(df.columns)}
        data_arr = df.to_numpy(dtype=np.float64, na_value=np.nan)
        container = _DataContainer(name=name, data_array=data_arr, column_names=col_map, notes=notes)
        self.add_dataset(name, container)

    def remove_dataset(self, name: str):
        """Allows a plugin to remove a dataset from the workspace."""
        if self._workspace:
            self._workspace.remove_dataset(name)

    # ==========================================
    # 2. UI & THEME SHORTCUTS (Backward Compatible)
    # ==========================================
    def get_theme_colours(self) -> Dict[str, str]:
        """Returns a dictionary of current UI colors."""
        return self.ui.get_theme_colours()

    def show_notification(self, title: str, message: str, is_error: bool = False):
        """Spawns a native EggSuite toast notification."""
        self.ui.show_notification(title, message, is_error)

    def show_error_dialog(self, title: str, message: str, details: str = ""):
        """Spawns the native copyable error dialog."""
        self.ui.show_error_dialog(title, message, details)

    # ==========================================
    # 3. FILE SYSTEM HELPERS
    # ==========================================
    def ask_for_file(self, title: str = "Select File", filter_string: str = "All Files (*.*)") -> str:
        """Opens a file dialog starting at the user's last known EggSuite directory."""
        last_dir = self._hub.settings.value("last_load_directory", "") if self._hub else ""
        fname, _ = QFileDialog.getOpenFileName(self._hub, title, last_dir, filter_string)
        if fname and self._hub:
            self._hub.settings.setValue("last_load_directory", os.path.dirname(fname))
        return fname or ""

    def ask_for_save_path(self, title: str = "Save File", default_name: str = "output.csv", filter_string: str = "CSV (*.csv)") -> str:
        """Opens a save dialog starting at the user's last known EggSuite directory."""
        last_dir = self._hub.settings.value("last_load_directory", "") if self._hub else ""
        start_path = os.path.join(last_dir, default_name)
        fname, _ = QFileDialog.getSaveFileName(self._hub, title, start_path, filter_string)
        return fname or ""

    # ==========================================
    # 4. SANDBOXED SETTINGS ENGINE
    # ==========================================
    def save_setting(self, key: str, value: Any):
        """Saves a setting specific to this plugin under plugins/<AppName>/<key>."""
        if self._hub and hasattr(self._hub, 'settings'):
            safe_key = f"plugins/{self._app_name}/{key}"
            self._hub.settings.setValue(safe_key, value)

    def load_setting(self, key: str, default_value: Any = None) -> Any:
        """Loads a setting specific to this plugin."""
        if self._hub and hasattr(self._hub, 'settings'):
            safe_key = f"plugins/{self._app_name}/{key}"
            return self._hub.settings.value(safe_key, default_value)
        return default_value


class PluginManager:
    """Handles the safe discovery, inspection, and execution of external plugins."""

    @staticmethod
    def get_default_plugin_dirs() -> List[str]:
        """Returns standard search directories for plugins."""
        dirs = []
        user_plugin_dir = os.path.join(os.path.expanduser("~"), ".egg_suite", "plugins")
        dirs.append(user_plugin_dir)
        dev_examples = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "examples", "plugins"))
        if os.path.isdir(dev_examples):
            dirs.append(dev_examples)
        return dirs

    @staticmethod
    def scan_plugins(apps_dir: Optional[Union[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """Scans plugin directories and returns a list of validated plugin metadata dictionaries."""
        valid_plugins = []
        seen_names = set()

        search_dirs = []
        if apps_dir:
            if isinstance(apps_dir, (list, tuple)):
                search_dirs.extend(apps_dir)
            else:
                search_dirs.append(apps_dir)
        else:
            search_dirs = PluginManager.get_default_plugin_dirs()

        for sdir in search_dirs:
            if not os.path.exists(sdir):
                try:
                    os.makedirs(sdir, exist_ok=True)
                except OSError:
                    continue

            for item in os.listdir(sdir):
                app_path = os.path.join(sdir, item)
                if not os.path.isdir(app_path):
                    continue
                manifest_path = os.path.join(app_path, "manifest.json")
                if not os.path.exists(manifest_path):
                    continue

                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)

                    name = manifest.get("name", "Unknown App")
                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    desc = manifest.get("description", "No description provided.")
                    icon = manifest.get("icon", "🧩")
                    author = manifest.get("author", "Unknown Author")
                    version = manifest.get("version", "1.0")
                    entry_file = manifest.get("entry_point", "main.py")
                    pinned = manifest.get("pinned", False)

                    dependencies = manifest.get("dependencies", [])
                    missing_deps = []
                    for dep in dependencies:
                        if importlib.util.find_spec(dep) is None:
                            missing_deps.append(dep)

                    entry_path = os.path.join(app_path, entry_file)
                    if not os.path.exists(entry_path):
                        continue

                    valid_plugins.append({
                        "name": name,
                        "description": desc,
                        "icon": icon,
                        "author": author,
                        "version": version,
                        "folder_path": app_path,
                        "entry_file": entry_file,
                        "missing_deps": missing_deps,
                        "pinned": pinned
                    })
                except Exception as e:
                    print(f"Failed to load plugin manifest in {item}: {e}")
        return valid_plugins

    @staticmethod
    def set_pinned_state(folder_path: str, state: bool) -> bool:
        """Updates manifest.json to persist the pinned state of a plugin."""
        manifest_path = os.path.join(folder_path, "manifest.json")
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data["pinned"] = state
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"Failed to pin app: {e}")
            return False

    @staticmethod
    def launch(app_name: str, folder_path: str, entry_file: str, workspace: Any, theme: Any, hub_window: Any) -> Optional[QWidget]:
        """Safely injects API and executes plugin with error isolation."""
        main_path = os.path.join(folder_path, entry_file)
        api = EggSuiteAPI(workspace, theme, hub_window, app_name)

        spec = importlib.util.spec_from_file_location(f"plugin_{app_name.replace(' ', '_')}", main_path)
        if spec is None or spec.loader is None:
            CopyableErrorDialog("Plugin Load Error", f"Could not load plugin specification from {main_path}", "", hub_window).exec()
            return None

        plugin_module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, folder_path)

        try:
            spec.loader.exec_module(plugin_module)
            if not hasattr(plugin_module, "run_app"):
                raise AttributeError("Plugin module must define a 'run_app(api)' entry function.")
            plugin_window = plugin_module.run_app(api)
            return plugin_window
        except Exception as e:
            error_details = traceback.format_exc()
            CopyableErrorDialog("Plugin Crash", f"The plugin '{app_name}' encountered a fatal error during launch.", f"{e}\n\n{error_details}", hub_window).exec()
            return None
        finally:
            if folder_path in sys.path:
                sys.path.remove(folder_path)