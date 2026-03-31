from PyQt6.QtCore import QObject, pyqtSignal

class GlobalWorkspace(QObject):
    # Signals broadcasted to ALL open windows in the suite
    dataset_added = pyqtSignal(str)      # Fired when a new file is loaded
    dataset_removed = pyqtSignal(str)    # Fired when a file is closed
    data_modified = pyqtSignal(str)      # Fired when math generates a new column

    def __init__(self):
        super().__init__()
        self.datasets = {}  # Dictionary holding { "filename.csv": dataset_object }

    def add_dataset(self, filename, dataset):
        """Registers a loaded dataset into the global memory."""
        self.datasets[filename] = dataset
        self.dataset_added.emit(filename)

    def remove_dataset(self, filename):
        """Removes a dataset from global memory."""
        if filename in self.datasets:
            del self.datasets[filename]
            self.dataset_removed.emit(filename)

    def get_dataset(self, filename):
        """Fetches the active dataset object."""
        return self.datasets.get(filename)