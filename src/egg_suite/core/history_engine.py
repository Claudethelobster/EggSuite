from datetime import datetime

class EggCommand:
    """Abstract base class for all undoable actions."""
    def __init__(self, description=""):
        self.description = description

    def execute(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError

    def redo(self):
        self.execute()

class CommandNode:
    """A single node representing a point in time in the history tree."""
    def __init__(self, command, parent=None):
        self.command = command
        self.parent = parent
        self.children = []
        
        # Meta-data for the UI
        self.timestamp = datetime.now().strftime("%H:%M:%S")
        self.description = command.description if command else "Original File State"
        
    def add_child(self, command):
        """Creates a new branch from this node."""
        new_node = CommandNode(command, parent=self)
        self.children.append(new_node)
        return new_node

class HistoryTree:
    """Manages execution, undo, and redo of commands with branching timelines."""
    def __init__(self):
        self.root = CommandNode(None)
        self.current_node = self.root

    def execute_command(self, command):
        """Executes a command and adds it as a new branch in the tree."""
        command.execute()
        # Branch off the current node!
        self.current_node = self.current_node.add_child(command)
        return self.current_node

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
        
    def teleport_to_node(self, target_node):
        """
        The magic method. Calculates the path from the current state to ANY other 
        state in the tree and executes the Undos/Redos necessary to get there!
        """
        if target_node == self.current_node: return
        
        # 1. Find the path from root to current, and root to target
        def get_path(node):
            path = []
            curr = node
            while curr is not None:
                path.append(curr)
                curr = curr.parent
            return path[::-1] # Reverse so it goes Root -> Node
            
        curr_path = get_path(self.current_node)
        target_path = get_path(target_node)
        
        # 2. Find the Lowest Common Ancestor (where the timelines diverged)
        lca = self.root
        for c_node, t_node in zip(curr_path, target_path):
            if c_node == t_node:
                lca = c_node
            else:
                break
                
        # 3. Undo backwards until we hit the LCA
        while self.current_node != lca:
            self.undo()
            
        # 4. Redo forwards down the new branch until we hit the Target
        lca_idx = target_path.index(lca)
        for node_to_redo in target_path[lca_idx + 1:]:
            node_to_redo.command.redo()
            self.current_node = node_to_redo