"""Core ORM models for clinical and biomedical knowledge platform."""

import datetime
from typing import Any, Dict, Optional
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils import timezone


def parse_ctgov_date(date_str: Optional[str]) -> Optional[datetime.date]:
    """Parse a ClinicalTrials.gov date string (YYYY-MM-DD, YYYY-MM, or YYYY) into datetime.date."""
    if not date_str:
        return None
    cleaned = str(date_str).strip()
    try:
        return datetime.date.fromisoformat(cleaned)
    except ValueError:
        pass
    parts = cleaned.split('-')
    try:
        if len(parts) == 2:
            return datetime.date(int(parts[0]), int(parts[1]), 1)
        if len(parts) == 1 and len(parts[0]) == 4:
            return datetime.date(int(parts[0]), 1, 1)
    except Exception:
        pass
    return None


def parse_pubmed_date(date_val: Any) -> Optional[datetime.date]:
    """Parse various PubMed date formats (datetime, date, ISO string, YYYY-MM-DD, YYYY-MM, YYYY) into datetime.date."""
    if not date_val:
        return None
    if isinstance(date_val, datetime.date):
        if isinstance(date_val, datetime.datetime):
            return date_val.date()
        return date_val
    cleaned = str(date_val).strip()
    try:
        return datetime.date.fromisoformat(cleaned)
    except ValueError:
        pass
    parts = cleaned.split('-')
    try:
        if len(parts) == 2 and len(parts[0]) == 4:
            return datetime.date(int(parts[0]), int(parts[1]), 1)
        if len(parts) == 1 and len(parts[0]) == 4 and parts[0].isdigit():
            return datetime.date(int(parts[0]), 1, 1)
    except Exception:
        pass
    for fmt in ("%Y %b %d", "%Y %b", "%Y/%m/%d", "%Y/%m"):
        try:
            return datetime.datetime.strptime(cleaned, fmt).date()
        except Exception:
            pass
    return None


def sanitize_json_payload(obj: Any) -> Any:
    """Recursively sanitize complex nested objects for JSONB serialization."""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {
            str(k): sanitize_json_payload(v)
            for k, v in obj.items()
            if k not in ('content', '_root')
        }
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_json_payload(x) for x in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if hasattr(obj, 'tag') and hasattr(obj, 'attrib'):
        return None
    return str(obj)


class BaseModel(models.Model):
    """
    Abstract base model providing standard audit timestamps and JSONB metadata.
    Maximizes utility and schema consistency across all domain entities.
    """
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class Focus(BaseModel):
    """A saved search with durable pending source-ingestion counts."""

    query = models.CharField(max_length=500, unique=True)
    ingest_trials_count = models.PositiveIntegerField(default=0)
    ingest_publications_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created', '-id']
        verbose_name = 'Focus'
        verbose_name_plural = 'Focuses'

    def __str__(self) -> str:
        return self.query


class Disease(BaseModel):
    """Represents a medical condition, indication, or disease phenotype."""
    name = models.CharField(max_length=255, unique=True, db_index=True)
    mesh = models.CharField(max_length=64, blank=True, default='', db_index=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Disease'
        verbose_name_plural = 'Diseases'

    def __str__(self) -> str:
        return self.name


class Intervention(BaseModel):
    """Represents a therapeutic intervention, drug, biologic, device, or procedure."""
    name = models.CharField(max_length=255, unique=True, db_index=True)
    mesh = models.CharField(max_length=64, blank=True, default='', db_index=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Intervention'
        verbose_name_plural = 'Interventions'

    def __str__(self) -> str:
        return self.name


class Biomarker(BaseModel):
    """Represents a biological marker, genetic variant, receptor, or expression target."""
    name = models.CharField(max_length=255, unique=True, db_index=True)
    biomarker_type = models.CharField(max_length=100, blank=True, default='', db_index=True)
    gene = models.CharField(max_length=100, blank=True, default='', db_index=True)
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['name']
        verbose_name = 'Biomarker'
        verbose_name_plural = 'Biomarkers'

    def __str__(self) -> str:
        return self.name


class Trial(BaseModel):
    """Represents a clinical study / trial (e.g., from ClinicalTrials.gov)."""
    # Core identification & registry info
    nct_id = models.CharField(max_length=32, unique=True, db_index=True)
    title = models.TextField()
    official_title = models.TextField(blank=True, default='')
    acronym = models.CharField(max_length=64, blank=True, default='', db_index=True)
    org_study_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    organization = models.CharField(max_length=255, blank=True, default='')

    # Status, phase & study classification
    phase = models.CharField(max_length=100, blank=True, default='', db_index=True)
    status = models.CharField(max_length=100, blank=True, default='', db_index=True)
    study_type = models.CharField(max_length=64, blank=True, default='', db_index=True)
    lead_sponsor = models.CharField(max_length=255, blank=True, default='', db_index=True)
    collaborators = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True, default='')
    detailed_description = models.TextField(blank=True, default='')

    # Key timeline dates
    start_date = models.DateField(null=True, blank=True, db_index=True)
    start_date_type = models.CharField(max_length=32, blank=True, default='')
    completion_date = models.DateField(null=True, blank=True, db_index=True)
    completion_date_type = models.CharField(max_length=32, blank=True, default='')
    primary_completion_date = models.DateField(null=True, blank=True)
    first_posted_date = models.DateField(null=True, blank=True)
    last_update_posted_date = models.DateField(null=True, blank=True)

    # Enrollment & participant population
    enrollment = models.IntegerField(null=True, blank=True, db_index=True)
    enrollment_type = models.CharField(max_length=32, blank=True, default='')
    sex = models.CharField(max_length=32, blank=True, default='')
    minimum_age = models.CharField(max_length=32, blank=True, default='')
    maximum_age = models.CharField(max_length=32, blank=True, default='')
    healthy_volunteers = models.BooleanField(null=True, blank=True)
    eligibility_criteria = models.TextField(blank=True, default='')

    # Governance & results
    has_results = models.BooleanField(default=False, db_index=True)

    # Claims extraction bookkeeping: True once LLM has attempted claims,
    # even if zero claims were produced. Reset to False on source update.
    claims_generated = models.BooleanField(default=False, db_index=True)

    # Structured JSONB columns for nested clinical trial attributes
    conditions = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    design_info = models.JSONField(default=dict, blank=True)
    arms = models.JSONField(default=list, blank=True)
    interventions_list = models.JSONField(default=list, blank=True)
    outcomes = models.JSONField(default=dict, blank=True)
    locations = models.JSONField(default=list, blank=True)
    contacts = models.JSONField(default=dict, blank=True)
    references = models.JSONField(default=list, blank=True)

    # Raw full API response payload from ClinicalTrials.gov
    raw = models.JSONField(default=dict, blank=True, help_text="Raw API response payload from ClinicalTrials.gov")

    # M2M Relationships with core biomedical knowledge graph
    diseases = models.ManyToManyField(Disease, related_name='trials', blank=True)
    interventions = models.ManyToManyField(Intervention, related_name='trials', blank=True)
    biomarkers = models.ManyToManyField(Biomarker, related_name='trials', blank=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Trial'
        verbose_name_plural = 'Trials'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if 'raw_json' in kwargs and 'raw' not in kwargs:
            kwargs['raw'] = kwargs.pop('raw_json')
        super().__init__(*args, **kwargs)

    @property
    def raw_json(self) -> Dict[str, Any]:
        """Convenience property alias for raw JSONB response payload."""
        return self.raw

    @raw_json.setter
    def raw_json(self, value: Dict[str, Any]) -> None:
        self.raw = value

    @classmethod
    def parse_api_study(cls: "type[Trial]", study: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured model fields from a ClinicalTrials.gov API v2 study payload."""
        protocol = study.get("protocolSection", {})
        ident = protocol.get("identificationModule", {})
        status = protocol.get("statusModule", {})
        sponsor = protocol.get("sponsorCollaboratorsModule", {})
        design = protocol.get("designModule", {})
        desc = protocol.get("descriptionModule", {})
        cond = protocol.get("conditionsModule", {})
        arms = protocol.get("armsInterventionsModule", {})
        outcomes = protocol.get("outcomesModule", {})
        elig = protocol.get("eligibilityModule", {})
        contacts = protocol.get("contactsLocationsModule", {})
        refs = protocol.get("referencesModule", {})

        phases = design.get("phases", [])
        phase_str = ", ".join(phases) if phases else ""

        return {
            "nct_id": ident.get("nctId", ""),
            "title": ident.get("briefTitle", ""),
            "official_title": ident.get("officialTitle", ""),
            "acronym": ident.get("acronym", ""),
            "org_study_id": ident.get("orgStudyIdInfo", {}).get("id", ""),
            "organization": ident.get("organization", {}).get("fullName", ""),
            "status": status.get("overallStatus", ""),
            "phase": phase_str,
            "study_type": design.get("studyType", ""),
            "lead_sponsor": sponsor.get("leadSponsor", {}).get("name", ""),
            "collaborators": sponsor.get("collaborators", []),
            "summary": desc.get("briefSummary", ""),
            "detailed_description": desc.get("detailedDescription", ""),
            "start_date": parse_ctgov_date(status.get("startDateStruct", {}).get("date")),
            "start_date_type": status.get("startDateStruct", {}).get("type", ""),
            "completion_date": parse_ctgov_date(status.get("completionDateStruct", {}).get("date")),
            "completion_date_type": status.get("completionDateStruct", {}).get("type", ""),
            "primary_completion_date": parse_ctgov_date(status.get("primaryCompletionDateStruct", {}).get("date")),
            "first_posted_date": parse_ctgov_date(status.get("studyFirstPostDateStruct", {}).get("date")),
            "last_update_posted_date": parse_ctgov_date(status.get("lastUpdatePostDateStruct", {}).get("date")),
            "enrollment": design.get("enrollmentInfo", {}).get("count"),
            "enrollment_type": design.get("enrollmentInfo", {}).get("type", ""),
            "sex": elig.get("sex", ""),
            "minimum_age": elig.get("minimumAge", ""),
            "maximum_age": elig.get("maximumAge", ""),
            "healthy_volunteers": elig.get("healthyVolunteers"),
            "eligibility_criteria": elig.get("eligibilityCriteria", ""),
            "has_results": study.get("hasResults", False),
            "conditions": cond.get("conditions", []),
            "keywords": cond.get("keywords", []),
            "design_info": design.get("designInfo", {}),
            "arms": arms.get("armGroups", []),
            "interventions_list": arms.get("interventions", []),
            "outcomes": {
                "primaryOutcomes": outcomes.get("primaryOutcomes", []),
                "secondaryOutcomes": outcomes.get("secondaryOutcomes", []),
            },
            "locations": contacts.get("locations", []),
            "contacts": {
                "centralContacts": contacts.get("centralContacts", []),
                "overallOfficials": contacts.get("overallOfficials", []),
            },
            "references": refs.get("references", []),
            "raw": study,
        }

    def __str__(self) -> str:
        return f"[{self.nct_id}] {self.title[:80]}"


class PublicationTrialRelation(models.TextChoices):
    RESULT = 'RESULT', 'RESULT'
    BACKGROUND = 'BACKGROUND', 'BACKGROUND'
    PRIMARY = 'PRIMARY', 'PRIMARY'
    SECONDARY = 'SECONDARY', 'SECONDARY'
    CONCLUSION = 'CONCLUSION', 'CONCLUSION'
    SUPPORTING = 'SUPPORTING', 'SUPPORTING'
    DERIVED = 'DERIVED', 'DERIVED'
    DERIVED_FROM_TRIAL = 'DERIVED_FROM_TRIAL', 'DERIVED_FROM_TRIAL'
    BACKGROUND_FOR_TRIAL = 'BACKGROUND_FOR_TRIAL', 'BACKGROUND_FOR_TRIAL'
    REPORTS_TRIAL_RESULT = 'REPORTS_TRIAL_RESULT', 'REPORTS_TRIAL_RESULT'
    SUPPORTS_MECHANISM = 'SUPPORTS_MECHANISM', 'SUPPORTS_MECHANISM'
    RELATED = 'RELATED', 'RELATED'


class Publication(BaseModel):
    """Represents a biomedical scientific publication (e.g., from PubMed)."""
    # Core identification & registry info
    pmid = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.TextField()
    abstract = models.TextField(blank=True, default='')
    journal = models.CharField(max_length=255, blank=True, default='')
    publication_date = models.CharField(max_length=100, blank=True, default='')
    pub_date = models.DateField(null=True, blank=True, db_index=True)
    year = models.IntegerField(null=True, blank=True, db_index=True)

    # Bibliographic & citation metadata
    volume = models.CharField(max_length=64, blank=True, default='')
    issue = models.CharField(max_length=64, blank=True, default='')
    pages = models.CharField(max_length=64, blank=True, default='')
    doi = models.CharField(max_length=128, blank=True, default='', db_index=True)
    pmc = models.CharField(max_length=64, blank=True, default='', db_index=True)
    first_author = models.CharField(max_length=255, blank=True, default='', db_index=True)
    authors_str = models.TextField(blank=True, default='')
    citation = models.TextField(blank=True, default='')
    pubmed_type = models.CharField(max_length=64, blank=True, default='')
    url = models.URLField(max_length=500, blank=True, default='')

    # Structured JSONB columns for rich PubMed metadata
    authors = models.JSONField(default=list, blank=True)
    mesh_terms = models.JSONField(default=dict, blank=True)
    chemicals = models.JSONField(default=dict, blank=True)
    publication_types = models.JSONField(default=dict, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    databanks = models.JSONField(default=list, blank=True)
    grants = models.JSONField(default=list, blank=True)
    history = models.JSONField(default=dict, blank=True)

    # Raw full API response payload from PubMed/metapub/Entrez
    raw = models.JSONField(default=dict, blank=True, help_text="Raw payload from PubMed/metapub/Entrez")

    # Claims extraction bookkeeping: True once LLM has attempted claims,
    # even if zero claims were produced. Reset to False on source update.
    claims_generated = models.BooleanField(default=False, db_index=True)

    # M2M Relationships with core biomedical knowledge graph
    trials = models.ManyToManyField(
        Trial,
        through='PublicationTrial',
        related_name='publications',
        blank=True
    )
    diseases = models.ManyToManyField(Disease, related_name='publications', blank=True)
    interventions = models.ManyToManyField(Intervention, related_name='publications', blank=True)
    biomarkers = models.ManyToManyField(Biomarker, related_name='publications', blank=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Publication'
        verbose_name_plural = 'Publications'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if 'raw_json' in kwargs and 'raw' not in kwargs:
            kwargs['raw'] = kwargs.pop('raw_json')
        super().__init__(*args, **kwargs)

    @property
    def raw_json(self) -> Dict[str, Any]:
        """Convenience property alias for raw JSONB response payload."""
        return self.raw

    @raw_json.setter
    def raw_json(self, value: Dict[str, Any]) -> None:
        self.raw = value

    @classmethod
    def parse_article_data(cls: "type[Publication]", article_or_dict: Any) -> Dict[str, Any]:
        """Extract structured model fields from a metapub PubMedArticle object, Entrez record, or dictionary payload."""
        if hasattr(article_or_dict, 'to_dict') and callable(getattr(article_or_dict, 'to_dict')):
            article_dict = article_or_dict.to_dict()
            article_obj = article_or_dict
        elif isinstance(article_or_dict, dict):
            article_dict = article_or_dict
            article_obj = None
        else:
            article_dict = getattr(article_or_dict, '__dict__', {})
            article_obj = article_or_dict

        pmid = str(getattr(article_obj, 'pmid', None) or article_dict.get('pmid') or '')
        title = getattr(article_obj, 'title', None) or article_dict.get('title') or ''
        abstract = getattr(article_obj, 'abstract', None) or article_dict.get('abstract') or ''
        journal = getattr(article_obj, 'journal', None) or article_dict.get('journal') or ''

        year_raw = getattr(article_obj, 'year', None) or article_dict.get('year')
        year_int = None
        if year_raw is not None:
            try:
                year_int = int(str(year_raw).strip())
            except (ValueError, TypeError):
                year_int = None

        pubdate_raw = getattr(article_obj, 'pubdate', None) or article_dict.get('pubdate') or article_dict.get('pub_date')
        pub_date = parse_pubmed_date(pubdate_raw) or (datetime.date(year_int, 1, 1) if year_int else None)

        volume = str(getattr(article_obj, 'volume', None) or article_dict.get('volume') or '')
        issue = str(getattr(article_obj, 'issue', None) or article_dict.get('issue') or '')
        pages = str(getattr(article_obj, 'pages', None) or article_dict.get('pages') or '')
        doi = str(getattr(article_obj, 'doi', None) or article_dict.get('doi') or '')
        pmc = str(getattr(article_obj, 'pmc', None) or article_dict.get('pmc') or '')

        first_author = str(getattr(article_obj, 'author1_last_fm', None) or article_dict.get('author1_last_fm') or article_dict.get('first_author') or '')
        authors_str = str(getattr(article_obj, 'authors_str', None) or article_dict.get('authors_str') or '')
        citation = str(getattr(article_obj, 'citation', None) or article_dict.get('citation') or '')
        pubmed_type = str(getattr(article_obj, 'pubmed_type', None) or article_dict.get('pubmed_type') or 'article')
        url = str(getattr(article_obj, 'url', None) or article_dict.get('url') or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""))

        authors = getattr(article_obj, 'authors', None) or article_dict.get('authors') or []
        mesh_terms = getattr(article_obj, 'mesh', None) or article_dict.get('mesh') or article_dict.get('mesh_terms') or {}
        chemicals = getattr(article_obj, 'chemicals', None) or article_dict.get('chemicals') or {}
        publication_types = getattr(article_obj, 'publication_types', None) or article_dict.get('publication_types') or {}
        keywords = getattr(article_obj, 'keywords', None) or article_dict.get('keywords') or []
        grants = getattr(article_obj, 'grants', None) or article_dict.get('grants') or []
        history = getattr(article_obj, 'history', None) or article_dict.get('history') or {}

        # Extract databanks (e.g. ClinicalTrials.gov links) from XML if present or from dict
        databanks = article_dict.get('databanks', [])
        if not databanks and hasattr(article_obj, 'xml') and article_obj.xml:
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(article_obj.xml)
                for elem in root.iter('DataBank'):
                    name_el = elem.find('DataBankName')
                    db_name = name_el.text.strip() if name_el is not None and name_el.text else ""
                    accs = [acc.text.strip() for acc in elem.findall('.//AccessionNumber') if acc.text]
                    if db_name or accs:
                        databanks.append({"name": db_name, "accessions": accs})
            except Exception:
                pass

        raw_payload = sanitize_json_payload(article_dict)

        return {
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "journal": journal,
            "publication_date": str(year_raw or (pub_date.isoformat() if pub_date else "")),
            "pub_date": pub_date,
            "year": year_int,
            "volume": volume,
            "issue": issue,
            "pages": pages,
            "doi": doi,
            "pmc": pmc,
            "first_author": first_author,
            "authors_str": authors_str,
            "citation": citation,
            "pubmed_type": pubmed_type,
            "url": url,
            "authors": sanitize_json_payload(authors),
            "mesh_terms": sanitize_json_payload(mesh_terms),
            "chemicals": sanitize_json_payload(chemicals),
            "publication_types": sanitize_json_payload(publication_types),
            "keywords": sanitize_json_payload(keywords),
            "databanks": sanitize_json_payload(databanks),
            "grants": sanitize_json_payload(grants),
            "history": sanitize_json_payload(history),
            "raw": raw_payload,
        }

    def __str__(self) -> str:
        return f"[{self.pmid}] {self.title[:80]}"


class Chunk(BaseModel):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='chunks', null=True, blank=True)
    trial = models.ForeignKey(Trial, on_delete=models.CASCADE, related_name='chunks', null=True, blank=True)
    body = models.TextField()
    section = models.CharField(max_length=64)
    sequ = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(publication__isnull=False, trial__isnull=True)
                           | models.Q(publication__isnull=True, trial__isnull=False)),
                name='chunk_exactly_one_owner',
            ),
        ]


class Ner(BaseModel):
    trial = models.ForeignKey(Trial, on_delete=models.CASCADE, related_name='ners', null=True, blank=True)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='ners', null=True, blank=True)
    chunk = models.ForeignKey(Chunk, on_delete=models.CASCADE, related_name='ners', null=True, blank=True)
    section = models.CharField(max_length=64, blank=True, default='')
    disease = models.ForeignKey(Disease, on_delete=models.SET_NULL, related_name='ners', null=True, blank=True)
    intervention = models.ForeignKey(Intervention, on_delete=models.SET_NULL, related_name='ners', null=True, blank=True)
    text = models.TextField()
    label = models.JSONField(default=list)
    start = models.PositiveIntegerField()
    end = models.PositiveIntegerField()
    score = models.FloatField()
    method = models.JSONField(default=list)
    model_name = models.JSONField(default=list)
    links = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(publication__isnull=False, trial__isnull=True)
                           | models.Q(publication__isnull=True, trial__isnull=False)),
                name='ner_exactly_one_owner',
            ),
        ]


class PublicationTrial(BaseModel):
    """
    Explicit join table representing the many-to-many relation between Publication and Trial.
    Maintains semantic relation type, audit timestamps, and JSONB metadata.
    """
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='publication_trials')
    trial = models.ForeignKey(Trial, on_delete=models.CASCADE, related_name='publication_trials')
    relation = models.CharField(
        max_length=64,
        choices=PublicationTrialRelation.choices,
        default=PublicationTrialRelation.RELATED,
        db_index=True
    )

    class Meta:
        ordering = ['-created']
        unique_together = ('publication', 'trial', 'relation')
        verbose_name = 'Publication Trial Link'
        verbose_name_plural = 'Publication Trial Links'

    def __str__(self) -> str:
        return f"[{self.relation}] PMID:{self.publication.pmid} <-> NCT:{self.trial.nct_id}"


class Observation(BaseModel):
    """
    Represents an observed finding, outcome, biomarker measurement, or LLM-derived fact.
    Can be tied directly to a Trial, Publication, Biomarker, or general entity.
    """
    observation_type = models.CharField(max_length=100, db_index=True)
    summary = models.TextField()
    trial = models.ForeignKey(Trial, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    biomarker = models.ForeignKey(Biomarker, on_delete=models.SET_NULL, related_name='observations', null=True, blank=True)
    disease = models.ForeignKey(Disease, on_delete=models.SET_NULL, related_name='observations', null=True, blank=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Observation'
        verbose_name_plural = 'Observations'

    def __str__(self) -> str:
        return f"[{self.observation_type}] {self.summary[:80]}"


class ClaimStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class ClaimGroup(BaseModel):
    diseases = models.ManyToManyField(Disease, related_name='claim_groups', blank=True)
    interventions = models.ManyToManyField(Intervention, related_name='claim_groups', blank=True)
    evidence_summary = models.TextField(blank=True, default='')
    synced = models.BooleanField(default=False)
    status = models.CharField(max_length=8, choices=ClaimStatus.choices, default=ClaimStatus.PENDING)
    notes = models.TextField(blank=True, default='')

    @classmethod
    def refresh_status(cls: "type[ClaimGroup]", group_id: int | None) -> None:
        if not group_id:
            return
        statuses = set(Claim.objects.filter(claim_group_id=group_id).values_list('status', flat=True).distinct())
        status = (ClaimStatus.PENDING if not statuses or ClaimStatus.PENDING in statuses else
                  ClaimStatus.APPROVED if ClaimStatus.APPROVED in statuses else ClaimStatus.REJECTED)
        cls.objects.filter(pk=group_id).exclude(status=status).update(status=status, modified=timezone.now())


class Claim(BaseModel):
    """A scientific finding supported by a source section."""
    section = models.CharField(max_length=64)
    claim_type = models.CharField(max_length=64, db_index=True)
    evidence = models.TextField(blank=True, default='')
    status = models.CharField(max_length=8, choices=ClaimStatus.choices, default=ClaimStatus.PENDING)
    notes = models.TextField(blank=True, default='')
    trial = models.ForeignKey(Trial, on_delete=models.CASCADE, related_name='claims', null=True, blank=True)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='claims', null=True, blank=True)
    chunk = models.ForeignKey(Chunk, on_delete=models.CASCADE, related_name='claims', null=True, blank=True)
    diseases = models.ManyToManyField(Disease, related_name='claims', blank=True, db_table='claim_disease')
    interventions = models.ManyToManyField(Intervention, related_name='claims', blank=True, db_table='claim_intervention')
    ners = models.ManyToManyField(Ner, related_name='claims', blank=True, db_table='claim_ner')
    claim_group = models.ForeignKey(ClaimGroup, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='claims')

    class Meta:
        ordering = ['-created']
        verbose_name = 'Claim'
        verbose_name_plural = 'Claims'

    def __str__(self) -> str:
        return f"[{self.claim_type}] {self.section}"


class ClaimsGenerationFlags(BaseModel):
    """Record a claim type completed for exactly one source."""
    trial = models.ForeignKey(
        Trial, on_delete=models.CASCADE, related_name='claims_generation_flags', null=True, blank=True,
    )
    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name='claims_generation_flags', null=True, blank=True,
    )
    generated_claim_type = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(trial__isnull=False, publication__isnull=True)
                    | models.Q(trial__isnull=True, publication__isnull=False)
                ),
                name='cgen_flags_exactly_one_source',
            ),
            models.UniqueConstraint(
                fields=['trial', 'generated_claim_type'],
                condition=models.Q(trial__isnull=False),
                name='cgen_flags_trial_type_uniq',
            ),
            models.UniqueConstraint(
                fields=['publication', 'generated_claim_type'],
                condition=models.Q(publication__isnull=False),
                name='cgen_flags_pub_type_uniq',
            ),
        ]


class ClaimTrails(BaseModel):
    """Immutable snapshots of user-reviewed claim changes."""
    trial = models.ForeignKey(
        Trial, on_delete=models.CASCADE, related_name='claim_trails', null=True, blank=True,
    )
    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name='claim_trails', null=True, blank=True,
    )
    notes = models.TextField(blank=True, default='')
    status_from = models.CharField(max_length=8, choices=ClaimStatus.choices)
    new_status = models.CharField(max_length=8, choices=ClaimStatus.choices)
    diseases = ArrayField(models.IntegerField(), blank=True, default=list)
    interventions = ArrayField(models.IntegerField(), blank=True, default=list)

    class Meta:
        ordering = ['-created', '-id']
        verbose_name = 'Claim Trail'
        verbose_name_plural = 'Claim Trails'
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(trial__isnull=False) | models.Q(publication__isnull=False)),
                name='claim_trails_has_source',
            ),
        ]
        indexes = [
            GinIndex(fields=['diseases'], name='trails_diseases_gin'),
            GinIndex(fields=['interventions'], name='trails_interv_gin'),
        ]


class Judgement(BaseModel):
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='judgements')
    method = models.CharField(max_length=64)
    score = models.FloatField()

    def __str__(self) -> str:
        return f"[{self.method}] {self.score}"
