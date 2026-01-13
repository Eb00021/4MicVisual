"""
Super Fast 4-Mic Audio Visualizer
Real-time audio level visualization for 4 microphone inputs
"""

import numpy as np
import sounddevice as sd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from PIL import Image
import time
from collections import deque
import sys
import os
import warnings
import json
import tempfile

# Suppress numpy overflow warnings
warnings.filterwarnings('ignore', category=RuntimeWarning)

# Set PyQtGraph to use white background by default, we'll override with WVU colors
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

# GPU Acceleration and Performance Optimizations
# Enable OpenGL for GPU acceleration if available
GPU_ACCELERATION_ENABLED = False
GPU_ACCELERATION_STATUS_MSG = "Not checked"
try:
    # Check if OpenGL is available before enabling
    from pyqtgraph.Qt import QtGui, QtWidgets
    
    # Try to enable OpenGL - PyQtGraph will use it if available
    # Note: useOpenGL enables OpenGL rendering in GraphicsView/PlotWidget
    try:
        # Check if QOpenGLWidget is available (PyQt5 >= 5.4)
        if hasattr(QtWidgets, 'QOpenGLWidget'):
            # Enable OpenGL for GPU acceleration
            pg.setConfigOption('useOpenGL', True)
            # Also enable experimental features for better performance
            pg.setConfigOption('enableExperimental', True)
            GPU_ACCELERATION_ENABLED = True
            GPU_ACCELERATION_STATUS_MSG = "Enabled (QOpenGLWidget available)"
        else:
            # Try to enable anyway - PyQtGraph may still use OpenGL through Qt
            pg.setConfigOption('useOpenGL', True)
            pg.setConfigOption('enableExperimental', True)
            GPU_ACCELERATION_ENABLED = True
            GPU_ACCELERATION_STATUS_MSG = "Enabled (OpenGL via Qt, QOpenGLWidget not available)"
    except Exception as e:
        pg.setConfigOption('useOpenGL', False)
        GPU_ACCELERATION_ENABLED = False
        GPU_ACCELERATION_STATUS_MSG = f"Disabled (error: {str(e)[:50]})"
except Exception as e:
    # If we can't check, try to enable anyway
    try:
        pg.setConfigOption('useOpenGL', True)
        pg.setConfigOption('enableExperimental', True)
        GPU_ACCELERATION_ENABLED = True
        GPU_ACCELERATION_STATUS_MSG = f"Enabled (fallback, error: {str(e)[:50]})"
    except Exception as e2:
        pg.setConfigOption('useOpenGL', False)
        GPU_ACCELERATION_ENABLED = False
        GPU_ACCELERATION_STATUS_MSG = f"Disabled (error: {str(e2)[:50]})"

# Optimize rendering performance
# Note: enableExperimental is set above with OpenGL
pg.setConfigOption('antialias', True)  # Use antialiasing for smoother curves (GPU accelerated if available)
pg.setConfigOption('useNumba', False)  # Disable numba (not needed, can cause issues)
pg.setConfigOption('leftButtonPan', False)  # Optimize mouse interaction
pg.setConfigOption('crashWarning', False)  # Disable crash warnings for cleaner output
# Additional performance optimizations
pg.setConfigOption('clipToView', True)  # Only render visible portions
pg.setConfigOption('coordinateMode', 'ViewBox')  # Optimize coordinate transformations

# ANSI color codes for Windows (works with Windows 10+)
class Colors:
    """ANSI color codes for terminal output"""
    # WVU Colors
    GOLD = '\033[93m'  # Bright yellow (closest to gold)
    BLUE = '\033[94m'  # Bright blue
    BOLD = '\033[1m'
    RESET = '\033[0m'
    # Additional colors
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

# Enable ANSI colors on Windows
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        pass

def print_wvu_logo():
    """Print WVU header"""
    print()
    print_colored("EcoCAR EV CHALLENGE", Colors.GOLD, bold=True)
    print_colored("WEST VIRGINIA UNIVERSITY", Colors.WHITE, bold=True)
    print_colored("4-Mic Audio Visualizer System", Colors.GOLD, bold=True)
    print()

def print_colored(text, color=Colors.WHITE, bold=False):
    """Print colored text"""
    style = color
    if bold:
        style += Colors.BOLD
    print(f"{style}{text}{Colors.RESET}")

def print_header(text):
    """Print a header with WVU colors"""
    print_colored("="*80, Colors.BLUE)
    print_colored(text, Colors.GOLD, bold=True)
    print_colored("="*80, Colors.BLUE)

class AudioVisualizer(QtWidgets.QMainWindow):
    def __init__(self, sample_rate=44100, block_size=512, channels=4, devices=None, logo_path=None, icon_path=None):
        super().__init__()
        
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.channels = channels
        self.devices = devices
        self.streams = []
        self.icon_path = icon_path
        
        # WVU Colors
        self.wvu_old_gold = pg.mkColor('#EAAA00')
        self.wvu_blue = pg.mkColor('#002855')
        self.wvu_dark_gold = pg.mkColor('#B8860B')
        self.wvu_bg = pg.mkColor('#001122')
        
        # Audio data buffers
        self.buffer_size = 2048
        self.audio_buffers = [deque(maxlen=self.buffer_size) for _ in range(channels)]
        self.level_buffers = [deque(maxlen=100) for _ in range(channels)]
        
        # Level tracking
        self.current_levels = [0.0] * channels
        self.peak_levels = [0.0] * channels
        self.average_levels = [0.0] * channels  # Moving average levels
        self.average_window_size = 50  # Number of samples for averaging
        
        # Noise floor tracking for auto-leveling
        self.noise_floor_buffers = [deque(maxlen=200) for _ in range(channels)]  # Store recent RMS values for noise floor
        self.noise_floors = [0.001] * channels  # Estimated noise floor (minimum to avoid zero)
        self.y_axis_ranges = [(-1.0, 1.0)] * channels  # Current Y-axis ranges
        
        # Display gain (multiplier for displayed signal)
        self.display_gain = 1.0
        
        # Time plot mode settings
        self.time_plot_mode = False
        self.sample_rate_adjustment = 1.0
        # Reduced buffer size to prevent memory issues (30s at 48kHz instead of 60s)
        self.time_plot_buffers = [deque(maxlen=1440000) for _ in range(channels)]  # ~30s at 48kHz
        self.time_plot_start_time = None  # Start time for time plot mode
        self.time_plot_cache = [None] * channels  # Cache for numpy arrays to avoid repeated conversions
        self.time_plot_cache_dirty = [True] * channels  # Track if cache needs updating
        self.time_plot_update_counter = [0] * channels  # Counter to update cache periodically
        # Pre-allocated numpy arrays for time plot data to avoid repeated allocations
        self.time_plot_x_array = [None] * channels
        self.time_plot_y_array = [None] * channels
        
        # Fullscreen state
        self.is_fullscreen = False
        self.single_graph_mode = False
        self.fullscreen_graph_index = None
        
        # Pause state
        self.is_paused = False
        
        # Setup UI
        self.setup_ui(logo_path)
        
        # Setup update timer - Adaptive frame rate (30 FPS default, can be adjusted)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(33)  # ~30 FPS (33ms per frame) - better for performance
        self.frame_skip_counter = 0  # For adaptive frame skipping
        
    def setup_ui(self, logo_path):
        """Setup the user interface"""
        # Set window properties
        self.setWindowTitle('WVU 4-Mic Audio Visualizer - Real-time Level Monitoring')
        self.setStyleSheet(f"background-color: {self.wvu_blue.name()};")
        
        # Enable keyboard focus so we can receive spacebar events
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        
        # Set window icon
        self.set_window_icon()
        
        # Create menu bar
        menubar = self.menuBar()
        menubar.setStyleSheet(f"""
            QMenuBar {{
                background-color: {self.wvu_blue.name()};
                color: {self.wvu_old_gold.name()};
                font-weight: bold;
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 8px 12px;
            }}
            QMenuBar::item:selected {{
                background-color: {self.wvu_old_gold.name()};
                color: {self.wvu_blue.name()};
            }}
            QMenu {{
                background-color: {self.wvu_blue.name()};
                color: {self.wvu_old_gold.name()};
                border: 2px solid {self.wvu_old_gold.name()};
            }}
            QMenu::item:selected {{
                background-color: {self.wvu_old_gold.name()};
                color: {self.wvu_blue.name()};
            }}
        """)
        
        # Settings menu
        settings_menu = menubar.addMenu('Settings')
        settings_action = QtWidgets.QAction('Display Settings...', self)
        settings_action.setShortcut('Ctrl+S')
        settings_action.triggered.connect(self.show_settings_dialog)
        settings_menu.addAction(settings_action)
        
        # Central widget
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title bar with logo
        title_layout = QtWidgets.QHBoxLayout()
        
        # Logo
        if logo_path and os.path.exists(logo_path):
            try:
                logo_label = QtWidgets.QLabel()
                pixmap = QtGui.QPixmap(logo_path)
                pixmap = pixmap.scaled(100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                logo_label.setPixmap(pixmap)
                title_layout.addWidget(logo_label)
            except Exception as e:
                print(f"Warning: Could not load logo: {e}")
        
        # Title
        title_label = QtWidgets.QLabel('WVU 4-Mic Audio Visualizer')
        title_label.setStyleSheet(f"color: {self.wvu_old_gold.name()}; font-size: 24px; font-weight: bold; font-family: Helvetica, Arial, sans-serif;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # Fullscreen button
        self.fullscreen_btn = QtWidgets.QPushButton('⛶ Fullscreen')
        self.fullscreen_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.wvu_old_gold.name()};
                color: {self.wvu_blue.name()};
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 5px;
                font-size: 12px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: #FFD700;
            }}
        """)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        title_layout.addWidget(self.fullscreen_btn)
        
        # Comparison label
        self.comparison_label = QtWidgets.QLabel('Initializing...')
        self.comparison_label.setStyleSheet(f"""
            color: {self.wvu_blue.name()}; 
            font-size: 14px; 
            font-weight: bold;
            font-family: Helvetica, Arial, sans-serif;
            background-color: {self.wvu_old_gold.name()};
            padding: 10px;
            border-radius: 5px;
        """)
        self.comparison_label.setAlignment(QtCore.Qt.AlignCenter)
        title_layout.addWidget(self.comparison_label)
        
        # Pause indicator label (hidden by default)
        self.pause_label = QtWidgets.QLabel('⏸ PAUSED - Press SPACE to resume')
        self.pause_label.setStyleSheet(f"""
            color: white; 
            font-size: 18px; 
            font-weight: bold;
            font-family: Helvetica, Arial, sans-serif;
            background-color: rgba(255, 0, 0, 0.8);
            padding: 15px 25px;
            border-radius: 8px;
            border: 3px solid {self.wvu_old_gold.name()};
        """)
        self.pause_label.setAlignment(QtCore.Qt.AlignCenter)
        self.pause_label.hide()  # Hidden by default
        title_layout.addWidget(self.pause_label)
        
        main_layout.addLayout(title_layout)
        
        # Create grid of plots (will adjust based on number of channels)
        self.plot_grid = QtWidgets.QGridLayout()
        
        self.plot_widgets = []
        self.plot_curves = []
        self.level_labels = []
        self.level_bars = []
        self.plot_containers = []  # Store containers for each plot to show/hide
        
        for i in range(self.channels):
            # Create plot widget with OpenGL backend if available
            plot_widget = pg.PlotWidget()
            # Disable keyboard focus on plot widgets so main window can receive spacebar
            plot_widget.setFocusPolicy(QtCore.Qt.NoFocus)
            plot_widget.setBackground(self.wvu_bg)
            # Force OpenGL rendering if available
            try:
                if GPU_ACCELERATION_ENABLED:
                    # Use OpenGL widget for hardware acceleration
                    from pyqtgraph.Qt import QtWidgets
                    if hasattr(QtWidgets, 'QOpenGLWidget'):
                        # PyQtGraph should automatically use OpenGL if enabled
                        # But we can verify by checking the view
                        pass
            except:
                pass
            plot_widget.setTitle(f'Microphone {i+1}', color=self.wvu_old_gold.name(), size='14pt', font='Helvetica')
            # Set labels - each plot gets its own independent labels
            # Important: Set labels before configuring axes to ensure they're displayed
            plot_widget.setLabel('left', 'Amplitude', color=self.wvu_old_gold.name(), font='Helvetica')
            plot_widget.setLabel('bottom', 'Sample', color=self.wvu_old_gold.name(), font='Helvetica')
            plot_widget.showGrid(x=True, y=True, alpha=0.2)
            
            # Get the PlotItem to configure it independently
            plot_item = plot_widget.getPlotItem()
            # Ensure this plot doesn't link axes with other plots
            plot_item.setDownsampling(mode='peak')
            plot_item.setClipToView(True)
            
            # Performance optimizations for ViewBox
            view_box = plot_widget.getViewBox()
            # Enable optimizations
            try:
                view_box.setCacheMode(view_box.CacheModeFlag.CacheAll)  # Cache rendering for better performance
            except:
                pass  # Cache mode not available in all PyQtGraph versions
            
            # Store original setRange method and override it to lock X but allow Y
            original_setRange = view_box.setRange
            # Store original method as attribute so we can call it directly if needed
            view_box._original_setRange = original_setRange
            
            def locked_setRange(*args, **kwargs):
                # Extract Y range from various possible argument formats
                y_range = None
                
                # Check kwargs first (most common)
                if 'yRange' in kwargs:
                    y_range = kwargs['yRange']
                # Check if first arg is a dict with yRange
                elif len(args) > 0 and isinstance(args[0], dict) and 'yRange' in args[0]:
                    y_range = args[0]['yRange']
                # Check positional args: (xRange, yRange) - two separate args
                elif len(args) >= 2:
                    y_range = args[1]
                # Check if first arg is a tuple/list (xRange, yRange)
                elif len(args) > 0 and isinstance(args[0], (tuple, list)) and len(args[0]) == 2:
                    y_range = args[0][1]
                
                # If we still don't have a Y range, use current or default
                if y_range is None:
                    try:
                        current_range = view_box.viewRange()
                        if current_range and len(current_range) > 1:
                            y_range = current_range[1]
                        else:
                            y_range = (-1, 1)
                    except:
                        y_range = (-1, 1)
                
                # Always use the provided Y range, force X to be (0, 512)
                # Use update=True to force immediate update
                original_setRange(xRange=(0, 512), yRange=y_range, padding=0, update=True)
            view_box.setRange = locked_setRange
            
            # Disable ALL auto-scaling features
            view_box.disableAutoRange()
            view_box.setAutoVisible(x=False, y=False)
            view_box.enableAutoRange(x=False, y=False)
            
            # Set fixed X range, Y will be auto-scaled based on noise floor
            plot_widget.setXRange(0, 512, padding=0, update=False)
            plot_widget.setYRange(-1, 1, padding=0, update=False)
            
            # Lock X-axis but allow Y-axis to auto-scale
            view_box.setLimits(xMin=0, xMax=512, 
                             minXRange=512, maxXRange=512)
            view_box.setRange(xRange=(0, 512), yRange=(-1, 1), padding=0, update=False)
            
            # Disable mouse interaction for zooming/panning, but allow double-click
            view_box.setMouseEnabled(x=False, y=False)
            
            # Enable mouse events on the plot widget itself for double-click
            plot_widget.setMouseEnabled(True)
            
            # Set axis colors and fonts - configure each axis independently
            left_axis = plot_widget.getAxis('left')
            left_axis.setPen(pg.mkPen(self.wvu_old_gold))
            left_axis.setTextPen(pg.mkPen(self.wvu_old_gold))
            left_axis.setStyle(tickFont=QtGui.QFont('Helvetica', 10))
            # Set label text and ensure it's displayed for this specific plot
            left_axis.setLabel('Amplitude', color=self.wvu_old_gold.name())
            # Make sure the label is visible (not hidden by layout optimization)
            left_axis.label.setVisible(True)
            
            bottom_axis = plot_widget.getAxis('bottom')
            bottom_axis.setPen(pg.mkPen(self.wvu_old_gold))
            bottom_axis.setTextPen(pg.mkPen(self.wvu_old_gold))
            bottom_axis.setStyle(tickFont=QtGui.QFont('Helvetica', 10))
            # Set label text and ensure it's displayed for this specific plot
            bottom_axis.setLabel('Sample', color=self.wvu_old_gold.name())
            # Make sure the label is visible (not hidden by layout optimization)
            bottom_axis.label.setVisible(True)
            
            # Ensure all axes are visible for this plot (independent of other plots)
            plot_widget.showAxis('left', show=True)
            plot_widget.showAxis('bottom', show=True)
            plot_widget.showAxis('top', show=False)
            plot_widget.showAxis('right', show=False)
            
            # Create curve for waveform with performance optimizations
            # Use antialiasing and optimize for real-time updates
            curve = plot_widget.plot([], [], 
                                    pen=pg.mkPen(self.wvu_old_gold, width=2),
                                    antialias=True,  # Enable antialiasing (GPU accelerated if OpenGL enabled)
                                    clipToView=True,  # Only render visible portions
                                    skipFiniteCheck=True)  # Skip finite check for performance
            self.plot_curves.append(curve)
            
            # Level bar (will be created as a rectangle item)
            # We'll create it dynamically in update_plots
            self.level_bars.append(None)  # Placeholder, will be created on first update
            
            # Level label - use white text on gold background for better readability
            # Position it away from edges to avoid clipping by plot borders
            level_label = pg.TextItem('', anchor=(0, 1), color='white', 
                                    fill=pg.mkBrush(self.wvu_old_gold), border=pg.mkPen(self.wvu_dark_gold, width=2))
            # Set initial position - will be updated in update_plots
            # Use a position that's well within the visible plot area
            level_label.setPos(60, -0.7)  # X=60 (well away from left edge), Y near top but visible
            level_label.setZValue(100)  # Ensure it appears on top of other elements
            plot_widget.addItem(level_label)
            self.level_labels.append(level_label)
            
            self.plot_widgets.append(plot_widget)
            
            # Create a container widget for the plot (to enable show/hide and double-click)
            class PlotContainer(QtWidgets.QWidget):
                def __init__(self, plot_widget, graph_idx, visualizer):
                    super().__init__()
                    self.plot_widget = plot_widget
                    self.graph_idx = graph_idx
                    self.visualizer = visualizer
                    layout = QtWidgets.QVBoxLayout()
                    layout.setContentsMargins(0, 0, 0, 0)
                    layout.addWidget(plot_widget)
                    self.setLayout(layout)
                
                def mouseDoubleClickEvent(self, event):
                    self.visualizer.show_single_graph_fullscreen(self.graph_idx)
                    super().mouseDoubleClickEvent(event)
            
            plot_container = PlotContainer(plot_widget, i, self)
            self.plot_containers.append(plot_container)
            
            # Add plot to grid (dynamic layout based on number of channels)
            # For 1-2 channels: 1 row, 1-2 columns
            # For 3-4 channels: 2 rows, 2 columns
            # For 5-6 channels: 2 rows, 3 columns
            # For 7-8 channels: 2 rows, 4 columns
            if self.channels <= 2:
                row = 0
                col = i
            elif self.channels <= 4:
                row = i // 2
                col = i % 2
            elif self.channels <= 6:
                row = i // 3
                col = i % 3
            else:  # 7-8 channels
                row = i // 4
                col = i % 4
            self.plot_grid.addWidget(plot_container, row, col)
        
        main_layout.addLayout(self.plot_grid)
        
        # Store reference to main layout for switching views
        self.main_layout = main_layout
        
        # Set fullscreen
        self.showMaximized()
        
        # Ensure window gets focus for keyboard events
        self.raise_()
        self.activateWindow()
        self.setFocus()
        
    def make_audio_callback(self, channel_idx):
        """Create a callback function for a specific channel"""
        def callback(indata, frames, time_info, status):
            if status:
                pass  # Status information available but not logged
            
            try:
                # Get audio data - handle both 1D and 2D input arrays consistently for ALL mics
                if indata is None or len(indata) == 0:
                    audio_data = np.zeros(frames, dtype=np.float32)
                else:
                    # Extract audio data - same logic for ALL mics, no special handling
                    if len(indata.shape) == 2:
                        # 2D array: (frames, channels) - extract first channel
                        if indata.shape[1] >= 1:
                            audio_data = indata[:, 0].copy()
                        else:
                            audio_data = np.zeros(indata.shape[0], dtype=np.float32)
                    elif len(indata.shape) == 1:
                        # 1D array: (frames,) - already single channel
                        audio_data = indata.copy()
                    else:
                        # Unexpected shape - flatten
                        audio_data = indata.flatten()
                
                # Ensure audio_data is a proper numpy array with correct dtype
                audio_data = np.asarray(audio_data, dtype=np.float32)
                
                # Ensure we have a 1D array
                if len(audio_data.shape) > 1:
                    audio_data = audio_data.flatten()
                
                # Validate data length matches expected frames
                if len(audio_data) != frames:
                    if len(audio_data) > frames:
                        audio_data = audio_data[:frames]
                    elif len(audio_data) < frames:
                        # Pad with zeros if we got fewer samples than expected
                        padding = np.zeros(frames - len(audio_data), dtype=np.float32)
                        audio_data = np.concatenate([audio_data, padding])
                
                # Replace any invalid values with zeros
                if not np.all(np.isfinite(audio_data)):
                    audio_data = np.where(np.isfinite(audio_data), audio_data, 0.0)
                
                # Calculate RMS level - same calculation for ALL mics
                if len(audio_data) > 0:
                    audio_squared = audio_data ** 2
                    mean_squared = np.mean(audio_squared)
                    rms_level = np.sqrt(mean_squared)
                    if not np.isfinite(rms_level):
                        rms_level = 0.0
                else:
                    rms_level = 0.0
                
                # Update levels - ensure we're using the correct index
                if channel_idx < len(self.current_levels):
                    self.current_levels[channel_idx] = rms_level
                if channel_idx < len(self.level_buffers):
                    self.level_buffers[channel_idx].append(rms_level)
                
                # Update noise floor buffer
                if channel_idx < len(self.noise_floor_buffers):
                    self.noise_floor_buffers[channel_idx].append(rms_level)
                
                # Update peak level
                if channel_idx < len(self.peak_levels):
                    if rms_level > self.peak_levels[channel_idx]:
                        self.peak_levels[channel_idx] = rms_level
                    else:
                        # Decay peak slowly
                        self.peak_levels[channel_idx] *= 0.999
                
                # Add to buffer - always add data, even if it's zeros
                if channel_idx < len(self.audio_buffers):
                    self.audio_buffers[channel_idx].extend(audio_data)
            except Exception:
                # Silently handle errors - just skip this callback
                pass
        
        return callback
    
    def update_plots(self):
        """Update all plots"""
        # Skip frames occasionally for better performance (adaptive frame skipping)
        self.frame_skip_counter += 1
        skip_rendering = False
        
        # In time plot mode, skip more frames to reduce CPU load
        if self.time_plot_mode:
            # Skip rendering every 3rd frame in time plot mode for better performance
            # (but still process data to keep buffers updated)
            if self.frame_skip_counter % 3 == 0:
                skip_rendering = True
        else:
            # Skip rendering every 5th frame in normal mode
            if self.frame_skip_counter % 5 == 0:
                skip_rendering = True
        
        # Update waveform plots
        for i in range(self.channels):
            # Verify we have valid buffers for this index
            if i >= len(self.audio_buffers):
                continue
            
            # Convert deque to numpy array - optimized for performance
            if len(self.audio_buffers[i]) > 0:
                # Get the most recent samples from the buffer (last 512 samples for display)
                # Use islice for better performance when we only need last N samples
                buffer_len = len(self.audio_buffers[i])
                if buffer_len <= 512:
                    # Small buffer - convert directly
                    audio_data = np.fromiter(self.audio_buffers[i], dtype=np.float32, count=buffer_len)
                else:
                    # Large buffer - only take last 512 samples
                    audio_data = np.fromiter(
                        (self.audio_buffers[i][j] for j in range(buffer_len - 512, buffer_len)),
                        dtype=np.float32, count=512
                    )
            else:
                # If buffer is empty, use zeros
                audio_data = np.zeros(512, dtype=np.float32)
            
            # Replace invalid values with zeros (don't filter - keep array size)
            if not np.all(np.isfinite(audio_data)):
                audio_data = np.where(np.isfinite(audio_data), audio_data, 0.0)
            
            # Always process data, even if it's all zeros
            if len(audio_data) > 0:
                if self.time_plot_mode:
                    # Time plot mode: accumulate data over time
                    current_time = time.time()
                    if self.time_plot_start_time is None:
                        self.time_plot_start_time = current_time
                    
                    # Get sample rate from the stream if available, otherwise use default
                    sample_rate = self.sample_rate
                    if i < len(self.streams) and self.streams[i] is not None:
                        try:
                            stream_sr = self.streams[i].samplerate
                            if stream_sr > 0:
                                sample_rate = stream_sr
                        except:
                            pass
                    
                    # Calculate time per sample with adjustment
                    time_per_sample = 1.0 / sample_rate * self.sample_rate_adjustment
                    
                    # Calculate the time for the first sample in this block
                    # Use the current buffer length to determine the starting time
                    current_buffer_length = len(self.time_plot_buffers[i])
                    start_time = current_buffer_length * time_per_sample
                    
                    # Add new samples to time plot buffer with timestamps - optimized batch append
                    # Pre-calculate all timestamps as numpy array for better performance
                    num_samples = len(audio_data)
                    if num_samples > 0:
                        sample_times = start_time + np.arange(num_samples, dtype=np.float32) * time_per_sample
                        # Batch append using extend for better performance
                        time_data_pairs = list(zip(sample_times, audio_data))
                        self.time_plot_buffers[i].extend(time_data_pairs)
                    
                    # Mark cache as dirty (but update periodically for performance)
                    self.time_plot_cache_dirty[i] = True
                    self.time_plot_update_counter[i] += 1
                    
                    # Get data from time plot buffer (with downsampling for performance)
                    if len(self.time_plot_buffers[i]) > 0:
                        # Update cache if needed (every 3 frames for better performance in time plot mode)
                        update_cache = (self.time_plot_cache_dirty[i] and 
                                       (self.time_plot_update_counter[i] % 3 == 0 or 
                                        self.time_plot_cache[i] is None))
                        
                        if update_cache:
                            # Optimized conversion: use pre-allocated arrays if available
                            buffer_len = len(self.time_plot_buffers[i])
                            
                            # Reuse arrays if they're the right size, otherwise allocate new ones
                            if (self.time_plot_x_array[i] is None or 
                                len(self.time_plot_x_array[i]) != buffer_len):
                                self.time_plot_x_array[i] = np.empty(buffer_len, dtype=np.float32)
                                self.time_plot_y_array[i] = np.empty(buffer_len, dtype=np.float32)
                            
                            # Fast extraction using fromiter (faster than list comprehension)
                            x_array = self.time_plot_x_array[i][:buffer_len]
                            y_array = self.time_plot_y_array[i][:buffer_len]
                            
                            # Extract data efficiently
                            for idx, (t, val) in enumerate(self.time_plot_buffers[i]):
                                x_array[idx] = t
                                y_array[idx] = val
                            
                            x_data_full = x_array
                            y_data_full = y_array
                            
                            # Downsample for display if we have too many points (max 15000 points for better performance)
                            max_display_points = 15000
                            if len(x_data_full) > max_display_points:
                                # Use numpy-based decimation for better performance
                                step = max(1, len(x_data_full) // max_display_points)
                                indices = np.arange(0, len(x_data_full), step, dtype=np.int32)
                                # Also include the last point
                                if indices[-1] != len(x_data_full) - 1:
                                    indices = np.append(indices, len(x_data_full) - 1)
                                
                                x_data_display = x_data_full[indices]
                                
                                # Optimized peak-preserving downsampling using numpy
                                # For each chunk, find the peak and use it
                                y_downsampled = np.empty(len(indices), dtype=np.float32)
                                for chunk_idx in range(len(indices) - 1):
                                    start_idx = indices[chunk_idx]
                                    end_idx = indices[chunk_idx + 1]
                                    chunk = y_data_full[start_idx:end_idx]
                                    # Find peak using absolute value
                                    peak_idx = np.argmax(np.abs(chunk))
                                    y_downsampled[chunk_idx] = chunk[peak_idx]
                                # Always include last point
                                y_downsampled[-1] = y_data_full[-1]
                                audio_data_display = y_downsampled * self.display_gain
                            else:
                                x_data_display = x_data_full
                                audio_data_display = y_data_full * self.display_gain
                            
                            # Cache the result
                            self.time_plot_cache[i] = (x_data_display, audio_data_display)
                            self.time_plot_cache_dirty[i] = False
                        
                        # Always use cached data (or newly computed if cache was updated)
                        if self.time_plot_cache[i] is not None:
                            x_data_display, audio_data_display = self.time_plot_cache[i]
                        else:
                            # Fallback if cache not ready
                            x_data_display = np.array([], dtype=np.float32)
                            audio_data_display = np.array([], dtype=np.float32)
                    else:
                        x_data_display = np.array([], dtype=np.float32)
                        audio_data_display = np.array([], dtype=np.float32)
                else:
                    # Normal mode: show the most recent 512 samples
                    display_length = min(len(audio_data), 512)
                    if len(audio_data) > display_length:
                        # Take the last N samples (most recent)
                        audio_data_display = audio_data[-display_length:]
                    else:
                        # Use all available data
                        audio_data_display = audio_data
                    
                    # Apply display gain to the audio data
                    audio_data_display = audio_data_display * self.display_gain
                    
                    # Create x_data matching the display length, starting from 0
                    x_data_display = np.arange(len(audio_data_display), dtype=np.float32)
                
                # Calculate noise floor (use 10th percentile of recent RMS levels)
                if len(self.noise_floor_buffers[i]) > 20:
                    noise_floor_values = list(self.noise_floor_buffers[i])
                    # Use 10th percentile as noise floor estimate
                    self.noise_floors[i] = np.percentile(noise_floor_values, 10)
                    # Ensure minimum noise floor to avoid zero
                    self.noise_floors[i] = max(self.noise_floors[i], 0.001)
                else:
                    # Use a reasonable default until we have enough samples
                    self.noise_floors[i] = 0.001
                
                # Store data for global range calculation (after gain is applied)
                # We'll calculate a global Y range after processing all mics
                current_max = np.abs(audio_data_display).max() if len(audio_data_display) > 0 else 0.0
                
                # Ensure we have valid data for display
                if len(audio_data_display) == 0:
                    # If no data, create a zero array to show something
                    audio_data_display = np.zeros(512, dtype=np.float32) * self.display_gain
                    x_data_display = np.arange(512, dtype=np.int32)
                    current_max = 0.0
                
                # Store max value for this mic to calculate global range
                if not hasattr(self, '_mic_max_values'):
                    self._mic_max_values = [0.0] * self.channels
                self._mic_max_values[i] = current_max
                
                # Update curve - ensure data arrays match in length
                # Verify we have valid plot curve for this index
                if i >= len(self.plot_curves):
                    continue
                
                # Only update plot data if we're not skipping rendering
                if not skip_rendering:
                    # Ensure both arrays are the same length and have data
                    # Use optimized setData for better performance
                    if len(x_data_display) == len(audio_data_display) and len(audio_data_display) > 0:
                        # Both arrays match - use them directly
                        # Use skipFiniteCheck for better performance (we already validate data)
                        # Use autoDownsample for automatic downsampling if needed
                        self.plot_curves[i].setData(x_data_display, audio_data_display, 
                                                    connect='finite' if self.time_plot_mode else 'all',
                                                    skipFiniteCheck=True,
                                                    autoDownsample=True,
                                                    autoDownsampleFactor=1)
                    elif len(audio_data_display) > 0:
                        # Mismatch - create matching x_data for audio_data_display
                        x_fallback = np.arange(len(audio_data_display), dtype=np.float32)
                        self.plot_curves[i].setData(x_fallback, audio_data_display,
                                                    connect='finite' if self.time_plot_mode else 'all',
                                                    skipFiniteCheck=True,
                                                    autoDownsample=True,
                                                    autoDownsampleFactor=1)
                    else:
                        # No data - show empty plot
                        self.plot_curves[i].setData([], [])
        
        # Calculate global Y-axis range based on all mics' data
        # This ensures all graphs use the same scale for comparison
        if hasattr(self, '_mic_max_values') and len(self._mic_max_values) == self.channels:
            # Find the maximum value across all mics
            global_max = max(self._mic_max_values) if self._mic_max_values else 0.1
            
            # Add some headroom (20% above max)
            range_size = max(global_max * 1.2, 0.1)  # Minimum 0.1 range
            
            # Center around zero
            y_min = -range_size
            y_max = range_size
            
            # Smooth the range changes to avoid jitter
            if not hasattr(self, '_global_y_range'):
                self._global_y_range = (y_min, y_max)
            
            old_y_min, old_y_max = self._global_y_range
            smoothing_factor = 0.9  # Slower smoothing for global range
            y_min = old_y_min * smoothing_factor + y_min * (1 - smoothing_factor)
            y_max = old_y_max * smoothing_factor + y_max * (1 - smoothing_factor)
            
            # Ensure ranges are finite and reasonable
            if not np.isfinite(y_min) or not np.isfinite(y_max):
                y_min = -0.1
                y_max = 0.1
            
            self._global_y_range = (y_min, y_max)
            
            # Apply the same Y-axis range to all plots (only if not skipping rendering)
            if not skip_rendering:
                for i in range(self.channels):
                    if i < len(self.plot_widgets):
                        view_box = self.plot_widgets[i].getViewBox()
                        
                        if self.time_plot_mode:
                            # Time plot mode: unlock X-axis limits and auto-scale
                            view_box.setLimits(xMin=None, xMax=None, minXRange=None, maxXRange=None)
                            
                            # Time plot mode: auto-scale X-axis based on cached time data (more efficient)
                            if self.time_plot_cache[i] is not None:
                                x_data_display, _ = self.time_plot_cache[i]
                                if len(x_data_display) > 0:
                                    x_min = max(0, x_data_display.min() - 0.1)  # Start from 0 or slightly before
                                    x_max = max(x_data_display.max() + 0.1, 1.0)  # Add padding, minimum 1 second
                                else:
                                    x_min = 0
                                    x_max = 1.0
                            elif len(self.time_plot_buffers[i]) > 0:
                                # Fallback: calculate from buffer if cache not available
                                last_time = self.time_plot_buffers[i][-1][0]
                                x_min = 0
                                x_max = max(last_time + 0.1, 1.0)
                            else:
                                x_min = 0
                                x_max = 1.0
                            
                            # Smooth X-axis updates to reduce jitter
                            if not hasattr(self, '_time_plot_x_ranges'):
                                self._time_plot_x_ranges = [(0, 1.0)] * self.channels
                            
                            old_x_min, old_x_max = self._time_plot_x_ranges[i]
                            smoothing = 0.85  # Smoothing factor for X-axis
                            x_min = old_x_min * smoothing + x_min * (1 - smoothing)
                            x_max = old_x_max * smoothing + x_max * (1 - smoothing)
                            self._time_plot_x_ranges[i] = (x_min, x_max)
                            
                            # Update X-axis label for time plot mode
                            self.plot_widgets[i].setLabel('bottom', 'Time (seconds)', color=self.wvu_old_gold.name(), font='Helvetica')
                            
                            # Set ranges for time plot mode (only update if range changed significantly)
                            # Store last range to avoid unnecessary updates
                            if not hasattr(self, '_last_time_plot_ranges'):
                                self._last_time_plot_ranges = [None] * self.channels
                            
                            last_range = self._last_time_plot_ranges[i]
                            # Only update if range changed by more than 5% to reduce expensive setRange calls
                            range_changed = (last_range is None or 
                                            abs(last_range[0] - x_min) > x_max * 0.05 or 
                                            abs(last_range[1] - x_max) > x_max * 0.05 or
                                            abs(last_range[2] - y_min) > abs(y_max - y_min) * 0.05 or
                                            abs(last_range[3] - y_max) > abs(y_max - y_min) * 0.05)
                            
                            if range_changed:
                                if hasattr(view_box, '_original_setRange'):
                                    view_box._original_setRange(xRange=(x_min, x_max), yRange=(y_min, y_max), padding=0, update=True)
                                else:
                                    view_box.setRange(xRange=(x_min, x_max), yRange=(y_min, y_max), padding=0, update=True)
                                self.plot_widgets[i].setXRange(x_min, x_max, padding=0, update=True)
                                self.plot_widgets[i].setYRange(y_min, y_max, padding=0, update=True)
                                self._last_time_plot_ranges[i] = (x_min, x_max, y_min, y_max)
                        else:
                        # Normal mode: restore locked X-axis limits and fixed X range (0-512 samples)
                        view_box.setLimits(xMin=0, xMax=512, minXRange=512, maxXRange=512)
                        
                        # Restore X-axis label for normal mode
                        self.plot_widgets[i].setLabel('bottom', 'Sample', color=self.wvu_old_gold.name(), font='Helvetica')
                        
                        # Store last range to avoid unnecessary updates
                        if not hasattr(self, '_last_normal_plot_ranges'):
                            self._last_normal_plot_ranges = [None] * self.channels
                        
                        last_range = self._last_normal_plot_ranges[i]
                        # Only update if Y range changed by more than 2% to reduce expensive setRange calls
                        range_changed = (last_range is None or 
                                        abs(last_range[0] - y_min) > abs(y_max - y_min) * 0.02 or
                                        abs(last_range[1] - y_max) > abs(y_max - y_min) * 0.02)
                        
                        if range_changed:
                            # Try multiple methods to ensure Y range is set correctly
                            # Method 1: Call the original setRange directly if available (bypasses override)
                            if hasattr(view_box, '_original_setRange'):
                                view_box._original_setRange(xRange=(0, 512), yRange=(y_min, y_max), padding=0, update=True)
                            else:
                                # Fallback to override method
                                view_box.setRange(xRange=(0, 512), yRange=(y_min, y_max), padding=0, update=True)
                            # Method 2: Also set directly via plot widget as backup
                            self.plot_widgets[i].setYRange(y_min, y_max, padding=0, update=True)
                            self._last_normal_plot_ranges[i] = (y_min, y_max)
            
            # Update level bars and labels even when skipping frames (lighter operation)
            for i in range(self.channels):
                if i >= len(self.plot_widgets):
                    continue
                
                # Update level bar (only update every other frame to reduce overhead)
                if i < len(self.current_levels):
                    level = self.current_levels[i]
                    if not np.isfinite(level):
                        level = 0.0
                else:
                    level = 0.0
                
                # Update level bar less frequently (every 2 frames)
                if self.frame_skip_counter % 2 == 0:
                    try:
                        # Use global Y range for consistent scaling
                        if self.time_plot_mode:
                        # In time plot mode, use current X range for bar width calculation
                        if hasattr(self, '_time_plot_x_ranges') and i < len(self._time_plot_x_ranges):
                            x_min, x_max = self._time_plot_x_ranges[i]
                            max_x = max(x_max - x_min, 1.0)
                        else:
                            max_x = 1.0
                    else:
                        max_x = 512.0  # Fixed X range for normal mode
                    
                    if hasattr(self, '_global_y_range'):
                        y_min_view, y_max_view = self._global_y_range
                    else:
                        y_min_view, y_max_view = (-0.1, 0.1)
                    
                    bar_width = level * max_x * 0.15
                    bar_width = min(bar_width, max_x)  # Clamp bar width
                    
                    # Update level bar color
                    if level < 0.3:
                        color = self.wvu_old_gold
                    elif level < 0.7:
                        color = pg.mkColor('#FFD700')
                    else:
                        color = pg.mkColor('#FFA500')
                    
                    # Create or update level bar rectangle using fixed values
                    y_pos = y_max_view * 0.9
                    bar_height = (y_max_view - y_min_view) * 0.08
                    
                    # Update or create level bar - reuse existing item if possible
                    if self.level_bars[i] is not None:
                        # Update existing bar instead of recreating
                        try:
                            bar_x = np.array([0, bar_width, bar_width, 0, 0], dtype=np.float32)
                            bar_y = np.array([y_pos, y_pos, y_pos + bar_height, y_pos + bar_height, y_pos], dtype=np.float32)
                            self.level_bars[i].setData(bar_x, bar_y)
                            # Update color if needed
                            self.level_bars[i].setBrush(pg.mkBrush(color))
                            self.level_bars[i].setPen(pg.mkPen(color, width=2))
                        except:
                            # If update fails, recreate
                            self.plot_widgets[i].removeItem(self.level_bars[i])
                            self.level_bars[i] = None
                    
                    if self.level_bars[i] is None:
                        # Create new bar using PlotDataItem with fill
                        bar_x = np.array([0, bar_width, bar_width, 0, 0], dtype=np.float32)
                        bar_y = np.array([y_pos, y_pos, y_pos + bar_height, y_pos + bar_height, y_pos], dtype=np.float32)
                        bar_item = pg.PlotDataItem(bar_x, bar_y, fillLevel=y_pos, 
                                                  brush=pg.mkBrush(color), 
                                                  pen=pg.mkPen(color, width=2))
                        bar_item.setZValue(-10)
                        self.plot_widgets[i].addItem(bar_item)
                        self.level_bars[i] = bar_item
                    
                        # Update level label
                        level_db = 20 * np.log10(level + 1e-10)
                        if not np.isfinite(level_db):
                            level_db = -100.0
                        
                        self.level_labels[i].setText(
                            f'Level: {level:.3f} ({level_db:.1f} dB)\nPeak: {self.peak_levels[i]:.3f}'
                        )
                        # Position label away from edges to avoid clipping
                        # X position: 60 pixels from left (well away from y-axis and left border)
                        # Y position: 80% down from top (away from top border, title, and grid lines)
                        x_pos = 60  # Increased from 50 to give more clearance from left edge
                        y_pos = y_max_view * 0.80  # Moved down slightly from 85% to avoid top edge
                        self.level_labels[i].setPos(x_pos, y_pos)
                        # Ensure label stays on top of all other plot elements
                        self.level_labels[i].setZValue(100)
                    except:
                        pass
                except Exception as e:
                    # Silently handle any errors in level bar update
                    pass
        
        # Calculate moving averages for each channel
        for i in range(self.channels):
            if len(self.level_buffers[i]) > 0:
                # Calculate average from the level buffer
                recent_levels = list(self.level_buffers[i])
                if len(recent_levels) >= self.average_window_size:
                    # Use last N samples for average
                    recent_levels = recent_levels[-self.average_window_size:]
                self.average_levels[i] = np.mean(recent_levels) if recent_levels else 0.0
        
        # Update comparison text using averaged levels
        if any(avg > 0 for avg in self.average_levels):
            max_avg_idx = np.argmax(self.average_levels)
            max_avg_level = self.average_levels[max_avg_idx]
            comparison_msg = f'Highest Average Level: Microphone {max_avg_idx+1} ({max_avg_level:.3f})'
            
            # Show both current and average levels
            levels_str = ' | '.join([f'Mic{i+1}: {self.current_levels[i]:.3f} (avg: {self.average_levels[i]:.3f})' 
                                    for i in range(self.channels)])
            self.comparison_label.setText(f'{comparison_msg}\n{levels_str}')
    
    def start(self):
        """Start the audio streams"""
        try:
            # Open separate audio stream for each channel/device
            for ch in range(self.channels):
                # Get device for this channel - ensure we have a valid device list
                if self.devices is None or len(self.devices) <= ch:
                    device_idx = None
                    print_colored(f"Warning: No device specified for Mic {ch+1}, using default", Colors.YELLOW)
                else:
                    device_idx = self.devices[ch]
                
                callback = self.make_audio_callback(ch)
                
                # Validate device before opening
                if device_idx is not None:
                    try:
                        device_info = sd.query_devices(device_idx)
                        if device_info['max_input_channels'] == 0:
                            raise ValueError(f"Device {device_idx} does not support input")
                        
                        preferred_sr = device_info.get('default_samplerate', self.sample_rate)
                        sample_rate = int(preferred_sr) if preferred_sr else self.sample_rate
                        
                        print_colored(f"Opening Mic {ch+1} on device {device_idx} ({device_info['name']}) at {sample_rate} Hz...", Colors.CYAN)
                    except Exception as e:
                        print_colored(f"Error validating device {device_idx} for Mic {ch+1}: {e}", Colors.RED)
                        raise
                else:
                    sample_rate = self.sample_rate
                    print_colored(f"Opening Mic {ch+1} on default device at {sample_rate} Hz...", Colors.CYAN)
                
                # Try to open the stream with error handling and fallback sample rates
                stream = None
                sample_rates_to_try = [sample_rate, 44100, 48000, 96000, 192000]
                
                for sr in sample_rates_to_try:
                    try:
                        stream = sd.InputStream(
                            device=device_idx,
                            channels=1,
                            samplerate=sr,
                            blocksize=self.block_size,
                            callback=callback,
                            dtype='float32'
                        )
                        stream.start()
                        self.streams.append(stream)
                        
                        # Extra diagnostics for input 4 (channel index 3)
                        if ch == 3:
                            print_colored(f"✓ Mic {ch+1} (Input 4) stream details:", Colors.CYAN)
                            print_colored(f"  Device: {device_idx} ({device_info['name'] if device_idx is not None else 'default'})", Colors.CYAN)
                            print_colored(f"  Sample Rate: {sr} Hz", Colors.CYAN)
                            print_colored(f"  Block Size: {self.block_size}", Colors.CYAN)
                            print_colored(f"  Stream Active: {stream.active}", Colors.CYAN)
                        
                        if sr != sample_rate:
                            print_colored(f"✓ Successfully started stream for Mic {ch+1} at {sr} Hz (fallback rate)", Colors.GREEN)
                        else:
                            print_colored(f"✓ Successfully started stream for Mic {ch+1}", Colors.GREEN)
                        
                        break
                    except sd.PortAudioError as e:
                        if sr == sample_rates_to_try[-1]:
                            print_colored(f"✗ Failed to open device {device_idx} for Mic {ch+1} at any sample rate", Colors.RED)
                            print_colored(f"  Error: {e}", Colors.RED)
                            print_colored(f"  This device may be in use, not available, or incompatible.", Colors.YELLOW)
                            print_colored(f"  Please try a different device or check device settings.", Colors.YELLOW)
                            raise
                        continue
                    except Exception as e:
                        print_colored(f"✗ Unexpected error opening device {device_idx} for Mic {ch+1}: {e}", Colors.RED)
                        raise
                
                if stream is None:
                    raise RuntimeError(f"Could not open device {device_idx} for Mic {ch+1}")
                
                # Verify stream is actually running
                if not stream.active:
                    print_colored(f"Warning: Stream for Mic {ch+1} is not active after start!", Colors.YELLOW)
            
            print()
            print_colored("All streams started successfully!", Colors.GREEN, bold=True)
            print_colored(f"Total streams opened: {len(self.streams)}", Colors.CYAN)
            
            # Display GPU acceleration status
            if GPU_ACCELERATION_ENABLED:
                # Try to verify OpenGL is actually working
                try:
                    from pyqtgraph.Qt import QtGui, QtWidgets
                    # Check if we can verify OpenGL context (may not be available until window is shown)
                    if hasattr(QtGui, 'QOpenGLContext'):
                        try:
                            ctx = QtGui.QOpenGLContext.currentContext()
                            if ctx is not None:
                                print_colored(f"GPU acceleration: {GPU_ACCELERATION_STATUS_MSG} (OpenGL context active)", Colors.GREEN)
                            else:
                                print_colored(f"GPU acceleration: {GPU_ACCELERATION_STATUS_MSG} (context will activate when window opens)", Colors.GREEN)
                        except:
                            print_colored(f"GPU acceleration: {GPU_ACCELERATION_STATUS_MSG}", Colors.GREEN)
                    else:
                        print_colored(f"GPU acceleration: {GPU_ACCELERATION_STATUS_MSG}", Colors.GREEN)
                except:
                    print_colored(f"GPU acceleration: {GPU_ACCELERATION_STATUS_MSG}", Colors.GREEN)
            else:
                print_colored(f"GPU acceleration: {GPU_ACCELERATION_STATUS_MSG}", Colors.YELLOW)
            
            print_header("")
            
        except Exception as e:
            print()
            print_colored(f"Error starting audio streams: {e}", Colors.RED, bold=True)
            self.stop()
            sys.exit(1)
    
    def stop(self):
        """Stop all audio streams"""
        for stream in self.streams:
            if stream:
                stream.stop()
                stream.close()
        self.streams.clear()
    
    def set_window_icon(self):
        """Set the window icon from available icon files"""
        icon_path = self.icon_path
        
        # If no icon path provided, search for icon files
        if not icon_path:
            # Get the directory where the script/exe is located
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Try multiple possible icon file names and locations
            possible_icon_paths = [
                'icon.ico', 'app.ico', 'wvu_icon.ico', 'logo.ico',
                'icon.png', 'app.png', 'wvu_icon.png',
                os.path.join(base_dir, 'icon.ico'),
                os.path.join(base_dir, 'app.ico'),
                os.path.join(base_dir, 'wvu_icon.ico'),
                os.path.join(base_dir, 'logo.ico'),
                os.path.join(base_dir, 'icon.png'),
                os.path.join(base_dir, 'app.png'),
                os.path.join(base_dir, 'wvu_icon.png'),
            ]
            
            for path in possible_icon_paths:
                if os.path.exists(path):
                    icon_path = path
                    break
        
        # Try to load the icon
        if icon_path and os.path.exists(icon_path):
            try:
                icon = QtGui.QIcon(icon_path)
                self.setWindowIcon(icon)
            except Exception as e:
                print(f"Warning: Could not load window icon: {e}")
    
    def show_settings_dialog(self):
        """Show the settings dialog"""
        # Always pause plot updates while dialog is open to prevent stuttering
        # This works in both normal and time plot modes
        was_running = self.timer.isActive()
        was_paused = self.is_paused
        
        # Force stop the timer (works in both normal and time plot modes)
        if self.timer.isActive():
            self.timer.stop()
        
        try:
            dialog = SettingsDialog(self.display_gain, self.time_plot_mode, self.sample_rate_adjustment, parent=self, icon_path=self.icon_path)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.display_gain = dialog.get_gain()
                new_time_plot_mode = dialog.get_time_plot_mode()
                new_sample_rate_adjustment = dialog.get_sample_rate_adjustment()
                
                # If switching to time plot mode, reset buffers and start time, unlock X-axis
                if new_time_plot_mode and not self.time_plot_mode:
                    self.time_plot_buffers = [deque(maxlen=1000000) for _ in range(self.channels)]
                    self.time_plot_cache = [None] * self.channels
                    self.time_plot_cache_dirty = [True] * self.channels
                    self.time_plot_update_counter = [0] * self.channels
                    self.time_plot_start_time = time.time()
                    self._time_plot_x_ranges = [(0, 1.0)] * self.channels
                    # Restore original setRange for all plots to allow X-axis scaling
                    for i in range(self.channels):
                        if i < len(self.plot_widgets):
                            view_box = self.plot_widgets[i].getViewBox()
                            if hasattr(view_box, '_original_setRange'):
                                view_box.setRange = view_box._original_setRange
                            view_box.setLimits(xMin=None, xMax=None, minXRange=None, maxXRange=None)
                
                # If switching away from time plot mode, clear buffers and restore locked X-axis
                if not new_time_plot_mode and self.time_plot_mode:
                    self.time_plot_buffers = [deque(maxlen=1000000) for _ in range(self.channels)]
                    self.time_plot_cache = [None] * self.channels
                    self.time_plot_cache_dirty = [True] * self.channels
                    self.time_plot_update_counter = [0] * self.channels
                    self.time_plot_start_time = None
                    if hasattr(self, '_time_plot_x_ranges'):
                        del self._time_plot_x_ranges
                    # Restore locked X-axis for all plots
                    for i in range(self.channels):
                        if i < len(self.plot_widgets):
                            view_box = self.plot_widgets[i].getViewBox()
                            # Re-apply the locked setRange override
                            original_setRange = view_box.setRange
                            view_box._original_setRange = original_setRange
                            def locked_setRange(*args, **kwargs):
                                y_range = None
                                if 'yRange' in kwargs:
                                    y_range = kwargs['yRange']
                                elif len(args) >= 2:
                                    y_range = args[1]
                                if y_range is None:
                                    try:
                                        current_range = view_box.viewRange()
                                        if current_range and len(current_range) > 1:
                                            y_range = current_range[1]
                                        else:
                                            y_range = (-1, 1)
                                    except:
                                        y_range = (-1, 1)
                                original_setRange(xRange=(0, 512), yRange=y_range, padding=0, update=True)
                            view_box.setRange = locked_setRange
                            view_box.setLimits(xMin=0, xMax=512, minXRange=512, maxXRange=512)
                
                self.time_plot_mode = new_time_plot_mode
                self.sample_rate_adjustment = new_sample_rate_adjustment
        finally:
            # Resume plot updates when dialog closes (only if not paused and was running before)
            # Restore the previous state (paused or running)
            # This works in both normal and time plot modes
            if was_running and not was_paused:
                if not self.timer.isActive():  # Double-check timer is not already running
                    self.timer.start(16)  # ~60 FPS
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode for the main window or return to all graphs"""
        # If in single graph mode, return to all graphs first
        if self.single_graph_mode:
            self.show_all_graphs()
            return
        
        # Otherwise toggle fullscreen
        if self.is_fullscreen:
            self.showNormal()
            self.is_fullscreen = False
            self.fullscreen_btn.setText('⛶ Fullscreen')
        else:
            self.showFullScreen()
            self.is_fullscreen = True
            self.fullscreen_btn.setText('⛶ Exit Fullscreen')
    
    def show_single_graph_fullscreen(self, graph_index):
        """Show a single graph in fullscreen mode (toggle if already showing that graph)"""
        if graph_index < 0 or graph_index >= len(self.plot_widgets):
            return
        
        # If already showing this graph, return to all graphs
        if self.single_graph_mode and self.fullscreen_graph_index == graph_index:
            self.show_all_graphs()
            return
        
        self.single_graph_mode = True
        self.fullscreen_graph_index = graph_index
        
        # Hide all other graphs
        for i, container in enumerate(self.plot_containers):
            if i == graph_index:
                container.show()
            else:
                container.hide()
        
        # Update button text
        self.fullscreen_btn.setText('⛶ Show All Graphs')
        
        # Show a hint label
        if not hasattr(self, 'fullscreen_hint_label'):
            self.fullscreen_hint_label = QtWidgets.QLabel('Double-click graph to return to all graphs | Press ESC to exit')
            self.fullscreen_hint_label.setStyleSheet(f"""
                color: {self.wvu_old_gold.name()}; 
                font-size: 12px; 
                font-weight: bold;
                background-color: rgba(0, 40, 85, 0.8);
                padding: 8px;
                border-radius: 5px;
            """)
            self.fullscreen_hint_label.setAlignment(QtCore.Qt.AlignCenter)
            self.main_layout.addWidget(self.fullscreen_hint_label)
        self.fullscreen_hint_label.show()
    
    def show_all_graphs(self):
        """Return to showing all 4 graphs"""
        self.single_graph_mode = False
        self.fullscreen_graph_index = None
        
        # Show all graphs
        for container in self.plot_containers:
            container.show()
        
        # Update button text
        if self.is_fullscreen:
            self.fullscreen_btn.setText('⛶ Exit Fullscreen')
        else:
            self.fullscreen_btn.setText('⛶ Fullscreen')
        
        # Hide hint label
        if hasattr(self, 'fullscreen_hint_label'):
            self.fullscreen_hint_label.hide()
    
    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == QtCore.Qt.Key_Space:
            self.toggle_pause()
            event.accept()
        elif event.key() == QtCore.Qt.Key_Escape:
            if self.single_graph_mode:
                self.show_all_graphs()
            elif self.is_fullscreen:
                self.toggle_fullscreen()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def toggle_pause(self):
        """Toggle pause/play state of the graphs"""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            # Pause: stop the update timer
            self.timer.stop()
            self.pause_label.show()
        else:
            # Resume: start the update timer
            self.timer.start(16)  # ~60 FPS
            self.pause_label.hide()
    
    def showEvent(self, event):
        """Handle window show event - ensure focus for keyboard events"""
        super().showEvent(event)
        # Set focus when window is shown to receive keyboard events
        self.setFocus()
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.stop()
        event.accept()

def list_audio_devices():
    """List all available audio input devices"""
    devices = sd.query_devices()
    input_devices = []
    
    print()
    print_header("Available Audio Input Devices")
    print()
    
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            input_devices.append(i)
            channels = device['max_input_channels']
            default = f"{Colors.GREEN} (DEFAULT){Colors.RESET}" if i == sd.default.device[0] else ""
            print_colored(f"  [{i}] {device['name']}", Colors.GOLD)
            print(f"      Channels: {channels}, Sample Rate: {device['default_samplerate']} Hz{default}")
            print()
    
    return input_devices

def validate_device(device_idx, test_open=False):
    """Validate that a device can be opened"""
    try:
        device_info = sd.query_devices(device_idx)
        if device_info['max_input_channels'] == 0:
            return False, "Device does not support input"
        
        if test_open:
            try:
                test_stream = sd.InputStream(
                    device=device_idx,
                    channels=1,
                    samplerate=int(device_info.get('default_samplerate', 44100)),
                    blocksize=256,
                    dtype='float32'
                )
                test_stream.close()
                return True, "OK (tested)"
            except sd.PortAudioError as e:
                return False, f"Cannot open device: {str(e)}"
            except Exception as e:
                return False, f"Device test failed: {str(e)}"
        else:
            _ = device_info.get('default_samplerate', None)
            return True, "OK (info only)"
    except Exception as e:
        return False, f"Device query failed: {str(e)}"

def get_config_file_path():
    """Get path to config file for saving device selections"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Use temp directory for config file
    temp_dir = tempfile.gettempdir()
    config_file = os.path.join(temp_dir, 'wvu_4mic_visualizer_config.json')
    return config_file

def load_device_config():
    """Load saved device configuration"""
    config_file = get_config_file_path()
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                devices = config.get('devices', None)
                num_channels = config.get('num_channels', None)
                return devices, num_channels
        except Exception:
            return None, None
    return None, None

def save_device_config(devices, num_channels=None):
    """Save device configuration to temp file"""
    config_file = get_config_file_path()
    try:
        config = {'devices': devices}
        if num_channels is not None:
            config['num_channels'] = num_channels
        with open(config_file, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        print(f"Warning: Could not save device config: {e}")

class SettingsDialog(QtWidgets.QDialog):
    """Settings dialog for adjusting display gain"""
    def __init__(self, current_gain=1.0, time_plot_mode=False, sample_rate_adjustment=1.0, parent=None, icon_path=None):
        super().__init__(parent)
        self.current_gain = current_gain
        self.time_plot_mode = time_plot_mode
        self.sample_rate_adjustment = sample_rate_adjustment
        self.setWindowTitle('Display Settings - WVU 4-Mic Visualizer')
        self.setMinimumSize(500, 450)
        self.resize(550, 500)
        
        # Set window icon
        self.set_window_icon(icon_path)
        
        # WVU Colors
        self.wvu_gold = '#EAAA00'
        self.wvu_blue = '#002855'
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.wvu_blue};
                font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
                border: 2px solid {self.wvu_gold};
                border-radius: 12px;
            }}
            QLabel {{
                color: {self.wvu_gold};
                font-size: 12px;
                background-color: transparent;
            }}
            QPushButton {{
                background-color: {self.wvu_gold};
                color: {self.wvu_blue};
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                min-width: 90px;
            }}
            QPushButton:hover {{
                background-color: #FFD700;
            }}
            QPushButton:pressed {{
                background-color: #D4AF37;
            }}
            QDoubleSpinBox {{
                background-color: white;
                color: {self.wvu_blue};
                padding: 6px 8px;
                border: 2px solid {self.wvu_gold};
                border-radius: 6px;
                font-size: 11px;
            }}
            QDoubleSpinBox:focus {{
                border: 2px solid #FFD700;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {self.wvu_gold};
                height: 8px;
                background: {self.wvu_blue};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {self.wvu_gold};
                border: 2px solid {self.wvu_blue};
                width: 20px;
                margin: -4px 0;
                border-radius: 10px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #FFD700;
                border: 2px solid {self.wvu_blue};
            }}
            QGroupBox {{
                color: {self.wvu_gold};
                font-weight: bold;
                border: 2px solid {self.wvu_gold};
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                padding-bottom: 10px;
                background-color: rgba(234, 170, 0, 0.05);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                background-color: {self.wvu_blue};
            }}
            QCheckBox {{
                color: {self.wvu_gold};
                font-size: 12px;
                font-weight: bold;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {self.wvu_gold};
                border-radius: 4px;
                background-color: {self.wvu_blue};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.wvu_gold};
                border: 2px solid {self.wvu_gold};
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid #FFD700;
            }}
        """)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        self.setLayout(layout)
        
        # Title
        title = QtWidgets.QLabel('Display Settings')
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {self.wvu_gold}; padding: 5px;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        
        # Gain control group
        gain_group = QtWidgets.QGroupBox('Display Gain')
        gain_layout = QtWidgets.QVBoxLayout()
        gain_layout.setSpacing(12)
        gain_layout.setContentsMargins(15, 20, 15, 15)
        
        # Gain slider
        slider_layout = QtWidgets.QHBoxLayout()
        slider_layout.setSpacing(10)
        slider_label = QtWidgets.QLabel('Gain:')
        slider_label.setStyleSheet(f"font-weight: bold; min-width: 50px;")
        slider_layout.addWidget(slider_label)
        
        self.gain_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.gain_slider.setMinimum(0)  # 0.0x
        self.gain_slider.setMaximum(200)  # 2.0x (0.01 increments)
        self.gain_slider.setValue(int(self.current_gain * 100))
        self.gain_slider.valueChanged.connect(self.on_slider_changed)
        slider_layout.addWidget(self.gain_slider)
        
        self.gain_spinbox = QtWidgets.QDoubleSpinBox()
        self.gain_spinbox.setMinimum(0.0)
        self.gain_spinbox.setMaximum(2.0)
        self.gain_spinbox.setSingleStep(0.01)
        self.gain_spinbox.setDecimals(2)
        self.gain_spinbox.setValue(self.current_gain)
        self.gain_spinbox.setSuffix('x')
        self.gain_spinbox.valueChanged.connect(self.on_spinbox_changed)
        self.gain_spinbox.setMaximumWidth(80)
        slider_layout.addWidget(self.gain_spinbox)
        
        gain_layout.addLayout(slider_layout)
        
        # Gain description
        description = QtWidgets.QLabel('Adjust the gain multiplier for the displayed signal.\nRange: 0.0x (mute) to 2.0x (double amplitude)')
        description.setWordWrap(True)
        description.setAlignment(QtCore.Qt.AlignCenter)
        gain_layout.addWidget(description)
        
        gain_group.setLayout(gain_layout)
        layout.addWidget(gain_group)
        
        # Time plot mode group
        time_plot_group = QtWidgets.QGroupBox('Time Plot Mode')
        time_plot_layout = QtWidgets.QVBoxLayout()
        time_plot_layout.setSpacing(12)
        time_plot_layout.setContentsMargins(15, 20, 15, 15)
        
        # Time plot mode checkbox
        self.time_plot_checkbox = QtWidgets.QCheckBox('Enable Time Plot Mode (Autoscaling, Growing Plot)')
        self.time_plot_checkbox.setChecked(self.time_plot_mode)
        self.time_plot_checkbox.stateChanged.connect(self.on_time_plot_changed)
        time_plot_layout.addWidget(self.time_plot_checkbox)
        
        # Sample rate adjustment (hidden initially, shown when checkbox is checked)
        self.sample_rate_container = QtWidgets.QWidget()
        sample_rate_layout = QtWidgets.QVBoxLayout()
        sample_rate_layout.setContentsMargins(0, 10, 0, 0)
        self.sample_rate_container.setLayout(sample_rate_layout)
        
        slider_layout = QtWidgets.QHBoxLayout()
        slider_layout.setSpacing(10)
        sr_label = QtWidgets.QLabel('Sample Rate Adjustment:')
        sr_label.setStyleSheet(f"font-weight: bold; min-width: 150px;")
        slider_layout.addWidget(sr_label)
        
        self.sample_rate_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sample_rate_slider.setMinimum(10)  # 0.1x
        self.sample_rate_slider.setMaximum(200)  # 2.0x (0.01 increments)
        self.sample_rate_slider.setValue(int(self.sample_rate_adjustment * 100))
        self.sample_rate_slider.valueChanged.connect(self.on_sample_rate_slider_changed)
        slider_layout.addWidget(self.sample_rate_slider)
        
        self.sample_rate_spinbox = QtWidgets.QDoubleSpinBox()
        self.sample_rate_spinbox.setMinimum(0.1)
        self.sample_rate_spinbox.setMaximum(2.0)
        self.sample_rate_spinbox.setSingleStep(0.01)
        self.sample_rate_spinbox.setDecimals(2)
        self.sample_rate_spinbox.setValue(self.sample_rate_adjustment)
        self.sample_rate_spinbox.setSuffix('x')
        self.sample_rate_spinbox.valueChanged.connect(self.on_sample_rate_spinbox_changed)
        self.sample_rate_spinbox.setMaximumWidth(80)
        slider_layout.addWidget(self.sample_rate_spinbox)
        
        sample_rate_layout.addLayout(slider_layout)
        
        # Description
        sr_description = QtWidgets.QLabel('Adjust the time scale for the plot. Lower values = slower time, higher values = faster time.')
        sr_description.setWordWrap(True)
        sr_description.setAlignment(QtCore.Qt.AlignCenter)
        sample_rate_layout.addWidget(sr_description)
        
        time_plot_layout.addWidget(self.sample_rate_container)
        
        # Show/hide sample rate controls based on checkbox
        self.sample_rate_container.setVisible(self.time_plot_mode)
        
        time_plot_group.setLayout(time_plot_layout)
        layout.addWidget(time_plot_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        self.cancel_btn = QtWidgets.QPushButton('Cancel')
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.ok_btn = QtWidgets.QPushButton('Apply')
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
    
    def on_slider_changed(self, value):
        """Handle slider value change"""
        gain_value = value / 100.0
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(gain_value)
        self.gain_spinbox.blockSignals(False)
        self.current_gain = gain_value
    
    def on_spinbox_changed(self, value):
        """Handle spinbox value change"""
        slider_value = int(value * 100)
        self.gain_slider.blockSignals(True)
        self.gain_slider.setValue(slider_value)
        self.gain_slider.blockSignals(False)
        self.current_gain = value
    
    def on_time_plot_changed(self, state):
        """Handle time plot mode checkbox change"""
        self.time_plot_mode = (state == QtCore.Qt.Checked)
        self.sample_rate_container.setVisible(self.time_plot_mode)
    
    def on_sample_rate_slider_changed(self, value):
        """Handle sample rate slider value change"""
        sr_value = value / 100.0
        self.sample_rate_spinbox.blockSignals(True)
        self.sample_rate_spinbox.setValue(sr_value)
        self.sample_rate_spinbox.blockSignals(False)
        self.sample_rate_adjustment = sr_value
    
    def on_sample_rate_spinbox_changed(self, value):
        """Handle sample rate spinbox value change"""
        slider_value = int(value * 100)
        self.sample_rate_slider.blockSignals(True)
        self.sample_rate_slider.setValue(slider_value)
        self.sample_rate_slider.blockSignals(False)
        self.sample_rate_adjustment = value
    
    def set_window_icon(self, icon_path):
        """Set the window icon from available icon files"""
        if not icon_path:
            # Get the directory where the script/exe is located
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Try multiple possible icon file names and locations
            possible_icon_paths = [
                'icon.ico', 'app.ico', 'wvu_icon.ico', 'logo.ico',
                'icon.png', 'app.png', 'wvu_icon.png',
                os.path.join(base_dir, 'icon.ico'),
                os.path.join(base_dir, 'app.ico'),
                os.path.join(base_dir, 'wvu_icon.ico'),
                os.path.join(base_dir, 'logo.ico'),
                os.path.join(base_dir, 'icon.png'),
                os.path.join(base_dir, 'app.png'),
                os.path.join(base_dir, 'wvu_icon.png'),
            ]
            
            for path in possible_icon_paths:
                if os.path.exists(path):
                    icon_path = path
                    break
        
        # Try to load the icon
        if icon_path and os.path.exists(icon_path):
            try:
                icon = QtGui.QIcon(icon_path)
                self.setWindowIcon(icon)
            except Exception as e:
                print(f"Warning: Could not load window icon: {e}")
    
    def get_gain(self):
        """Get the current gain value"""
        return self.current_gain
    
    def get_time_plot_mode(self):
        """Get the time plot mode setting"""
        return self.time_plot_mode
    
    def get_sample_rate_adjustment(self):
        """Get the sample rate adjustment value"""
        return self.sample_rate_adjustment

class DeviceSelectionDialog(QtWidgets.QDialog):
    """GUI dialog for selecting audio input devices"""
    def __init__(self, num_channels=4, parent=None, icon_path=None):
        super().__init__(parent)
        self.num_channels = num_channels
        self.selected_devices = [None] * num_channels
        self.setWindowTitle('WVU Audio Visualizer - Device Selection')
        self.setMinimumSize(850, 750)
        self.resize(900, 800)
        
        # Set window icon
        self.set_window_icon(icon_path)
        
        # WVU Colors
        self.wvu_gold = '#EAAA00'
        self.wvu_blue = '#002855'
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.wvu_blue};
                font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
                border: 2px solid {self.wvu_gold};
                border-radius: 12px;
            }}
            QLabel {{
                color: {self.wvu_gold};
                font-size: 12px;
                background-color: transparent;
            }}
            QPushButton {{
                background-color: {self.wvu_gold};
                color: {self.wvu_blue};
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                min-width: 90px;
            }}
            QPushButton:hover {{
                background-color: #FFD700;
            }}
            QPushButton:pressed {{
                background-color: #D4AF37;
            }}
            QComboBox {{
                background-color: white;
                color: {self.wvu_blue};
                padding: 8px 10px;
                border: 2px solid {self.wvu_gold};
                border-radius: 6px;
                font-size: 11px;
            }}
            QComboBox:hover {{
                border: 2px solid #FFD700;
            }}
            QComboBox:focus {{
                border: 2px solid #FFD700;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 25px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {self.wvu_blue};
                margin-right: 5px;
            }}
            QGroupBox {{
                color: {self.wvu_gold};
                font-weight: bold;
                border: 2px solid {self.wvu_gold};
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                padding-bottom: 10px;
                background-color: rgba(234, 170, 0, 0.05);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                background-color: {self.wvu_blue};
            }}
            QSpinBox {{
                background-color: white;
                color: {self.wvu_blue};
                padding: 6px 8px;
                border: 2px solid {self.wvu_gold};
                border-radius: 6px;
                font-size: 11px;
            }}
            QSpinBox:focus {{
                border: 2px solid #FFD700;
            }}
        """)
        
        self.setup_ui()
        # Load saved config after UI is set up
        saved_devices, saved_num_channels = load_device_config()
        if saved_num_channels is not None and 1 <= saved_num_channels <= 8:
            self.num_channels = saved_num_channels
            self.channels_spinbox.setValue(saved_num_channels)
            self.update_device_selections()
        self.load_saved_config()
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        self.setLayout(layout)
        
        # Title
        title = QtWidgets.QLabel('Select Audio Input Devices')
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {self.wvu_gold}; padding: 5px;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        
        # Number of channels selector
        channels_group = QtWidgets.QGroupBox('Number of Microphones')
        channels_layout = QtWidgets.QHBoxLayout()
        channels_layout.setContentsMargins(15, 20, 15, 15)
        channels_layout.setSpacing(10)
        
        channels_label = QtWidgets.QLabel('Select number of microphone inputs:')
        channels_layout.addWidget(channels_label)
        
        self.channels_spinbox = QtWidgets.QSpinBox()
        self.channels_spinbox.setMinimum(1)
        self.channels_spinbox.setMaximum(8)
        self.channels_spinbox.setValue(self.num_channels)
        self.channels_spinbox.setSuffix(' microphone(s)')
        self.channels_spinbox.valueChanged.connect(self.on_channels_changed)
        channels_layout.addWidget(self.channels_spinbox)
        channels_layout.addStretch()
        
        channels_group.setLayout(channels_layout)
        layout.addWidget(channels_group)
        
        # Instructions (will be updated dynamically)
        self.instructions = QtWidgets.QLabel(f'Select one input device for each of the {self.num_channels} microphone(s):')
        self.instructions.setStyleSheet(f"padding: 5px;")
        self.instructions.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.instructions)
        
        # Get available devices
        all_devices = sd.query_devices()
        self.input_devices = []
        self.device_names = []
        
        for i, device in enumerate(all_devices):
            if device['max_input_channels'] > 0:
                self.input_devices.append(i)
                default_text = " (DEFAULT)" if i == sd.default.device[0] else ""
                self.device_names.append(f"[{i}] {device['name']}{default_text}")
        
        # Container for device selection groups (so we can dynamically add/remove)
        self.device_groups_container = QtWidgets.QWidget()
        self.device_groups_layout = QtWidgets.QVBoxLayout()
        self.device_groups_layout.setContentsMargins(0, 0, 0, 0)
        self.device_groups_layout.setSpacing(0)
        self.device_groups_container.setLayout(self.device_groups_layout)
        layout.addWidget(self.device_groups_container)
        
        # Store device groups and combo boxes
        self.device_groups = []
        self.combo_boxes = []
        
        # Create initial device selection widgets
        self.update_device_selections()
        
        layout.addStretch()
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.clear_memory_btn = QtWidgets.QPushButton('Clear Memory')
        self.clear_memory_btn.clicked.connect(self.clear_saved_config)
        button_layout.addWidget(self.clear_memory_btn)
        
        button_layout.addStretch()
        
        self.cancel_btn = QtWidgets.QPushButton('Cancel')
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.ok_btn = QtWidgets.QPushButton('Start Visualizer')
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
    
    def on_channels_changed(self, new_count):
        """Handle number of channels change"""
        old_count = self.num_channels
        self.num_channels = new_count
        
        # Update selected_devices list
        if new_count > old_count:
            # Add None for new channels
            self.selected_devices.extend([None] * (new_count - old_count))
        elif new_count < old_count:
            # Remove excess devices
            self.selected_devices = self.selected_devices[:new_count]
        
        # Update instructions
        self.instructions.setText(f'Select one input device for each of the {self.num_channels} microphone(s):')
        
        # Update device selection widgets
        self.update_device_selections()
    
    def update_device_selections(self):
        """Update the device selection widgets based on current num_channels"""
        current_count = len(self.combo_boxes)
        target_count = self.num_channels
        
        if target_count > current_count:
            # Add new device selection groups
            for i in range(current_count, target_count):
                self.add_device_selection(i)
        elif target_count < current_count:
            # Remove excess device selection groups
            for i in range(current_count - 1, target_count - 1, -1):
                self.remove_device_selection(i)
    
    def add_device_selection(self, index):
        """Add a device selection group"""
        group = QtWidgets.QGroupBox(f'Microphone {index + 1}')
        group_layout = QtWidgets.QVBoxLayout()
        group_layout.setContentsMargins(15, 20, 15, 15)
        group_layout.setSpacing(8)
        
        combo = QtWidgets.QComboBox()
        combo.addItem("Default Device", None)
        for idx, name in zip(self.input_devices, self.device_names):
            combo.addItem(name, idx)
        combo.setCurrentIndex(0)
        
        combo.currentIndexChanged.connect(lambda idx, mic=index: self.on_device_changed(mic, idx))
        self.combo_boxes.append(combo)
        self.device_groups.append(group)
        
        group_layout.addWidget(combo)
        group.setLayout(group_layout)
        self.device_groups_layout.addWidget(group)
        
        # Initialize device selection
        if index < len(self.selected_devices):
            device_idx = self.selected_devices[index]
            if device_idx is not None:
                for j in range(combo.count()):
                    if combo.itemData(j) == device_idx:
                        combo.setCurrentIndex(j)
                        break
    
    def remove_device_selection(self, index):
        """Remove a device selection group"""
        if index < len(self.device_groups):
            group = self.device_groups[index]
            self.device_groups_layout.removeWidget(group)
            group.setParent(None)
            group.deleteLater()
            self.device_groups.pop(index)
            self.combo_boxes.pop(index)
    
    def on_device_changed(self, mic_index, combo_index):
        """Handle device selection change"""
        if mic_index < len(self.combo_boxes):
            combo = self.combo_boxes[mic_index]
            device_idx = combo.itemData(combo_index)
            if mic_index < len(self.selected_devices):
                self.selected_devices[mic_index] = device_idx
            else:
                # Extend list if needed
                while len(self.selected_devices) <= mic_index:
                    self.selected_devices.append(None)
                self.selected_devices[mic_index] = device_idx
    
    def clear_saved_config(self):
        """Clear saved device configuration"""
        config_file = get_config_file_path()
        try:
            if os.path.exists(config_file):
                os.remove(config_file)
                # Reset all combo boxes to default
                for combo in self.combo_boxes:
                    combo.setCurrentIndex(0)
                # Reset selected devices
                self.selected_devices = [None] * self.num_channels
                # Show confirmation message
                msg = QtWidgets.QMessageBox(self)
                msg.setWindowTitle('Memory Cleared')
                msg.setText('Saved device configuration has been cleared.')
                msg.setIcon(QtWidgets.QMessageBox.Information)
                msg.setStyleSheet(f"""
                    QMessageBox {{
                        background-color: {self.wvu_blue};
                        color: {self.wvu_gold};
                    }}
                    QPushButton {{
                        background-color: {self.wvu_gold};
                        color: {self.wvu_blue};
                        font-weight: bold;
                        padding: 8px;
                        border-radius: 4px;
                    }}
                """)
                msg.exec_()
            else:
                # No config file to clear
                msg = QtWidgets.QMessageBox(self)
                msg.setWindowTitle('No Saved Configuration')
                msg.setText('No saved device configuration found.')
                msg.setIcon(QtWidgets.QMessageBox.Information)
                msg.setStyleSheet(f"""
                    QMessageBox {{
                        background-color: {self.wvu_blue};
                        color: {self.wvu_gold};
                    }}
                    QPushButton {{
                        background-color: {self.wvu_gold};
                        color: {self.wvu_blue};
                        font-weight: bold;
                        padding: 8px;
                        border-radius: 4px;
                    }}
                """)
                msg.exec_()
        except Exception as e:
            # Show error message
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle('Error')
            msg.setText(f'Error clearing configuration: {str(e)}')
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStyleSheet(f"""
                QMessageBox {{
                    background-color: {self.wvu_blue};
                    color: {self.wvu_gold};
                }}
                QPushButton {{
                    background-color: {self.wvu_gold};
                    color: {self.wvu_blue};
                    font-weight: bold;
                    padding: 8px;
                    border-radius: 4px;
                }}
            """)
            msg.exec_()
    
    def load_saved_config(self):
        """Load saved device configuration"""
        saved_devices, saved_num_channels = load_device_config()
        
        # Load number of channels if available
        if saved_num_channels is not None and 1 <= saved_num_channels <= 8:
            self.num_channels = saved_num_channels
            self.channels_spinbox.setValue(saved_num_channels)
            self.selected_devices = [None] * self.num_channels
        
        # Load device selections
        if saved_devices:
            all_devices = sd.query_devices()
            # Update device selections to match saved config
            for i, device_idx in enumerate(saved_devices):
                if i < self.num_channels:
                    if i < len(self.selected_devices):
                        self.selected_devices[i] = device_idx
                    else:
                        self.selected_devices.append(device_idx)
                    
                    # Update combo box if it exists
                    if i < len(self.combo_boxes):
                        if device_idx is None:
                            self.combo_boxes[i].setCurrentIndex(0)  # Default
                        else:
                            # Find the combo box item with this device index
                            for j in range(self.combo_boxes[i].count()):
                                if self.combo_boxes[i].itemData(j) == device_idx:
                                    self.combo_boxes[i].setCurrentIndex(j)
                                    break
    
    def set_window_icon(self, icon_path):
        """Set the window icon from available icon files"""
        if not icon_path:
            # Get the directory where the script/exe is located
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Try multiple possible icon file names and locations
            possible_icon_paths = [
                'icon.ico', 'app.ico', 'wvu_icon.ico', 'logo.ico',
                'icon.png', 'app.png', 'wvu_icon.png',
                os.path.join(base_dir, 'icon.ico'),
                os.path.join(base_dir, 'app.ico'),
                os.path.join(base_dir, 'wvu_icon.ico'),
                os.path.join(base_dir, 'logo.ico'),
                os.path.join(base_dir, 'icon.png'),
                os.path.join(base_dir, 'app.png'),
                os.path.join(base_dir, 'wvu_icon.png'),
            ]
            
            for path in possible_icon_paths:
                if os.path.exists(path):
                    icon_path = path
                    break
        
        # Try to load the icon
        if icon_path and os.path.exists(icon_path):
            try:
                icon = QtGui.QIcon(icon_path)
                self.setWindowIcon(icon)
            except Exception as e:
                print(f"Warning: Could not load window icon: {e}")
    
    def get_selected_devices(self):
        """Get the selected devices"""
        # Make sure we read current values from all combo boxes
        # (in case user didn't change some selections)
        for i in range(self.num_channels):
            if i < len(self.combo_boxes):
                combo = self.combo_boxes[i]
                current_idx = combo.currentIndex()
                device_idx = combo.itemData(current_idx)
                if i < len(self.selected_devices):
                    self.selected_devices[i] = device_idx
                else:
                    self.selected_devices.append(device_idx)
        # Ensure we return exactly num_channels devices
        return self.selected_devices[:self.num_channels]
    
    def get_num_channels(self):
        """Get the selected number of channels"""
        return self.num_channels

def select_input_devices_gui(num_channels=4, icon_path=None):
    """GUI-based device selection"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    
    dialog = DeviceSelectionDialog(num_channels=num_channels, icon_path=icon_path)
    
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        num_channels = dialog.get_num_channels()
        devices = dialog.get_selected_devices()
        # Ensure we have exactly num_channels devices
        if len(devices) < num_channels:
            print_colored(f"Warning: Only {len(devices)} devices selected, expected {num_channels}", Colors.YELLOW)
            # Pad with None if needed
            while len(devices) < num_channels:
                devices.append(None)
        # Save configuration (including num_channels)
        save_device_config(devices, num_channels)
        print_colored(f"Selected {num_channels} microphone(s) with devices: {devices}", Colors.CYAN)
        return num_channels, devices
    else:
        sys.exit(0)

def select_input_devices(num_channels=4):
    """Interactive device selection for multiple channels"""
    input_devices = list_audio_devices()
    all_devices = sd.query_devices()
    
    if not input_devices:
        print_colored("No input devices found!", Colors.RED, bold=True)
        sys.exit(1)
    
    print_header(f"Select {num_channels} Input Devices (one for each microphone)")
    print_colored(f"  Enter device number (0-{len(all_devices)-1}) for each mic, or 'd' for default", Colors.WHITE)
    print_colored("  Enter 'q' to quit", Colors.WHITE)
    print_colored("  Note: Devices will be validated before use", Colors.CYAN)
    print()
    
    selected_devices = []
    
    for mic_num in range(1, num_channels + 1):
        while True:
            prompt = f"{Colors.GOLD}Select device for Mic {mic_num}{Colors.RESET} (or 'd' for default, 'q' to quit): "
            choice = input(prompt).strip().lower()
            
            if choice == 'q':
                print_colored("Exiting...", Colors.YELLOW)
                sys.exit(0)
            elif choice == 'd':
                selected_devices.append(None)
                print_colored(f"Mic {mic_num}: Using default device", Colors.GREEN)
                break
            elif choice.isdigit():
                device_idx = int(choice)
                all_devices = sd.query_devices()
                if 0 <= device_idx < len(all_devices):
                    device = all_devices[device_idx]
                    if device['max_input_channels'] > 0:
                        is_valid, msg = validate_device(device_idx, test_open=False)
                        if is_valid:
                            selected_devices.append(device_idx)
                            print_colored(f"Mic {mic_num}: Selected device [{device_idx}] {device['name']} ✓", Colors.GREEN)
                            break
                        else:
                            print_colored(f"Device [{device_idx}] validation failed: {msg}", Colors.RED)
                            print_colored("Please select a different device.", Colors.YELLOW)
                    else:
                        print_colored(f"Device [{device_idx}] does not support input channels. Please select a different device.", Colors.RED)
                else:
                    all_devices = sd.query_devices()
                    print_colored(f"Invalid device number. Please enter a number from 0 to {len(all_devices)-1}", Colors.RED)
            else:
                print_colored("Invalid input. Please enter a device number, 'd' for default, or 'q' to quit", Colors.RED)
    
    return selected_devices

def main():
    """Main function"""
    # Create Qt application
    app = QtWidgets.QApplication(sys.argv)
    
    # Check for logo file - supports multiple locations and names
    logo_path = None
    
    # Get the directory where the script/exe is located
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try multiple possible logo file names and locations
    possible_logo_paths = [
        'logo.png', 'wvu_logo.png',
        os.path.join(base_dir, 'logo.png'),
        os.path.join(base_dir, 'wvu_logo.png'),
        os.path.join(base_dir, 'logo.jpg'),
        os.path.join(base_dir, 'ecocar_logo.png'),
    ]
    
    for path in possible_logo_paths:
        if os.path.exists(path):
            logo_path = path
            break
    
    # Try to find icon file (similar search pattern)
    icon_path = None
    possible_icon_paths = [
        'icon.ico', 'app.ico', 'wvu_icon.ico', 'logo.ico',
        'icon.png', 'app.png', 'wvu_icon.png',
        os.path.join(base_dir, 'icon.ico'),
        os.path.join(base_dir, 'app.ico'),
        os.path.join(base_dir, 'wvu_icon.ico'),
        os.path.join(base_dir, 'logo.ico'),
        os.path.join(base_dir, 'icon.png'),
        os.path.join(base_dir, 'app.png'),
        os.path.join(base_dir, 'wvu_icon.png'),
    ]
    
    for path in possible_icon_paths:
        if os.path.exists(path):
            icon_path = path
            break
    
    # Select input devices using GUI (pass icon_path so dialog uses same icon)
    num_channels, devices = select_input_devices_gui(num_channels=4, icon_path=icon_path)
    
    # Create and start visualizer
    visualizer = AudioVisualizer(channels=num_channels, devices=devices, logo_path=logo_path, icon_path=icon_path)
    visualizer.start()
    visualizer.show()
    visualizer.setFocus()  # Ensure window receives keyboard focus for spacebar
    
    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        pass
    finally:
        visualizer.stop()

if __name__ == "__main__":
    main()
