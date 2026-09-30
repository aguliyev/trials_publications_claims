"""
1FL Library Package.
Provides convenience wrappers for:
- Database / PostgreSQL (db)
- PubMed querying and parsing (pubmed)
- ClinicalTrials.gov querying (clinical_trials)
- Instructor and LLM structured extraction (llm)
"""

import os

# Auto-initialize Django when importing lib if not yet initialized
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings")
try:
    import django
    from django.apps import apps
    if not apps.ready and not apps.loading:
        django.setup()
except Exception:
    pass

from . import db, pubmed, clinical_trials, llm

__all__ = ["db", "pubmed", "clinical_trials", "llm"]
