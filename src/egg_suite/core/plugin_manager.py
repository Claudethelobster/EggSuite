import os
import sys
import importlib.util
import traceback
import json
from PyQt6.QtWidgets import QFileDialog
from ui.dialogs.data_mgmt import CopyableErrorDialog

class EggSuiteAPI:
    """The secure bridge between external plugins and the EggSuite core."""
    
    # --- FIX: Added app_name to the init so we can sandbox settings ---
    def __init__(self, workspace, theme, hub_window, app_name):
        self._workspace = workspace
        self._theme = theme
        self._hub = hub_window
        self._app_name = app_name # Used for secure settings namespacing

    # ==========================================
    # DATA MANAGEMENT
    # ==========================================
    def get_dataset_names(self):
        """Returns a list of all dataset names currently loaded in the Hub."""
        return list(self._workspace.datasets.keys())

    def get_dataset(self, name):
        """Returns the raw dataset object for a given name."""
        info = self._workspace.get_item_info(name)
        return info["dataset"] if info else None
        
    def add_dataset(self, name, dataset_object):
        """Allows a plugin to push new data back into the main EggSuite workspace."""
        # The workspace handles the signalling, so the Hub UI will update automatically!
        self._workspace.add_single_file(name, dataset_object)
        
    def remove_dataset(self, name):
        """Allows a plugin to delete data from the workspace."""
        self._workspace.remove_dataset(name)

    # ==========================================
    # UI & THEME ENGINE
    # ==========================================
    def get_theme_colours(self):
        """Returns a dictionary of the current UI colours so plugins match the suite."""
        return {
            "bg": self._theme.bg,
            "fg": self._theme.fg,
            "panel_bg": self._theme.panel_bg,
            "border": self._theme.border,
            "primary_bg": self._theme.primary_bg,
            "primary_text": self._theme.primary_text,
            "primary_border": self._theme.primary_border
        }

    def show_notification(self, title, message, is_error=False):
        """Spawns a native EggSuite toast notification."""
        self._hub.show_toast(title, message, is_error)
        
    def show_error_dialog(self, title, message, details=""):
        """Spawns the native EggSuite Copyable Error box."""
        CopyableErrorDialog(title, message, details, self._hub).exec()

    # ==========================================
    # FILE SYSTEM HELPERS
    # ==========================================
    def ask_for_file(self, title="Select File", filter_string="All Files (*.*)"):
        """Opens a file dialog starting at the user's last known EggSuite directory."""
        last_dir = self._hub.settings.value("last_load_directory", "")
        fname, _ = QFileDialog.getOpenFileName(self._hub, title, last_dir, filter_string)
        if fname:
            # Update the global suite directory so it remembers for next time
            import os
            self._hub.settings.setValue("last_load_directory", os.path.dirname(fname))
        return fname
        
    def ask_for_save_path(self, title="Save File", default_name="output.csv", filter_string="CSV (*.csv)"):
        """Opens a save dialog starting at the user's last known EggSuite directory."""
        last_dir = self._hub.settings.value("last_load_directory", "")
        import os
        start_path = os.path.join(last_dir, default_name)
        fname, _ = QFileDialog.getSaveFileName(self._hub, title, start_path, filter_string)
        return fname

    # ==========================================
    # SANDBOXED SETTINGS ENGINE
    # ==========================================
    def save_setting(self, key, value):
        """Saves a setting specific to this plugin."""
        # We prepend 'plugins/AppName/' to ensure they don't overwrite EggSuite's main settings
        safe_key = f"plugins/{self._app_name}/{key}"
        self._hub.settings.setValue(safe_key, value)
        
    def load_setting(self, key, default_value=None):
        """Loads a setting specific to this plugin."""
        safe_key = f"plugins/{self._app_name}/{key}"
        return self._hub.settings.value(safe_key, default_value)

class PluginManager:
    """Handles the safe injection, execution, and discovery of external modules."""
    
    # --- ADD THIS NEW METHOD ---
    @staticmethod
    def scan_plugins(apps_dir):
        """Scans the directory and returns a list of valid plugin dictionaries."""
        valid_plugins = []
        if not os.path.exists(apps_dir):
            os.makedirs(apps_dir)
            return valid_plugins
            
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
                author = manifest.get("author", "Unknown Author")
                version = manifest.get("version", "1.0")
                entry_file = manifest.get("entry_point", "main.py")
                
                # --- NEW: Read Pinned State ---
                pinned = manifest.get("pinned", False)
                # ------------------------------
                
                dependencies = manifest.get("dependencies", [])
                missing_deps = []
                for dep in dependencies:
                    if importlib.util.find_spec(dep) is None:
                        missing_deps.append(dep)
                
                entry_path = os.path.join(app_path, entry_file)
                if not os.path.exists(entry_path): continue
                    
                valid_plugins.append({
                    "name": name,
                    "description": desc,
                    "icon": icon,
                    "author": author,
                    "version": version,
                    "folder_path": app_path,
                    "entry_file": entry_file,
                    "missing_deps": missing_deps,
                    "pinned": pinned # Pass it to the UI
                })
            except Exception as e:
                print(f"Failed to load plugin manifest in {item}: {e}")
        return valid_plugins

    # --- NEW METHOD ---
    @staticmethod
    def set_pinned_state(folder_path, state):
        """Rewrites the manifest.json to permanently save the pinned state."""
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
    def launch(app_name, folder_path, entry_file, workspace, theme, hub_window):
        """Safely injects and launches a plugin with Error Isolation."""
        main_path = os.path.join(folder_path, entry_file)
        
        # 1. Create the secure API bridge
        api = EggSuiteAPI(workspace, theme, hub_window, app_name)
        
        spec = importlib.util.spec_from_file_location(f"plugin_{app_name.replace(' ', '_')}", main_path)
        plugin_module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, folder_path)
        
        try:
            spec.loader.exec_module(plugin_module)
            
            # 2. We pass ONLY the API to the plugin, not the raw workspace!
            plugin_window = plugin_module.run_app(api)
            return plugin_window
            
        except Exception as e:
            # 3. ERROR ISOLATION: The Hub catches the crash and stays alive!
            error_details = traceback.format_exc()
            CopyableErrorDialog("Plugin Crash", f"The plugin '{app_name}' encountered a fatal error during launch.", f"{e}\n\n{error_details}", hub_window).exec()
            return None
            
        finally:
            if folder_path in sys.path:
                sys.path.remove(folder_path)