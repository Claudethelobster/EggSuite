import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt

class RandomWalkApp(QMainWindow):
    def __init__(self, api):
        super().__init__()
        self.api = api
        
        # Fetch the theme colours securely through the API
        self.colours = self.api.get_theme_colours()
        
        self.setWindowTitle("Random Walk Simulator (API Version)")
        self.resize(800, 600)
        
        # Apply the EggSuite theme using the API dictionary
        self.setStyleSheet(f"background-color: {self.colours['bg']}; color: {self.colours['fg']};")
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Build the Plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(self.colours['panel_bg'])
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Add a custom curve
        self.curve = pg.PlotCurveItem(pen=pg.mkPen(self.colours['primary_bg'], width=2))
        self.plot_widget.addItem(self.curve)
        
        layout.addWidget(self.plot_widget)
        
        # Controls
        btn_lay = QHBoxLayout()
        self.btn_generate = QPushButton("🎲 Generate New Walk")
        self.btn_generate.setStyleSheet(f"""
            QPushButton {{
                font-weight: bold; padding: 10px; 
                background-color: {self.colours['primary_bg']}; color: {self.colours['primary_text']}; 
                border: 1px solid {self.colours['primary_border']}; border-radius: 4px;
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
        x_steps = np.random.choice([-1, 1], size=steps)
        y_steps = np.random.choice([-1, 1], size=steps)
        
        x_pos = np.cumsum(x_steps)
        y_pos = np.cumsum(y_steps)
        
        self.curve.setData(x_pos, y_pos)

# --- THE MANDATORY ENTRY POINT ---
def run_app(api):
    """
    This function is called by the EggSuite PluginManager.
    It accepts the secure API and returns the window.
    """
    window = RandomWalkApp(api)
    return window