"""
Hickmet Premium Backend Application
"""
import os
import sys

# Корень проекта (Tour_code/) в sys.path, чтобы `from db import ...` работало
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

__version__ = "1.0.0"
