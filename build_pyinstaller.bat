@echo off
REM PyInstaller build script for WVU 4-Mic Audio Visualizer
REM This script builds the executable with all assets included

echo Building WVU 4-Mic Audio Visualizer...
echo.

REM Clean previous builds (optional - comment out if you want to keep them)
REM rmdir /s /q build dist 2>nul

REM PyInstaller command with all assets included
REM Note: Add --add-data for each asset file that exists in your project
REM The code searches for these files, so include any that you have:
REM Icons: icon.ico, app.ico, wvu_icon.ico, logo.ico, icon.png, app.png, wvu_icon.png
REM Logos: logo.png, wvu_logo.png, logo.jpg, wvu_logo.jpg, WVU_logo.png, WVU_logo.jpg, ecocar_logo.png, ecocar_logo.jpg

pyinstaller ^
    --name="WVU_4Mic_Visualizer" ^
    --onedir ^
    --windowed ^
    --noconsole ^
    --icon=icon.ico ^
    --add-data "icon.ico;." ^
    --add-data "icon.png;." ^
    --add-data "logo.png;." ^
    --hidden-import=PyQt5 ^
    --hidden-import=PyQt5.QtCore ^
    --hidden-import=PyQt5.QtGui ^
    --hidden-import=PyQt5.QtWidgets ^
    --hidden-import=pyqtgraph ^
    --hidden-import=numpy ^
    --hidden-import=sounddevice ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=OpenGL ^
    --hidden-import=OpenGL.GL ^
    --collect-all=pyqtgraph ^
    --collect-all=PyQt5 ^
    --collect-all=OpenGL ^
    main.py

REM If you have additional asset files, add them like this:
REM --add-data "wvu_logo.png;."
REM --add-data "ecocar_logo.png;."
REM --add-data "app.ico;."

echo.
echo Build complete! Check the 'dist' folder for the executable.
echo.
pause
