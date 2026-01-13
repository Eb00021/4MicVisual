# Building the WVU 4-Mic Visualizer Executable

## Prerequisites
1. Install PyInstaller: `pip install pyinstaller`
2. Ensure you have `icon.ico` and `logo.png` in the project directory

## Quick Build (Windows)
Run the batch file:
```batch
build_exe.bat
```

## Manual Build Command

### Windows (Command Prompt or PowerShell):
```batch
pyinstaller --onefile --windowed --name "WVU_4Mic_Visualizer" --icon=icon.ico --add-data "logo.png;." --add-data "icon.ico;." --hidden-import=PyQt5 --hidden-import=pyqtgraph --hidden-import=numpy --hidden-import=sounddevice --hidden-import=PIL --hidden-import=scipy --collect-all pyqtgraph --collect-all PyQt5 main.py
```

### Linux/Mac:
```bash
pyinstaller --onefile --windowed --name "WVU_4Mic_Visualizer" --icon=icon.ico --add-data "logo.png:." --add-data "icon.ico:." --hidden-import=PyQt5 --hidden-import=pyqtgraph --hidden-import=numpy --hidden-import=sounddevice --hidden-import=PIL --hidden-import=scipy --collect-all pyqtgraph --collect-all PyQt5 main.py
```

## Command Options Explained:
- `--onefile`: Creates a single executable file
- `--windowed` / `--noconsole`: Hides the console window (GUI app)
- `--name "WVU_4Mic_Visualizer"`: Sets the output executable name
- `--icon=icon.ico`: Sets the application icon
- `--add-data "logo.png;."`: Includes logo.png in the executable (Windows uses `;`, Linux/Mac uses `:`)
- `--add-data "icon.ico;."`: Includes icon.ico as a data file
- `--hidden-import`: Ensures these modules are included
- `--collect-all`: Collects all submodules and data files for these packages

## Output
The executable will be created in the `dist` folder.

## Notes:
- On Windows, use semicolon (`;`) to separate paths in `--add-data`
- On Linux/Mac, use colon (`:`) to separate paths in `--add-data`
- The logo.png and icon.ico files will be bundled inside the executable and extracted at runtime
