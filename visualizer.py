"""
AudioVisualizer class for real-time audio visualization.
"""
import numpy as np
import sounddevice as sd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import time
from collections import deque
import sys
import os

from config import GPU_ACCELERATION_ENABLED
from utils import SVG_SUPPORT, QSvgRenderer
from dialogs import SettingsDialog

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
        # Rolling window buffer - keeps last 0.3 seconds of data (auto-clears after 0.3s)
        # At 48kHz: 0.3s * 48000 = 14400 samples
        self.time_plot_window_seconds = 0.3  # 0.3 second window
        self.time_plot_max_samples = 14400  # ~0.3 seconds at 48kHz (will adjust based on actual sample rate)
        self.time_plot_buffers = [deque(maxlen=self.time_plot_max_samples) for _ in range(channels)]
        self.time_plot_start_time = None  # Start time for time plot mode
        self.time_plot_cache = [None] * channels  # Cache for numpy arrays to avoid repeated conversions
        self.time_plot_cache_dirty = [True] * channels  # Track if cache needs updating
        self.time_plot_update_counter = [0] * channels  # Counter to update cache periodically
        # Pre-allocated numpy arrays for time plot data to avoid repeated allocations
        self.time_plot_x_array = [None] * channels
        self.time_plot_y_array = [None] * channels
        # Auto-clear counter - clear old data after 0.3 seconds
        self.time_plot_last_clear_time = None
        
        # FPS tracking
        self.fps_enabled = False  # FPS indicator setting
        self.fps_counter = 0
        self.fps_last_time = time.time()
        self.current_fps = 0.0
        self.fps_label = None  # Will be created in setup_ui
        
        # Fullscreen state
        self.is_fullscreen = False
        self.single_graph_mode = False
        self.fullscreen_graph_index = None
        
        # Pause state
        self.is_paused = False
        
        # FPS lock setting (in milliseconds, default 8ms = ~120 FPS)
        self.fps_lock_ms = 8  # Default to ~120 FPS
        
        # Track open settings dialogs for pause management
        self.open_settings_dialogs = []
        
        # Setup UI
        self.setup_ui(logo_path)
        
        # Setup update timer - Maximum FPS for smooth rendering
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(self.fps_lock_ms)  # Use FPS lock setting
        self.frame_skip_counter = 0  # For tracking
        
    def setup_ui(self, logo_path):
        """Setup the user interface"""
        # Access QtWidgets through the module to avoid UnboundLocalError
        # Import the Qt module and access QtWidgets as an attribute
        import pyqtgraph.Qt as _Qt
        _QtWidgets = _Qt.QtWidgets
        
        # Set window properties
        self.setWindowTitle('WVU 4-Mic Audio Visualizer - Real-time Level Monitoring')
        self.setStyleSheet(f"background-color: {self.wvu_blue.name()};")
        
        # Enable keyboard focus to receive spacebar events
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
        settings_action = _QtWidgets.QAction('Display Settings...', self)
        settings_action.setShortcut('Ctrl+S')
        settings_action.triggered.connect(self.show_settings_dialog)
        settings_menu.addAction(settings_action)
        
        # Add hover detection to pause when hovering over Settings menu
        settings_menu.aboutToShow.connect(self.on_settings_menu_hover)
        settings_menu.aboutToHide.connect(self.on_settings_menu_leave)
        
        # Central widget
        central_widget = _QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = _QtWidgets.QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title bar with logo
        title_layout = _QtWidgets.QHBoxLayout()
        
        # Logo - support both PNG and SVG
        if logo_path and os.path.exists(logo_path):
            try:
                logo_label = _QtWidgets.QLabel()
                if logo_path.lower().endswith('.svg') and SVG_SUPPORT:
                    # Load SVG using QSvgRenderer and preserve aspect ratio
                    renderer = QSvgRenderer(logo_path)
                    # Get the SVG's natural size
                    svg_size = renderer.defaultSize()
                    if svg_size.width() > 0 and svg_size.height() > 0:
                        # Calculate size maintaining aspect ratio (max 150px on longest side)
                        max_size = 150
                        aspect_ratio = svg_size.width() / svg_size.height()
                        if aspect_ratio > 1:
                            # Wider than tall
                            width = max_size
                            height = int(max_size / aspect_ratio)
                        else:
                            # Taller than wide or square
                            height = max_size
                            width = int(max_size * aspect_ratio)
                    else:
                        # Fallback if size can't be determined
                        width, height = 150, 150
                    pixmap = QtGui.QPixmap(width, height)
                    pixmap.fill(QtCore.Qt.transparent)
                    painter = QtGui.QPainter(pixmap)
                    renderer.render(painter)
                    painter.end()
                    logo_label.setPixmap(pixmap)
                else:
                    # Load PNG or other raster formats
                    pixmap = QtGui.QPixmap(logo_path)
                    pixmap = pixmap.scaled(150, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                    logo_label.setPixmap(pixmap)
                title_layout.addWidget(logo_label)
            except Exception:
                pass
        
        # Title
        title_label = _QtWidgets.QLabel('WVU 4-Mic Audio Visualizer')
        title_label.setStyleSheet(f"color: {self.wvu_old_gold.name()}; font-size: 24px; font-weight: bold; font-family: Helvetica, Arial, sans-serif;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # Fullscreen button
        self.fullscreen_btn = _QtWidgets.QPushButton('⛶ Fullscreen')
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
        self.comparison_label = _QtWidgets.QLabel('Initializing...')
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
        
        # FPS indicator label (hidden by default, shown when enabled in settings)
        self.fps_label = _QtWidgets.QLabel('FPS: 0.0')
        self.fps_label.setStyleSheet(f"""
            color: {self.wvu_old_gold.name()}; 
            font-size: 12px; 
            font-weight: bold;
            font-family: 'Courier New', monospace;
            background-color: rgba(0, 40, 85, 0.9);
            padding: 5px 10px;
            border-radius: 5px;
            border: 1px solid {self.wvu_old_gold.name()};
        """)
        self.fps_label.setAlignment(QtCore.Qt.AlignCenter)
        self.fps_label.hide()  # Hidden by default
        title_layout.addWidget(self.fps_label)
        
        # Pause indicator label (hidden by default)
        self.pause_label = _QtWidgets.QLabel('⏸ PAUSED - Press SPACE to resume')
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
        self.plot_grid = _QtWidgets.QGridLayout()
        
        self.plot_widgets = []
        self.plot_curves = []
        self.level_labels = []
        self.level_bars = []
        self.plot_containers = []  # Store containers for each plot to show/hide
        
        for i in range(self.channels):
            # Create plot widget - PyQtGraph will use OpenGL if enabled via setConfigOption
            # Force GPU acceleration by ensuring OpenGL is enabled
            plot_widget = pg.PlotWidget()
            # Force OpenGL rendering hints for maximum GPU usage
            try:
                if GPU_ACCELERATION_ENABLED:
                    # Set rendering hints for GPU acceleration
                    plot_widget.setRenderHint(QtGui.QPainter.Antialiasing, True)
                    plot_widget.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            except:
                pass
            
            # Disable keyboard focus on plot widgets so main window can receive spacebar
            plot_widget.setFocusPolicy(QtCore.Qt.NoFocus)
            plot_widget.setBackground(self.wvu_bg)
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
            
            # Performance optimizations for ViewBox - maximize GPU usage
            view_box = plot_widget.getViewBox()
            # Enable optimizations for maximum performance
            try:
                view_box.setCacheMode(view_box.CacheModeFlag.CacheAll)  # Cache rendering for better performance
            except:
                pass  # Cache mode not available in all PyQtGraph versions
            # Enable auto-range optimization
            view_box.enableAutoRange(enable=True)
            # Set update mode for smooth rendering (if available)
            try:
                # Try to set minimal update mode for better performance
                if hasattr(view_box, 'setUpdateMode'):
                    view_box.setUpdateMode('minimal')  # Only update what changed
            except:
                pass
            
            # Store original setRange method and override it to lock X but allow Y
            original_setRange = view_box.setRange
            # Store original method as attribute for direct access if needed
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
                
                # If no Y range found, use current or default
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
            
            # Create curve for waveform with maximum performance optimizations
            # Use antialiasing and optimize for real-time updates with GPU
            curve = plot_widget.plot([], [], 
                                    pen=pg.mkPen(self.wvu_old_gold, width=2),
                                    antialias=True,  # Enable antialiasing (GPU accelerated if OpenGL enabled)
                                    clipToView=True,  # Only render visible portions
                                    skipFiniteCheck=True,  # Skip finite check for performance
                                    autoDownsample=True,  # Enable automatic downsampling
                                    downsampleMethod='peak',  # Preserve peaks when downsampling
                                    autoDownsampleFactor=1)  # Start with no downsampling, auto-adjust
            self.plot_curves.append(curve)
            
            # Level bar (will be created as a rectangle item)
            # Created dynamically in update_plots
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
            class PlotContainer(_QtWidgets.QWidget):
                def __init__(self, plot_widget, graph_idx, visualizer):
                    super().__init__()
                    self.plot_widget = plot_widget
                    self.graph_idx = graph_idx
                    self.visualizer = visualizer
                    layout = _QtWidgets.QVBoxLayout()
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
                
                # Ensure a 1D array
                if len(audio_data.shape) > 1:
                    audio_data = audio_data.flatten()
                
                # Validate data length matches expected frames
                if len(audio_data) != frames:
                    if len(audio_data) > frames:
                        audio_data = audio_data[:frames]
                    elif len(audio_data) < frames:
                        # Pad with zeros if fewer samples than expected
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
                
                # Update levels - ensure using the correct index
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
        """Update all plots - optimized for maximum FPS with GPU acceleration"""
        self.frame_skip_counter += 1
        
        # Update FPS counter
        current_time = time.time()
        self.fps_counter += 1
        if current_time - self.fps_last_time >= 1.0:  # Update FPS every second
            self.current_fps = self.fps_counter / (current_time - self.fps_last_time)
            self.fps_counter = 0
            self.fps_last_time = current_time
            # Update FPS label if enabled
            if self.fps_enabled and self.fps_label is not None:
                self.fps_label.setText(f'FPS: {self.current_fps:.1f}')
        
        # Time plot mode uses deque maxlen for automatic rolling window
        # No manual clearing needed - deque automatically removes old data
        # Update buffer size dynamically based on sample rate if needed
        if self.time_plot_mode:
            max_sample_rate = max([s.samplerate if s is not None else self.sample_rate 
                                  for s in self.streams] + [self.sample_rate])
            actual_max_samples = int(self.time_plot_window_seconds * max_sample_rate)
            # Update deque maxlen if sample rate changed significantly
            for i in range(self.channels):
                if self.time_plot_buffers[i].maxlen != actual_max_samples:
                    # Create new deque with updated maxlen
                    old_data = list(self.time_plot_buffers[i])
                    self.time_plot_buffers[i] = deque(old_data, maxlen=actual_max_samples)
                    self.time_plot_cache_dirty[i] = True
                    self.time_plot_cache[i] = None
        
        # Update waveform plots
        for i in range(self.channels):
            # Verify valid buffers for this index
            if i >= len(self.audio_buffers):
                continue
            
            # Convert deque to numpy array - optimized for performance
            if len(self.audio_buffers[i]) > 0:
                # Get the most recent samples from the buffer (last 512 samples for display)
                # Use islice for better performance when only last N samples are needed
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
                    # Time plot mode: accumulate data over time with absolute timestamps
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
                    
                    # Use absolute time from start, then normalize to 0-0.3s window when displaying
                    # Calculate elapsed time since start
                    elapsed_time = current_time - self.time_plot_start_time
                    
                    # Get the most recent time in buffer to continue from, or use elapsed time
                    if len(self.time_plot_buffers[i]) > 0:
                        last_time = self.time_plot_buffers[i][-1][0]
                        # Continue from last time + time_per_sample to maintain continuity
                        start_time = last_time + time_per_sample
                    else:
                        # First sample - start from 0
                        start_time = 0.0
                    
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
                        # Update cache more frequently for smoother display (every 2 frames)
                        update_cache = (self.time_plot_cache_dirty[i] and 
                                       (self.time_plot_update_counter[i] % 2 == 0 or 
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
                            
                            # Normalize time to adjusted window for continuous display
                            # Use the oldest sample time as reference (time 0)
                            if len(x_data_full) > 0:
                                # Find the minimum time in the buffer (oldest sample)
                                min_time = x_data_full[0]
                                # Normalize all times to start from 0
                                x_data_normalized = x_data_full - min_time
                                # Calculate adjusted window size based on sample rate adjustment
                                # When adjustment is 0.69x, time accumulates slower, so less time data in same real time
                                adjusted_window = self.time_plot_window_seconds * max(self.sample_rate_adjustment, 0.01)
                                # The data should naturally be within the adjusted window due to deque maxlen
                                # But clamp to ensure it's within bounds
                                x_data_normalized = np.clip(x_data_normalized, 0.0, adjusted_window)
                                
                                # Use all points for high resolution (no downsampling for continuous line)
                                x_data_display = x_data_normalized
                                audio_data_display = y_data_full * self.display_gain
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
                    # Use a reasonable default until enough samples are available
                    self.noise_floors[i] = 0.001
                
                # Store data for global range calculation (after gain is applied)
                # Calculate a global Y range after processing all mics
                current_max = np.abs(audio_data_display).max() if len(audio_data_display) > 0 else 0.0
                
                # Ensure valid data for display
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
                # Verify valid plot curve for this index
                if i >= len(self.plot_curves):
                    continue
                
                # Always update plot data for maximum smoothness (GPU handles rendering efficiently)
                # Ensure both arrays are the same length and have data
                # Use optimized setData for better performance
                if len(x_data_display) == len(audio_data_display) and len(audio_data_display) > 0:
                    # Both arrays match - use them directly
                    # Use 'all' for continuous high-resolution line in time plot mode
                    # Use skipFiniteCheck for better performance (data already validated)
                    # Disable autoDownsample for high resolution
                    self.plot_curves[i].setData(x_data_display, audio_data_display, 
                                                connect='all',
                                                skipFiniteCheck=True,
                                                autoDownsample=False)
                elif len(audio_data_display) > 0:
                    # Mismatch - create matching x_data for audio_data_display
                    x_fallback = np.arange(len(audio_data_display), dtype=np.float32)
                    self.plot_curves[i].setData(x_fallback, audio_data_display,
                                                connect='all' if self.time_plot_mode else 'all',
                                                skipFiniteCheck=True,
                                                autoDownsample=False)
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
            
            # Apply the same Y-axis range to all plots (always update for smoothness)
            for i in range(self.channels):
                    if i < len(self.plot_widgets):
                        view_box = self.plot_widgets[i].getViewBox()
                        
                        if self.time_plot_mode:
                            # Time plot mode: unlock X-axis limits and auto-scale
                            view_box.setLimits(xMin=None, xMax=None, minXRange=None, maxXRange=None)
                            
                            # Time plot mode: adjust X-axis range based on sample rate adjustment
                            # When sample_rate_adjustment is higher (faster), more time accumulates in the same real time
                            # When sample_rate_adjustment is lower (slower), less time accumulates in the same real time
                            # So the X-axis width should be: base_window * adjustment
                            # Example: 0.3s window * 0.69x = 0.207s of time data accumulated
                            x_min = 0.0
                            x_max = self.time_plot_window_seconds * max(self.sample_rate_adjustment, 0.01)  # Multiply, not divide!
                            
                            # Store X-axis range (no smoothing needed since it's fixed)
                            if not hasattr(self, '_time_plot_x_ranges'):
                                adjusted_window = self.time_plot_window_seconds * max(self.sample_rate_adjustment, 0.01)
                                self._time_plot_x_ranges = [(0, adjusted_window)] * self.channels
                            
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
                
                # Update level bar (every frame for smoothness with GPU)
                if True:  # Always update for maximum smoothness
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
                        
                        # Update level label (always update, not just when creating bar)
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
                # Get device for this channel - ensure a valid device list exists
                if self.devices is None or len(self.devices) <= ch:
                    device_idx = None
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
                    except Exception as e:
                        raise
                else:
                    sample_rate = self.sample_rate
                
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
                        break
                    except sd.PortAudioError:
                        if sr == sample_rates_to_try[-1]:
                            raise
                        continue
                    except Exception:
                        raise
                
                if stream is None:
                    raise RuntimeError(f"Could not open device {device_idx} for Mic {ch+1}")
            
        except Exception as e:
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
                pass
    
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
            dialog = SettingsDialog(self.display_gain, self.time_plot_mode, self.sample_rate_adjustment, 
                                   self.fps_enabled, self.fps_lock_ms, parent=self, icon_path=self.icon_path)
            # Track this dialog
            self.open_settings_dialogs.append(dialog)
            
            # Connect to dialog close events
            dialog.finished.connect(lambda: self.on_settings_dialog_closed(dialog))
            
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.display_gain = dialog.get_gain()
                new_time_plot_mode = dialog.get_time_plot_mode()
                new_sample_rate_adjustment = dialog.get_sample_rate_adjustment()
                self.fps_enabled = dialog.get_fps_enabled()
                
                # Show/hide FPS label based on setting
                if self.fps_label is not None:
                    if self.fps_enabled:
                        self.fps_label.show()
                    else:
                        self.fps_label.hide()
                
                # If switching to time plot mode, reset buffers and start time, unlock X-axis
                if new_time_plot_mode and not self.time_plot_mode:
                    # Calculate buffer size based on actual sample rate (0.3 seconds)
                    max_sample_rate = max([s.samplerate if s is not None else self.sample_rate 
                                          for s in self.streams] + [self.sample_rate])
                    actual_max_samples = int(self.time_plot_window_seconds * max_sample_rate)
                    self.time_plot_buffers = [deque(maxlen=actual_max_samples) for _ in range(self.channels)]
                    self.time_plot_cache = [None] * self.channels
                    self.time_plot_cache_dirty = [True] * self.channels
                    self.time_plot_update_counter = [0] * self.channels
                    self.time_plot_start_time = time.time()
                    self.time_plot_last_clear_time = None  # Reset clear timer
                    # Initialize X ranges with sample rate adjustment
                    # Multiply: when adjustment is 0.69x, time accumulates slower, so less time data
                    adjusted_window = self.time_plot_window_seconds * max(new_sample_rate_adjustment, 0.01)
                    self._time_plot_x_ranges = [(0, adjusted_window)] * self.channels
                    # Restore original setRange for all plots to allow X-axis scaling
                    for i in range(self.channels):
                        if i < len(self.plot_widgets):
                            view_box = self.plot_widgets[i].getViewBox()
                            if hasattr(view_box, '_original_setRange'):
                                view_box.setRange = view_box._original_setRange
                            view_box.setLimits(xMin=None, xMax=None, minXRange=None, maxXRange=None)
                
                # If switching away from time plot mode, clear buffers and restore locked X-axis
                if not new_time_plot_mode and self.time_plot_mode:
                    self.time_plot_buffers = [deque(maxlen=self.time_plot_max_samples) for _ in range(self.channels)]
                    self.time_plot_cache = [None] * self.channels
                    self.time_plot_cache_dirty = [True] * self.channels
                    self.time_plot_update_counter = [0] * self.channels
                    self.time_plot_start_time = None
                    self.time_plot_last_clear_time = None
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
                # If sample rate adjustment changed, invalidate cache so data gets renormalized
                if self.sample_rate_adjustment != new_sample_rate_adjustment:
                    # Mark all caches as dirty to force renormalization with new window size
                    for i in range(self.channels):
                        self.time_plot_cache_dirty[i] = True
                        self.time_plot_cache[i] = None
                self.sample_rate_adjustment = new_sample_rate_adjustment
                # Update FPS lock if changed
                new_fps_lock_ms = dialog.get_fps_lock_ms()
                if new_fps_lock_ms != self.fps_lock_ms:
                    self.fps_lock_ms = new_fps_lock_ms
                    # Restart timer with new FPS if it's running
                    if self.timer.isActive():
                        self.timer.stop()
                        self.timer.start(self.fps_lock_ms)
        finally:
            # Remove dialog from tracking
            if dialog in self.open_settings_dialogs:
                self.open_settings_dialogs.remove(dialog)
            # Resume plot updates when dialog closes (only if not paused and no other dialogs open)
            # Restore the previous state (paused or running)
            # This works in both normal and time plot modes
            if was_running and not was_paused and len(self.open_settings_dialogs) == 0:
                if not self.timer.isActive():  # Double-check timer is not already running
                    self.timer.start(self.fps_lock_ms)  # Use FPS lock setting
    
    def on_settings_dialog_closed(self, dialog):
        """Handle settings dialog close event"""
        # Remove dialog from tracking
        if dialog in self.open_settings_dialogs:
            self.open_settings_dialogs.remove(dialog)
        # Resume if no other dialogs are open and not paused
        if len(self.open_settings_dialogs) == 0 and not self.is_paused:
            if not self.timer.isActive():
                self.timer.start(self.fps_lock_ms)
    
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
            self.timer.start(self.fps_lock_ms)  # Use FPS lock setting
            self.pause_label.hide()
    
    def on_settings_menu_hover(self):
        """Pause graphs when hovering over Settings menu"""
        if not self.is_paused and self.timer.isActive():
            self.timer.stop()
    
    def on_settings_menu_leave(self):
        """Resume graphs when leaving Settings menu (if no dialogs are open)"""
        if not self.is_paused and len(self.open_settings_dialogs) == 0:
            self.timer.start(self.fps_lock_ms)
    
    def showEvent(self, event):
        """Handle window show event - ensure focus for keyboard events"""
        super().showEvent(event)
        # Set focus when window is shown to receive keyboard events
        self.setFocus()
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.stop()
        event.accept()

