"""
Build script to create an executable from the 4-Mic Audio Visualizer
Uses PyInstaller to create a standalone executable
"""

import PyInstaller.__main__
import os
import sys

def build_executable():
    """Build the executable using PyInstaller"""
    
    # Get the current directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(script_dir, 'main.py')
    
    # PyInstaller arguments
    args = [
        main_script,
        '--name=WVU_4Mic_Visualizer',
        '--onefile',  # Create a single executable file
        '--windowed',  # No console window (Windows) / --noconsole (cross-platform)
        '--noconsole',  # Alternative flag for no console
        '--icon=NONE',  # Add icon file path here if you have one (e.g., 'icon.ico')
        '--hidden-import=PyQt5',
        '--hidden-import=pyqtgraph',
        '--hidden-import=numpy',
        '--hidden-import=sounddevice',
        '--hidden-import=PIL',
        '--hidden-import=scipy',  # sounddevice dependency
        '--collect-all=pyqtgraph',
        '--collect-all=PyQt5',
        '--noconfirm',  # Overwrite output without asking
        '--clean',  # Clean cache before building
    ]
    
    # Add logo files if they exist
    logo_files = ['logo.png', 'wvu_logo.png', 'ecocar_logo.png', 'logo.jpg', 'wvu_logo.jpg']
    for logo in logo_files:
        logo_path = os.path.join(script_dir, logo)
        if os.path.exists(logo_path):
            # Format: source_path;destination (Windows uses semicolon)
            if sys.platform == 'win32':
                args.append(f'--add-data={logo_path};.')
            else:
                args.append(f'--add-data={logo_path}:.')
            print(f"Including logo: {logo}")
    
    # Add README if it exists
    readme_path = os.path.join(script_dir, 'README.md')
    if os.path.exists(readme_path):
        if sys.platform == 'win32':
            args.append(f'--add-data={readme_path};.')
        else:
            args.append(f'--add-data={readme_path}:.')
    
    print("Building executable...")
    print("This may take a few minutes...")
    print()
    
    try:
        PyInstaller.__main__.run(args)
        print()
        print("="*60)
        print("Build completed successfully!")
        print("="*60)
        print(f"Executable location: {os.path.join(script_dir, 'dist', 'WVU_4Mic_Visualizer.exe')}")
        print()
        print("To include a custom logo:")
        print("  1. Place your logo file (logo.png, wvu_logo.png, or ecocar_logo.png)")
        print("     in the same directory as main.py")
        print("  2. Rebuild the executable")
        print()
    except Exception as e:
        print(f"Error building executable: {e}")
        print()
        print("Make sure PyInstaller is installed:")
        print("  pip install pyinstaller")
        sys.exit(1)

if __name__ == '__main__':
    build_executable()

