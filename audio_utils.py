"""
Audio device management and configuration utilities.
"""
import os
import sys
import json
import tempfile
import sounddevice as sd


def list_audio_devices():
    """List all available audio input devices"""
    devices = sd.query_devices()
    input_devices = []
    
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            input_devices.append(i)
    
    return input_devices


def validate_device(device_idx, test_open=False):
    """Validate that a device can be opened"""
    try:
        device_info = sd.query_devices(device_idx)
        if device_info['max_input_channels'] == 0:
            return False, "Device does not support input"
        
        if test_open:
            try:
                test_stream = sd.InputStream(
                    device=device_idx,
                    channels=1,
                    samplerate=int(device_info.get('default_samplerate', 44100)),
                    blocksize=256,
                    dtype='float32'
                )
                test_stream.close()
                return True, "OK (tested)"
            except sd.PortAudioError as e:
                return False, f"Cannot open device: {str(e)}"
            except Exception as e:
                return False, f"Device test failed: {str(e)}"
        else:
            _ = device_info.get('default_samplerate', None)
            return True, "OK (info only)"
    except Exception as e:
        return False, f"Device query failed: {str(e)}"


def get_config_file_path():
    """Get path to config file for saving device selections"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Use temp directory for config file
    temp_dir = tempfile.gettempdir()
    config_file = os.path.join(temp_dir, 'wvu_4mic_visualizer_config.json')
    return config_file


def load_device_config():
    """Load saved device configuration"""
    config_file = get_config_file_path()
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                devices = config.get('devices', None)
                num_channels = config.get('num_channels', None)
                return devices, num_channels
        except Exception:
            return None, None
    return None, None


def save_device_config(devices, num_channels=None):
    """Save device configuration to temp file"""
    config_file = get_config_file_path()
    try:
        config = {'devices': devices}
        if num_channels is not None:
            config['num_channels'] = num_channels
        with open(config_file, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        pass
