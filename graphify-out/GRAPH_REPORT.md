# Graph Report - trials_publications_claims  (2026-10-02)

## Corpus Check
- 111 files · ~225,816 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: .ipynb 5, (none) 3, .css 1)

## Summary
- 911 nodes · 1756 edges · 100 communities (42 shown, 48 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 337 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Claim Group
- Workspace Js
- Evidence Backed Claim
- Publication Components
- Api Py
- Llm Py
- Core Urls Py
- Core Models Py
- Disease Components
- Logs Py
- Logged Components
- Patch Components
- Linked Relations Contract Test
- Ner Persistence Test Case
- Ner Entities Test
- Workspace List Api Test
- Fetch And Upsert Trial
- Logging Test Case
- Publication View Set
- Fetch And Upsert Publication
- Refetch Source Test Case
- Publication 22763196 Antiangiogenic Drugs
- Selected Claim 109
- Workspace Detail Api Test
- Claim Components
- Pipeline Scripts Test Case
- Import Api Test Case
- Admin Py
- Judgement Components
- To Internal Value
- Test Api Py
- Selected Publication Detail Panel
- Trial 07736495 Protective Role
- Trial 07736495 Protective Role 2
- Save Judgements
- Claim Group 3 Two
- Claim Group Api Test
- Chunk Test Case
- Db Py
- 4403 Disease Mention In
- Selected Intervention Cholestyramine
- Claim Review Patch Test
- Claim List Serializer
- Selected Trial Detail Panel
- Django App Init Py
- Text Tools Py
- Disease Browser With Searchable
- Migration Scripts Test Case
- Pub Med Search Test
- Django App Service
- Test Case
- Text Tools Test Case
- Core Config
- Manage Py
- Install Test Case
- Preload Models Test Case
- Claim Evidence Migration Test
- Require Csrf Token
- 0009 Claim Entity Relations
- 0011 Ner Section Py
- 0012 Claim Evidence Py
- 0016 Claim Group Status
- Install Components
- Makemigrations Components
- Manage Components
- Migrate Components
- Pipeline Components
- Start Components
- Stop Components
- Test Components
- Workspace Pagination
- 0001 Initial Py
- 0002 Trial Acronym Trial
- 0003 Publication Authors Publication
- 0004 Chunk Py
- 0005 Ner Py
- 0006 Alter Publicationtrial Relation
- 0007 Replace Claim Py
- 0008 Ner Entities Py
- 0010 Judgement Py
- 0013 Claim Status Py
- 0014 Claim Notes Py
- 0015 Claim Group Py
- 0017 Expand Publicationtrial Relation
- 0018 Claims Generated Py
- Prompts Claim Groups Py
- Prompts Claims Py
- Prompts Init Py
- Prompts Judgement Py
- Settings Py

## God Nodes (most connected - your core abstractions)
1. `Trial` - 47 edges
2. `Publication` - 47 edges
3. `logged()` - 37 edges
4. `Claim` - 36 edges
5. `Disease` - 29 edges
6. `Intervention` - 27 edges
7. `make()` - 24 edges
8. `WorkspaceListApiTestCase` - 24 edges
9. `WorkspaceDetailApiTestCase` - 24 edges
10. `clear()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `ClaimGroupApiTestCase` --uses--> `Disease`  [INFERRED]
  tests/django_app/core/test_api.py → django_app/core/models.py
- `WorkspaceDetailApiTestCase` --uses--> `Disease`  [INFERRED]
  tests/django_app/core/test_api.py → django_app/core/models.py
- `WorkspaceListApiTestCase` --uses--> `Disease`  [INFERRED]
  tests/django_app/core/test_api.py → django_app/core/models.py
- `ModelSanityTestCase` --uses--> `Disease`  [INFERRED]
  tests/django_app/core/test_models.py → django_app/core/models.py
- `LinkedRelationsContractTestCase` --uses--> `Disease`  [INFERRED]
  tests/django_app/core/test_workspace.py → django_app/core/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Source to review pipeline** — readme_trial, readme_section_chunk, readme_ner, readme_claim, readme_judgement, readme_human_review [EXTRACTED 1.00]

## Communities (100 total, 48 thin omitted)

### Community 0 - "Claim Group"
Cohesion: 0.06
Nodes (41): ClaimGroup, invalidate_claim_group(), invalidate_deleted_claim(), invalidate_group_entities(), invalidate_updated_group(), publication_post_save_link_trials(), Django signals and automatic linking helpers for Trials and Publications., Trigger trial-to-publications link updates on Trial insert or update. (+33 more)

### Community 1 - "Workspace Js"
Cohesion: 0.14
Nodes (58): badgeCell(), buildListUrl(), cellValue(), clear(), csrfToken(), currentConfig(), diseaseRows(), emptyNote() (+50 more)

### Community 2 - "Evidence Backed Claim"
Cohesion: 0.06
Nodes (44): Record details pane, Shared record and operation modal, External source search form, Searchable paginated record table, Workspace record tabs, Biomedical NLP model catalog, MeSH, UMLS (+36 more)

### Community 3 - "Publication Components"
Cohesion: 0.11
Nodes (18): date, SourceDetailView, parse_ctgov_date(), parse_pubmed_date(), Publication, Any, Parse a ClinicalTrials.gov date string (YYYY-MM-DD, YYYY-MM, or YYYY) into…, Represents a clinical study / trial (e.g., from ClinicalTrials.gov). (+10 more)

### Community 4 - "Api Py"
Cohesion: 0.14
Nodes (23): BiomarkerSerializer, ChunkSerializer, ClaimDetailSerializer, ClaimGroupListSerializer, ClaimGroupNotesSerializer, ClaimReviewSerializer, DiseaseDetailSerializer, DiseaseSerializer (+15 more)

### Community 5 - "Llm Py"
Cohesion: 0.12
Nodes (21): extract_structured(), get_default_model(), get_instructor_client(), get_llm_api_key(), get_llm_uri(), _load_secrets(), LLM and Instructor helpers for structured extraction., Extract structured data conforming to a Pydantic model using Instructor. (+13 more)

### Community 6 - "Core Urls Py"
Cohesion: 0.11
Nodes (12): APIView, BaseReadOnlyViewSet, ClaimGroupViewSet, ClaimViewSet, DiseaseViewSet, _ImportView, InterventionViewSet, SourceSearchView (+4 more)

### Community 7 - "Core Models Py"
Cohesion: 0.13
Nodes (17): Biomarker, Intervention, Observation, PublicationTrial, PublicationTrialRelation, Core ORM models for clinical and biomedical knowledge platform., Represents a therapeutic intervention, drug, biologic, device, or procedure., Represents a biological marker, genetic variant, receptor, or expression target. (+9 more)

### Community 8 - "Disease Components"
Cohesion: 0.13
Nodes (14): BaseModel, Chunk, Disease, Meta, Ner, Abstract base model providing standard audit timestamps and JSONB metadata.…, Represents a medical condition, indication, or disease phenotype., ClaimSuggestions (+6 more)

### Community 9 - "Logs Py"
Cohesion: 0.12
Nodes (14): ClinicalTrials.gov database ingestion., Search the first 100 matching studies without saving them., # TODO: fetch_trial_publications() can be long-running (one PubMed fetch per, search_trials(), wrapper(), Shared, payload-safe logging for the ingestion pipeline., Never render payloads or object reprs (which may contain credentials/text)., _summary() (+6 more)

### Community 10 - "Logged Components"
Cohesion: 0.24
Nodes (16): logged(), Log calls and results at DEBUG, failures at ERROR, without changing behavior., gliner_entities(), _gliner_model(), hunflair2_entities(), _hunflair2_linkers(), _hunflair2_model(), _merge_entities() (+8 more)

### Community 11 - "Patch Components"
Cohesion: 0.18
Nodes (3): Analyze NER-bearing sections of publications and trials not yet processed., save_claims(), SourceSearchApiTestCase

### Community 12 - "Linked Relations Contract Test"
Cohesion: 0.12
Nodes (4): LinkedRelationsContractTestCase, TestCase, JSON the lower-pane related tables consume (Task 6, Step 1)., WorkspaceShellTestCase

### Community 13 - "Ner Persistence Test Case"
Cohesion: 0.12
Nodes (5): DatabaseTestCase, NerPersistenceTestCase, extract(), NerTestCase, TestCase

### Community 14 - "Ner Entities Test"
Cohesion: 0.22
Nodes (7): save_ner_diseases(), mesh_from_uid(), Shared matching for diseases and interventions from source records and NER., upsert_entity(), save_ner_interventions(), NerEntitiesTest, TestCase

### Community 16 - "Fetch And Upsert Trial"
Cohesion: 0.19
Nodes (10): fetch_and_upsert_trial(), fetch_study_v2(), fetch_trial_publications(), Any, Fetch and upsert one study by NCT ID or payload, or a list of NCT IDs. Lists…, Fetch a single study by NCT ID from ClinicalTrials.gov API v2 via httpx., Link publications for saved trials; lists return links in input order., ClinicalTrialsTestCase (+2 more)

### Community 17 - "Logging Test Case"
Cohesion: 0.14
Nodes (7): get_logger(), Return a module logger; optionally configure its level and console format., Logger, LoggingTestCase, inner(), outer(), TestCase

### Community 18 - "Publication View Set"
Cohesion: 0.14
Nodes (7): action, NerViewSet, _parse_bool_param(), _parse_int_param(), PublicationViewSet, RefetchMixin, TrialViewSet

### Community 19 - "Fetch And Upsert Publication"
Cohesion: 0.20
Nodes (7): Update or create links between the given Publication and any Trials in the…, update_publication_trial_links(), fetch_and_upsert_publication(), Any, Fetch and upsert a publication by PMID or payload, or a list of PMIDs. Lists…, PubMedTestCase, TestCase

### Community 20 - "Refetch Source Test Case"
Cohesion: 0.25
Nodes (4): Refresh a saved source; leave disease/intervention rows and existing…, refetch_source(), TestCase, RefetchSourceTestCase

### Community 21 - "Publication 22763196 Antiangiogenic Drugs"
Cohesion: 0.18
Nodes (14): Aflibercept, Angiogenesis in tumor development and progression, Antiangiogenic drugs, Bevacizumab, Publication claims panel with review status, Colorectal cancer, Named entities panel with entity labels and scores, Bevacizumab and aflibercept showed survival benefit in phase III trials (+6 more)

### Community 22 - "Selected Claim 109"
Cohesion: 0.15
Nodes (14): Claim 109 evidence excerpt, Claim search and filters, Paginated claims table, Claims review workspace, Colorectal cancers, PDT intervention, Jev supports judgement, score 0.86, Named entity mentions (+6 more)

### Community 24 - "Claim Components"
Cohesion: 0.18
Nodes (4): Claim, A scientific finding supported by a source section., ModelSanityTestCase, TestCase

### Community 27 - "Admin Py"
Cohesion: 0.31
Nodes (10): BiomarkerAdmin, ClaimAdmin, DiseaseAdmin, InterventionAdmin, ObservationAdmin, PublicationAdmin, PublicationTrialAdmin, PublicationTrialInline (+2 more)

### Community 28 - "Judgement Components"
Cohesion: 0.24
Nodes (5): ClaimGroupDetailSerializer, _ner_rows(), Return {kind, id, section, text} or None per workspace contract., resolve_section_text(), Judgement

### Community 29 - "To Internal Value"
Cohesion: 0.24
Nodes (4): ImportPayloadSerializer, PublicationImportSerializer, PublicationImportView, TrialImportSerializer

### Community 30 - "Test Api Py"
Cohesion: 0.22
Nodes (5): capture_lib_logs(), _ImportLogHandler, Capture payload-safe ingestion messages for one import request., Forward this context's lib.* records without mixing concurrent requests., capture()

### Community 31 - "Selected Publication Detail Panel"
Cohesion: 0.24
Nodes (11): Publication claims panel, Head and neck cancer, Named entities panel, Oral mucositis, Publication 27555604: oral silymarin for radiotherapy induced mucositis, Selected publication detail panel, Publications browser, Searchable publications table (+3 more)

### Community 32 - "Trial 07736495 Protective Role"
Cohesion: 0.24
Nodes (11): Ain Shams University, trial organization and lead sponsor, Alpha-lipoic acid 600 mg twice daily drug intervention, Seven pending intervention_worked_for_disease claims for trial NCT07736495, Colorectal cancer, Trial filters: search, status, phase, has results, publication ID, Chemotherapy-induced oral mucositis, Related publications for trial NCT07736495, including PMIDs 28062278, 36290656, 16904799, and 33299302, Trials browser with searchable list and selected-trial detail (+3 more)

### Community 33 - "Trial 07736495 Protective Role 2"
Cohesion: 0.24
Nodes (11): Ain Shams University, trial organization and lead sponsor, Alpha-lipoic acid 600 mg twice daily drug intervention, Seven pending intervention_worked_for_disease claims for trial NCT07736495, Colorectal cancer, Trial filters: search, status, phase, has results, publication ID, Chemotherapy-induced oral mucositis, Related publications for trial NCT07736495, including PMIDs 28062278, 36290656, 16904799, and 33299302, Trials browser with searchable list and selected-trial detail (+3 more)

### Community 34 - "Save Judgements"
Cohesion: 0.27
Nodes (5): Score extracted claims against their original source material., Evaluate claims without judgements using System One., save_judgements(), JudgementTestCase, TestCase

### Community 35 - "Claim Group 3 Two"
Cohesion: 0.27
Nodes (10): Alpha-lipoic acid intervention, Claim 67: intervention_worked_for_disease evidence from 800 mg/day alpha-lipoic acid abstract; pending, Claim 68: intervention_worked_for_disease evidence from 1200 mg/day alpha-lipoic acid abstract; pending, ClaimGroup 3: two excerpts report IFG and IGT return-to-euglycemia counts in alpha-lipoic acid groups; 800 mg/day: 5 IFG and 1 IGT; 1200 mg/day: 11 IFG and 3 IGT. Denominators and controls are absent, so efficacy cannot be inferred. Pending judgement 1.0, Claim group browser with evidence summaries, status, judgement, and linked-entity counts, Selected claim group detail with evidence summary, judgement scores, notes, and linked records, Searchable table of three claim groups with pending status and maximum judgement, IFG, MeSH C563242 (+2 more)

### Community 38 - "Db Py"
Cohesion: 0.22
Nodes (8): check_db_connection(), execute_query(), get_db_version(), Any, Database helpers using Django ORM and django.db., Verify that PostgreSQL database is reachable via Django connection., Return PostgreSQL server version., Execute raw SQL query and return rows as list of dictionaries.

### Community 39 - "4403 Disease Mention In"
Cohesion: 0.25
Nodes (9): Chunk 241: publication abstract containing the CRC mention, Disease 232: colorectal cancers, MeSH D015179, NER search and filters by trial, publication, chunk, disease, intervention, claim, label, and section, NER 4403: CRC, disease mention in abstract, score 0.9998717308044434, NER browser with entity list and linked-record detail, Selected NER detail panel with extraction metadata and linked records, NER extraction methods: OpenMed, GLiNER, and HunFlair, Paginated NER results table with text, label, score, section, model count, and modified time (+1 more)

### Community 40 - "Selected Intervention Cholestyramine"
Cohesion: 0.22
Nodes (9): Abstract evidence excerpt, Selected intervention: cholestyramine, Claim 112: intervention_worked_for_disease, Intervention detail panel, Intervention search and MeSH filter, Paginated intervention table, Interventions workspace, Pending claim review status (+1 more)

### Community 42 - "Claim List Serializer"
Cohesion: 0.32
Nodes (4): _chunk_conflicts(), ClaimListSerializer, Return (source_kind, source_id, source_label) per workspace contract., resolve_claim_source()

### Community 43 - "Selected Trial Detail Panel"
Cohesion: 0.25
Nodes (8): Not in database status, Fetch trial action, Fetch with publications option, NCT05289076 clinical trial, Source keyword search, Sources workspace screenshot, Selected trial detail panel, Clinical trial search results

### Community 45 - "Text Tools Py"
Cohesion: 0.53
Nodes (5): Split text at natural boundaries with overlap to retain edge entities., _replace_chunks(), save_publication_chunks(), save_trial_chunks(), split_ner_text()

### Community 46 - "Disease Browser With Searchable"
Cohesion: 0.40
Nodes (6): Linked claims panel showing no claims for disease 629, Disease 629: intestinal inflammation, MeSH D004751, Disease browser with searchable catalog and selected-disease detail, Selected disease detail showing identifiers, timestamps, and linked claims, Paginated disease table with ID, name, MeSH, claim count, and modified time; 441 records, Disease filters: free-text search and MeSH identifier

### Community 48 - "Pub Med Search Test"
Cohesion: 0.40
Nodes (4): PubMedSearchTestCase, patch, SimpleTestCase, _response()

### Community 49 - "Django App Service"
Cohesion: 0.50
Nodes (5): Django app service, Jupyter service, PostgreSQL service, Django, PostgreSQL Python drivers

### Community 53 - "Manage Py"
Cohesion: 0.50
Nodes (3): main(), Django's command-line utility for administrative tasks., Run administrative tasks.

## Knowledge Gaps
- **73 isolated node(s):** `Migration`, `Migration`, `Migration`, `Migration`, `Migration` (+68 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 384 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **48 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Trial` connect `Publication Components` to `Claim Group`, `Api Py`, `Core Urls Py`, `Core Models Py`, `Disease Components`, `Logged Components`, `Patch Components`, `Linked Relations Contract Test`, `Ner Persistence Test Case`, `Ner Entities Test`, `Workspace List Api Test`, `Fetch And Upsert Trial`, `Publication View Set`, `Fetch And Upsert Publication`, `Refetch Source Test Case`, `Workspace Detail Api Test`, `Claim Components`, `Import Api Test Case`, `Admin Py`, `Judgement Components`, `Save Judgements`, `Claim Group Api Test`, `Chunk Test Case`, `Test Case`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `Publication` connect `Publication Components` to `Claim Group`, `Api Py`, `Core Urls Py`, `Core Models Py`, `Disease Components`, `Logged Components`, `Patch Components`, `Linked Relations Contract Test`, `Ner Persistence Test Case`, `Ner Entities Test`, `Workspace List Api Test`, `Fetch And Upsert Trial`, `Publication View Set`, `Fetch And Upsert Publication`, `Refetch Source Test Case`, `Workspace Detail Api Test`, `Claim Components`, `Import Api Test Case`, `Admin Py`, `Judgement Components`, `Save Judgements`, `Claim Group Api Test`, `Chunk Test Case`, `Test Case`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `logged()` connect `Logged Components` to `Save Judgements`, `Llm Py`, `Db Py`, `Logs Py`, `Patch Components`, `Text Tools Py`, `Ner Entities Test`, `Fetch And Upsert Trial`, `Logging Test Case`, `Fetch And Upsert Publication`, `Refetch Source Test Case`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `Trial` (e.g. with `ClaimGroupDetailSerializer` and `SourceDetailView`) actually correct?**
  _`Trial` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 36 inferred relationships involving `Publication` (e.g. with `ClaimGroupDetailSerializer` and `PublicationDetailSerializer`) actually correct?**
  _`Publication` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `Claim` (e.g. with `ClaimDetailSerializer` and `ClaimListSerializer`) actually correct?**
  _`Claim` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `Disease` (e.g. with `DiseaseDetailSerializer` and `DiseaseSerializer`) actually correct?**
  _`Disease` has 21 INFERRED edges - model-reasoned connections that need verification._