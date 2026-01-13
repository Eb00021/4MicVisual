"""
Configuration module for PyQtGraph and GPU acceleration settings.
"""
import warnings
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets

# Suppress numpy overflow warnings
warnings.filterwarnings('ignore', category=RuntimeWarning)

# Set PyQtGraph to use white background by default, will be overridden with WVU colors
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

# GPU Acceleration and Performance Optimizations
# Enable OpenGL for GPU acceleration if available
GPU_ACCELERATION_ENABLED = False
GPU_ACCELERATION_STATUS_MSG = "Not checked"

try:
    # Check if OpenGL is available before enabling
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
    # If OpenGL check fails, try to enable anyway
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
# Note: clipToView and coordinateMode are set per-item, not as global config options
