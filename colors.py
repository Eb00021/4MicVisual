"""
Terminal color utilities for WVU branding.
"""
import sys

# ANSI color codes for Windows (works with Windows 10+)
class Colors:
    """ANSI color codes for terminal output"""
    # WVU Colors
    GOLD = '\033[93m'  # Bright yellow (closest to gold)
    BLUE = '\033[94m'  # Bright blue
    BOLD = '\033[1m'
    RESET = '\033[0m'
    # Additional colors
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

# Enable ANSI colors on Windows
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        pass

def print_wvu_logo():
    """Print WVU header"""
    print()
    print_colored("EcoCAR EV CHALLENGE", Colors.GOLD, bold=True)
    print_colored("WEST VIRGINIA UNIVERSITY", Colors.WHITE, bold=True)
    print_colored("4-Mic Audio Visualizer System", Colors.GOLD, bold=True)
    print()

def print_colored(text, color=Colors.WHITE, bold=False):
    """Print colored text"""
    style = color
    if bold:
        style += Colors.BOLD
    print(f"{style}{text}{Colors.RESET}")

def print_header(text):
    """Print a header with WVU colors"""
    print_colored("="*80, Colors.BLUE)
    print_colored(text, Colors.GOLD, bold=True)
    print_colored("="*80, Colors.BLUE)
