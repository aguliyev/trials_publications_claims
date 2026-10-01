# Trials Publications Claims

Dockerized environment combining PostgreSQL 16, Django application, and JupyterLab, configured for biomedical and clinical research workflows.

## System Diagram

[View application screenshots](docs/illustrations/)

```text
┌────────────────────────────── PUBLIC DATA SOURCES ──────────────────────────────┐
│                                                                                 │
│     ClinicalTrials.gov API                          PubMed API                   │
│     • Trial registry records                       • Publications               │
│     • Conditions/interventions                     • Abstracts and metadata     │
│     • Referenced PMIDs                             • Referenced NCT IDs          │
│                                                                                 │
└─────────────────┬─────────────────────────────────────┬─────────────────────────┘
                  │ Search and fetch                    │ Search and fetch
                  ▼                                     ▼
┌──────────────────────────── SOURCE INGESTION ───────────────────────────────────┐
│                                                                                 │
│  Parse and upsert Trial                    Parse and upsert Publication          │
│  • Structured fields                       • Structured fields                  │
│  • Complete raw API response               • Complete raw API response          │
│  • Source identifier: NCT ID               • Source identifier: PMID            │
│                                                                                 │
│                 Link related records using references                           │
│                                                                                 │
│        Trial ◄──────── PublicationTrial + relation ────────► Publication         │
│                                                                                 │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────── TEXT PREPARATION ───────────────────────────────────┐
│                                                                                 │
│  Trial sections                              Publication sections               │
│  • Title                                     • Title                            │
│  • Official title                            • Abstract                         │
│  • Summary                                                                      │
│  • Detailed description                                                        │
│  • Eligibility criteria                                                        │
│                                                                                 │
│           Long sections are split into overlapping, ordered chunks              │
│                                                                                 │
│       Source ──► Section ──► Chunk {section, sequence, exact source text}        │
│                                                                                 │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────── NAMED-ENTITY RECOGNITION ───────────────────────────────┐
│                                                                                 │
│        OpenMed models + GLiNER-BioMed + HunFlair2                               │
│                                   │                                             │
│                                   ▼                                             │
│  NER mention                                                                    │
│  • Exact text span                         • Model and extraction method         │
│  • Section and chunk                       • External terminology links         │
│  • Start/end offsets                       • Confidence score                    │
│  • Labels: disease, cancer, drug, chemical, etc.                                │
│                                   │                                             │
│                     Normalize and connect entities                              │
│                       ┌───────────┴───────────┐                                 │
│                       ▼                       ▼                                 │
│                    Disease               Intervention                           │
│                                                                                 │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────── CLAIM EXTRACTION ───────────────────────────────────┐
│                                                                                 │
│     One section/chunk + its NER mentions are submitted to the claim LLM         │
│                                   │                                             │
│                                   ▼                                             │
│  Extract only explicit positive claims of:                                      │
│                                                                                 │
│                 “Intervention worked for Disease”                               │
│                                                                                 │
│  Validation gates                                                               │
│  • Evidence must be a verbatim excerpt from the supplied text                   │
│  • Returned NER IDs must exist in that section/chunk                            │
│  • Objectives, hypotheses, co-mentions and negative results are excluded        │
│                                   │                                             │
│                                   ▼                                             │
│  Candidate Claim                                                                │
│  • Claim type                              • Disease(s) and intervention(s)      │
│  • Evidence excerpt                        • Linked NER mentions                 │
│  • Trial or publication                    • Status: pending                     │
│  • Exact section/chunk                                                           │
│                                                                                 │
└───────────────────────────┬──────────────────────┬──────────────────────────────┘
                            │                      │
                            ▼                      ▼
┌─────────────────────────────────────┐   ┌───────────────────────────────────────┐
│ CLAIM JUDGEMENT                     │   │ CLAIM GROUPING                        │
│                                    │   │                                       │
│ Claim + complete source record      │   │ Match the complete normalized sets of │
│              │                     │   │ diseases and interventions.           │
│              ▼                     │   │                 │                     │
│ System-One / Jev                   │   │                 ▼                     │
│                                    │   │ ClaimGroup                            │
│ • Supports                         │   │ • Matching claims                     │
│ • Contradicts                      │   │ • Evidence summary                    │
│ • Unaddressed                      │   │ • Related trials                      │
│ • Source-support probability       │   │ • Related publications                │
│                                    │   │ • Maximum judgement score             │
└──────────────────┬──────────────────┘   └───────────────────┬───────────────────┘
                   │                                          │
                   └────────────────────┬─────────────────────┘
                                        ▼
┌──────────────────────── SOURCE-TRACKED EVIDENCE STORE ──────────────────────────┐
│                                                                                 │
│  PostgreSQL evidence graph                                                      │
│                                                                                 │
│  Trial ◄────► Publication                                                       │
│    │               │                                                            │
│    └──► Section / Chunk ◄── NER mention ◄── Disease / Intervention              │
│                 │                                                               │
│                 └──► Claim ──► Judgement                                        │
│                        │                                                        │
│                        └──► ClaimGroup                                           │
│                                                                                 │
│  Every candidate claim remains connected to the source text that produced it.  │
│                                                                                 │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────── HUMAN REVIEW WORKSPACE ─────────────────────────────┐
│                                                                                 │
│  Browse and search                                                              │
│  • Sources, trials and publications       • Diseases and interventions          │
│  • Claims and claim groups                • Evidence excerpts and source text    │
│  • NER provenance                        • Jev judgements                       │
│                                                                                 │
│  Reviewer action                                                                │
│  • Inspect the exact supporting section/chunk                                   │
│  • Mark claim pending, approved or rejected                                     │
│  • Add review notes                                                             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

The central system flow is:

```text
PUBLIC SOURCE
    → SOURCE VERSION CURRENTLY STORED
    → SECTION/CHUNK
    → NER MENTIONS
    → NORMALIZED ENTITIES
    → EVIDENCE-BACKED CLAIM
    → SOURCE-SUPPORT JUDGEMENT
    → CROSS-SOURCE CLAIM GROUP
    → HUMAN REVIEW
```

## Models

### Named-entity recognition and linking

- [OpenMed DiseaseDetect PubMed 335M](https://huggingface.co/OpenMed/OpenMed-NER-DiseaseDetect-PubMed-335M) detects disease mentions.
- [OpenMed PharmaDetect PubMed 335M](https://huggingface.co/OpenMed/OpenMed-NER-PharmaDetect-PubMed-335M) detects pharmaceutical and chemical mentions.
- [OpenMed PathologyDetect PubMed 335M](https://huggingface.co/OpenMed/OpenMed-NER-PathologyDetect-PubMed-335M) detects pathology concepts.
- [OpenMed OncologyDetect PubMed 335M](https://huggingface.co/OpenMed/OpenMed-NER-OncologyDetect-PubMed-335M) detects oncology concepts.
- [GLiNER-BioMed Large v1.0](https://huggingface.co/Ihor/gliner-biomed-large-v1.0) performs open biomedical NER using the system's requested labels.
- [HunFlair2 NER](https://huggingface.co/hunflair/hunflair2-ner) provides biomedical entity recognition.
- [HunFlair2 disease linker](https://flairnlp.github.io/flair/master/tutorial/tutorial-hunflair2/linking.html) normalizes disease mentions to identifiers such as MeSH IDs.

### Claim extraction and evidence synthesis

- [Meta Muse Spark 1.3 Contributor](https://dev.meta.ai/models/muse-spark) performs structured claim extraction and summarizes evidence within claim groups. The configured model ID is `muse-spark-1.3-contributor`.

### Claim judgement

- [TypeSafe Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) is called through the System One API to classify each claim as supported, contradicted, or unaddressed and return calibrated probabilities. The API's current model alias is documented as `jev-latest`.

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
- `./bin/test`: Runs environment verification and Django unit tests in disposable test databases; it does not write to the development database.
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
- **Status JSON**: [http://localhost:8001/status/](http://localhost:8001/status/)
- **PostgreSQL**: `localhost:5433` (db: `fl_db`, user: `postgres`)

## Code Examples

Notebooks in `notebooks/` demonstrate the interactive workflow (with `%load_ext autoreload`, `%autoreload 2`):

- `sources.ipynb`: PubMed / ClinicalTrials.gov fetching and upserts.
- `ner.ipynb`: NER extraction.
- `claims.ipynb`: claim extraction.
- `judgement.ipynb`: judgement scoring.
- `pipeline.ipynb`: end-to-end sequence (`fetch_and_upsert_trial`, `fetch_trial_publications`, then the six `jobs/pipeline.py` stages).
