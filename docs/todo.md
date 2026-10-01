in projects/1fl/django_app/lib/clinical_trials.py make a func which gets trial nct_id, checks trials.references which is in format:

```commandline
[
  {
    "pmid": "41115454",
    "type": "DERIVED",
    "citation": "Tan PB, Verschoor YL, van den Berg JG, Balduzzi S, Kok NFM, Ijsselsteijn ME, Moore K, Jurdi A, Tin A, Kaptein P, van Leerdam ME, Haanen JBAG, Voest EE, de Miranda NFCC, Schumacher TN, Wessels LFA, Chalabi M. Neoadjuvant immunotherapy in mismatch-repair-proficient colon cancers. Nature. 2025 Dec;648(8094):726-735. doi: 10.1038/s41586-025-09679-4. Epub 2025 Oct 20."
  },
  {
    "pmid": "39278994",
    "type": "DERIVED",
    "citation": "de Gooyer PGM, Verschoor YL, van den Dungen LDW, Balduzzi S, Marsman HA, Geukes Foppen MH, Grootscholten C, Dokter S, den Hartog AG, Verbeek WHM, Woensdregt K, van den Broek JJ, Oosterling SJ, Schumacher TN, Kuhlmann KFD, Beets-Tan RGH, Haanen JBAG, van Leerdam ME, van den Berg JG, Chalabi M. Neoadjuvant nivolumab and relatlimab in locally advanced MMR-deficient colon cancer: a phase 2 trial. Nat Med. 2024 Nov;30(11):3284-3290. doi: 10.1038/s41591-024-03250-w. Epub 2024 Sep 15."
  }
]
```

gets pmid and loads those publications, setting in `core_publicationtrial.relation` what it sees in `TYPE` (or default, if the value is invalid).

add calling this func in sources notebook.

----------------------------------------

the claim model must be different. it must have:

common created,modified,meta.
section
claim_type
FK to trial,
FK to publication,
FK to Chunk.
FK to disease.
FK to intervention.
(all fks nullable, at least 1 should exist)
drop other columns.

how we create them - 
make in projects/1fl/django_app/lib/claims.py a function.
it goes through the publications and trials that have ners but have no claim.
it takes a "analyzable bundle":
for publication: title, chunks
for trial: title, official_title, chunks
for each analyzable bundle it gets it as a text, section_name and collection of NERs,
and it uses our projects/1fl/django_app/lib/llm.py to send a request to LLM, asking it to analyze the text and NERs and suggest any claim it can do.
it uses prompt specific for claim_type.

have a dict with 1 claim_type for now: intervention_worked_for_disease
write  a prompt for it.


call this func in projects/1fl/notebooks/claims.ipynb

---------------

make a model Disease
fields:
common created,modified,meta.
name
mesh

let us make a func in projects/1fl/django_app/lib/diseases.py
process every ner which has in labels disease, cancer (case insensitive) (the list is const on the top of module)
find matching disease by name or by mesh.  See the structure of NER:

```commandline
{'text': 'chronic myeloid leukemia',
  'label': ['DISEASE', 'Disease', 'Cancer', 'Disease', 'Disease'],
  'start': 108,
  'end': 132,
  'score': 0.9999924103418986,
  'method': ['openmed', 'gliner', 'hunflair'],
  'model_name': ['OpenMed/OpenMed-NER-DiseaseDetect-PubMed-335M',
   'OpenMed/OpenMed-NER-PathologyDetect-PubMed-335M',
   'OpenMed/OpenMed-NER-OncologyDetect-PubMed-335M',
   'Ihor/gliner-biomed-large-v1.0',
   'hunflair2'],
  'links': [{'id': 'MESH:D015464', 'score': np.float32(203.84323)}]}
```

insert if not found.
set on NER FK to that disease.
connect it (using many-to-many) to the publication or trial, per NER FK


then

make a model Intervention
fields:
common created,modified,meta.
name
mesh

let us make a func in projects/1fl/django_app/lib/interventions.py
process every ner which has in labels 'CHEM', 'Simple_chemical', 'Drug', 'Chemical' (case insensitive) (the list is const on the top of module)
find matching intervention by name or by mesh.  See the structure of NER:

```commandline
{'text': 'chronic myeloid leukemia',
  'label': ['DISEASE', 'Disease', 'Cancer', 'Disease', 'Disease'],
  'start': 108,
  'end': 132,
  'score': 0.9999924103418986,
  'method': ['openmed', 'gliner', 'hunflair'],
  'model_name': ['OpenMed/OpenMed-NER-DiseaseDetect-PubMed-335M',
   'OpenMed/OpenMed-NER-PathologyDetect-PubMed-335M',
   'OpenMed/OpenMed-NER-OncologyDetect-PubMed-335M',
   'Ihor/gliner-biomed-large-v1.0',
   'hunflair2'],
  'links': [{'id': 'MESH:D015464', 'score': np.float32(203.84323)}]},
  
  {'text': 'imatinib',
  'label': ['CHEM', 'Simple_chemical', 'Drug', 'Chemical'],
  'start': 95,
  'end': 103,
  'score': 0.9999761581420898,
  'method': ['openmed', 'gliner', 'hunflair'],
  'model_name': ['OpenMed/OpenMed-NER-PharmaDetect-PubMed-335M',
   'OpenMed/OpenMed-NER-OncologyDetect-PubMed-335M',
   'Ihor/gliner-biomed-large-v1.0',
   'hunflair2'],
  'links': []}
```

insert if not found.
set on NER FK to that intervention.
connect it (using many-to-many) to the publication or trial, per NER FK

in sources notebook, after calling `save_ner_trials()` call also these func `save_ner_interventions(), save_ner_diseases()`

------------------

what are our high level funcs, and how do we cal them in sequence?
make a notebook `pipeline` (follow the pattern of other notebooks),  with the sequence of calls.

----------

add package `typesafe-sdk`
see how to use it https://docs.typesafe.ai/sdk/python/usage

create model Judgement
fields:
common created,modified,meta.
method str
score float
FK to claim

now, for every claim which has no judgements,
pass the claim, 
and its trial or publication fields -
TRIAL_FIELDS_TO_CHUNK, TRIAL_FIELDS_NOT_TO_CHUNK
PUBLICATION_FIELDS_TO_CHUNK, PUBLICATION_FIELDS_NOT_TO_CHUNK

to the system_one model,
and ask to score is this claim correct or not.
store it in judgement

add the call of this func to notebook pipeline, and new notebook `judgement`

-------------------------

make in 
django_app/lib/clinical_trials.py , django_app/lib/pubmed.py
funcs which can get query and search for trials and publications, and return results as id, link, title.
add to sources notebook calls whith example for searching for colorectal cancer

----------------------------

make lib/logs.py
make a func for loggin with formatter and level,
and let every module use it.
in each our func give useful loggin;  func call args, func call kwargs, func return value, log before and after calling 3rd-party resources,
use levels as needed; more debugs than info; some warnings if it is needed; if any exception then error log...
follow good practice.  and make our whole system log well.

-----------

Claim should have column:

evidence str

so when LLM returns them,  save them to the column not to meta.

in migration update the current table records.


--------------------

create implementation plan for our web ui. save implementation plan to .md file.

we want a django rest framework and 1 page app.

authorization is not needed
the page is split horizontally to 40%/60%

upper pane:

we have tabs for seeing tables of:

claims
diseases
interventions
trials
publications

user can switch tab to change the upper pane,
it shows a table for those models, with filters, text-search, pagination, sortable columns.

when user cliks any row, more details open in the lower pane for that model record.

lower pane:

looks differently depending on what is opened in it:

claims:
on left:
show all details of the record
emphasized box of "judgement"
status selector and "notes" and button to save.
(notes are saved into additiional notes column you add to Claim)
on right:
related section text (can be chunk, or not-chunked-section)
list of diseases for this claim
list of interventions for this claim
table of NERs for this claim
things which belong to another model record are clickable and they open a modal with all details of that model record


diseases:
on left:
show all details of the record
on right:
table of claims for this disease
things which belong to another model record are clickable and they open a modal with all details of that model record


interventions:
on left:
show all details of the record
on right:
table of claims for this intervention
things which belong to another model record are clickable and they open a modal with all details of that model record


trials:
on left:
show all details of the record
on right:
table of claims
list of publications
things which belong to another model record are clickable and they open a modal with all details of that model record


publications:
on left:
show all details of the record
on right:
table of claims
list of trials
things which belong to another model record are clickable and they open a modal with all details of that model record


-------------

make a directory jobs/
there will be scripts that can be run inside the container.

make a script `jobs/pipeline.py` which runs inside the container, which runs these:

`lib.ner.save_ner_trials()`
`lib.ner.save_ner_publications()`
`lib.interventions.save_ner_interventions()`
`lib.diseases.save_ner_diseases()`
`lib.claims.save_claims()`
`lib.judgement.save_judgements()`

with logging of course.

then make a bin/ script which runs it inside a already running django container.

-------------------

web UI:

remove the top block:
"Review workspace
1FL Clinical Knowledge Platform"

for claims: make the form compact in 1 row

for trials and publications: make the loading form compact in 1 line


-------------------------

in web ui, add new tab:  Sources

it has form to search by keyword publications and trials (radio button to select which
use our funcs search_trials, search_publications.
and shows in the top pane a table of findings
when you click the record in the upper pane,
show its details in the lower pane, on left.
with the link to open the link to pubmed or clinicaltrials site in a new tab.
and in the lower pane on right, show button to fetch it into our database (our fetch_and_upsert_* funcs);
for clinical trial there should be also checkbox to fetch with its publications. - fetch_trial_publications

after adding this, you can drop the forms for fetching we have now inside the tabs: trials, publications.

------------------------------

new model: ClaimGroup
usual fields: created, modified, meta
many to many to claims, diseases, interventions.
evidence_summary

these connect Claims which have mathcing diseases and the interventions


let us make a function `add_claim_to_claim_group` which will:
get claim
find a ClaimGroup with the same diseases and the interventions,
add claim to this claimGroup.

let us make a function `pair_claim_to_another_in_claim_group` which will:
get claim,
find another claim, which is not in ClaimGroup yet, with the same diseases and the interventions,
create a ClaimGroup and add these both to it.

let us make a function `add_claim_to_existing_or_new_claim_group` which will:
get claim,
find a ClaimGroup with the same diseases and the interventions,
add claim to this claimGroup.
if it did not find/do anything, then call pair_claim_to_another_in_claim_group.


let us make a function `process_claims_to_claim_groups` which will:
process one by one every claim which is not in claimGroup
for each call add_claim_to_existing_or_new_claim_group.
add this func call to notebook claims.

also, make a signal for creation of claim,
after it is created, call add_claim_to_existing_or_new_claim_group.


1.
  DRY all claim creations through 1 func, and add this add_claim_to_existing_or_new_claim_group after other calls, when the claim entities are connected.
2.
yes, both sets are equal to both sets of another.  empty is equal to empty.
3.
if we require exact match, then claim can belong to 1 claimgroup only.  yes, FK is better.
4.
claims grouped in claimgroup can be any types, trials,publications
5.
changing of claim may lead to its disconnecting from group, and move to another group.  Do not drop existing group even if 1 or 0 claims belong to it; we can leave it.
6.
make a func to find and merge together claimgroups with identical diseases&interventions. (the 2nd is dropped, and its claims  connected to the 1st one).  put this func call to the claims notebook.
7.
evidence_summary - make a func summarize_evidences which will get evidences of all claims in that group, send to LLM asking to summarize them;  use our llm.py , make a prompt to make summary.
8.
on claimgroup, have a field synced boolean ; every time claimgroup is updated, or some claim is linked/unlinked - set it to false
9.
make a func which processes all claimgroups where synced=false, and updates evidence_summary with result of summarize_evidences called for all evidences of the group.


--------------------------


