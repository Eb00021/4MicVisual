"""
Dialog classes for settings and device selection.
"""
import os
import sys
import sounddevice as sd
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from audio_utils import load_device_config, save_device_config, get_config_file_path
from utils import SVG_SUPPORT, QSvgRenderer


class SettingsDialog(QtWidgets.QDialog):
    """Settings dialog for adjusting display gain and performance settings"""
    
    def __init__(self, current_gain=1.0, time_plot_mode=False, sample_rate_adjustment=1.0, 
                 fps_enabled=False, fps_lock_ms=8, parent=None, icon_path=None):
        super().__init__(parent)
        self.current_gain = current_gain
        self.time_plot_mode = time_plot_mode
        self.sample_rate_adjustment = sample_rate_adjustment
        self.fps_enabled = fps_enabled
        self.fps_lock_ms = fps_lock_ms
        self.setWindowTitle('Display Settings - WVU 4-Mic Visualizer')
        self.setMinimumSize(650, 800)
        self.resize(700, 850)
        
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
        
        # FPS indicator group
        fps_group = QtWidgets.QGroupBox('Performance')
        fps_layout = QtWidgets.QVBoxLayout()
        fps_layout.setSpacing(12)
        fps_layout.setContentsMargins(15, 20, 15, 15)
        
        # FPS indicator checkbox
        self.fps_checkbox = QtWidgets.QCheckBox('Show FPS Indicator')
        self.fps_checkbox.setChecked(self.fps_enabled)
        self.fps_checkbox.stateChanged.connect(self.on_fps_changed)
        fps_layout.addWidget(self.fps_checkbox)
        
        # Description
        fps_description = QtWidgets.QLabel('Display the current frames per second in the title bar.')
        fps_description.setWordWrap(True)
        fps_description.setAlignment(QtCore.Qt.AlignCenter)
        fps_layout.addWidget(fps_description)
        
        # FPS Lock slider
        fps_lock_layout = QtWidgets.QVBoxLayout()
        fps_lock_layout.setSpacing(8)
        
        fps_lock_label_layout = QtWidgets.QHBoxLayout()
        fps_lock_label = QtWidgets.QLabel('FPS Lock:')
        fps_lock_label.setStyleSheet(f"font-weight: bold; min-width: 120px;")
        fps_lock_label_layout.addWidget(fps_lock_label)
        fps_lock_label_layout.addStretch()
        fps_lock_layout.addLayout(fps_lock_label_layout)
        
        slider_layout = QtWidgets.QHBoxLayout()
        slider_layout.setSpacing(10)
        
        self.fps_lock_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        # FPS lock range: 5ms (200 FPS) to 100ms (10 FPS)
        # Store as milliseconds, display as FPS
        self.fps_lock_slider.setMinimum(5)  # 5ms = 200 FPS
        self.fps_lock_slider.setMaximum(100)  # 100ms = 10 FPS
        self.fps_lock_slider.setValue(self.fps_lock_ms)
        self.fps_lock_slider.valueChanged.connect(self.on_fps_lock_slider_changed)
        slider_layout.addWidget(self.fps_lock_slider)
        
        self.fps_lock_spinbox = QtWidgets.QSpinBox()
        self.fps_lock_spinbox.setMinimum(5)
        self.fps_lock_spinbox.setMaximum(100)
        self.fps_lock_spinbox.setSingleStep(1)
        self.fps_lock_spinbox.setValue(self.fps_lock_ms)
        self.fps_lock_spinbox.setSuffix(' ms')
        self.fps_lock_spinbox.valueChanged.connect(self.on_fps_lock_spinbox_changed)
        self.fps_lock_spinbox.setMaximumWidth(90)
        slider_layout.addWidget(self.fps_lock_spinbox)
        
        # FPS display label
        self.fps_lock_fps_label = QtWidgets.QLabel()
        self.fps_lock_fps_label.setStyleSheet(f"font-weight: bold; min-width: 80px;")
        slider_layout.addWidget(self.fps_lock_fps_label)
        
        # Update FPS label after widget is created
        self.update_fps_lock_fps_label()
        
        fps_lock_layout.addLayout(slider_layout)
        
        # Description
        fps_lock_description = QtWidgets.QLabel('Lock the frame rate to reduce CPU/GPU usage. Lower values = higher FPS (more CPU/GPU usage).')
        fps_lock_description.setWordWrap(True)
        fps_lock_description.setAlignment(QtCore.Qt.AlignCenter)
        fps_lock_layout.addWidget(fps_lock_description)
        
        fps_layout.addLayout(fps_lock_layout)
        
        fps_group.setLayout(fps_layout)
        layout.addWidget(fps_group)
        
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
    
    def on_fps_changed(self, state):
        """Handle FPS indicator checkbox change"""
        self.fps_enabled = (state == QtCore.Qt.Checked)
    
    def on_fps_lock_slider_changed(self, value):
        """Handle FPS lock slider value change"""
        self.fps_lock_spinbox.blockSignals(True)
        self.fps_lock_spinbox.setValue(value)
        self.fps_lock_spinbox.blockSignals(False)
        self.fps_lock_ms = value
        self.update_fps_lock_fps_label()
    
    def on_fps_lock_spinbox_changed(self, value):
        """Handle FPS lock spinbox value change"""
        self.fps_lock_slider.blockSignals(True)
        self.fps_lock_slider.setValue(value)
        self.fps_lock_slider.blockSignals(False)
        self.fps_lock_ms = value
        self.update_fps_lock_fps_label()
    
    def update_fps_lock_fps_label(self):
        """Update the FPS display label"""
        if self.fps_lock_ms > 0:
            fps = int(1000.0 / self.fps_lock_ms)
            self.fps_lock_fps_label.setText(f"({fps} FPS)")
        else:
            self.fps_lock_fps_label.setText("(∞ FPS)")
    
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
            except Exception:
                pass
    
    def get_gain(self):
        """Get the current gain value"""
        return self.current_gain
    
    def get_time_plot_mode(self):
        """Get the time plot mode setting"""
        return self.time_plot_mode
    
    def get_sample_rate_adjustment(self):
        """Get the sample rate adjustment value"""
        return self.sample_rate_adjustment
    
    def get_fps_enabled(self):
        """Get the FPS indicator setting"""
        return self.fps_enabled
    
    def get_fps_lock_ms(self):
        """Get the FPS lock setting in milliseconds"""
        return self.fps_lock_ms


class DeviceSelectionDialog(QtWidgets.QDialog):
    """GUI dialog for selecting audio input devices"""
    
    def __init__(self, num_channels=4, parent=None, icon_path=None, logo_path=None):
        super().__init__(parent)
        self.num_channels = num_channels
        self.selected_devices = [None] * num_channels
        self.logo_path = logo_path
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
        
        # Title bar with logo
        title_layout = QtWidgets.QHBoxLayout()
        
        # Logo - support both PNG and SVG
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                logo_label = QtWidgets.QLabel()
                if self.logo_path.lower().endswith('.svg') and SVG_SUPPORT:
                    # Load SVG using QSvgRenderer and preserve aspect ratio
                    renderer = QSvgRenderer(self.logo_path)
                    # Get the SVG's natural size
                    svg_size = renderer.defaultSize()
                    if svg_size.width() > 0 and svg_size.height() > 0:
                        # Calculate size maintaining aspect ratio (max 120px on longest side)
                        max_size = 120
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
                        width, height = 120, 120
                    pixmap = QtGui.QPixmap(width, height)
                    pixmap.fill(QtCore.Qt.transparent)
                    painter = QtGui.QPainter(pixmap)
                    renderer.render(painter)
                    painter.end()
                    logo_label.setPixmap(pixmap)
                else:
                    # Load PNG or other raster formats
                    pixmap = QtGui.QPixmap(self.logo_path)
                    pixmap = pixmap.scaled(120, 120, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                    logo_label.setPixmap(pixmap)
                title_layout.addWidget(logo_label)
            except Exception:
                pass
        
        # Title
        title = QtWidgets.QLabel('Select Audio Input Devices')
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {self.wvu_gold}; padding: 5px;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
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
        
        # Container for device selection groups (allows dynamic add/remove)
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
            except Exception:
                pass
    
    def get_selected_devices(self):
        """Get the selected devices"""
        # Read current values from all combo boxes
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
        # Return exactly num_channels devices
        return self.selected_devices[:self.num_channels]
    
    def get_num_channels(self):
        """Get the selected number of channels"""
        return self.num_channels


def select_input_devices_gui(num_channels=4, icon_path=None, logo_path=None):
    """GUI-based device selection"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    
    dialog = DeviceSelectionDialog(num_channels=num_channels, icon_path=icon_path, logo_path=logo_path)
    
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        num_channels = dialog.get_num_channels()
        devices = dialog.get_selected_devices()
        # Ensure exactly num_channels devices are returned
        if len(devices) < num_channels:
            # Pad with None if needed
            while len(devices) < num_channels:
                devices.append(None)
        # Save configuration (including num_channels)
        save_device_config(devices, num_channels)
        return num_channels, devices
    else:
        sys.exit(0)
