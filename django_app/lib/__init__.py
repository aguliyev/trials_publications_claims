"""
1FL Library Package.
Provides convenience wrappers for:
- Database / PostgreSQL (db)
- PubMed querying and parsing (pubmed)
- ClinicalTrials.gov querying (clinical_trials)
- Instructor and LLM structured extraction (llm)
"""

import importlib as _importlib


def __getattr__(name: str):
    # ponytail: lazy so `import lib` never pulls DB/ORM models pre-setup
    if name in ("db", "pubmed", "clinical_trials", "llm", "logs", "text_tools"):
        return _importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["db", "pubmed", "clinical_trials", "llm", "logs", "text_tools"]
