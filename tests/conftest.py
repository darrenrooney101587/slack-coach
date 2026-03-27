"""Pytest configuration.

Tests import modules from the repository root (e.g. `from app.main import DailyCoach`).
When running pytest from outside the repo (or with certain tooling), the repo root
isn't always on `sys.path`, which can cause `ModuleNotFoundError: app` during
collection.

Also adds the `app/` directory so that intra-app imports (e.g. `from server import app`)
work without the `app.` prefix, matching how the modules import each other at runtime.
"""

import os
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIR = os.path.join(PROJECT_ROOT, "app")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
