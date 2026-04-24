# external_modules/matplot_translator.py
import pyqtgraph as pg
import numpy as np
import re
import html
from PyQt6.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QDialog, 
                             QTabWidget, QFormLayout, QLineEdit, QComboBox, 
                             QPushButton, QDoubleSpinBox, QColorDialog, QDialogButtonBox, QLabel)
from PyQt6.QtGui import QColor, QPainter, QIcon, QAction
from PyQt6.QtCore import Qt, pyqtSignal
from ui.theme import theme
from ui.custom_widgets import ColorButton

# --- Matplotlib Imports ---
import matplotlib
try:
    matplotlib.use('QtAgg', force=True)
except Exception:
    pass 
    
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import matplotlib.colors as mcolors

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_mpl_linestyle(qpen):
    style = qpen.style()
    if style == Qt.PenStyle.SolidLine: return '-'
    elif style == Qt.PenStyle.DashLine: return '--'
    elif style == Qt.PenStyle.DotLine: return ':'
    elif style == Qt.PenStyle.DashDotLine: return '-.'
    elif style == Qt.PenStyle.DashDotDotLine: return '-.'
    elif style == Qt.PenStyle.NoPen: return 'None'
    return '-'

def qcolor_to_mpl_rgba(qcolor):
    """Bulletproof conversion: QColor to Matplotlib RGBA float tuple."""
    return (qcolor.redF(), qcolor.greenF(), qcolor.blueF(), qcolor.alphaF())

def mpl_color_to_qcolor(mpl_color):
    """Converts Matplotlib color (string, hex, or tuple) to QColor."""
    try:
        rgba = mcolors.to_rgba(mpl_color)
        return QColor(int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255), int(rgba[3]*255))
    except Exception:
        return QColor(255, 255, 255)

def extract_legends(main_window):
    """Builds a map of PlotDataItems to their clean legend names."""
    item_to_name = {}
    legends = [getattr(main_window, 'legend', None), getattr(main_window, 'fit_legend', None)]
    for leg in legends:
        if leg is not None and hasattr(leg, 'items'):
            for sample, label in leg.items:
                item = getattr(sample, 'item', None)
                if item is not None:
                    name = getattr(label, 'base_name', label.text) if hasattr(label, 'text') else str(label)
                    name = html.unescape(name)
                    clean_name = re.sub('<[^<]+>', '', name)
                    item_to_name[item] = clean_name
    return item_to_name

def extract_live_styles(item):
    """Reaches into the live plot item and extracts the exact current styles."""
    opts = getattr(item, 'opts', {})
    
    has_curve = True
    has_scatter = True
    if hasattr(item, 'curve'): has_curve = item.curve.isVisible()
    if hasattr(item, 'scatter'): has_scatter = item.scatter.isVisible()
    
    if isinstance(item, pg.PlotCurveItem): has_scatter = False
    if isinstance(item, pg.ScatterPlotItem): has_curve = False

    line_pen = opts.get('pen')
    sym = opts.get('symbol')
    sym_size = opts.get('symbolSize', opts.get('size', 5))
    sym_brush = opts.get('symbolBrush', opts.get('brush'))
    sym_pen = opts.get('symbolPen')

    if has_curve and hasattr(item, 'curve'):
        line_pen = item.curve.opts.get('pen', line_pen)
        
    if has_scatter and hasattr(item, 'scatter'):
        sym = item.scatter.opts.get('symbol', sym)
        sym_size = item.scatter.opts.get('size', sym_size)
        sym_brush = item.scatter.opts.get('brush', sym_brush)
        sym_pen = item.scatter.opts.get('pen', sym_pen)

    if not has_curve:
        p_line = pg.mkPen(style=Qt.PenStyle.NoPen)
    else:
        p_line = pg.mkPen(line_pen) if line_pen is not None else pg.mkPen(None)
        
    if not has_scatter:
        sym = None
        
    fallback_color = p_line.color() if p_line.style() != Qt.PenStyle.NoPen else pg.getConfigOption('foreground')
    if sym_brush is None: sym_brush = fallback_color
    if sym_pen is None: sym_pen = fallback_color

    b_sym = pg.mkBrush(sym_brush)
    p_sym = pg.mkPen(sym_pen)
    
    return p_line, sym, sym_size, b_sym, p_sym


# ==========================================
# CUSTOM UI WIDGETS
# ==========================================


class CustomFigureOptionsDialog(QDialog):
    """A beautiful, native EggSuite replacement for Matplotlib's clunky options menu."""
    def __init__(self, ax, parent=None):
        super().__init__(parent)
        self.ax = ax
        self.setWindowTitle("Figure Options")
        self.setMinimumWidth(380)
        
        # --- FIX: Extract logical handles from the legend, not the raw lines! ---
        handles, labels = self.ax.get_legend_handles_labels()
        self.lines = handles 
        # ------------------------------------------------------------------------
        
        self.ls_map = {'Solid': '-', 'Dashed': '--', 'DashDot': '-.', 'Dotted': ':', 'None': 'None'}
        self.ls_map_inv = {v: k for k, v in self.ls_map.items()}
        self.marker_map = {'Circle': 'o', 'Square': 's', 'Triangle Up': '^', 'Triangle Down': 'v', 'Diamond': 'd', 'Cross': '+', 'X': 'x', 'None': 'None'}
        self.marker_map_inv = {v: k for k, v in self.marker_map.items()}
        
        self.layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        self._build_axes_tab()
        self._build_curves_tab()
        
        self.layout.addWidget(self.tabs)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        btn_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_changes)
        
        self.layout.addWidget(btn_box)
        
    def _build_axes_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        
        self.title_edit = QLineEdit(self.ax.get_title())
        form.addRow("Title:", self.title_edit)
        
        form.addRow(QLabel("<b>X-Axis</b>"), QWidget())
        self.xmin_edit = QLineEdit(str(self.ax.get_xlim()[0]))
        self.xmax_edit = QLineEdit(str(self.ax.get_xlim()[1]))
        self.xlabel_edit = QLineEdit(self.ax.get_xlabel())
        self.xscale_combo = QComboBox()
        self.xscale_combo.addItems(["linear", "log"])
        self.xscale_combo.setCurrentText(self.ax.get_xscale())
        
        form.addRow("Min:", self.xmin_edit)
        form.addRow("Max:", self.xmax_edit)
        form.addRow("Label:", self.xlabel_edit)
        form.addRow("Scale:", self.xscale_combo)
        
        form.addRow(QLabel("<b>Y-Axis</b>"), QWidget())
        self.ymin_edit = QLineEdit(str(self.ax.get_ylim()[0]))
        self.ymax_edit = QLineEdit(str(self.ax.get_ylim()[1]))
        self.ylabel_edit = QLineEdit(self.ax.get_ylabel())
        self.yscale_combo = QComboBox()
        self.yscale_combo.addItems(["linear", "log"])
        self.yscale_combo.setCurrentText(self.ax.get_yscale())
        
        form.addRow("Min:", self.ymin_edit)
        form.addRow("Max:", self.ymax_edit)
        form.addRow("Label:", self.ylabel_edit)
        form.addRow("Scale:", self.yscale_combo)
        
        self.tabs.addTab(tab, "Axes")

    def _build_curves_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        
        self.curve_combo = QComboBox()
        for line in self.lines:
            self.curve_combo.addItem(line.get_label())
        self.curve_combo.currentIndexChanged.connect(self._load_curve_data)
        form.addRow("Curve:", self.curve_combo)
        
        self.curve_label_edit = QLineEdit()
        form.addRow("Label:", self.curve_label_edit)
        
        form.addRow(QLabel("<b>Line</b>"), QWidget())
        self.line_style_combo = QComboBox()
        self.line_style_combo.addItems(list(self.ls_map.keys()))
        self.line_width_spin = QDoubleSpinBox()
        self.line_width_spin.setRange(0, 20)
        self.line_width_spin.setSingleStep(0.5)
        self.line_color_btn = ColorButton()
        
        form.addRow("Line style:", self.line_style_combo)
        form.addRow("Width:", self.line_width_spin)
        form.addRow("Color:", self.line_color_btn)
        
        form.addRow(QLabel("<b>Marker</b>"), QWidget())
        self.marker_style_combo = QComboBox()
        self.marker_style_combo.addItems(list(self.marker_map.keys()))
        self.marker_size_spin = QDoubleSpinBox()
        self.marker_size_spin.setRange(0, 50)
        self.marker_face_btn = ColorButton()
        self.marker_edge_btn = ColorButton()
        
        form.addRow("Style:", self.marker_style_combo)
        form.addRow("Size:", self.marker_size_spin)
        form.addRow("Face color:", self.marker_face_btn)
        form.addRow("Edge color:", self.marker_edge_btn)
        
        self.tabs.addTab(tab, "Curves")
        if self.lines: self._load_curve_data(0)

    def _load_curve_data(self, idx):
        if idx < 0 or idx >= len(self.lines): return
        handle = self.lines[idx]
        
        # --- FIX: Extract the main line if it is trapped inside an ErrorbarContainer ---
        is_container = hasattr(handle, 'lines')
        main_line = handle.lines[0] if is_container else handle
        # -------------------------------------------------------------------------------
        
        self.curve_label_edit.setText(handle.get_label())
        self.line_style_combo.setCurrentText(self.ls_map_inv.get(main_line.get_linestyle(), 'Solid'))
        self.line_width_spin.setValue(main_line.get_linewidth())
        self.line_color_btn._color = mpl_color_to_qcolor(main_line.get_color())
        self.line_color_btn.update_style()
        
        self.marker_style_combo.setCurrentText(self.marker_map_inv.get(main_line.get_marker(), 'None'))
        self.marker_size_spin.setValue(main_line.get_markersize())
        self.marker_face_btn._color = mpl_color_to_qcolor(main_line.get_markerfacecolor())
        self.marker_face_btn.update_style()
        self.marker_edge_btn._color = mpl_color_to_qcolor(main_line.get_markeredgecolor())
        self.marker_edge_btn.update_style()

    def _save_current_curve(self):
        idx = self.curve_combo.currentIndex()
        if idx < 0 or idx >= len(self.lines): return
        handle = self.lines[idx]
        
        # --- FIX: Target the main line inside the container ---
        is_container = hasattr(handle, 'lines')
        main_line = handle.lines[0] if is_container else handle
        # ------------------------------------------------------
        
        # Update curve label in combo box cleanly
        new_label = self.curve_label_edit.text()
        handle.set_label(new_label)
        self.curve_combo.setItemText(idx, new_label)
        
        main_line.set_linestyle(self.ls_map[self.line_style_combo.currentText()])
        main_line.set_linewidth(self.line_width_spin.value())
        main_line.set_color(qcolor_to_mpl_rgba(self.line_color_btn.get_color()))
        
        main_line.set_marker(self.marker_map[self.marker_style_combo.currentText()])
        main_line.set_markersize(self.marker_size_spin.value())
        main_line.set_markerfacecolor(qcolor_to_mpl_rgba(self.marker_face_btn.get_color()))
        main_line.set_markeredgecolor(qcolor_to_mpl_rgba(self.marker_edge_btn.get_color()))

    def apply_changes(self):
        try: self.ax.set_xlim([float(self.xmin_edit.text()), float(self.xmax_edit.text())])
        except Exception: pass
        try: self.ax.set_ylim([float(self.ymin_edit.text()), float(self.ymax_edit.text())])
        except Exception: pass
        
        self.ax.set_title(self.title_edit.text())
        self.ax.set_xlabel(self.xlabel_edit.text())
        self.ax.set_ylabel(self.ylabel_edit.text())
        self.ax.set_xscale(self.xscale_combo.currentText())
        self.ax.set_yscale(self.yscale_combo.currentText())
        
        self._save_current_curve()

    def accept(self):
        self.apply_changes()
        super().accept()


# ==========================================
# THE MAIN WINDOW
# ==========================================
class MatplotlibPopout(QMainWindow):
    def __init__(self, main_window, title="Detached Plot (Matplotlib)"):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle(title)
        self.resize(800, 600)
        
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)
        
        # Inherit theme state
        self.is_dark_mode = QColor(theme.bg).lightness() < 128
        self._apply_stylesheets()
        
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        
        # --- MENU HIJACKING ---
        # 1. Disable the native matplotlib option menu
        for action in self.toolbar.actions():
            if 'Customize' in action.text() or 'Edit axes' in action.toolTip():
                try: action.triggered.disconnect()
                except: pass
                action.triggered.connect(self._open_custom_settings)
        
        # 2. Add the Lightbulb Toggle
        self.toolbar.addSeparator()
        self.theme_action = QAction("💡 Toggle Theme", self)
        self.theme_action.setToolTip("Switch Matplotlib background between Light and Dark mode")
        self.theme_action.triggered.connect(self._toggle_theme)
        self.toolbar.addAction(self.theme_action)
        # ----------------------
        
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas)
        
        self._refresh_plot()

    def _open_custom_settings(self):
        """Intercepts the native menu click and spawns our beautiful replacement."""
        dlg = CustomFigureOptionsDialog(self.ax, self)
        if dlg.exec() == QDialog.DialogCode.Accepted or dlg.result() == QDialog.DialogCode.Accepted:
            # When changes are applied, force the legend to rebuild securely!
            self._rebuild_legend_securely()
            self.canvas.draw_idle()

    def _apply_stylesheets(self):
        input_bg = "#1e1e1e" if self.is_dark_mode else "#ffffff"
        input_border = "#777777" if self.is_dark_mode else "#aaaaaa"
        btn_bg = "#333333" if self.is_dark_mode else "#e0e0e0"
        btn_hover = "#4a4a4a" if self.is_dark_mode else "#d0d0d0"
        
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {theme.panel_bg}; }}
            
            QDialog {{ background-color: {theme.panel_bg}; color: {theme.fg}; }}
            QDialog QLabel, QDialog QCheckBox {{ color: {theme.fg}; background: transparent; }}
            
            QDialog QLineEdit, QDialog QComboBox, QDialog QAbstractSpinBox {{ 
                background-color: {input_bg}; color: {theme.fg}; 
                border: 1px solid {input_border}; border-radius: 4px; 
                padding: 4px 6px; min-height: 20px;
            }}
            QDialog QLineEdit:focus, QDialog QComboBox:focus, QDialog QAbstractSpinBox:focus {{
                border: 1px solid #3388ff;
            }}
            QDialog QComboBox::drop-down {{
                subcontrol-origin: padding; subcontrol-position: top right;
                width: 20px; border-left: 1px solid {input_border};
            }}
            
            QDialog QPushButton {{ 
                background-color: {btn_bg}; color: {theme.fg}; 
                border: 1px solid {input_border}; padding: 5px 15px; border-radius: 4px; 
            }}
            QDialog QPushButton:hover {{ 
                background-color: {btn_hover}; border: 1px solid {theme.primary_border};
            }}
            
            QDialog QTabWidget::pane {{ 
                border: 1px solid {input_border}; background-color: {theme.panel_bg}; top: -1px;
            }}
            QDialog QTabBar::tab {{ 
                background-color: {theme.bg}; color: {theme.fg}; 
                padding: 6px 14px; border: 1px solid {input_border}; 
                border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px;
            }}
            QDialog QTabBar::tab:selected {{ 
                background-color: {theme.panel_bg}; color: {theme.fg}; 
                border-bottom: 1px solid {theme.panel_bg}; font-weight: bold; 
            }}
            
            QGroupBox {{ font-weight: bold; padding-top: 15px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }}
        """)

    def _toggle_theme(self):
        """Inverts the Matplotlib canvas theme and instantly redraws."""
        self.is_dark_mode = not self.is_dark_mode
        self._apply_stylesheets()
        
        bg_color = theme.panel_bg if self.is_dark_mode else "#ffffff"
        fg_color = theme.fg if self.is_dark_mode else "#000000"
        grid_color = "#444444" if self.is_dark_mode else "#cccccc"
        toolbar_bg = theme.panel_bg if self.is_dark_mode else theme.border
        
        self.toolbar.setStyleSheet(f"QToolBar {{ background-color: {toolbar_bg}; border: none; }}")
        self.fig.patch.set_facecolor(bg_color)
        self.ax.set_facecolor(bg_color)
        
        for spine in self.ax.spines.values():
            spine.set_color(fg_color)
        self.ax.tick_params(colors=fg_color, which='both')
        self.ax.xaxis.label.set_color(fg_color)
        self.ax.yaxis.label.set_color(fg_color)
        self.ax.title.set_color(fg_color)
        
        # Force grid color update
        if self.ax.get_xgridlines() and self.ax.get_ygridlines():
            show_x = self.main_window.grid_x_cb.isChecked()
            show_y = self.main_window.grid_y_cb.isChecked()
            try: alpha = float(self.main_window.grid_alpha_edit.text())
            except ValueError: alpha = 0.35
            
            if show_x and show_y: self.ax.grid(True, axis='both', color=grid_color, linestyle='--', alpha=alpha)
            elif show_x: self.ax.grid(True, axis='x', color=grid_color, linestyle='--', alpha=alpha)
            elif show_y: self.ax.grid(True, axis='y', color=grid_color, linestyle='--', alpha=alpha)
        
        self._rebuild_legend_securely()
        self.canvas.draw_idle()

    def _rebuild_legend_securely(self):
        """Builds the legend while strictly enforcing dark mode and custom marker sizes."""
        if not self.ax.get_lines() and not self.ax.containers: return
        
        bg_color = theme.panel_bg if self.is_dark_mode else "#ffffff"
        fg_color = theme.fg if self.is_dark_mode else "#000000"
        grid_color = "#444444" if self.is_dark_mode else "#cccccc"
        
        # Pull exact handles safely from Matplotlib's native generator
        handles, labels = self.ax.get_legend_handles_labels()
        if not handles: return
        
        legend = self.ax.legend(handles, labels, facecolor=bg_color, edgecolor=grid_color)
        for text in legend.get_texts():
            text.set_color(fg_color)
            
        import matplotlib
        leg_handles = getattr(legend, 'legend_handles', getattr(legend, 'legendHandles', []))
        
        # Safely enforce marker sizes by checking object types
        for orig_handle, leg_handle in zip(handles, leg_handles):
            try:
                if isinstance(orig_handle, matplotlib.container.ErrorbarContainer):
                    main_line = orig_handle.lines[0] # Extract the main plot line from the container
                    if hasattr(leg_handle, 'lines'):
                        leg_line = leg_handle.lines[0]
                        leg_line.set_markersize(main_line.get_markersize())
                        leg_line.set_linewidth(main_line.get_linewidth())
                elif isinstance(orig_handle, matplotlib.lines.Line2D):
                    if hasattr(leg_handle, 'set_markersize'):
                        leg_handle.set_markersize(orig_handle.get_markersize())
                    if hasattr(leg_handle, 'set_linewidth'):
                        leg_handle.set_linewidth(orig_handle.get_linewidth())
            except Exception:
                pass

    def _refresh_plot(self):
        """Clears the axes and completely rebuilds the Matplotlib figure from the Qt canvas."""
        self.ax.clear()
        
        bg_color = theme.panel_bg if self.is_dark_mode else "#ffffff"
        fg_color = theme.fg if self.is_dark_mode else "#000000"
        grid_color = "#444444" if self.is_dark_mode else "#cccccc"
        toolbar_bg = theme.panel_bg if self.is_dark_mode else theme.border
        
        self.toolbar.setStyleSheet(f"QToolBar {{ background-color: {toolbar_bg}; border: none; }}")
        
        # Theme the toolbar icons dynamically
        if self.is_dark_mode:
            for action in self.toolbar.actions():
                icon = action.icon()
                if not icon.isNull() and action != self.theme_action:
                    pixmap = icon.pixmap(24, 24)
                    painter = QPainter(pixmap)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor(theme.fg))
                    painter.end()
                    action.setIcon(QIcon(pixmap))
        
        self.fig.patch.set_facecolor(bg_color)
        self.ax.set_facecolor(bg_color)
        
        for spine in self.ax.spines.values():
            spine.set_color(fg_color)
        self.ax.tick_params(colors=fg_color, which='both')
        self.ax.xaxis.label.set_color(fg_color)
        self.ax.yaxis.label.set_color(fg_color)
        self.ax.title.set_color(fg_color)
        
        self._translate_plot(grid_color, bg_color, fg_color)
        self.canvas.draw()

    def _translate_plot(self, grid_color, bg_color, fg_color):
        original_plot = self.main_window.plot_widget
        item_to_name = extract_legends(self.main_window)
        
        bottom_axis = original_plot.getAxis('bottom')
        left_axis = original_plot.getAxis('left')
        if bottom_axis.isVisible(): self.ax.set_xlabel(bottom_axis.labelText)
        if left_axis.isVisible(): self.ax.set_ylabel(left_axis.labelText)
        
        xlog = self.main_window.xscale.currentText() == "Log"
        ylog = self.main_window.yscale.currentText() == "Log"
        xbase = self.main_window._parse_log_base(self.main_window.xbase.text())
        ybase = self.main_window._parse_log_base(self.main_window.ybase.text())
        
        # --- NEW: BUILD AN ERROR BAR HASH MAP (Collision Proof) ---
        eb_map = {}
        for eb in self.main_window.avg_error_pool:
            if not eb.isVisible(): continue
            x_data = eb.opts.get('x')
            if x_data is not None and len(x_data) > 0:
                sig = (len(x_data), float(x_data[0])) # Include length to prevent collisions
                eb_map[sig] = eb.opts
        # ----------------------------------------------------------

        mpl_symbols = {'o':'o', 's':'s', 't':'^', 't1':'^', 't2':'v', 't3':'>', 'd':'d', '+':'+', 'x':'x', 'p':'p', 'h':'h', 'star':'*'}

        # --- FIX 2: Explicitly draw Confidence Bands (FillBetweenItems) ---
        for fit in getattr(self.main_window, 'active_fits', []):
            band = fit.get("band_item")
            if band is not None and band.isVisible():
                x_vis = fit["plot_item"].xData
                y_vis = fit["plot_item"].yData
                y_up = y_vis + fit["band_std"]
                y_dn = y_vis - fit["band_std"]
                
                x_raw, y_up_raw = self.main_window._get_raw_fit_coords(x_vis, y_up)
                _, y_dn_raw = self.main_window._get_raw_fit_coords(x_vis, y_dn)
                
                brush = band.brush() if hasattr(band, 'brush') else pg.mkBrush(255, 0, 0, 60)
                rgba = qcolor_to_mpl_rgba(brush.color())
                self.ax.fill_between(x_raw, y_dn_raw, y_up_raw, facecolor=rgba, edgecolor='none', zorder=band.zValue())
        # ------------------------------------------------------------------

        for item in original_plot.listDataItems():
            if not item.isVisible(): continue # --- FIX 1: Ignore Phantom Curves ---
            if not hasattr(item, 'getData'): continue
            try:
                data = item.getData()
                if data is None or data[0] is None or data[1] is None: continue
                x, y = np.array(data[0]), np.array(data[1])
            except Exception:
                continue
            
            if len(x) == 0: continue
                
            with np.errstate(over='ignore', invalid='ignore'):
                if xlog: x = np.power(xbase, x)
                if ylog: y = np.power(ybase, y)
                
            p_line, sym, sym_size, b_sym, p_sym = extract_live_styles(item)
            
            # --- FIX: Extract PyQtGraph's Z-order hierarchy ---
            z_order = item.zValue()
            # --------------------------------------------------
            
            if p_line.style() == Qt.PenStyle.NoPen:
                line_color, width, linestyle = 'none', 0.0, 'None'
            else:
                line_color = qcolor_to_mpl_rgba(p_line.color())
                width = max(1.0, p_line.widthF())
                linestyle = get_mpl_linestyle(p_line)
                
            marker = mpl_symbols.get(sym, 'o') if sym else 'None'
            face_color = 'none' if b_sym.style() == Qt.BrushStyle.NoBrush else qcolor_to_mpl_rgba(b_sym.color())
            edge_color = 'none' if p_sym.style() == Qt.PenStyle.NoPen else qcolor_to_mpl_rgba(p_sym.color())

            name = item_to_name.get(item, getattr(item, 'opts', {}).get('name', None))
            
            # --- FIX: UNIFIED RENDERING ENGINE ---
            x_sig = (len(data[0]), float(data[0][0]))
            eb_opts = eb_map.get(x_sig)
            
            if eb_opts:
                # We have matching error bars! Let Matplotlib draw the line, symbol, AND errors at once.
                xerr = eb_opts.get('width') / 2.0 if eb_opts.get('width') is not None else None
                yerr = eb_opts.get('height') / 2.0 if eb_opts.get('height') is not None else None
                
                if xerr is not None and not np.any(xerr > 0): xerr = None
                if yerr is not None and not np.any(yerr > 0): yerr = None
                
                raw_color = eb_opts.get('mpl_ecolor')
                ecolor = qcolor_to_mpl_rgba(pg.mkColor(raw_color)) if raw_color else line_color
                elinewidth = eb_opts.get('mpl_elinewidth', width)
                capsize = eb_opts.get('mpl_capsize', 3.0)
                
                # --- FIX: Inject zorder ---
                self.ax.errorbar(x, y, xerr=xerr, yerr=yerr, color=line_color, linewidth=width, 
                                 linestyle=linestyle, marker=marker, markersize=sym_size, 
                                 markerfacecolor=face_color, markeredgecolor=edge_color,
                                 ecolor=ecolor, elinewidth=elinewidth, capsize=capsize, 
                                 label=name, zorder=z_order) 
            else:
                # Standard trace without error bars
                # --- FIX: Inject zorder ---
                self.ax.plot(x, y, color=line_color, linewidth=width, linestyle=linestyle, 
                             marker=marker, markersize=sym_size, 
                             markerfacecolor=face_color, markeredgecolor=edge_color, 
                             label=name, zorder=z_order) 
            # -------------------------------------
            
        if xlog: self.ax.set_xscale('log', base=xbase)
        if ylog: self.ax.set_yscale('log', base=ybase)
                
        # --- Synchronised Dynamic Gridlines ---
        show_x = self.main_window.grid_x_cb.isChecked()
        show_y = self.main_window.grid_y_cb.isChecked()
        try: alpha = float(self.main_window.grid_alpha_edit.text())
        except ValueError: alpha = 0.35
        
        if show_x and show_y: self.ax.grid(True, axis='both', color=grid_color, linestyle='--', alpha=alpha)
        elif show_x: self.ax.grid(True, axis='x', color=grid_color, linestyle='--', alpha=alpha)
        elif show_y: self.ax.grid(True, axis='y', color=grid_color, linestyle='--', alpha=alpha)
        else: self.ax.grid(False)
            
        self._rebuild_legend_securely()
        self.fig.tight_layout()