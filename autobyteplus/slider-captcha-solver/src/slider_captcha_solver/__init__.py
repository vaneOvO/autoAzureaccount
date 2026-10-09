"""slider-captcha-solver: solve jigsaw slider captchas in browser automation."""

from .detection import detect_gap_x, detect_piece_left
from .trajectory import human_drag_trajectory

try:
    from .playwright_solver import try_solve_slider
except ImportError:  # playwright not installed
    try_solve_slider = None

__version__ = "0.1.0"
__all__ = [
    "detect_gap_x",
    "detect_piece_left",
    "human_drag_trajectory",
    "try_solve_slider",
]
