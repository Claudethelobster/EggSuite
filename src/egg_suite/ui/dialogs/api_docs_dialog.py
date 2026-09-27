"""
api_docs_dialog.py - In-app Interactive Plugin API Documentation and Reference Window.
Provides plugin creators and developers with complete API documentation, method signatures,
parameter tables, and interactive code examples.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QSplitter, QWidget, QLabel
)
from egg_suite.ui.theme import theme


DOC_SECTIONS = {
    "quickstart": {
        "title": "🚀 Quickstart & Plugin Lifecycle",
        "category": "Getting Started",
        "html": f"""
        <h2>Plugin Architecture & Lifecycle</h2>
        <div class='callout'>
            EggSuite plugins are lightweight, modular Python packages discovered automatically from 
            <code>~/.egg_suite/plugins/</code> and <code>examples/plugins/</code>.
        </div>

        <h3>1. Directory Structure</h3>
        <pre><code>my_custom_plugin/
├── manifest.json   # Plugin metadata, permissions, and dependencies
└── main.py         # Entry point defining run_app(api)</code></pre>

        <h3>2. The Manifest File (<code>manifest.json</code>)</h3>
        <p>Every plugin requires a <code>manifest.json</code> in its root folder:</p>
        <pre><code>{{
    "name": "My Analysis Tool",
    "description": "Calculates custom metrics and fits mathematical models.",
    "icon": "🔬",
    "author": "Your Name",
    "version": "1.0.0",
    "entry_point": "main.py",
    "pinned": false,
    "dependencies": ["numpy", "scipy", "pandas", "pyqtgraph"]
}}</code></pre>

        <h3>3. The Entry Point (<code>main.py</code>)</h3>
        <p>Your entry file must define a top-level function named <code>run_app(api)</code> that receives the <b>EggSuiteAPI</b> instance and returns a <code>QMainWindow</code> or <code>QWidget</code>:</p>
        <pre><code>import sys
from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget

class MyPluginWindow(QMainWindow):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setWindowTitle("My Analysis Tool")
        self.resize(800, 600)
        
        # Apply the suite theme
        self.api.ui.apply_theme(self)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("Plugin connected to EggSuite!"))

def run_app(api):
    return MyPluginWindow(api)</code></pre>
        """
    },
    "data_management": {
        "title": "📊 Data Management & DataFrames",
        "category": "Core API",
        "html": f"""
        <h2>Data Management API</h2>
        <p>Interact with datasets loaded in the Hub, retrieve them as <b>Pandas DataFrames</b> or <b>NumPy arrays</b>, and push new or transformed data back into the suite.</p>

        <h3>Methods Reference</h3>
        <table class='api-table'>
            <tr>
                <th>Method</th>
                <th>Arguments</th>
                <th>Returns</th>
                <th>Description</th>
            </tr>
            <tr>
                <td><code>api.get_dataset_names()</code></td>
                <td>None</td>
                <td><code>list[str]</code></td>
                <td>Returns a list of all dataset identifiers/paths loaded in the workspace.</td>
            </tr>
            <tr>
                <td><code>api.get_dataframe(name)</code></td>
                <td><code>name: str</code></td>
                <td><code>pandas.DataFrame | None</code></td>
                <td><b>Recommended.</b> Returns the dataset as a standardized DataFrame with named column headers.</td>
            </tr>
            <tr>
                <td><code>api.get_column_names(name)</code></td>
                <td><code>name: str</code></td>
                <td><code>list[str]</code></td>
                <td>Returns all column header strings for the given dataset.</td>
            </tr>
            <tr>
                <td><code>api.get_column_data(name, column)</code></td>
                <td><code>name: str, col: str | int</code></td>
                <td><code>np.ndarray | None</code></td>
                <td>Extracts a 1D NumPy array for a specific column (by name or index).</td>
            </tr>
            <tr>
                <td><code>api.add_dataframe(name, df, notes="")</code></td>
                <td><code>name: str, df: DataFrame, notes: str</code></td>
                <td><code>None</code></td>
                <td>Wraps and registers a DataFrame into the Hub workspace so other apps can use it.</td>
            </tr>
            <tr>
                <td><code>api.get_dataset(name)</code></td>
                <td><code>name: str</code></td>
                <td><code>object | None</code></td>
                <td>Returns the raw internal dataset object (CSVSweep, HDF5, or BadgerLoop).</td>
            </tr>
            <tr>
                <td><code>api.remove_dataset(name)</code></td>
                <td><code>name: str</code></td>
                <td><code>None</code></td>
                <td>Removes a dataset from the workspace.</td>
            </tr>
        </table>

        <h3>Code Example: Reading and Modifying Data</h3>
        <pre><code># 1. Get available datasets
datasets = self.api.get_dataset_names()
if datasets:
    target = datasets[0]
    
    # 2. Extract as Pandas DataFrame
    df = self.api.get_dataframe(target)
    print("Columns:", df.columns)
    
    # 3. Perform a transformation
    df["Normalized_Y"] = df.iloc[:, 1] / df.iloc[:, 1].max()
    
    # 4. Push back to workspace
    self.api.add_dataframe("Normalized_" + target, df)
    self.api.ui.show_notification("Success", "Added normalized dataset to Hub.")</code></pre>
        """
    },
    "math_and_fitting": {
        "title": "📈 Fitting, Signal Processing & Math",
        "category": "Core API",
        "html": f"""
        <h2>Mathematical Analysis Engine (<code>api.analysis</code>)</h2>
        <p>EggSuite includes a pure Python/SciPy mathematical engine accessible directly via <code>api.analysis</code>.</p>

        <h3>1. Curve Fitting (<code>api.analysis.fit_curve</code>)</h3>
        <table class='api-table'>
            <tr>
                <th>Argument</th>
                <th>Type</th>
                <th>Default</th>
                <th>Description</th>
            </tr>
            <tr>
                <td><code>x, y</code></td>
                <td><code>array_like</code></td>
                <td><i>Required</i></td>
                <td>1D coordinates to fit.</td>
            </tr>
            <tr>
                <td><code>model</code></td>
                <td><code>str</code></td>
                <td><code>"polynomial"</code></td>
                <td>Model: <code>"polynomial"</code>, <code>"gaussian"</code>, <code>"lorentzian"</code>, <code>"exponential"</code>, <code>"logarithmic"</code>, <code>"sine"</code>, <code>"power_law"</code>, <code>"custom"</code>.</td>
            </tr>
            <tr>
                <td><code>degree</code></td>
                <td><code>int</code></td>
                <td><code>1</code></td>
                <td>Degree when <code>model="polynomial"</code> (e.g. 1 for linear).</td>
            </tr>
            <tr>
                <td><code>sigma</code></td>
                <td><code>array_like</code></td>
                <td><code>None</code></td>
                <td>Optional 1D uncertainty/error weighting for y.</td>
            </tr>
            <tr>
                <td><code>custom_func</code></td>
                <td><code>Callable</code></td>
                <td><code>None</code></td>
                <td>Custom function <code>f(x, *params)</code> when <code>model="custom"</code>.</td>
            </tr>
        </table>

        <h4>FitResult Object</h4>
        <p><code>fit_curve()</code> returns a <b>FitResult</b> object with:</p>
        <ul>
            <li><code>result.parameters</code>: Dictionary of fitted parameter values (e.g. <code>{{"amplitude": 10.2, "center": 5.0, ...}}</code>).</li>
            <li><code>result.parameter_errors</code>: Standard errors for each parameter.</li>
            <li><code>result.r_squared</code>: R² goodness of fit.</li>
            <li><code>result.rmse</code>: Root Mean Square Error.</li>
            <li><code>result.evaluate(x_new)</code>: Evaluates fitted curve at arbitrary x points.</li>
            <li><code>result.summary()</code>: Formatted text summary.</li>
        </ul>

        <h3>2. Signal Processing & Statistics</h3>
        <table class='api-table'>
            <tr>
                <th>Function</th>
                <th>Arguments</th>
                <th>Description</th>
            </tr>
            <tr>
                <td><code>api.analysis.find_peaks()</code></td>
                <td><code>y, x=None, height=None, distance=None, prominence=None</code></td>
                <td>Detects peaks and returns indices, x, y coordinates, and widths.</td>
            </tr>
            <tr>
                <td><code>api.analysis.compute_fft()</code></td>
                <td><code>y, sample_spacing=1.0, window="hann"</code></td>
                <td>Computes Fourier Transform. Returns <code>(frequencies, magnitudes)</code>.</td>
            </tr>
            <tr>
                <td><code>api.analysis.smooth_data()</code></td>
                <td><code>y, method="savgol", window_length=11, polyorder=3</code></td>
                <td>Smooths noisy data via Savitzky-Golay or Moving Average.</td>
            </tr>
            <tr>
                <td><code>api.analysis.integrate_area()</code></td>
                <td><code>x, y, baseline_method="endpoints"</code></td>
                <td>Integrates Area Under Curve with baseline subtraction. Returns net area and baseline area.</td>
            </tr>
            <tr>
                <td><code>api.analysis.compute_statistics()</code></td>
                <td><code>data</code></td>
                <td>Returns mean, std, median, quartiles, min, max, skewness, and kurtosis.</td>
            </tr>
        </table>
        """
    },
    "ui_and_widgets": {
        "title": "🎨 UI Builders & Theming",
        "category": "User Interface",
        "html": f"""
        <h2>UI & Theme Engine (<code>api.ui</code>)</h2>
        <p>Create native-looking PyQt6 interfaces that automatically match the user's active EggSuite theme.</p>

        <h3>Theme Palette (<code>api.ui.get_theme_colours()</code>)</h3>
        <pre><code>colours = self.api.ui.get_theme_colours()
# Returns dictionary:
# colours['bg']             -> Main background color (e.g. #1e1e1e)
# colours['panel_bg']       -> Card & panel background (e.g. #252526)
# colours['fg']             -> Main text color (e.g. #cccccc)
# colours['border']         -> Subtle border color
# colours['primary_bg']     -> Accent/button color
# colours['primary_text']   -> Contrast text on primary buttons
# colours['primary_border'] -> Accent border color</code></pre>

        <h3>UI Helper Methods</h3>
        <table class='api-table'>
            <tr>
                <th>Method</th>
                <th>Description</th>
            </tr>
            <tr>
                <td><code>api.ui.apply_theme(widget)</code></td>
                <td>Automatically styles a widget or window with the default background and text colors.</td>
            </tr>
            <tr>
                <td><code>api.ui.create_button(text, is_primary=False, parent=None)</code></td>
                <td>Creates a pre-styled QPushButton matching suite hover states and borders.</td>
            </tr>
            <tr>
                <td><code>api.ui.create_plot_widget(title="", show_grid=True, parent=None)</code></td>
                <td>Creates a pre-themed <code>pyqtgraph.PlotWidget</code> with grid lines and palette set.</td>
            </tr>
            <tr>
                <td><code>api.ui.show_notification(title, message, is_error=False)</code></td>
                <td>Displays a non-blocking toast notification in the EggSuite Hub.</td>
            </tr>
            <tr>
                <td><code>api.ui.show_error_dialog(title, message, details="")</code></td>
                <td>Spawns the modal dialog with copyable error and traceback text.</td>
            </tr>
        </table>
        """
    },
    "settings_and_files": {
        "title": "💾 Settings & File Dialogs",
        "category": "Utilities",
        "html": f"""
        <h2>Sandboxed Settings & File Helpers</h2>

        <h3>1. Sandboxed Settings (<code>save_setting</code> / <code>load_setting</code>)</h3>
        <p>EggSuite provides a sandboxed key-value store using <code>QSettings</code>. Settings are automatically namespaced under <code>plugins/&lt;AppName&gt;/</code> so they never collide with the core app or other plugins.</p>
        <pre><code># Save user preference
self.api.save_setting("default_smoothing_window", 15)
self.api.save_setting("auto_fit_enabled", True)

# Load setting with fallback default
window_len = self.api.load_setting("default_smoothing_window", default_value=11)
auto_fit = self.api.load_setting("auto_fit_enabled", default_value=False)</code></pre>

        <h3>2. File System Helpers</h3>
        <p>These methods spawn native Qt dialogs and remember the user's last visited directory globally across EggSuite:</p>
        <pre><code># Ask user to pick a file
filepath = self.api.ask_for_file(
    title="Select Calibration CSV",
    filter_string="CSV Files (*.csv);;All Files (*.*)"
)

# Ask user where to save an output
save_path = self.api.ask_for_save_path(
    title="Export Fit Report",
    default_name="fit_results.csv",
    filter_string="CSV Files (*.csv)"
)</code></pre>
        """
    },
    "event_hooks": {
        "title": "📡 Signals & Event Hooks",
        "category": "Advanced",
        "html": f"""
        <h2>Event Hooks (<code>api.events</code>)</h2>
        <p>Plugins can subscribe to global workspace events to automatically update UI dropdowns, recalculate fits, or refresh plots when data changes in the Hub.</p>

        <h3>Supported Signals</h3>
        <table class='api-table'>
            <tr>
                <th>Method</th>
                <th>Callback Signature</th>
                <th>Description</th>
            </tr>
            <tr>
                <td><code>api.events.on_dataset_added(cb)</code></td>
                <td><code>def on_added(filepath: str)</code></td>
                <td>Triggered whenever a new dataset is loaded or added to the workspace.</td>
            </tr>
            <tr>
                <td><code>api.events.on_dataset_removed(cb)</code></td>
                <td><code>def on_removed(filepath: str)</code></td>
                <td>Triggered when a dataset is removed.</td>
            </tr>
            <tr>
                <td><code>api.events.on_data_modified(cb)</code></td>
                <td><code>def on_modified(filepath: str)</code></td>
                <td>Triggered when columns are renamed, dropped, or modified.</td>
            </tr>
        </table>

        <h3>Code Example: Auto-Updating Dropdown</h3>
        <pre><code>class MyPlugin(QMainWindow):
    def __init__(self, api):
        super().__init__()
        self.api = api
        
        self.combo = QComboBox()
        self.refresh_datasets()
        
        # Subscribe to workspace signals
        self.api.events.on_dataset_added(self.on_dataset_list_changed)
        self.api.events.on_dataset_removed(self.on_dataset_list_changed)

    def refresh_datasets(self):
        self.combo.clear()
        self.combo.addItems(self.api.get_dataset_names())

    def on_dataset_list_changed(self, filepath):
        self.refresh_datasets()
        self.api.ui.show_notification("Workspace Updated", f"Dataset list changed: {{filepath}}")</code></pre>
        """
    },
    "full_examples": {
        "title": "💡 Full Working Examples",
        "category": "Examples",
        "html": f"""
        <h2>Complete Plugin Example: Interactive Curve Fitter</h2>
        <p>A fully functional EggSuite plugin demonstrating theme styling, DataFrame loading, Gaussian/Polynomial fitting, and interactive plotting:</p>

        <pre><code>import sys
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QComboBox, QPushButton, QLabel, QTextEdit
)
from PyQt6.QtCore import Qt

class CurveFitterPlugin(QMainWindow):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setWindowTitle("Interactive Curve Fitter (API Demo)")
        self.resize(900, 650)
        self.api.ui.apply_theme(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Left control panel
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("<b>1. Select Dataset:</b>"))
        self.dataset_combo = QComboBox()
        self.dataset_combo.addItems(self.api.get_dataset_names())
        left_panel.addWidget(self.dataset_combo)

        left_panel.addWidget(QLabel("<b>2. Model:</b>"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gaussian", "lorentzian", "exponential", "polynomial"])
        left_panel.addWidget(self.model_combo)

        self.btn_fit = self.api.ui.create_button("⚡ Run Fit", is_primary=True)
        self.btn_fit.clicked.connect(self.run_fit)
        left_panel.addWidget(self.btn_fit)

        self.results_box = QTextEdit()
        self.results_box.setReadOnly(True)
        left_panel.addWidget(QLabel("<b>Fit Summary:</b>"))
        left_panel.addWidget(self.results_box)
        layout.addLayout(left_panel, stretch=1)

        # Right plot area
        self.plot_widget = self.api.ui.create_plot_widget(title="Data & Fitted Curve")
        self.data_scatter = pg.ScatterPlotItem(pen=pg.mkPen(None), brush=pg.mkBrush(200, 200, 200, 180), size=6)
        self.fit_curve_item = pg.PlotCurveItem(pen=pg.mkPen(color=self.api.get_theme_colours()['primary_bg'], width=2.5))
        self.plot_widget.addItem(self.data_scatter)
        self.plot_widget.addItem(self.fit_curve_item)
        layout.addWidget(self.plot_widget, stretch=2)

    def run_fit(self):
        target = self.dataset_combo.currentText()
        df = self.api.get_dataframe(target)
        if df is None or len(df.columns) < 2:
            self.api.ui.show_notification("Fit Error", "Select a valid dataset with at least 2 columns.", is_error=True)
            return

        x = df.iloc[:, 0].to_numpy()
        y = df.iloc[:, 1].to_numpy()

        model = self.model_combo.currentText()
        fit = self.api.analysis.fit_curve(x, y, model=model)

        # Plot raw data & fitted curve
        self.data_scatter.setData(x, y)
        x_dense = np.linspace(np.min(x), np.max(x), 300)
        y_fit = fit.evaluate(x_dense)
        self.fit_curve_item.setData(x_dense, y_fit)

        self.results_box.setPlainText(fit.summary())
        self.api.ui.show_notification("Fit Converged", f"R² = {{fit.r_squared:.4f}}")

def run_app(api):
    return CurveFitterPlugin(api)</code></pre>
        """
    }
}


class ApiDocumentationDialog(QDialog):
    """Interactive documentation and reference window for the EggSuite API."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EggSuite Plugin API Reference & Developer Guide")
        self.resize(1100, 780)

        # Styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.bg};
                color: {theme.fg};
            }}
            QSplitter::handle {{
                background-color: {theme.border};
                width: 2px;
            }}
        """)

        self.css = f"""
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 14px;
                color: {theme.fg};
                line-height: 1.6;
                padding: 10px;
            }}
            h2 {{
                color: {theme.primary_text};
                border-bottom: 2px solid {theme.border};
                padding-bottom: 6px;
                margin-top: 5px;
                margin-bottom: 12px;
                font-size: 22px;
            }}
            h3 {{
                color: {theme.primary_text};
                margin-top: 20px;
                margin-bottom: 8px;
                font-size: 16px;
            }}
            h4 {{
                color: {theme.fg};
                margin-top: 14px;
                margin-bottom: 4px;
                font-size: 14px;
            }}
            p, li {{
                color: {theme.fg};
                margin-bottom: 8px;
            }}
            code {{
                background-color: {theme.panel_bg};
                padding: 2px 6px;
                border-radius: 4px;
                font-family: Consolas, 'Courier New', monospace;
                color: {theme.primary_text};
                font-weight: bold;
                border: 1px solid {theme.border};
                font-size: 13px;
            }}
            pre {{
                background-color: {theme.panel_bg};
                border: 1px solid {theme.border};
                border-radius: 6px;
                padding: 12px;
                margin: 10px 0px;
                overflow-x: auto;
            }}
            pre code {{
                background-color: transparent;
                border: none;
                padding: 0;
                color: {theme.fg};
                font-weight: normal;
            }}
            .callout {{
                background-color: {theme.panel_bg};
                border-left: 4px solid {theme.primary_bg};
                padding: 12px 16px;
                margin: 12px 0px;
                border-radius: 0px 4px 4px 0px;
                color: {theme.fg};
            }}
            .api-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 12px 0px;
            }}
            .api-table th {{
                background-color: {theme.panel_bg};
                color: {theme.primary_text};
                font-weight: bold;
                text-align: left;
                padding: 8px 12px;
                border: 1px solid {theme.border};
            }}
            .api-table td {{
                padding: 8px 12px;
                border: 1px solid {theme.border};
                vertical-align: top;
            }}
            .api-table tr:nth-child(even) {{
                background-color: {theme.panel_bg};
            }}
        </style>
        """

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header Bar
        header_lay = QHBoxLayout()
        header_title = QLabel("📖 EggSuite Developer API Guide")
        header_title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {theme.primary_text};")
        header_lay.addWidget(header_title)
        header_lay.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px; font-weight: bold;
                background-color: {theme.panel_bg}; color: {theme.fg};
                border: 1px solid {theme.border}; border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {theme.bg}; color: {theme.primary_text}; }}
        """)
        close_btn.clicked.connect(self.accept)
        header_lay.addWidget(close_btn)
        layout.addLayout(header_lay)

        # Splitter Layout (Left: Navigation List, Right: Content Browser)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 5, 5, 0)

        # Search Bar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Filter API topics...")
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 10px; font-size: 13px;
                background-color: {theme.panel_bg}; color: {theme.fg};
                border: 1px solid {theme.border}; border-radius: 4px;
            }}
            QLineEdit:focus {{ border: 1px solid {theme.primary_border}; }}
        """)
        self.search_box.textChanged.connect(self._filter_sections)
        left_layout.addWidget(self.search_box)

        # Navigation List
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {theme.panel_bg}; border: 1px solid {theme.border};
                border-radius: 4px; padding: 4px;
            }}
            QListWidget::item {{
                padding: 10px 12px; margin-bottom: 4px; border-radius: 4px;
                color: {theme.fg}; font-size: 13px; font-weight: 500;
            }}
            QListWidget::item:hover {{
                background-color: {theme.bg}; color: {theme.primary_text};
            }}
            QListWidget::item:selected {{
                background-color: {theme.primary_bg}; color: {theme.primary_text}; font-weight: bold;
            }}
        """)
        self._populate_nav_list()
        self.nav_list.currentRowChanged.connect(self._on_section_selected)
        left_layout.addWidget(self.nav_list)
        splitter.addWidget(left_widget)

        # Right Panel (Browser)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {theme.panel_bg};
                border: 1px solid {theme.border};
                border-radius: 4px;
                padding: 15px;
            }}
        """)
        splitter.addWidget(self.browser)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

        # Select first item
        if self.nav_list.count() > 0:
            self.nav_list.setCurrentRow(0)

    def _populate_nav_list(self, filter_text: str = ""):
        self.nav_list.clear()
        query = filter_text.strip().lower()

        for key, section in DOC_SECTIONS.items():
            title = section["title"]
            category = section.get("category", "")
            raw_text = f"{title} {category} {section['html']}".lower()

            if not query or query in raw_text:
                item = QListWidgetItem(title)
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.nav_list.addItem(item)

    def _filter_sections(self, text: str):
        self._populate_nav_list(text)
        if self.nav_list.count() > 0:
            self.nav_list.setCurrentRow(0)

    def _on_section_selected(self, row: int):
        item = self.nav_list.item(row)
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        section = DOC_SECTIONS.get(key)
        if section:
            full_html = self.css + section["html"]
            self.browser.setHtml(full_html)
