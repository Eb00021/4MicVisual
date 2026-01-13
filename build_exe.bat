@echo off
REM PyInstaller command to build WVU 4-Mic Visualizer executable
REM Make sure icon.ico and logo.png are in the same directory as main.py

pyinstaller --onefile ^
    --windowed ^
    --name "WVU_4Mic_Visualizer" ^
    --icon=icon.ico ^
    --add-data "logo.png;." ^
    --add-data "icon.ico;." ^
    --hidden-import=PyQt5 ^
    --hidden-import=pyqtgraph ^
    --hidden-import=numpy ^
    --hidden-import=sounddevice ^
    --hidden-import=PIL ^
    --hidden-import=scipy ^
    --collect-all pyqtgraph ^
    --collect-all PyQt5 ^
    main.py

echo.
echo Build complete! The executable should be in the 'dist' folder.
pause
