"""
commands.py - Centralized undoable Command implementations for EggSuite.
Implements the Command pattern derived from EggCommand for data operations.
"""

import copy
import numpy as np
from egg_suite.core.history_engine import EggCommand


class DropNaNCommand(EggCommand):
    """Command that removes rows containing NaN from a dataset array."""
    def __init__(self, dataset, previous_data, new_data, description="Drop NaN Rows"):
        super().__init__(description=description)
        self.dataset = dataset
        self.previous_data = previous_data
        self.new_data = new_data

    def execute(self):
        self.dataset.data = self.new_data
        self.dataset.num_points = len(self.new_data) if self.new_data is not None else 0

    def undo(self):
        self.dataset.data = self.previous_data
        self.dataset.num_points = len(self.previous_data) if self.previous_data is not None else 0


class SlicerCommand(EggCommand):
    """Command that slices a dataset to keep rows between start_idx and end_idx."""
    def __init__(self, dataset, previous_data, new_data, start_idx, end_idx, description=None):
        desc = description or f"Slice Rows [{start_idx}:{end_idx}]"
        super().__init__(description=desc)
        self.dataset = dataset
        self.previous_data = previous_data
        self.new_data = new_data

    def execute(self):
        self.dataset.data = self.new_data
        self.dataset.num_points = len(self.new_data) if self.new_data is not None else 0

    def undo(self):
        self.dataset.data = self.previous_data
        self.dataset.num_points = len(self.previous_data) if self.previous_data is not None else 0


class RenameColumnCommand(EggCommand):
    """Command that renames a column in a dataset."""
    def __init__(self, dataset, col_idx, old_name, new_name):
        super().__init__(description=f"Rename Column '{old_name}' -> '{new_name}'")
        self.dataset = dataset
        self.col_idx = col_idx
        self.old_name = old_name
        self.new_name = new_name

    def execute(self):
        if hasattr(self.dataset, 'column_names'):
            self.dataset.column_names[self.col_idx] = self.new_name

    def undo(self):
        if hasattr(self.dataset, 'column_names'):
            self.dataset.column_names[self.col_idx] = self.old_name


class DeleteColumnCommand(EggCommand):
    """Command that deletes a column from a dataset."""
    def __init__(self, dataset, col_idx, col_name, old_data, old_column_names):
        super().__init__(description=f"Delete Column '{col_name}'")
        self.dataset = dataset
        self.col_idx = col_idx
        self.col_name = col_name
        self.old_data = copy.deepcopy(old_data) if old_data is not None else None
        self.old_column_names = copy.deepcopy(old_column_names)

    def execute(self):
        if hasattr(self.dataset, 'data') and self.dataset.data is not None:
            self.dataset.data = np.delete(self.dataset.data, self.col_idx, axis=1)
            self.dataset.num_inputs = self.dataset.data.shape[1]
        
        # Shift column names down
        new_names = {}
        for idx, name in sorted(self.old_column_names.items()):
            if idx < self.col_idx:
                new_names[idx] = name
            elif idx > self.col_idx:
                new_names[idx - 1] = name
        self.dataset.column_names = new_names

    def undo(self):
        self.dataset.data = copy.deepcopy(self.old_data)
        if self.old_data is not None:
            self.dataset.num_inputs = self.old_data.shape[1]
        self.dataset.column_names = copy.deepcopy(self.old_column_names)


class AppendColumnCommand(EggCommand):
    """Command that appends a newly calculated or imported column to a dataset."""
    def __init__(self, dataset, new_col_name, new_col_data, old_data, old_column_names):
        super().__init__(description=f"Append Column '{new_col_name}'")
        self.dataset = dataset
        self.new_col_name = new_col_name
        self.new_col_data = new_col_data
        self.old_data = copy.deepcopy(old_data) if old_data is not None else None
        self.old_column_names = copy.deepcopy(old_column_names)

    def execute(self):
        col_arr = np.asarray(self.new_col_data).reshape(-1, 1)
        if hasattr(self.dataset, 'data') and self.dataset.data is not None and self.dataset.data.size > 0:
            self.dataset.data = np.hstack([self.dataset.data, col_arr])
        else:
            self.dataset.data = col_arr
        
        self.dataset.num_inputs = self.dataset.data.shape[1]
        new_idx = self.dataset.num_inputs - 1
        if not hasattr(self.dataset, 'column_names'):
            self.dataset.column_names = {}
        self.dataset.column_names[new_idx] = self.new_col_name

    def undo(self):
        self.dataset.data = copy.deepcopy(self.old_data)
        if self.old_data is not None:
            self.dataset.num_inputs = self.old_data.shape[1]
        self.dataset.column_names = copy.deepcopy(self.old_column_names)
