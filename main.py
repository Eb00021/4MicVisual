"""
Super Fast 4-Mic Audio Visualizer
Real-time audio level visualization for 4 microphone inputs
"""
import sys
import os
import config  # Initialize PyQtGraph configuration
from pyqtgraph.Qt import QtWidgets
from visualizer import AudioVisualizer
from dialogs import select_input_devices_gui


def main():
    """Main entry point for the application"""
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
    
    # Try multiple possible logo file names and locations (prioritize SVG)
    possible_logo_paths = [
        'logo.svg', 'wvu_logo.svg',  # SVG first
        'logo.png', 'wvu_logo.png',
        os.path.join(base_dir, 'logo.svg'),
        os.path.join(base_dir, 'wvu_logo.svg'),
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
    
    # Select input devices using GUI (pass icon_path and logo_path so dialog uses same assets)
    num_channels, devices = select_input_devices_gui(num_channels=4, icon_path=icon_path, logo_path=logo_path)
    
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
