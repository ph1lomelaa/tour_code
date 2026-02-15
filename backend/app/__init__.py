"""
Hickmet Premium Backend Application
"""
import os
import sys

# Корень проекта (Tour_code/) в sys.path, чтобы `from db import ...` работало
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

__version__ = "1.0.0"
