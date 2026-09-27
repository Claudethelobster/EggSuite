# dev_tools/apply_patch.py
import os
import sys
import json
import shutil
import ast
import textwrap
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QTextBrowser, QPushButton, 
                             QLabel, QMessageBox)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt

# Calculate absolute paths to ensure the tool works no matter where it is launched from
DEV_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(DEV_TOOLS_DIR, '..'))
BACKUP_DIR = os.path.join(DEV_TOOLS_DIR, '.backups')

class UniversalPatcherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Delta Patcher (AST Engine)")
        self.resize(950, 750)
        
        # Memory bank for the Revert function
        self.last_backups = []
        
        # Ensure backup directory exists
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        self._build_ui()
        self.log("System Initialised. AST Engine Active.", "#4caf50")
        self.log(f"Project Root: {PROJECT_ROOT}\n", "gray")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # JSON Input Area
        layout.addWidget(QLabel("<b>Paste JSON Delta Payload:</b>"))
        self.json_input = QTextEdit()
        self.json_input.setFont(QFont("Consolas", 10))
        self.json_input.setPlaceholderText(
            '[\n'
            '  { "file": "...", "search": "...", "replace": "..." },\n'
            '  { "file": "...", "action": "add_import", "import": "import numpy as np" },\n'
            '  { "file": "...", "class": "ClassName", "method": "method_name", "action": "replace_in_method", "search": "...", "replace": "..." },\n'
            '  { "file": "...", "class": "ClassName", "method": "old_func", "action": "delete_method" },\n'
            '  { "file": "new_script.py", "action": "create_file", "content": "print(\'hello\')" }\n'
            ']'
        )
        self.json_input.textChanged.connect(self._reset_deploy_state)
        layout.addWidget(self.json_input, stretch=2)
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_check = QPushButton("Check Code")
        self.btn_check.setStyleSheet("font-weight: bold; background-color: #d0e8ff; border: 2px solid #0055ff; padding: 8px; border-radius: 4px;")
        self.btn_check.clicked.connect(self.check_code)
        
        self.btn_deploy = QPushButton("Deploy Code")
        self.btn_deploy.setStyleSheet("font-weight: bold; background-color: #d4edda; color: #155724; border: 2px solid #28a745; padding: 8px; border-radius: 4px;")
        self.btn_deploy.setEnabled(False)
        self.btn_deploy.clicked.connect(self.deploy_code)
        
        self.btn_revert = QPushButton("Revert Last Patch")
        self.btn_revert.setStyleSheet("font-weight: bold; background-color: #f8d7da; color: #721c24; border: 2px solid #dc3545; padding: 8px; border-radius: 4px;")
        self.btn_revert.setEnabled(False)
        self.btn_revert.clicked.connect(self.revert_code)
        
        btn_layout.addWidget(self.btn_check)
        btn_layout.addWidget(self.btn_deploy)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_revert)
        layout.addLayout(btn_layout)
        
        # Terminal Output
        layout.addWidget(QLabel("<b>Terminal Output:</b>"))
        self.terminal = QTextBrowser()
        self.terminal.setFont(QFont("Consolas", 10))
        self.terminal.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.terminal, stretch=1)

    def log(self, message, color="#d4d4d4"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.terminal.append(f"<span style='color: #888;'>[{timestamp}]</span> <span style='color: {color};'>{message}</span>")
        # Scroll to bottom
        scrollbar = self.terminal.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _reset_deploy_state(self):
        """Require a new check if the user edits the JSON text."""
        self.btn_deploy.setEnabled(False)

    def _parse_json(self):
        raw_text = self.json_input.toPlainText().strip()
        if not raw_text:
            self.log("❌ Error: JSON payload is empty.", "#f44336")
            return None
        try:
            payload = json.loads(raw_text)
            if not isinstance(payload, list):
                self.log("❌ Error: Payload must be a JSON array [ ... ]", "#f44336")
                return None
            return payload
        except json.JSONDecodeError as e:
            self.log(f"❌ JSON Parsing Error: {e}", "#f44336")
            return None

    def _ast_patch(self, file_content, change):
        """Locates and manipulates code safely using Python's native AST parser."""
        try:
            tree = ast.parse(file_content)
        except SyntaxError as e:
            return file_content, False, f"AST Parse Error: Source file has invalid syntax: {e}"

        action = change.get("action", "replace_method")
        lines = file_content.split('\n')
        
        # 1. Smart Auto-Imports
        if action == "add_import":
            import_stmt = change.get("import")
            if not import_stmt: return file_content, False, "Missing 'import' key."
            
            if import_stmt in file_content:
                return file_content, True, "Import already exists."
                
            last_import_line = 0
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    last_import_line = node.end_lineno
                    
            if last_import_line == 0:
                if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, (ast.Str, ast.Constant)):
                    last_import_line = tree.body[0].end_lineno
                    
            new_lines = lines[:last_import_line] + [import_stmt] + lines[last_import_line:]
            return '\n'.join(new_lines), True, "AST Engine: Injected Import"

        class_name = change.get("class")
        method_name = change.get("method")
        
        class_node = None
        target_node = None

        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                class_node = node
                if method_name:
                    for child in node.body:
                        if isinstance(child, ast.FunctionDef) and child.name == method_name:
                            target_node = child
                            break
                break

        if not class_node:
            return file_content, False, f"Class '{class_name}' not found"

        if action == "append_method":
            end_idx = class_node.end_lineno
            class_indent = lines[class_node.lineno - 1][:len(lines[class_node.lineno - 1]) - len(lines[class_node.lineno - 1].lstrip())]
            method_indent = class_indent + "    "
            
            dedented_replace = textwrap.dedent(change.get("replace", "").strip('\n'))
            formatted_replace = [method_indent + line if line.strip() else "" for line in dedented_replace.split('\n')]
            
            new_lines = lines[:end_idx] + [""] + formatted_replace + lines[end_idx:]
            return '\n'.join(new_lines), True, f"AST Engine: Appended {method_name}()"

        if not target_node:
            return file_content, False, f"Method '{method_name}' not found in class '{class_name}'"
            
        start_idx = target_node.lineno - 1
        if target_node.decorator_list:
            start_idx = target_node.decorator_list[0].lineno - 1
        end_idx = target_node.end_lineno

        # 2. Safe Deletion
        if action == "delete_method":
            new_lines = lines[:start_idx] + lines[end_idx:]
            return '\n'.join(new_lines), True, f"AST Engine: Deleted {method_name}()"

        # 3. AST-Scoped String Replacement
        if action == "replace_in_method":
            search_str = change.get("search")
            replace_str = change.get("replace", "")
            if not search_str: return file_content, False, "Missing 'search' key for scoped replacement."
            
            method_chunk = '\n'.join(lines[start_idx:end_idx])
            new_chunk, success, msg = self._smart_patch(method_chunk, search_str, replace_str)
            
            if not success:
                return file_content, False, f"Scoped replace failed: {msg}"
                
            new_lines = lines[:start_idx] + new_chunk.split('\n') + lines[end_idx:]
            return '\n'.join(new_lines), True, f"AST Engine: Scoped replace inside {method_name}()"

        if action == "replace_method":
            file_indent = lines[start_idx][:len(lines[start_idx]) - len(lines[start_idx].lstrip())]
            dedented_replace = textwrap.dedent(change.get("replace", "").strip('\n'))
            formatted_replace = [file_indent + line if line.strip() else "" for line in dedented_replace.split('\n')]

            new_lines = lines[:start_idx] + formatted_replace + lines[end_idx:]
            return '\n'.join(new_lines), True, f"AST Engine: Replaced {class_name}.{method_name}()"

        return file_content, False, f"Unknown AST action '{action}'"

    def _smart_patch(self, file_content, search_text, replace_text):
        """Legacy string-based fuzzy matcher."""
        if file_content.count(search_text) == 1:
            return file_content.replace(search_text, replace_text), True, "Exact Match"

        search_raw_lines = search_text.split('\n')
        search_norm = [(i, line.strip()) for i, line in enumerate(search_raw_lines) if line.strip()]
        
        if not search_norm:
            return file_content, False, "Search text is empty or only whitespace."

        file_raw_lines = file_content.split('\n')
        file_norm = [(i, line.strip()) for i, line in enumerate(file_raw_lines) if line.strip()]

        search_strings = [s[1] for s in search_norm]
        search_len = len(search_strings)
        
        matches = []
        for i in range(len(file_norm) - search_len + 1):
            window = [f[1] for f in file_norm[i:i+search_len]]
            if window == search_strings:
                matches.append((file_norm[i][0], file_norm[i+search_len-1][0]))

        if len(matches) == 0:
            return file_content, False, "Code not found (whitespace/structure mismatch)."
        elif len(matches) > 1:
            if file_content.count(search_text) == 1:
                return file_content.replace(search_text, replace_text), True, "Exact match resolved ambiguity"
            return file_content, False, f"Ambiguous match: Found {len(matches)} identical blocks."

        start_line_idx, end_line_idx = matches[0]

        orig_start_line = file_raw_lines[start_line_idx]
        file_indent = orig_start_line[:len(orig_start_line) - len(orig_start_line.lstrip())]

        search_first_line = search_raw_lines[search_norm[0][0]]
        search_indent = search_first_line[:len(search_first_line) - len(search_first_line.lstrip())]

        replace_raw_lines = replace_text.split('\n')
        while replace_raw_lines and not replace_raw_lines[0].strip(): replace_raw_lines.pop(0)
        while replace_raw_lines and not replace_raw_lines[-1].strip(): replace_raw_lines.pop()

        formatted_replace = []
        for line in replace_raw_lines:
            if line.startswith(search_indent):
                formatted_replace.append(file_indent + line[len(search_indent):])
            elif not line.strip():
                formatted_replace.append("")
            else:
                formatted_replace.append(file_indent + line.lstrip())

        new_file_lines = file_raw_lines[:start_line_idx] + formatted_replace + file_raw_lines[end_line_idx+1:]
        return '\n'.join(new_file_lines), True, "Fuzzy Match (Auto-Aligned)"

    def check_code(self):
        self.terminal.clear()
        self.log("Starting Pre-Flight Check...", "#569cd6")
        
        payload = self._parse_json()
        if not payload: return
        
        all_good = True
        
        for i, change in enumerate(payload):
            target_file = change.get("file")
            action = change.get("action", "")
            
            if not target_file:
                self.log(f"❌ Block {i+1}: Missing 'file' key.", "#f44336")
                all_good = False
                continue
                
            abs_path = os.path.join(PROJECT_ROOT, target_file)
            
            if action == "create_file":
                if os.path.exists(abs_path):
                    self.log(f"❌ Block {i+1}: File already exists: {target_file}", "#f44336")
                    all_good = False
                elif "content" not in change:
                    self.log(f"❌ Block {i+1}: 'create_file' missing 'content' key.", "#f44336")
                    all_good = False
                continue

            if not os.path.exists(abs_path):
                self.log(f"❌ Block {i+1}: File not found: {target_file}", "#f44336")
                all_good = False
                continue
                
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    
                if action or "class" in change:
                    _, success, msg = self._ast_patch(file_content, change)
                else:
                    _, success, msg = self._smart_patch(file_content, change.get("search", ""), change.get("replace", ""))
                
                if not success:
                    self.log(f"❌ Block {i+1}: Mismatch in: {target_file} ({msg})", "#f44336")
                    all_good = False
                else:
                    self.log(f"✅ Block {i+1}: Match verified: {target_file} [{msg}]", "#4caf50")
                    
            except Exception as e:
                self.log(f"❌ Block {i+1}: Error reading file: {e}", "#f44336")
                all_good = False
                
        if all_good:
            self.log("\n✅ All checks passed. Ready to deploy.", "#4caf50")
            self.btn_deploy.setEnabled(True)
        else:
            self.log("\n❌ Pre-flight checks failed. Deployment locked.", "#f44336")
            self.btn_deploy.setEnabled(False)

    def deploy_code(self):
        payload = self._parse_json()
        if not payload: return
        
        self.log("\nInitiating Deployment...", "#569cd6")
        self.btn_deploy.setEnabled(False)
        self.last_backups.clear() 
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for i, change in enumerate(payload):
            target_file = change["file"]
            action = change.get("action", "")
            abs_path = os.path.join(PROJECT_ROOT, target_file)
            
            base_name = os.path.basename(target_file)
            backup_name = f"{base_name}_{timestamp_str}_block{i}.bak"
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            
            if action == "create_file":
                try:
                    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                    content = textwrap.dedent(change.get("content", "")).lstrip()
                    with open(abs_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.last_backups.append({"original": abs_path, "backup": None, "created": True})
                    self.log(f"✅ Created: {target_file}", "#4caf50")
                    continue
                except Exception as e:
                    self.log(f"❌ Deployment crashed on {target_file}: {e}", "#f44336")
                    self.log("Triggering Auto-Revert...", "#ffcc00")
                    self._execute_revert()
                    return

            try:
                shutil.copy2(abs_path, backup_path)
                self.last_backups.append({"original": abs_path, "backup": backup_path})
            except Exception as e:
                self.log(f"❌ CRITICAL: Failed to create backup for {target_file}. Aborting.", "#f44336")
                return
                
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    
                if action or "class" in change:
                    new_content, success, msg = self._ast_patch(file_content, change)
                else:
                    new_content, success, msg = self._smart_patch(file_content, change.get("search", ""), change.get("replace", ""))
                
                if not success:
                    raise Exception(msg)
                    
                with open(abs_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                    
                self.log(f"✅ Deployed: {target_file} [{msg}]", "#4caf50")
                
            except Exception as e:
                self.log(f"❌ Deployment crashed on {target_file}: {e}", "#f44336")
                self.log("Triggering Auto-Revert...", "#ffcc00")
                self._execute_revert()
                return
                
        self.log("\n✅ Deployment Complete!", "#4caf50")
        self.btn_revert.setEnabled(True)
        self.json_input.clear()

    def revert_code(self):
        if not self.last_backups:
            self.log("No valid backups found in memory to revert.", "#ffcc00")
            return
            
        ans = QMessageBox.warning(
            self, "Confirm Revert", 
            "Are you sure you want to revert the last deployed batch?\nThis will overwrite the live files with the backup.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if ans == QMessageBox.StandardButton.Yes:
            self._execute_revert()

    def _execute_revert(self):
            for record in self.last_backups:
                orig = record.get("original")
                bak = record.get("backup")
                created = record.get("created", False)
                try:
                    if created:
                        if os.path.exists(orig):
                            os.remove(orig)
                        self.log(f"Reverted (Deleted): {os.path.basename(orig)}", "#ffaa00")
                    else:
                        shutil.copy2(bak, orig)
                        self.log(f"Reverted (Restored): {os.path.basename(orig)}", "#ffaa00")
                except Exception as e:
                    self.log(f"❌ FATAL: Failed to revert {orig}: {e}", "#f44336")

            self.last_backups.clear()
            self.btn_revert.setEnabled(False)
            self.log("Revert protocol finished.", "#569cd6")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UniversalPatcherApp()
    window.show()
    sys.exit(app.exec())