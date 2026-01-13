#!/bin/bash
# PyInstaller build script for WVU 4-Mic Audio Visualizer
# This script builds the executable with all assets included

echo "Building WVU 4-Mic Audio Visualizer..."
echo ""

# Clean previous builds (optional - uncomment if you want to clean)
# rm -rf build dist

# PyInstaller command with all assets included
# Note: Add --add-data for each asset file that exists in your project
# The code searches for these files, so include any that you have:
# Icons: icon.ico, app.ico, wvu_icon.ico, logo.ico, icon.png, app.png, wvu_icon.png
# Logos: logo.png, wvu_logo.png, logo.jpg, wvu_logo.jpg, WVU_logo.png, WVU_logo.jpg, ecocar_logo.png, ecocar_logo.jpg

pyinstaller \
    --name="WVU_4Mic_Visualizer" \
    --onedir \
    --windowed \
    --noconsole \
    --icon=icon.ico \
    --add-data "icon.ico:." \
    --add-data "icon.png:." \
    --add-data "logo.png:." \
    --hidden-import=PyQt5 \
    --hidden-import=PyQt5.QtCore \
    --hidden-import=PyQt5.QtGui \
    --hidden-import=PyQt5.QtWidgets \
    --hidden-import=pyqtgraph \
    --hidden-import=numpy \
    --hidden-import=sounddevice \
    --hidden-import=PIL \
    --hidden-import=PIL.Image \
    --hidden-import=OpenGL \
    --hidden-import=OpenGL.GL \
    --collect-all=pyqtgraph \
    --collect-all=PyQt5 \
    --collect-all=OpenGL \
    main.py

# If you have additional asset files, add them like this:
# --add-data "wvu_logo.png:."
# --add-data "ecocar_logo.png:."
# --add-data "app.ico:."

echo ""
echo "Build complete! Check the 'dist' folder for the executable."
echo ""
