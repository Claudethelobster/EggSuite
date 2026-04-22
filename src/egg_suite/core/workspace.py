import os
from PyQt6.QtCore import QObject, pyqtSignal
from core.history_engine import HistoryTree # <--- ADD IMPORT

class GlobalWorkspace(QObject):
    dataset_added = pyqtSignal(str)      
    dataset_removed = pyqtSignal(str)    
    data_modified = pyqtSignal(str)      

    def __init__(self):
        super().__init__()
        self.datasets = {}

    def add_single_file(self, filepath, dataset):
        """Registers a standard, standalone CSV or HDF5 file."""
        self.datasets[filepath] = {
            "type": "file",
            "name": os.path.basename(filepath),
            "dataset": dataset,
            "parent": None,
            "children": [],
            "history": HistoryTree() # <--- 2. ADD THIS TO THE DICT
        }
        self.dataset_added.emit(filepath)

    def add_folder(self, folderpath, multi_dataset):
        """Registers a folder and automatically maps its children."""
        # Assuming your MultiCSVDataset stores a list of the files it contains
        child_paths = multi_dataset.file_list  
        
        # 1. Register the parent folder
        self.datasets[folderpath] = {
            "type": "folder",
            "name": os.path.basename(folderpath),
            "dataset": multi_dataset,
            "parent": None,
            "children": child_paths,
            "history": HistoryTree() # <--- 3. ADD THIS TO THE DICT
        }
        
        # 2. Register all the children so they can be accessed independently
        for child_path in child_paths:
            self.datasets[child_path] = {
                "type": "child",
                "name": os.path.basename(child_path),
                # We don't load a full dataset for the child yet to save memory.
                "dataset": None, 
                "parent": folderpath,
                "children": []
            }
        
        self.dataset_added.emit(folderpath)

    def remove_dataset(self, path):
        """Safely removes an item, ensuring children are purged if a folder is deleted."""
        if path not in self.datasets: 
            return
            
        item = self.datasets[path]
        
        # If it is a folder, kill all the child references first
        if item["type"] == "folder":
            for child in item["children"]:
                self.datasets.pop(child, None)
        
        # If it is a child file, remove it from the parent's record
        if item["type"] == "child" and item["parent"] in self.datasets:
            parent_children = self.datasets[item["parent"]]["children"]
            if path in parent_children:
                parent_children.remove(path)

        # Finally, remove the item itself
        self.datasets.pop(path, None)
        self.dataset_removed.emit(path)

    def get_dataset(self, path):
        """Fetches the active dataset object for plotting."""
        item = self.datasets.get(path)
        if not item: 
            return None
        return item.get("dataset")
        
    def get_item_info(self, path):
        """Retrieves the full metadata block (useful for the UI tree widget)."""
        return self.datasets.get(path)