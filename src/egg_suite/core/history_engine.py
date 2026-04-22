class EggCommand:
    """Abstract base class for all undoable actions."""
    def __init__(self, description=""):
        self.description = description

    def execute(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError

    def redo(self):
        # By default, redoing an action is just executing it again
        self.execute()

class CommandNode:
    """A single node representing a point in time in the history tree."""
    def __init__(self, command, parent=None):
        self.command = command
        self.parent = parent
        self.children = []

class HistoryTree:
    """Manages execution, undo, and redo of commands with branching timelines."""
    def __init__(self):
        self.root = CommandNode(None)
        self.current_node = self.root

    def execute_command(self, command):
        """Executes a command and adds it as a new branch in the tree."""
        command.execute()
        new_node = CommandNode(command, parent=self.current_node)
        self.current_node.children.append(new_node)
        self.current_node = new_node

    def undo(self):
        """Reverts the current node and steps back in time."""
        if self.current_node.parent is not None and self.current_node.command is not None:
            self.current_node.command.undo()
            self.current_node = self.current_node.parent
            return True
        return False

    def redo(self, branch_index=-1):
        """Steps forward into a child timeline. Defaults to the most recent branch."""
        if self.current_node.children:
            next_node = self.current_node.children[branch_index]
            next_node.command.redo()
            self.current_node = next_node
            return True
        return False