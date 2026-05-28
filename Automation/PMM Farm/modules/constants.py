"""
Constants and Enumerations Module.

Contains program IDs and other constants used across the application.
"""

from enum import IntEnum


class Program(IntEnum):
    """
    Enumeration of supported program IDs for SMT monitoring.
    
    These IDs correspond to programs in the Stack Management Tool (SMT).
    """
    MAGNUS = 1            # Placeholder - ID TBD
    GAINSBOROUGH = 1434
    SOUNDWAVE = 1427
    CANIS = 1430
