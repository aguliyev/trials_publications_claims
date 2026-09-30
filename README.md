# Trials Publications Claims

Dockerized environment combining PostgreSQL 16, Django application, and JupyterLab, configured for biomedical and clinical research workflows.

## Directory Structure

```text
./
├── bin/            # Executable scripts (install, start, stop, test, manage)
├── etc/            # Environment configs (.env, requirements.txt, secrets/)
├── dockerfiles/    # Dedicated Dockerfiles for Jupyter and Django
├── django_app/     # Django app with domain models and common lib/
│   ├── core/       # Models: Trial, Publication, PublicationTrial, Disease, Intervention, Biomarker, Observation, Claim
│   └── lib/        # Shared library (db, pubmed, clinical_trials, llm)
├── notebooks/      # Jupyter notebooks with code examples and autoreload
└── tests/          # Integration and environment test suites
```

## Management Scripts (`bin/`)

All operations are handled via scripts in `bin/`:

- `./bin/install`: Builds Docker images, initializes `etc/.env`, and runs initial database migrations.
- `./bin/start`: Starts all services (`postgres`, `django-app`, `jupyter`) in the background.
- `./bin/stop`: Stops all containers (accepts `-v` to prune volumes).
- `./bin/test`: Runs environment verification and Django unit test suites.
- `./bin/manage [cmd]`: Runs Django `manage.py` commands inside the Django container (e.g. `./bin/manage migrate`).

## Access Endpoints

- **JupyterLab**: [http://localhost:8888](http://localhost:8888)
- **Django Application**: [http://localhost:8001](http://localhost:8001)
- **PostgreSQL**: `localhost:5433` (db: `fl_db`, user: `postgres`)

## Code Examples

See **`notebooks/sample_exploration.ipynb`** for interactive code examples demonstrating:
- Live module autoreloading (`%load_ext autoreload`, `%autoreload 2`)
- Importing and querying Django ORM models (`Trial`, `Publication`, `PublicationTrial`, `Disease`, `Intervention`, `Biomarker`, `Observation`) with JSONB metadata
- PubMed, ClinicalTrials.gov, and Instructor LLM extraction utilities
