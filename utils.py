"""
Utility functions for SVG support and icon loading.
"""
# Import SVG support if available
try:
    from PyQt5.QtSvg import QSvgRenderer
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False
    QSvgRenderer = None
