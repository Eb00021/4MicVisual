# WVU 4-Mic Audio Visualizer

A real-time audio visualization tool designed for monitoring multiple microphone inputs simultaneously. This tool helps identify which microphone is receiving higher audio levels with advanced visualization features and WVU branding.

## Features

### Core Functionality
- **Real-time Processing**: Optimized for low-latency audio processing with GPU acceleration support
- **Flexible Channel Support**: Monitor 1-8 microphone inputs simultaneously (configurable at startup)
- **Multi-Device Support**: Use different audio input devices for each microphone channel
- **GUI Device Selection**: Interactive dialog for selecting audio devices with saved configuration
- **Level Comparison**: Automatically highlights which mic has the highest average level
- **WVU Branding**: Custom color scheme (WVU Old Gold and Blue) with logo support

### Visualization Modes
- **Normal Mode**: Fixed 512-sample window display with locked X-axis
- **Time Plot Mode**: Continuous rolling time-based plot (0.3 second window) with auto-scaling
- **Dual Display Options**:
  - All graphs view (grid layout)
  - Single graph fullscreen (double-click any graph)
  - Window fullscreen mode

### Display Features
- **Real-time Waveforms**: High-resolution waveform display for each microphone
- **Level Indicators**: Color-coded level bars (gold → yellow → orange based on level)
- **Level Information**: 
  - RMS level and dB readings for each mic
  - Peak level tracking with decay
  - Moving average levels for stable comparison
- **Global Y-Axis Scaling**: All graphs use synchronized Y-axis ranges for easy comparison
- **Auto-scaling**: Y-axis automatically adjusts based on signal levels across all mics

### Settings & Controls
- **Display Gain**: Adjustable gain multiplier (0.0x to 2.0x) for signal amplification
- **Time Plot Controls**: 
  - Enable/disable time plot mode
  - Sample rate adjustment (0.1x to 2.0x) for time scale control
- **Performance Settings**:
  - FPS indicator (optional display)
  - FPS lock (5ms to 100ms, ~200 FPS to ~10 FPS)
- **Keyboard Shortcuts**:
  - `SPACE`: Pause/resume visualization
  - `ESC`: Exit fullscreen or single graph mode
  - `Ctrl+S`: Open settings dialog

### Advanced Features
- **GPU Acceleration**: OpenGL rendering support for improved performance
- **Pause/Resume**: Temporarily pause visualization updates
- **Device Memory**: Saves device selections for quick startup
- **Logo Support**: Displays WVU logo (SVG or PNG) in title bar
- **Icon Support**: Custom window icon (ICO or PNG)
- **Smooth Rendering**: Optimized for high frame rates with efficient buffer management

## Installation

1. Install Python 3.7 or higher

2. Install required packages:
```bash
pip install -r requirements.txt
```

Required packages:
- `numpy` - Numerical operations
- `sounddevice` - Audio input handling
- `pyqtgraph` - Real-time plotting
- `PyQt5` - GUI framework
- `Pillow` - Image processing
- `PyOpenGL` - GPU acceleration (optional but recommended)

## Usage

### Starting the Visualizer

Run the visualizer:
```bash
python main.py
```

### Device Selection

1. At startup, a GUI dialog will appear showing:
   - Number of microphones selector (1-8)
   - Device selection dropdown for each microphone
   - Option to use default device or select specific devices

2. Configure your setup:
   - Select the number of microphones you want to monitor
   - Choose an audio input device for each microphone
   - Click "Start Visualizer" to begin

3. Your device selections are automatically saved and will be remembered for next time

### Main Window

The visualization window displays:
- **Title Bar**: Logo, title, fullscreen button, comparison label, FPS indicator (optional), pause indicator
- **Graph Grid**: Individual plots for each microphone showing:
  - Real-time waveform
  - Level bar indicator
  - Level and peak information overlay
- **Comparison Display**: Shows which microphone has the highest average level and current levels for all mics

### Settings Dialog

Access via `Settings > Display Settings...` or `Ctrl+S`:

- **Display Gain**: Adjust signal amplification (0.0x = mute, 2.0x = double amplitude)
- **Time Plot Mode**: 
  - Enable continuous time-based plotting
  - Adjust sample rate multiplier for time scale control
- **Performance**:
  - Show/hide FPS indicator
  - Adjust FPS lock (lower = higher FPS, more CPU/GPU usage)

### Viewing Modes

- **All Graphs**: Default view showing all microphone plots in a grid
- **Single Graph Fullscreen**: Double-click any graph to view it fullscreen
- **Window Fullscreen**: Click the "Fullscreen" button or press `F11` (if supported)
- **Return to All**: Double-click again or press `ESC` to return to all graphs view

### Keyboard Controls

- `SPACE`: Pause/resume visualization updates
- `ESC`: Exit fullscreen or single graph mode, return to all graphs
- `Ctrl+S`: Open settings dialog

## Requirements

- **Audio Input**: One or more audio input devices (microphones, audio interfaces, etc.)
- **Python**: 3.7 or higher
- **Operating System**: Windows, macOS, or Linux
- **Hardware**: 
  - GPU with OpenGL support (recommended for best performance)
  - Sufficient CPU for real-time audio processing

## Performance Notes

- **GPU Acceleration**: OpenGL rendering is automatically enabled if available for improved performance
- **Optimized Processing**: 
  - Efficient numpy operations for fast processing
  - Small buffer sizes (512 samples) for low latency
  - Optimized PyQtGraph rendering with caching
- **FPS Control**: Adjustable frame rate lock to balance smoothness vs. CPU/GPU usage
- **Memory Management**: Efficient buffer management with fixed-size deques
- **RMS Calculation**: Accurate level measurement using RMS (Root Mean Square)

## Troubleshooting

- **No devices found**: 
  - Make sure your audio interface is connected and drivers are installed
  - Check that devices support input channels
  - Try restarting the application

- **Low channel count**: 
  - Some devices may only support 1-2 channels
  - You can use multiple devices (one per microphone) to overcome this limitation
  - The visualizer supports 1-8 microphones with flexible device assignment

- **High CPU/GPU usage**: 
  - Try increasing the FPS lock in settings (higher ms = lower FPS = less CPU usage)
  - Disable FPS indicator if enabled
  - Reduce the number of microphones being monitored
  - Check if GPU acceleration is enabled (should be automatic)

- **Audio dropouts or stuttering**:
  - Try using a different sample rate
  - Increase buffer size if possible
  - Close other audio applications
  - Check audio driver settings

- **Settings dialog causes stuttering**:
  - This is normal - the visualization pauses automatically when the settings dialog is open
  - The visualization resumes when you close the dialog

- **Logo/icon not showing**:
  - Ensure logo/icon files are in the same directory as the script
  - Supported formats: SVG, PNG, ICO, JPG
  - Try common names: `logo.svg`, `wvu_logo.svg`, `logo.png`, `icon.ico`, etc.

## Technical Details

- **Sample Rate**: Automatically detects and uses device's preferred sample rate (typically 44.1kHz or 48kHz)
- **Buffer Size**: 512 samples per block for low latency
- **Display Buffer**: 2048 samples for smooth waveform display
- **Time Plot Window**: 0.3 seconds of continuous data in time plot mode
- **Level Averaging**: 50-sample moving average for stable level comparison
- **Noise Floor**: Automatic noise floor estimation for better auto-scaling

