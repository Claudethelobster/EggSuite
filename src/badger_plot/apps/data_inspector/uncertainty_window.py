# app/data_inspector/uncertainty_window.py
import re
import io
import numpy as np
from PyQt6.QtGui import QPixmap, QImage, QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QWidget, QScrollArea, QTabWidget, QFormLayout,
    QLineEdit
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from ui.theme import theme

class UncertaintyCalculatorDialog(QDialog):
    def __init__(self, dataset, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculate Uncertainties")
        self.resize(850, 700)
        self.dataset = dataset
        self.available_columns = dataset.column_names
        
        self.is_valid = False

        self.main_layout = QVBoxLayout(self)

        # 1. The North Star: Live HTML Preview
        self.main_layout.addWidget(QLabel("<b>Mathematical Preview:</b>"))
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(f"background-color: {theme.panel_bg}; color: {theme.fg}; border: 1px solid {theme.border}; font-size: 20px; font-family: Cambria, serif; font-style: italic; padding: 15px;")
        
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setWidget(self.preview_label)
        self.preview_scroll.setMinimumHeight(120)
        self.preview_scroll.setMaximumHeight(150)
        self.main_layout.addWidget(self.preview_scroll)

        # 2. The Mode Tabs
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        self._build_tab_standard()
        self._build_tab_general()
        self._build_tab_custom()
        
        self.tabs.currentChanged.connect(self.update_preview)
        

        # 3. Action Buttons
        btn_box = QHBoxLayout()
        
        btn_box.addWidget(QLabel("<b>Output Column Name:</b>"))
        self.output_name_input = QLineEdit("Calculated_Error")
        self.output_name_input.setFixedWidth(200)
        btn_box.addWidget(self.output_name_input)
        
        btn_box.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("padding: 8px;")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        self.calc_btn = QPushButton("⚙️ Calculate & Save")
        self.calc_btn.setStyleSheet(f"font-weight: bold; background-color: {theme.primary_bg}; color: {theme.primary_text}; padding: 8px 15px; border: 1px solid {theme.primary_border}; border-radius: 4px;")
        self.calc_btn.clicked.connect(self._run_calculation)
        btn_box.addWidget(self.calc_btn)
        
        self.main_layout.addLayout(btn_box)

        # Trigger initial preview
        self.update_preview()

    def _build_column_grid(self, target_input=None):
        """Generates the reusable grid of blue column buttons."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(110)
        btn_container = QWidget()
        grid = QFormLayout(btn_container)
        
        row_layout = QHBoxLayout()
        cols_in_row = 0
        for i, name in self.available_columns.items():
            btn = QPushButton(f"[{name}]")
            btn.setStyleSheet(f"color: {theme.primary_text}; font-weight: bold; border: 1px solid {theme.primary_border}; padding: 4px;")
            
            # If a target input is provided, clicking the button types the column name into it
            if target_input:
                btn.clicked.connect(lambda checked, n=name, target=target_input: target.textCursor().insertText(f"[{n}]"))
                
            row_layout.addWidget(btn)
            cols_in_row += 1
            if cols_in_row == 4:
                grid.addRow(row_layout)
                row_layout = QHBoxLayout()
                cols_in_row = 0
        if cols_in_row > 0:
            grid.addRow(row_layout)
            
        scroll.setWidget(btn_container)
        return scroll

    def _build_tab_standard(self):
        self.tab_standard = QWidget()
        layout = QVBoxLayout(self.tab_standard)
        
        # Method Dropdown & Pill Switch
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("<b>Propagation Method:</b>"))
        self.standard_combo = QComboBox()
        self.standard_combo.addItems([
            "Addition in Quadrature (Independent Errors)",
            "Simple Addition (Worst-Case Errors)",
            "Fractional / Relative Error"
        ])
        self.standard_combo.currentTextChanged.connect(self._on_standard_mode_changed)
        mode_layout.addWidget(self.standard_combo)
        
        mode_layout.addSpacing(20)
        
        # The Pill Switch
        from PyQt6.QtWidgets import QCheckBox
        self.power_switch = QCheckBox("Enable Exponents (n)")
        self.power_switch.setStyleSheet(f"font-weight: bold; color: {theme.warning_text};")
        self.power_switch.stateChanged.connect(self._on_standard_mode_changed)
        mode_layout.addWidget(self.power_switch)
        
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # The Dynamic Row Table (Now with 3 columns!)
        layout.addWidget(QLabel("<b>Map Data & Uncertainties:</b> <i>(Add rows for each term in your equation)</i>"))
        self.standard_table = QTableWidget()
        self.standard_table.setColumnCount(3)
        self.standard_table.setHorizontalHeaderLabels(["Base Data Column", "Uncertainty Column (δ)", "Exponent (n)"])
        self.standard_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.standard_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.standard_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.standard_table.verticalHeader().setVisible(False)
        self.standard_table.setAlternatingRowColors(True)
        layout.addWidget(self.standard_table)
        
        # Row Controls
        row_btns = QHBoxLayout()
        self.add_row_btn = QPushButton("➕ Add Row")
        self.add_row_btn.setStyleSheet(f"font-weight: bold; color: {theme.primary_text}; padding: 4px 10px;")
        self.add_row_btn.clicked.connect(self._add_standard_row)
        
        self.rem_row_btn = QPushButton("➖ Remove Row")
        self.rem_row_btn.setStyleSheet("padding: 4px 10px;")
        self.rem_row_btn.clicked.connect(self._rem_standard_row)
        
        row_btns.addWidget(self.add_row_btn)
        row_btns.addWidget(self.rem_row_btn)
        row_btns.addStretch()
        layout.addLayout(row_btns)
        
        self.tabs.addTab(self.tab_standard, "Standard Presets")
        
        # Add one default row to start
        self._add_standard_row()
        self._on_standard_mode_changed() # Trigger initial visibility

    def _add_standard_row(self):
        from PyQt6.QtWidgets import QLineEdit
        row = self.standard_table.rowCount()
        self.standard_table.insertRow(row)
        
        combo_data = QComboBox()
        combo_err = QComboBox()
        
        combo_data.addItem("None")
        combo_err.addItem("None")
        
        for col_idx, col_name in self.available_columns.items():
            combo_data.addItem(f"{col_idx}: {col_name}", col_idx)
            combo_err.addItem(f"{col_idx}: {col_name}", col_idx)
            
        # The new Exponent input box
        exp_edit = QLineEdit("1")
        exp_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        exp_edit.setMaximumWidth(80)
            
        self.standard_table.setCellWidget(row, 0, combo_data)
        self.standard_table.setCellWidget(row, 1, combo_err)
        self.standard_table.setCellWidget(row, 2, exp_edit)
        
        combo_data.currentIndexChanged.connect(self.update_preview)
        combo_err.currentIndexChanged.connect(self.update_preview)
        exp_edit.textChanged.connect(self.update_preview)
        
        self.update_preview()
        
    def _rem_standard_row(self):
        row = self.standard_table.currentRow()
        if row < 0:
            row = self.standard_table.rowCount() - 1
        if row >= 0:
            self.standard_table.removeRow(row)
            self.update_preview()

    def _on_standard_mode_changed(self, *args):
        # The logic gatekeeper
        is_fractional = "Fractional" in self.standard_combo.currentText()
        is_powers_on = self.power_switch.isChecked()
        
        # The Exponent column only shows if the switch is ON
        self.standard_table.setColumnHidden(2, not is_powers_on)
        
        # The Base Data column shows if Fractional is selected OR if Powers are enabled
        self.standard_table.setColumnHidden(0, not (is_fractional or is_powers_on))
        
        self.update_preview()

    def _build_tab_general(self):
        self.tab_general = QWidget()
        layout = QVBoxLayout(self.tab_general)
        
        layout.addWidget(QLabel("<b>1. Build Base Equation:</b> <i>(e.g. [Voltage] / [Current])</i>"))
        
        self.general_input = QTextEdit()
        self.general_input.setMaximumHeight(60)
        self.general_input.textChanged.connect(self.update_preview)
        
        layout.addWidget(self._build_column_grid(target_input=self.general_input))
        layout.addWidget(self.general_input)
        
        layout.addWidget(QLabel("<b>2. Map Variables to Uncertainties:</b>"))
        self.general_table = QTableWidget()
        self.general_table.setColumnCount(2)
        self.general_table.setHorizontalHeaderLabels(["Variable in Equation", "Associated Uncertainty Column (δ)"])
        self.general_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.general_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.general_table.verticalHeader().setVisible(False)
        self.general_table.setAlternatingRowColors(True)
        layout.addWidget(self.general_table)
        
        self.tabs.addTab(self.tab_general, "General Propagation (Derivatives)")

    def _build_tab_custom(self):
        self.tab_custom = QWidget()
        layout = QVBoxLayout(self.tab_custom)
        
        layout.addWidget(QLabel("<b>Custom Error Equation:</b> <i>(Define the exact error formula using columns directly)</i>"))
        
        self.custom_input = QTextEdit()
        self.custom_input.textChanged.connect(self.update_preview)
        
        layout.addWidget(self._build_column_grid(target_input=self.custom_input))
        layout.addWidget(self.custom_input)
        
        self.tabs.addTab(self.tab_custom, "Custom Formula")
        
    def _render_html_maths(self, raw_text):
        import re
        html_text = raw_text

        # 1. Variables in brackets [Var]
        cols = []
        def col_repl(m):
            cols.append(m.group(1))
            return f"__COL{len(cols)-1}__"
        html_text = re.sub(r'\[(.*?)\]', col_repl, html_text)

        # 2. Physics Constants
        consts = []
        def const_repl(m):
            from core.constants import PHYSICS_CONSTANTS
            c_key = m.group(1)
            if c_key in PHYSICS_CONSTANTS:
                c_html = PHYSICS_CONSTANTS[c_key]["html"]
                span = f"<span style='color: {theme.success_text}; font-weight: bold; font-style: normal;'>{c_html}</span>"
            else:
                span = f"<span style='color: {theme.danger_text};'>{{\\{c_key}}}</span>"
            consts.append(span)
            return f"__CONST{len(consts)-1}__"
        html_text = re.sub(r'\{\\(.*?)\}', const_repl, html_text)

        # Replace basic symbols
        html_text = html_text.replace('*', '&middot;')
        html_text = html_text.replace('-', '&minus;')
        html_text = re.sub(r'\bpi\b', 'π', html_text)
        
        # Convert sqrt() to √() for the parser
        html_text = html_text.replace('sqrt(', '√(')

        # Math functions
        funcs = []
        def func_repl(m):
            func = m.group(1).lower()
            func = re.sub(r'_?([0-9]+)', r"<sub style='font-size:12px;'>\1</sub>", func)
            funcs.append(f"<span style='font-style: normal; font-weight: bold; color: {theme.fg};'>{func}</span>")
            return f"__FUNC{len(funcs)-1}__"
        
        math_funcs = ['arcsin','arccos','arctan','arcsinh','arccosh','arctanh','sinh','cosh','tanh','sin','cos','tan','ln','log(?:_?[0-9]+)?','abs','norm', 'exp']
        html_text = re.sub(r'\b(' + '|'.join(math_funcs) + r')\b', func_repl, html_text, flags=re.IGNORECASE)

        # Standard tokenizer
        def tokenize_to_horizontal(text, f_size):
            parts = re.split(r'(__COL\d+__|__FUNC\d+__|__PAREN\d+__|__EXP\d+__|__CONST\d+__)', text)
            row_html = "<table style='display:inline-table; border-collapse: collapse; margin: 0;'><tr>"
            for p in parts:
                if not p: continue
                row_html += f"<td style='vertical-align:middle; padding:0; white-space:nowrap; font-size:{f_size};'>{p}</td>"
            return row_html + "</tr></table>"

        # Exponents
        exps = []
        def resolve_exponents(text, is_exp=False):
            f_size_base = "15px" if is_exp else "22px"
            f_size_exp  = "10px" if is_exp else "15px"
            spacer      = "6px"  if is_exp else "10px"
            while True:
                # Allowed Unicode characters for calculus formatting
                match = re.search(r'([a-zA-Zπδ∂\.]+|[0-9\.]+|__COL\d+__|__PAREN\d+__|__FUNC\d+__|__EXP\d+__|__CONST\d+__)\s*\^\s*(-?[a-zA-Zπδ∂\.]+|-?[0-9\.]+|__COL\d+__|__PAREN\d+__|__FUNC\d+__|__EXP\d+__|__CONST\d+__)', text)
                if not match: break
                base, exp = match.group(1), match.group(2)
                table = (
                    f"<table style='display:inline-table; border-collapse:collapse; margin: 0;'>"
                    f"<tr>"
                    f"<td style='vertical-align:bottom; padding:0; padding-right:1px; font-size:{f_size_base};'>{base}</td>"
                    f"<td style='vertical-align:top; padding:0;'>"
                    f"  <table style='border-collapse:collapse; margin:0; padding:0;'>"
                    f"    <tr><td style='vertical-align:top; padding:0; font-size:{f_size_exp};'>{exp}</td></tr>"
                    f"    <tr><td style='font-size:{spacer}; padding:0;'>&nbsp;</td></tr>"
                    f"  </table>"
                    f"</td>"
                    f"</tr></table>"
                )
                exps.append(table)
                text = text[:match.start()] + f"__EXP{len(exps)-1}__" + text[match.end():]
            return text

        parens = []
        def process_math_block(text, is_exp=False, has_parens=False, is_sqrt=False):
            f_size = "15px" if is_exp else "20px"
            
            is_frac = '/' in text
            if is_exp:
                p_size = "200%" if is_frac else "110%"
                rad_size = "200%" if is_frac else "120%"
            else:
                # 300% ensures the brackets/radical span the entire 2-line fraction height
                p_size = "300%" if is_frac else "110%"
                rad_size = "280%" if is_frac else "120%"
            
            if not is_frac:
                res = tokenize_to_horizontal(text, f_size)
                if has_parens:
                    res = (
                        f"<table cellspacing='0' cellpadding='0' style='display:inline-table; border-collapse:collapse; margin:0; vertical-align: middle;'>"
                        f"<tr>"
                        f"<td style='vertical-align:middle; font-size:{f_size}; padding:0 2px; color:{theme.fg};'>(</td>"
                        f"<td style='vertical-align:middle; padding:0;'>{res}</td>"
                        f"<td style='vertical-align:middle; font-size:{f_size}; padding:0 2px; color:{theme.fg};'>)</td>"
                        f"</tr></table>"
                    )
            else:
                parts = text.split('/')
                num = tokenize_to_horizontal(parts[0].strip() or "&nbsp;", f_size)
                
                for p in parts[1:]:
                    den = tokenize_to_horizontal(p.strip() or "&nbsp;", f_size)
                    if has_parens:
                        # Single giant bracket, but with 10px padding on the fraction to prevent clipping!
                        res = (
                            f"<table cellspacing='0' cellpadding='0' style='display:inline-table; vertical-align:middle; border-collapse:collapse; margin: 0 4px;'>"
                            f"<tr>"
                            f"<td rowspan='2' style='vertical-align:middle; font-size:{p_size}; padding: 0 2px 6px 2px; color:{theme.fg}; font-family: \"Cambria Math\", \"Segoe UI\", sans-serif; font-weight: 300;'>(</td>"
                            f"<td style='border-bottom:1px solid {theme.fg}; padding: 0 10px; text-align:center; vertical-align:bottom;'>{num}</td>"
                            f"<td rowspan='2' style='vertical-align:middle; font-size:{p_size}; padding: 0 2px 6px 2px; color:{theme.fg}; font-family: \"Cambria Math\", \"Segoe UI\", sans-serif; font-weight: 300;'>)</td>"
                            f"</tr>"
                            f"<tr><td style='padding: 4px 10px 0 10px; text-align:center; vertical-align:top;'>{den}</td></tr>"
                            f"</table>"
                        )
                        has_parens = False 
                    else:
                        res = (
                            f"<table cellspacing='0' cellpadding='0' style='display:inline-table; vertical-align:middle; border-collapse:collapse; margin: 0 2px;'>"
                            f"<tr><td style='border-bottom:1px solid {theme.fg}; padding: 0 8px; text-align:center; vertical-align:bottom;'>{num}</td></tr>"
                            f"<tr><td style='padding: 4px 8px 0 8px; text-align:center; vertical-align:top;'>{den}</td></tr>"
                            f"</table>"
                        )
                    num = res 
                    
            if is_sqrt:
                # Giant radical aligned to the middle so its top bar naturally meets the fraction roof
                res = (
                    f"<table cellspacing='0' cellpadding='0' style='display:inline-table; border-collapse:collapse; margin:0 4px; vertical-align: middle;'>"
                    f"<tr>"
                    f"<td style='vertical-align:middle; font-size:{rad_size}; padding:0 2px 6px 0; color:{theme.fg}; font-family: \"Cambria Math\", serif; font-weight: lighter;'>&radic;</td>"
                    f"<td style='border-top:1px solid {theme.fg}; padding: 4px 4px 0 4px; vertical-align:middle;'>{res}</td>"
                    f"</tr></table>"
                )
                
            return res
        while True:
            match = re.search(r'(√?|\^?)\(([^()]*)\)', html_text)
            if not match: break
            
            prefix = match.group(1)
            is_e = (prefix == '^')
            is_s = (prefix == '√')
            inner = match.group(2)
            
            inner = resolve_exponents(inner, is_exp=is_e) 
            formatted_inner = process_math_block(inner, is_exp=is_e, has_parens=(not is_s), is_sqrt=is_s)
            
            ph = f"__PAREN{len(parens)}__"
            parens.append(formatted_inner)
            
            if is_e:
                html_text = html_text[:match.start()] + '^' + ph + html_text[match.end():]
            else:
                html_text = html_text[:match.start()] + ph + html_text[match.end():]
            
        html_text = resolve_exponents(html_text, is_exp=False) 
        html_text = process_math_block(html_text, is_exp=False, has_parens=False)
        
        for _ in range(15): 
            if not re.search(r'__(EXP|PAREN|FUNC|COL|CONST)\d+__', html_text): break
            for i in range(len(exps)): html_text = html_text.replace(f"__EXP{i}__", exps[i])
            for i in range(len(parens)): html_text = html_text.replace(f"__PAREN{i}__", parens[i])
            for i in range(len(funcs)): html_text = html_text.replace(f"__FUNC{i}__", funcs[i])
            for i in range(len(consts)): html_text = html_text.replace(f"__CONST{i}__", consts[i])
            for i in range(len(cols)):
                span = f"<span style='color: {theme.primary_text}; font-weight: bold;'>{cols[i]}</span>"
                html_text = html_text.replace(f"__COL{i}__", span)
            
        return html_text

    def update_preview(self):
        current_tab = self.tabs.currentIndex()
        latex_str = ""
        
        # Helper for the Standard Tab to match the new bracket styling
        def clean_var(name):
            clean_name = name.replace("_", r"\_").replace(" ", "~")
            return r"\left[ \mathbf{" + clean_name + r"} \right]"
        
        if current_tab == 0:
            # Standard Tab Preview Logic
            mode = self.standard_combo.currentText()
            is_powers_on = self.power_switch.isChecked()
            
            terms = []
            frac_terms = []
            linear_terms = [] 
            
            for row in range(self.standard_table.rowCount()):
                data_cb = self.standard_table.cellWidget(row, 0)
                err_cb = self.standard_table.cellWidget(row, 1)
                exp_edit = self.standard_table.cellWidget(row, 2)
                
                d_text = data_cb.currentText().split(": ")[-1] if data_cb.currentIndex() > 0 else f"A_{row+1}"
                e_text = err_cb.currentText().split(": ")[-1] if err_cb.currentIndex() > 0 else f"\\delta A_{row+1}"
                
                d_latex = clean_var(d_text) if data_cb.currentIndex() > 0 else d_text
                e_latex = clean_var(e_text) if err_cb.currentIndex() > 0 else e_text
                
                exp_text = exp_edit.text().strip() if is_powers_on else ""
                try:
                    if not exp_text:
                        n_val, n_mult, pow_str = 1.0, "", ""
                    elif "/" in exp_text:
                        from fractions import Fraction
                        f = Fraction(exp_text.replace(" ", ""))
                        n_val = float(f)
                        
                        if f.denominator == 1: n_mult = f"{f.numerator} \\cdot "
                        else:
                            sign = "-" if f < 0 else ""
                            n_mult = f"{sign}\\frac{{{abs(f.numerator)}}}{{{f.denominator}}} \\cdot "
                            
                        f_pow = f - 1
                        if f_pow == 1: pow_str = ""
                        elif f_pow.denominator == 1: pow_str = f"^{{{f_pow.numerator}}}"
                        else:
                            p_sign = "-" if f_pow < 0 else ""
                            pow_str = f"^{{ {p_sign}\\frac{{{abs(f_pow.numerator)}}}{{{f_pow.denominator}}} }}"
                    else:
                        n_val = float(exp_text)
                        if n_val == 1.0: n_mult, pow_str = "", ""
                        else:
                            n_mult = f"{n_val:g} \\cdot "
                            pow_str = f"^{{{n_val - 1:g}}}" if (n_val - 1) != 1.0 else ""
                except Exception:
                    n_val, n_mult, pow_str = 1.0, "", ""
                
                if n_val == 1.0:
                    terms.append(f"{e_latex}^2")
                    linear_terms.append(e_latex)
                else:
                    terms.append(r"\left( " + f"{n_mult}{d_latex}{pow_str} \\cdot {e_latex}" + r" \right)^2")
                    linear_terms.append(f"{n_mult}{d_latex}{pow_str} \\cdot {e_latex}")
                    
                if n_val == 1.0:
                    frac_terms.append(r"\left( \frac{" + e_latex + "}{" + d_latex + r"} \right)^2")
                else:
                    frac_terms.append(r"\left( " + f"{n_mult}\\frac{{{e_latex}}}{{{d_latex}}}" + r" \right)^2")
                
            if not terms:
                self.preview_label.setText("<span style='color: #888;'>Add a row to see the equation...</span>")
                return
            else:
                if "Quadrature" in mode: latex_str = r"\delta q = \sqrt{ " + " + ".join(terms) + " }"
                elif "Worst-Case" in mode: latex_str = r"\delta q = " + " + ".join(linear_terms)
                elif "Fractional" in mode: latex_str = r"\frac{\delta q}{q} = \sqrt{ " + " + ".join(frac_terms) + " }"
                    
        elif current_tab == 1:
            # General Derivative Tab Preview Logic
            raw_text = self.general_input.toPlainText().strip()
            if not raw_text:
                self.preview_label.setText("<span style='color: #888;'>Type a base equation to see derivative propagation...</span>")
                self._update_mapping_table([])
                return
                
            # Process via the new LaTeX engine!
            formatted_base, error_chars = self._format_latex_equation(raw_text)
            
            if error_chars:
                self.preview_label.setText(f"<span style='color: #ff5555;'><b>Invalid unrecognised variables:</b> {error_chars}</span><br><span style='color: #888; font-size: 14px;'>Please use the blue buttons for columns, or valid math functions (sin, cos, ln, etc).</span>")
                self._update_mapping_table([])
                return

            base_eq_str = r"q = " + formatted_base
                
            vars_detected = list(set(re.findall(r'\[(.*?)\]', raw_text)))
            if vars_detected:
                terms = [r"\left( \frac{\partial q}{\partial " + clean_var(v) + r"} \delta " + clean_var(v) + r" \right)^2" for v in vars_detected]
                deriv_eq_str = r"\delta q = \sqrt{ " + " + ".join(terms) + " }"
                latex_str = base_eq_str + "\n" + r"\Downarrow" + "\n" + deriv_eq_str
            else:
                latex_str = base_eq_str
                
            self._update_mapping_table(vars_detected)
            
        elif current_tab == 2:
            # Custom Tab Preview Logic
            raw_text = self.custom_input.toPlainText().strip()
            if not raw_text:
                self.preview_label.setText("<span style='color: #888;'>Type a custom equation...</span>")
                return
            
            formatted_custom, error_chars = self._format_latex_equation(raw_text)
            
            if error_chars:
                self.preview_label.setText(f"<span style='color: #ff5555;'><b>Invalid unrecognised variables:</b> {error_chars}</span><br><span style='color: #888; font-size: 14px;'>Please use the blue buttons for columns, or valid math functions (sin, cos, ln, etc).</span>")
                return
                
            latex_str = r"\delta q = " + formatted_custom

        # Render the LaTeX string to an image
        pixmap = self._render_latex_pixmap(latex_str)
        
        if pixmap:
            self.preview_label.setPixmap(pixmap)
        else:
            self.preview_label.setText("<span style='color: #ff5555;'>Invalid mathematical syntax</span>")

    def _update_mapping_table(self, vars_detected):
        """Dynamically builds the dropdown table for the General tab."""
        current_rows = [self.general_table.item(i, 0).text() for i in range(self.general_table.rowCount())]
        if set(current_rows) == set(f"[{v}]" for v in vars_detected):
            return
            
        self.general_table.setRowCount(len(vars_detected))
        for i, var in enumerate(vars_detected):
            var_item = QTableWidgetItem(f"[{var}]")
            var_item.setFlags(var_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            # --- FIX THIS LINE ---
            var_item.setForeground(QColor(theme.primary_text))
            
            font = var_item.font()
            font.setBold(True)
            var_item.setFont(font)
            self.general_table.setItem(i, 0, var_item)
            
            combo = QComboBox()
            combo.addItem("None (Assume Zero Error)")
            for col_idx, col_name in self.available_columns.items():
                combo.addItem(f"{col_idx}: {col_name}", col_idx)
            self.general_table.setCellWidget(i, 1, combo)
            
    def _render_latex_pixmap(self, latex_str):
        """Renders a LaTeX string into a transparent PyQt6 QPixmap."""
        try:
            fig = Figure(figsize=(0.01, 0.01), facecolor="none", edgecolor="none")
            canvas = FigureCanvasAgg(fig)
            
            # Split by newline and wrap each line in $...$ to stack equations
            formatted_text = "\n".join([f"${line}$" for line in latex_str.split("\n")])
            
            # Added ha='center' so stacked equations align beautifully in the middle
            text = fig.text(0, 0, formatted_text, fontsize=18, color=theme.fg, ha='center')
            
            canvas.draw()
            bbox = text.get_window_extent()
            
            fig.set_size_inches(bbox.width / fig.dpi, bbox.height / fig.dpi)
            
            import io
            buf = io.BytesIO()
            fig.savefig(buf, format='png', transparent=True, dpi=120, bbox_inches='tight', pad_inches=0.1)
            buf.seek(0)
            
            img = QImage.fromData(buf.read())
            return QPixmap.fromImage(img)
            
        except Exception as e:
            print(f"Matplotlib LaTeX Error: {e}")
            print(f"Attempted String: {latex_str}")
            return None
        
    def _format_latex_equation(self, raw_text):
        """Parses raw user input into safely formatted LaTeX, handling fractions and validation."""
        if not raw_text:
            return "", None

        import re

        # 1. Validation: Check for nonsense variables
        temp_text = re.sub(r'\[(.*?)\]', '', raw_text)
        
        funcs = ['sin', 'cos', 'tan', 'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh', 'ln', 'log', 'exp', 'sqrt', 'abs']
        constants = ['pi', 'e']
        
        # Strip out allowed math functions and constants
        temp_text = re.sub(r'\b(' + '|'.join(funcs + constants) + r')\b', '', temp_text)
        
        # Strip out standard math operators, numbers, and spaces
        temp_text = re.sub(r'[0-9\.\+\-\*\/\^\(\)\s]', '', temp_text)
        
        if len(temp_text) > 0:
            invalid_chars = ", ".join(set(temp_text))
            return None, invalid_chars

        # 2. Extract Columns to safe placeholders
        cols = []
        def col_repl(m):
            cols.append(m.group(1))
            return f"__COL{len(cols)-1}__"
        text = re.sub(r'\[(.*?)\]', col_repl, raw_text)

        # 3. Parse Fractions FIRST (Before adding LaTeX backslashes!)
        while '/' in text:
            idx = text.find('/')
            
            # --- Numerator Bounds ---
            num_start = idx - 1
            while num_start >= 0 and text[num_start] == ' ': num_start -= 1
            
            if num_start >= 0 and text[num_start] == ')':
                parens = 1
                num_start -= 1
                while num_start >= 0 and parens > 0:
                    if text[num_start] == ')': parens += 1
                    elif text[num_start] == '(': parens -= 1
                    num_start -= 1
                # Continue backwards to grab function names like 'sin' before the '('
                while num_start >= 0 and (text[num_start].isalnum() or text[num_start] in '_.'):
                    num_start -= 1
                num_start += 1
            else:
                while num_start >= 0 and (text[num_start].isalnum() or text[num_start] in '_.'):
                    num_start -= 1
                num_start += 1
            numerator = text[num_start:idx]

            # --- Denominator Bounds ---
            den_end = idx + 1
            while den_end < len(text) and text[den_end] == ' ': den_end += 1
            
            if den_end < len(text) and text[den_end] == '(':
                parens = 1
                den_end += 1
                while den_end < len(text) and parens > 0:
                    if text[den_end] == '(': parens += 1
                    elif text[den_end] == ')': parens -= 1
                    den_end += 1
                den_end -= 1
            else:
                while den_end < len(text) and (text[den_end].isalnum() or text[den_end] in '_.'):
                    den_end += 1
                # If a function name is immediately followed by parens, grab them too!
                if den_end < len(text) and text[den_end] == '(':
                    parens = 1
                    den_end += 1
                    while den_end < len(text) and parens > 0:
                        if text[den_end] == '(': parens += 1
                        elif text[den_end] == ')': parens -= 1
                        den_end += 1
                den_end -= 1
            denominator = text[idx+1:den_end+1]

            # Helper to strip redundant outer parentheses
            def strip_parens(s):
                s = s.strip()
                if s.startswith('(') and s.endswith(')'):
                    p = 0
                    for i, c in enumerate(s):
                        if c == '(': p += 1
                        elif c == ')': p -= 1
                        if p == 0 and i < len(s) - 1: return s
                    return s[1:-1]
                return s

            num_clean = strip_parens(numerator)
            den_clean = strip_parens(denominator)

            # --- FIX: Protect against dangling fractions during live-typing ---
            if not num_clean: num_clean = "~"
            if not den_clean: den_clean = "~"
            # ------------------------------------------------------------------

            replace_str = r"\frac{" + num_clean + r"}{" + den_clean + r"}"
            text = text[:num_start] + replace_str + text[den_end+1:]

        # 4. Format Math Functions to upright (non-italic) Roman text
        def func_repl(m):
            return r"\mathrm{" + m.group(1) + r"}"
        text = re.sub(r'\b(' + '|'.join(funcs) + r')\b', func_repl, text)

        # 5. Format Constants (The Special Way)
        text = re.sub(r'\bpi\b', r'\\pi ', text)
        text = re.sub(r'\be\b', r'\\mathrm{e}', text)

        # 6. Restore columns and wrap them in elegant LaTeX square brackets
        for i, col in enumerate(cols):
            clean_name = col.replace("_", r"\_").replace(" ", "~")
            col_latex = r"\left[ \mathbf{" + clean_name + r"} \right]"
            text = text.replace(f"__COL{i}__", col_latex)

        # 7. Final Polish (dot multiplication and protecting dangling exponents)
        text = text.replace('*', r'\cdot ')
        text = re.sub(r'\^$', '^{}', text)
        text = re.sub(r'\^(\s+)', r'^{}\1', text)

        return text, None
    
    def _run_calculation(self):
        import numpy as np
        from PyQt6.QtWidgets import QMessageBox
        import copy
        import os
        import glob
        
        out_name = self.output_name_input.text().strip()
        if not out_name:
            QMessageBox.warning(self, "Missing Output Name", "Please provide a name for the new output column.")
            return

        # Grab the Pandas DataFrame from the parent window
        parent_win = self.parent()
        df = parent_win.df
        current_tab = self.tabs.currentIndex()
        
        try:
            if current_tab == 0:
                # ==========================================
                # TAB 0: PURE NUMPY VECTORISED STANDARD MATH
                # ==========================================
                mode = self.standard_combo.currentText()
                is_powers_on = self.power_switch.isChecked()
                term_arrays = []
                
                for row in range(self.standard_table.rowCount()):
                    data_cb = self.standard_table.cellWidget(row, 0)
                    err_cb = self.standard_table.cellWidget(row, 1)
                    exp_edit = self.standard_table.cellWidget(row, 2)
                    
                    if err_cb.currentIndex() <= 0: continue
                        
                    err_col_name = err_cb.currentText().split(": ")[-1]
                    err_arr = df[err_col_name].to_numpy(dtype=float)
                    
                    if data_cb.currentIndex() > 0:
                        data_col_name = data_cb.currentText().split(": ")[-1]
                        data_arr = df[data_col_name].to_numpy(dtype=float)
                    else:
                        data_arr = np.ones_like(err_arr)
                    
                    exp_text = exp_edit.text().strip() if is_powers_on else ""
                    try:
                        if not exp_text: n_val = 1.0
                        elif "/" in exp_text:
                            from fractions import Fraction
                            n_val = float(Fraction(exp_text.replace(" ", "")))
                        else: n_val = float(exp_text)
                    except Exception: n_val = 1.0

                    if "Quadrature" in mode or "Worst-Case" in mode:
                        term = err_arr if n_val == 1.0 else n_val * np.power(data_arr, n_val - 1) * err_arr
                    elif "Fractional" in mode:
                        term = n_val * (err_arr / data_arr)
                    
                    term_arrays.append(term)

                if not term_arrays:
                    QMessageBox.warning(self, "No Data", "Please map at least one uncertainty column.")
                    return

                if "Quadrature" in mode or "Fractional" in mode:
                    squared_sum = sum(np.power(t, 2) for t in term_arrays)
                    final_result = np.sqrt(squared_sum)
                elif "Worst-Case" in mode:
                    final_result = sum(np.abs(t) for t in term_arrays)

                df[out_name] = final_result

            elif current_tab == 1:
                # ==========================================
                # TAB 1: UNCERTAINTIES MODULE (DERIVATIVES)
                # ==========================================
                from uncertainties import unumpy
                
                raw_text = self.general_input.toPlainText().strip()
                if not raw_text: return
                
                # 1. Build the safe math environment for unumpy
                safe_env = {
                    'sin': unumpy.sin, 'cos': unumpy.cos, 'tan': unumpy.tan,
                    'arcsin': unumpy.arcsin, 'arccos': unumpy.arccos, 'arctan': unumpy.arctan,
                    'sinh': unumpy.sinh, 'cosh': unumpy.cosh, 'tanh': unumpy.tanh,
                    'exp': unumpy.exp, 'log': unumpy.log, 'ln': unumpy.log,
                    'sqrt': unumpy.sqrt, 'abs': abs, 'pi': np.pi, 'e': np.e
                }
                
                # 2. Extract variables and map them to ufloat arrays
                vars_detected = list(set(re.findall(r'\[(.*?)\]', raw_text)))
                parsed_eq = raw_text.replace('^', '**') # Python uses ** for powers
                
                for i, var in enumerate(vars_detected):
                    base_arr = df[var].to_numpy(dtype=float)
                    
                    # Find the mapped error column from the table
                    err_col = None
                    for row in range(self.general_table.rowCount()):
                        if self.general_table.item(row, 0).text() == f"[{var}]":
                            combo = self.general_table.cellWidget(row, 1)
                            if combo.currentIndex() > 0:
                                err_col = combo.currentText().split(": ")[-1]
                            break
                            
                    err_arr = df[err_col].to_numpy(dtype=float) if err_col else np.zeros_like(base_arr)
                    
                    # Create the unumpy array and inject it into the environment!
                    var_name = f"var_{i}"
                    safe_env[var_name] = unumpy.uarray(base_arr, err_arr)
                    parsed_eq = parsed_eq.replace(f"[{var}]", var_name)
                    
                # 3. Evaluate the expression
                u_result = eval(parsed_eq, {"__builtins__": {}}, safe_env)
                
                # 4. Extract just the standard deviations (the propagated error!)
                df[out_name] = unumpy.std_devs(u_result)

            elif current_tab == 2:
                # ==========================================
                # TAB 2: PURE NUMPY (CUSTOM FORMULA)
                # ==========================================
                raw_text = self.custom_input.toPlainText().strip()
                if not raw_text: return
                
                safe_env = {
                    'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
                    'arcsin': np.arcsin, 'arccos': np.arccos, 'arctan': np.arctan,
                    'sinh': np.sinh, 'cosh': np.cosh, 'tanh': np.tanh,
                    'exp': np.exp, 'log': np.log, 'ln': np.log,
                    'sqrt': np.sqrt, 'abs': np.abs, 'pi': np.pi, 'e': np.e
                }
                
                vars_detected = list(set(re.findall(r'\[(.*?)\]', raw_text)))
                parsed_eq = raw_text.replace('^', '**')
                
                for i, var in enumerate(vars_detected):
                    var_name = f"var_{i}"
                    safe_env[var_name] = df[var].to_numpy(dtype=float)
                    parsed_eq = parsed_eq.replace(f"[{var}]", var_name)
                    
                df[out_name] = eval(parsed_eq, {"__builtins__": {}}, safe_env)
            
            # ==========================================
            # FINAL SAVE ROUTINE (MIRROR FILE LOGIC)
            # ==========================================
            dataset = parent_win.current_dataset
            fname = dataset.filename
            orig_name = os.path.basename(fname)
            directory = os.path.dirname(fname)
            
            if not orig_name.startswith("MIRROR_"):
                name_only, ext = os.path.splitext(orig_name)
                search_pattern = os.path.join(directory, f"MIRROR_{name_only}*{ext}")
                existing_mirrors = [os.path.basename(p) for p in glob.glob(search_pattern)]
                
                max_num = max([int(m.group(1)) for m in [re.search(r'\((\d+)\)', x) for x in existing_mirrors] if m] + [1 if f"MIRROR_{orig_name}" in existing_mirrors else 0])
                mirror_name = f"MIRROR_{name_only} ({max_num + 1}){ext}" if existing_mirrors else f"MIRROR_{orig_name}"
                target_file = os.path.join(directory, mirror_name)
                
                QMessageBox.information(self, "Mirror Created", f"To protect original data, your calculations have been saved to a Mirror file:\n{mirror_name}")
            else:
                target_file = fname
                
            df.to_csv(target_file, index=False, encoding='utf-8-sig')
            
            if target_file != fname:
                new_dataset = copy.deepcopy(dataset)
                new_dataset.data = df.to_numpy()
                
                num_existing_cols = len(new_dataset.column_names)
                new_dataset.column_names[num_existing_cols] = out_name
                new_dataset.num_inputs += 1 
                new_dataset.num_points = len(df)
                new_dataset.filename = target_file
                
                if hasattr(parent_win.workspace, 'add_single_file'):
                    parent_win.workspace.add_single_file(target_file, new_dataset)
                else:
                    parent_win.workspace.datasets[target_file] = {
                        "name": os.path.basename(target_file), "type": "file", 
                        "parent": None, "children": [], "dataset": new_dataset
                    }
                    
                parent_win.current_dataset = new_dataset
                parent_win.workspace_btn.setText(f"Active: {os.path.basename(target_file)} ▾")
                parent_win.workspace.dataset_added.emit(target_file)
            else:
                dataset.data = df.to_numpy()
                num_existing_cols = len(dataset.column_names)
                dataset.column_names[num_existing_cols] = out_name
                dataset.num_inputs += 1
                dataset.num_points = len(df)
            
            parent_win.table_model.set_dataframe(df)
            parent_win.df = df
            parent_win.stats_label.setText(f"Rows: {len(df):,} | Columns: {len(df.columns)}")
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"A mathematical error occurred during processing:\n\n{str(e)}\n\nCheck for division by zero, invalid powers, or unmapped columns.")