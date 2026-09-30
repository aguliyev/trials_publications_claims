"""
Django App Package for 1FL Workspace.
Allows direct importing of Django modules, ORM models, and common lib.
"""

def __getattr__(name: str):
    # ponytail: lazy so importing django_app.settings never pulls lib/core models pre-setup
    if name == "lib":
        from . import lib as _lib
        return _lib
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["lib"]
