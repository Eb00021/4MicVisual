# Super Fast 4-Mic Audio Visualizer

A real-time audio visualization tool designed for monitoring 4 microphone inputs simultaneously. This tool helps identify which microphone is receiving higher audio levels.

## Features

- **Real-time Processing**: Optimized for low-latency audio processing
- **4-Channel Support**: Simultaneously monitor 4 microphone inputs
- **Interactive Device Selection**: Choose your audio input device at startup
- **Level Comparison**: Automatically highlights which mic has the highest level
- **Multiple Visualizations**:
  - Real-time waveform display for each mic
  - Color-coded level indicators (green → yellow → red)
  - RMS level and dB readings
  - Peak level tracking

## Installation

1. Install Python 3.7 or higher

2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the visualizer:
```bash
python main.py
```

1. At startup, you'll see a list of available audio input devices
2. Select a device:
   - Enter `0` to use the default device
   - Enter a number (1-N) to select a specific device
   - Enter `q` to quit

3. The visualization window will open showing:
   - 4 separate plots (one for each mic)
   - Real-time waveform for each channel
   - Current level and peak level for each mic
   - Comparison showing which mic has the highest level

## Requirements

- An audio input device with at least 4 input channels (or use a multi-channel audio interface)
- Python 3.7+
- Windows/Mac/Linux compatible

## Performance Notes

- Uses optimized numpy operations for fast processing
- Small buffer sizes for low latency
- Blitted matplotlib animations for smooth 60 FPS updates
- RMS level calculation for accurate level measurement

## Troubleshooting

- **No devices found**: Make sure your audio interface is connected and drivers are installed
- **Low channel count**: Some devices may only support 1-2 channels. The visualizer will use available channels
- **High CPU usage**: Try increasing the `block_size` parameter in the code (default: 1024)

