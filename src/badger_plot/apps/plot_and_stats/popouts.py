import pyqtgraph as pg
import numpy as np
import re
import html
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QDialog
from PyQt6.QtGui import QColor, QPainter, QIcon
from PyQt6.QtCore import Qt
from ui.theme import theme

# --- Matplotlib Imports ---
import matplotlib
try:
    matplotlib.use('QtAgg', force=True)
except Exception:
    pass 
    
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

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


class MatplotlibPopout(QMainWindow):
    def __init__(self, main_window, title="Detached Plot (Matplotlib)"):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(800, 600)
        
        self.central = QWidget()
        self.setCentralWidget(self.central)
        layout = QVBoxLayout(self.central)
        
        is_dark = QColor(theme.bg).lightness() < 128
        bg_color = theme.panel_bg
        fg_color = theme.fg
        grid_color = "#444444" if is_dark else "#cccccc"
        
        input_bg = "#1e1e1e" if is_dark else "#ffffff"
        input_border = "#777777" if is_dark else "#aaaaaa"
        btn_bg = "#333333" if is_dark else "#e0e0e0"
        btn_hover = "#4a4a4a" if is_dark else "#d0d0d0"
        
        # Target QDialog dynamically so it styles the spawned figure options menus
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
        """)
        
        self.fig = Figure(facecolor=bg_color)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(bg_color)
        
        for spine in self.ax.spines.values():
            spine.set_color(fg_color)
        self.ax.tick_params(colors=fg_color, which='both')
        self.ax.xaxis.label.set_color(fg_color)
        self.ax.yaxis.label.set_color(fg_color)
        self.ax.title.set_color(fg_color)
        
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        
        # CRITICAL FIX: Only apply 'border: none' to the QToolBar itself!
        toolbar_bg = theme.panel_bg if is_dark else theme.border
        self.toolbar.setStyleSheet(f"QToolBar {{ background-color: {toolbar_bg}; border: none; }}")
        
        if is_dark:
            for action in self.toolbar.actions():
                icon = action.icon()
                if not icon.isNull():
                    pixmap = icon.pixmap(24, 24)
                    painter = QPainter(pixmap)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor(theme.fg))
                    painter.end()
                    action.setIcon(QIcon(pixmap))
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        self._translate_plot(main_window, grid_color, bg_color, fg_color)

    def _translate_plot(self, main_window, grid_color, bg_color, fg_color):
        original_plot = main_window.plot_widget
        item_to_name = extract_legends(main_window)
        
        bottom_axis = original_plot.getAxis('bottom')
        left_axis = original_plot.getAxis('left')
        if bottom_axis.isVisible(): self.ax.set_xlabel(bottom_axis.labelText)
        if left_axis.isVisible(): self.ax.set_ylabel(left_axis.labelText)
        
        xlog = main_window.xscale.currentText() == "Log"
        ylog = main_window.yscale.currentText() == "Log"
        xbase = main_window._parse_log_base(main_window.xbase.text())
        ybase = main_window._parse_log_base(main_window.ybase.text())
        
        has_labels = False
        mpl_symbols = {'o':'o', 's':'s', 't':'^', 't1':'^', 't2':'v', 't3':'>', 'd':'d', '+':'+', 'x':'x', 'p':'p', 'h':'h', 'star':'*'}

        for item in original_plot.listDataItems():
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
            
            if p_line.style() == Qt.PenStyle.NoPen:
                line_color = 'none'
                width = 0.0
                linestyle = 'None'
            else:
                line_color = qcolor_to_mpl_rgba(p_line.color())
                width = max(1.0, p_line.widthF())
                linestyle = get_mpl_linestyle(p_line)
                
            marker = mpl_symbols.get(sym, 'o') if sym else 'None'
            face_color = 'none' if b_sym.style() == Qt.BrushStyle.NoBrush else qcolor_to_mpl_rgba(b_sym.color())
            edge_color = 'none' if p_sym.style() == Qt.PenStyle.NoPen else qcolor_to_mpl_rgba(p_sym.color())

            name = item_to_name.get(item, getattr(item, 'opts', {}).get('name', None))
            if name: has_labels = True
                    
            self.ax.plot(x, y, color=line_color, linewidth=width, linestyle=linestyle, 
                         marker=marker, markersize=sym_size, 
                         markerfacecolor=face_color, markeredgecolor=edge_color, label=name)
            
        if xlog: self.ax.set_xscale('log', base=xbase)
        if ylog: self.ax.set_yscale('log', base=ybase)
                
        self.ax.grid(True, color=grid_color, linestyle='--', alpha=0.5)
        
        if has_labels:
            legend = self.ax.legend(facecolor=bg_color, edgecolor=grid_color)
            for text in legend.get_texts():
                text.set_color(fg_color)
                
        self.fig.tight_layout()