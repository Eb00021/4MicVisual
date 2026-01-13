# PyInstaller Build Instructions

## Quick Build (Windows)

Run the batch file:
```batch
build_pyinstaller.bat
```

## Quick Build (Linux/Mac)

Run the shell script:
```bash
chmod +x build_pyinstaller.sh
./build_pyinstaller.sh
```

## Manual Build Command

### Windows:
```batch
pyinstaller --name="WVU_4Mic_Visualizer" --onedir --windowed --noconsole --icon=icon.ico --add-data "icon.ico;." --add-data "icon.png;." --add-data "logo.png;." --hidden-import=PyQt5 --hidden-import=PyQt5.QtCore --hidden-import=PyQt5.QtGui --hidden-import=PyQt5.QtWidgets --hidden-import=pyqtgraph --hidden-import=numpy --hidden-import=sounddevice --hidden-import=PIL --hidden-import=PIL.Image --collect-all=pyqtgraph --collect-all=PyQt5 main.py
```

### Linux/Mac:
```bash
pyinstaller --name="WVU_4Mic_Visualizer" --onedir --windowed --noconsole --icon=icon.ico --add-data "icon.ico:." --add-data "icon.png:." --add-data "logo.png:." --hidden-import=PyQt5 --hidden-import=PyQt5.QtCore --hidden-import=PyQt5.QtGui --hidden-import=PyQt5.QtWidgets --hidden-import=pyqtgraph --hidden-import=numpy --hidden-import=sounddevice --hidden-import=PIL --hidden-import=PIL.Image --collect-all=pyqtgraph --collect-all=PyQt5 main.py
```

## Command Options Explained

- `--name="WVU_4Mic_Visualizer"` - Name of the executable
- `--onedir` - Creates a directory with the executable (not a single file)
- `--windowed` / `--noconsole` - No console window (GUI only)
- `--icon=icon.ico` - Sets the application icon
- `--add-data` - Includes asset files (images, icons) in the build
  - Windows format: `"file;destination"`
  - Linux/Mac format: `"file:destination"`
- `--hidden-import` - Ensures these modules are included
- `--collect-all` - Collects all submodules and data files for these packages

## Output

The executable will be in: `dist/WVU_4Mic_Visualizer/`

## Adding More Assets

If you have additional image files (logo.jpg, wvu_logo.png, etc.), add them with:
```batch
--add-data "logo.jpg;."
--add-data "wvu_logo.png;."
```

## Troubleshooting

If assets are missing:
1. Check that asset files exist in the project directory
2. Verify the `--add-data` paths are correct
3. Check `dist/WVU_4Mic_Visualizer/` folder to see if files were copied

If imports fail:
1. Make sure all dependencies are installed: `pip install -r requirements.txt`
2. Add missing modules to `--hidden-import` list
3. Use `--collect-all` for complex packages like PyQt5
