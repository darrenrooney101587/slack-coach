"""Pytest configuration.

Tests import modules from the repository root (e.g. `from app.main import DailyCoach`).
When running pytest from outside the repo (or with certain tooling), the repo root
isn't always on `sys.path`, which can cause `ModuleNotFoundError: app` during
collection.

This fixture ensures the project root is importable for all tests.
"""

import os
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
