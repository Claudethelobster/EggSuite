import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt

class RandomWalkApp(QMainWindow):
    def __init__(self, workspace, current_theme):
        super().__init__()
        self.workspace = workspace
        self.theme = current_theme
        
        self.setWindowTitle("Random Walk Simulator (External Plugin)")
        self.resize(800, 600)
        
        # Apply the EggSuite theme!
        self.setStyleSheet(f"background-color: {self.theme.bg}; color: {self.theme.fg};")
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Build the Plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(self.theme.panel_bg)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Add a custom curve
        self.curve = pg.PlotCurveItem(pen=pg.mkPen(self.theme.primary_bg, width=2))
        self.plot_widget.addItem(self.curve)
        
        layout.addWidget(self.plot_widget)
        
        # Controls
        btn_lay = QHBoxLayout()
        self.btn_generate = QPushButton("🎲 Generate New Walk")
        self.btn_generate.setStyleSheet(f"""
            QPushButton {{
                font-weight: bold; padding: 10px; 
                background-color: {self.theme.primary_bg}; color: {self.theme.primary_text}; 
                border: 1px solid {self.theme.primary_border}; border-radius: 4px;
            }}
            QPushButton:hover {{ border: 1px solid white; }}
        """)
        self.btn_generate.clicked.connect(self.generate_walk)
        
        btn_lay.addStretch()
        btn_lay.addWidget(self.btn_generate)
        btn_lay.addStretch()
        
        layout.addLayout(btn_lay)
        
        # Generate initial data
        self.generate_walk()

    def generate_walk(self):
        """Generates a 10,000 point 2D random walk."""
        steps = 10000
        # Generate random steps of -1 or 1
        x_steps = np.random.choice([-1, 1], size=steps)
        y_steps = np.random.choice([-1, 1], size=steps)
        
        # Calculate cumulative sum to get the walk path
        x_pos = np.cumsum(x_steps)
        y_pos = np.cumsum(y_steps)
        
        self.curve.setData(x_pos, y_pos)

# --- THE MANDATORY ENTRY POINT ---
def run_app(workspace, current_theme):
    """
    This function is called by the EggSuite Hub when the user clicks 'Launch'.
    It must accept the workspace and theme, and return a QMainWindow or QDialog.
    """
    # We instantiate the window and return it to the Hub so it isn't garbage collected
    window = RandomWalkApp(workspace, current_theme)
    return window