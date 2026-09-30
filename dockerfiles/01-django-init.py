# Auto-initialize Django within Jupyter notebooks and enable module autoreload
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

try:
    import django
    from django.apps import apps
    if not apps.ready:
        django.setup()
except Exception:
    pass

try:
    ipython = get_ipython()
    if ipython:
        ipython.run_line_magic("load_ext", "autoreload")
        ipython.run_line_magic("autoreload", "2")
except Exception:
    pass
