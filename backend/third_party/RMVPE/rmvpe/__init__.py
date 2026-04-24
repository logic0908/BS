"""
RMVPE: A Robust Model for Vocal Pitch Estimation in Polyphonic Music.

This package provides a simple interface for pitch estimation from audio using
the RMVPE deep learning model.
"""

from .inference import RMVPE

__version__ = "0.1.0"
__all__ = ["RMVPE"]

