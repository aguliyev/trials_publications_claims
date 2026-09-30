# Trials Publications Claims

Dockerized environment combining PostgreSQL 16, Django application, and JupyterLab, configured for biomedical and clinical research workflows.

## Directory Structure

```text
./
├── bin/            # Executable host scripts (install, start, stop, test, manage, makemigrations, migrate, pipeline)
├── jobs/           # Scripts run inside the container (pipeline.py)
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
- `./bin/makemigrations [args]`: Creates new migrations inside the running Django container using `docker compose exec`.
- `./bin/migrate [args]`: Runs database migrations inside the running Django container using `docker compose exec`.
- `./bin/pipeline`: Runs `jobs/pipeline.py` inside the already-running Django container using `docker compose exec -T django-app`. Requires `./bin/start` first.
- `bin/preload_models.py`: Container-side helper used by `./bin/install` to preload biomedical NER models into the shared cache.

## Pipeline Jobs (`jobs/`)

`jobs/pipeline.py` runs inside the Django container (via `./bin/pipeline`). It calls `django.setup()`, then runs these stages in order with INFO logging per stage, stopping on first failure:

1. `lib.ner.save_ner_trials()`
2. `lib.ner.save_ner_publications()`
3. `lib.interventions.save_ner_interventions()`
4. `lib.diseases.save_ner_diseases()`
5. `lib.claims.save_claims()`
6. `lib.judgement.save_judgements()`

Usage:

```sh
./bin/start
./bin/pipeline
```

## Access Endpoints

- **JupyterLab**: [http://localhost:8888](http://localhost:8888)
- **Django Application**: [http://localhost:8001](http://localhost:8001)
- **PostgreSQL**: `localhost:5433` (db: `fl_db`, user: `postgres`)

## Code Examples

Notebooks in `notebooks/` demonstrate the interactive workflow (with `%load_ext autoreload`, `%autoreload 2`):

- `sources.ipynb`: PubMed / ClinicalTrials.gov fetching and upserts.
- `ner.ipynb`: NER extraction.
- `claims.ipynb`: claim extraction.
- `judgement.ipynb`: judgement scoring.
- `pipeline.ipynb`: end-to-end sequence (`fetch_and_upsert_trial`, `fetch_trial_publications`, then the six `jobs/pipeline.py` stages).
