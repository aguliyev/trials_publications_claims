"""
Django App Package for 1FL Workspace.
Allows direct importing of Django modules, ORM models, and common lib.
"""

import os

# Auto-initialize Django when importing django_app if not yet initialized
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings")

try:
    import django
    from django.apps import apps
    if not apps.ready:
        django.setup()
except Exception:
    pass

from . import lib

__all__ = ["lib"]
