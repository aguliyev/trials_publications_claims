"""Workspace list/detail, claim review and import API."""

from functools import wraps

from django.db import transaction
from django.db.models import Avg, Case, CharField, Count, F, Func, IntegerField, Max, Min, Q, Value, When
from django.db.models.functions import Cast, Concat
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import UpdateModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Biomarker,
    Chunk,
    Claim,
    ClaimGroup,
    ClaimTrails,
    ClaimStatus,
    Disease,
    Focus,
    Intervention,
    Judgement,
    Ner,
    Observation,
    Publication,
    PublicationTrial,
    Trial,
)
from .operation_logs import capture_lib_logs
from .claim_trails import create_claim_trail
from lib.focuses import focus_state, get_or_create_focus


class ImportPayloadSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise ValidationError('Expected a JSON object.')
        unknown = set(data) - set(self.fields)
        if unknown:
            raise ValidationError({key: 'Unexpected field.' for key in unknown})
        return super().to_internal_value(data)


class PublicationImportSerializer(ImportPayloadSerializer):
    pmid = serializers.RegexField(r'\A[0-9]{1,64}\Z', max_length=64, trim_whitespace=False)

    def to_internal_value(self, data):
        if isinstance(data, dict) and 'pmid' in data and not isinstance(data['pmid'], str):
            raise ValidationError({'pmid': 'Expected a string.'})
        return super().to_internal_value(data)


class TrialImportSerializer(ImportPayloadSerializer):
    nct_id = serializers.RegexField(r'\A[Nn][Cc][Tt][0-9]{8}\Z', trim_whitespace=False)
    load_related_publications = serializers.BooleanField()

    def to_internal_value(self, data):
        if isinstance(data, dict) and 'load_related_publications' in data \
                and type(data['load_related_publications']) is not bool:
            raise ValidationError({'load_related_publications': 'Expected a boolean.'})
        return super().to_internal_value(data)

    def validate_nct_id(self, value):
        return value.upper()


class WorkspacePagination(PageNumberPagination):
    page_size = 25


def _parse_int_param(name, value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({name: 'Enter a valid integer.'})


def _parse_bool_param(name, value):
    normalized = str(value).strip().lower()
    if normalized in ('true', '1'):
        return True
    if normalized in ('false', '0'):
        return False
    raise ValidationError({name: 'Enter a valid boolean (true/false).'})


def _chunk_conflicts(claim):
    if not claim.chunk_id:
        return False
    chunk = getattr(claim, 'chunk', None)
    if chunk is None:
        return False
    if claim.section != chunk.section:
        return True
    if claim.trial_id and claim.trial_id != chunk.trial_id:
        return True
    if claim.publication_id and claim.publication_id != chunk.publication_id:
        return True
    return False


def resolve_claim_source(claim):
    """Return (source_kind, source_id, source_label) per workspace contract."""
    both = bool(claim.trial_id) and bool(claim.publication_id)
    if both or (claim.chunk_id and _chunk_conflicts(claim)):
        return None, None, 'Ambiguous source'
    if claim.trial_id:
        trial = getattr(claim, 'trial', None)
        label = trial.nct_id if trial is not None else str(claim.trial_id)
        return 'trials', claim.trial_id, label
    if claim.publication_id:
        publication = getattr(claim, 'publication', None)
        label = publication.pmid if publication is not None else str(claim.publication_id)
        return 'publications', claim.publication_id, label
    if claim.chunk_id:
        return 'chunks', claim.chunk_id, f'Chunk #{claim.chunk_id}'
    return None, None, 'No source'


class ClaimListSerializer(serializers.ModelSerializer):
    evidence_excerpt = serializers.SerializerMethodField()
    source_kind = serializers.SerializerMethodField()
    source_id = serializers.SerializerMethodField()
    source_label = serializers.SerializerMethodField()
    max_judgement_score = serializers.FloatField(read_only=True)

    class Meta:
        model = Claim
        fields = ('id', 'claim_type', 'evidence_excerpt', 'source_kind',
                  'source_id', 'source_label', 'section', 'status', 'modified',
                  'max_judgement_score')

    def get_evidence_excerpt(self, obj):
        return (obj.evidence or '')[:160]

    def get_source_kind(self, obj):
        return resolve_claim_source(obj)[0]

    def get_source_id(self, obj):
        return resolve_claim_source(obj)[1]

    def get_source_label(self, obj):
        return resolve_claim_source(obj)[2]


class ClaimGroupListSerializer(serializers.ModelSerializer):
    evidence_summary_excerpt = serializers.SerializerMethodField()
    max_judgement_score = serializers.FloatField(read_only=True)
    claims_count = serializers.IntegerField(read_only=True)
    trials_count = serializers.IntegerField(read_only=True)
    publications_count = serializers.IntegerField(read_only=True)
    diseases_count = serializers.IntegerField(read_only=True)
    interventions_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ClaimGroup
        fields = ('id', 'evidence_summary_excerpt', 'status', 'max_judgement_score',
                  'claims_count', 'trials_count', 'publications_count',
                  'diseases_count', 'interventions_count')

    def get_evidence_summary_excerpt(self, obj):
        return obj.evidence_summary[:160]


class FocusListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Focus
        fields = ('id', 'query', 'ingest_trials_count', 'ingest_publications_count', 'modified')


class FocusDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Focus
        fields = ('id', 'query', 'ingest_trials_count', 'ingest_publications_count',
                  'notes', 'meta', 'created', 'modified')
        read_only_fields = ('id', 'meta', 'created', 'modified')

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise ValidationError('Expected a JSON object.')
        allowed = {'query', 'ingest_trials_count', 'ingest_publications_count', 'notes'}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValidationError({key: 'This field cannot be updated.' for key in unknown})
        return super().to_internal_value(data)

    def validate_query(self, value):
        value = value.strip()
        if not value:
            raise ValidationError('Enter a nonblank query.')
        return value


class FocusSourceSerializer(ImportPayloadSerializer):
    kind = serializers.ChoiceField(choices=('claims', 'claim-groups'))
    id = serializers.IntegerField(min_value=1)


class ClaimGroupDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimGroup
        fields = ('id', 'evidence_summary', 'status', 'notes', 'synced', 'created', 'modified')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['focus'] = focus_state(instance)
        data['diseases'] = [{'id': item.pk, 'name': item.name, 'mesh': item.mesh}
                            for item in instance.diseases.all()]
        data['interventions'] = [{'id': item.pk, 'name': item.name, 'mesh': item.mesh}
                                 for item in instance.interventions.all()]
        data['trials'] = list(Trial.objects.filter(claims__claim_group=instance)
                              .order_by('id').values('id', 'nct_id', 'title', 'status', 'phase').distinct())
        data['publications'] = list(Publication.objects.filter(claims__claim_group=instance)
                                    .order_by('id').values('id', 'pmid', 'title', 'journal', 'year').distinct())
        data['judgement_scores'] = Judgement.objects.filter(claim__claim_group=instance).aggregate(
            min=Min('score'), max=Max('score'), mean=Avg('score'))
        data['claim_notes'] = list(instance.claims.exclude(notes='').order_by('pk').values('id', 'notes'))
        return data


class ClaimGroupNotesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimGroup
        fields = ('notes', 'modified')
        read_only_fields = ('modified',)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise ValidationError('Expected a JSON object.')
        unknown = sorted(set(data) - {'notes'})
        if unknown:
            raise ValidationError({key: 'This field cannot be updated.' for key in unknown})
        return super().to_internal_value(data)


def resolve_section_text(claim):
    """Return {kind, id, section, text} or None per workspace contract."""
    # ponytail: lazy import avoids lib/__init__ heavy chain at app-load time
    from lib.text_tools import (
        PUBLICATION_FIELDS_NOT_TO_CHUNK,
        PUBLICATION_FIELDS_TO_CHUNK,
        TRIAL_FIELDS_NOT_TO_CHUNK,
        TRIAL_FIELDS_TO_CHUNK,
    )
    if claim.chunk_id:
        chunk = getattr(claim, 'chunk', None)
        if chunk is None:
            try:
                chunk = Chunk.objects.select_related('trial', 'publication').get(pk=claim.chunk_id)
            except Chunk.DoesNotExist:
                return None
        if (claim.section != chunk.section
                or (claim.trial_id and claim.trial_id != chunk.trial_id)
                or (claim.publication_id and claim.publication_id != chunk.publication_id)):
            return None
        return {'kind': 'chunks', 'id': claim.chunk_id,
                'section': chunk.section, 'text': chunk.body}
    if bool(claim.publication_id) == bool(claim.trial_id):
        return None
    owner = claim.publication if claim.publication_id else claim.trial
    allowed = (PUBLICATION_FIELDS_TO_CHUNK + PUBLICATION_FIELDS_NOT_TO_CHUNK
               if claim.publication_id else TRIAL_FIELDS_TO_CHUNK + TRIAL_FIELDS_NOT_TO_CHUNK)
    if owner is None or claim.section not in allowed:
        return None
    return {'kind': 'publications' if claim.publication_id else 'trials',
            'id': owner.pk, 'section': claim.section, 'text': getattr(owner, claim.section)}


def _ner_rows(instance):
    return [{
        'id': n.pk, 'text': n.text, 'label': n.label, 'score': n.score,
        'section': n.section, 'start': n.start, 'end': n.end,
        'disease_id': n.disease_id, 'intervention_id': n.intervention_id,
    } for n in instance.ners.all()]


class ClaimDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['focus'] = focus_state(instance)
        data['judgements'] = [
            {'id': j.pk, 'method': j.method, 'score': j.score, 'meta': j.meta,
             'created': j.created.isoformat() if j.created else None,
             'modified': j.modified.isoformat() if j.modified else None}
            for j in instance.judgements.all()
        ]
        diseases = instance.diseases.all() if hasattr(instance, 'diseases') else []
        data['diseases'] = [{'id': d.pk, 'name': d.name, 'mesh': d.mesh} for d in diseases]
        interventions = instance.interventions.all() if hasattr(instance, 'interventions') else []
        data['interventions'] = [{'id': i.pk, 'name': i.name, 'mesh': i.mesh} for i in interventions]
        data['ners'] = _ner_rows(instance)
        data['section_text'] = resolve_section_text(instance)
        return data


class ClaimTrailsListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimTrails
        fields = ('id', 'created', 'status_from', 'new_status', 'notes')


class ClaimTrailsDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimTrails
        fields = ('id', 'created', 'modified', 'status_from', 'new_status', 'notes',
                  'trial', 'publication', 'meta')


class DiseaseSerializer(serializers.ModelSerializer):
    claims_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Disease
        fields = ('id', 'name', 'mesh', 'modified', 'claims_count')


class DiseaseDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disease
        fields = '__all__'


class InterventionSerializer(serializers.ModelSerializer):
    claims_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Intervention
        fields = ('id', 'name', 'mesh', 'modified', 'claims_count')


class InterventionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intervention
        fields = '__all__'


class TrialListSerializer(serializers.ModelSerializer):
    claims_count = serializers.IntegerField(read_only=True)
    publications_count = serializers.IntegerField(read_only=True)
    references_count = serializers.SerializerMethodField()

    class Meta:
        model = Trial
        fields = ('id', 'nct_id', 'title', 'status', 'phase', 'start_date', 'claims_count',
                  'publications_count', 'references_count')

    def get_references_count(self, obj):
        return len(obj.references) if isinstance(obj.references, list) else 0


class TrialDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trial
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['linked_publications'] = [{
            'id': link.publication_id,
            'pmid': link.publication.pmid,
            'title': link.publication.title,
            'journal': link.publication.journal,
            'year': link.publication.year,
            'relation': link.relation,
        } for link in instance.publication_trials.select_related('publication').all()]
        data['ners'] = _ner_rows(instance)
        return data


class PublicationListSerializer(serializers.ModelSerializer):
    claims_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Publication
        fields = ('id', 'pmid', 'title', 'journal', 'year', 'pub_date', 'claims_count')


class PublicationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['linked_trials'] = [{
            'id': link.trial_id,
            'nct_id': link.trial.nct_id,
            'title': link.trial.title,
            'status': link.trial.status,
            'phase': link.trial.phase,
            'relation': link.relation,
        } for link in instance.publication_trials.select_related('trial').all()]
        data['ners'] = _ner_rows(instance)
        return data


def require_csrf_token(view_func):
    """csrf_protect that also applies when the test client disables CSRF checks.

    The review PATCH is intentionally writable without login, so a missing
    token must always be rejected; the Django test client's bypass flag is
    cleared to keep that guarantee visible in tests.
    """
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        request._dont_enforce_csrf_checks = False
        return csrf_protect(view_func)(request, *args, **kwargs)
    return wrapped


class RefetchMixin:
    @action(detail=True, methods=['post'], url_path='refetch')
    @method_decorator(require_csrf_token)
    def refetch(self, request, pk=None):
        source = self.get_object()
        from lib.refetch import refetch_source

        logs = []
        with capture_lib_logs(logs.append):
            try:
                refreshed = refetch_source(source)
            except Exception:
                return Response({'status': 'failed', 'error': 'Could not re-fetch this record. Retry later.',
                                 'logs': logs}, status=502)
        return Response({'status': 'ok', 'record_id': refreshed.pk, 'logs': logs})


class BaseReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = WorkspacePagination
    filter_backends = [SearchFilter, OrderingFilter]
    ordering = ['-created', '-id']

    def filter_queryset(self, queryset):
        if self.action != 'list':
            return queryset
        return super().filter_queryset(queryset)


@method_decorator(require_csrf_token, name='dispatch')
class _ImportView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['post', 'options']


class SourceSearchView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['get', 'head', 'options']

    def get(self, request):
        kind = request.query_params.get('kind')
        query = request.query_params.get('query', '').strip()
        if kind not in ('trials', 'publications') or not query or len(query) > 500:
            raise ValidationError({'query': 'Enter a keyword and choose trials or publications (maximum 500 characters).'})
        try:
            if kind == 'trials':
                from lib.clinical_trials import search_trials
                results = search_trials(query)
            else:
                from lib.pubmed import search_publications
                results = search_publications(query)
        except Exception:
            return Response({'error': 'Could not search sources. Retry your search.'}, status=502)
        model = Trial if kind == 'trials' else Publication
        identifier = 'nct_id' if kind == 'trials' else 'pmid'
        existing = dict(model.objects.filter(
            **{identifier + '__in': [row['id'] for row in results]}
        ).values_list(identifier, 'pk'))
        results = [dict(row, database_record_id=existing.get(row['id'])) for row in results]
        return Response({'results': results, 'count': len(results)})


class SourceDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['get', 'head', 'options']

    def get(self, request, kind, source_id):
        if kind == 'trials':
            serializer = TrialImportSerializer(data={'nct_id': source_id, 'load_related_publications': False})
            fields = ('nct_id', 'title', 'official_title', 'status', 'phase', 'study_type',
                      'lead_sponsor', 'enrollment', 'conditions', 'interventions_list',
                      'summary', 'detailed_description', 'eligibility_criteria')
        elif kind == 'publications':
            serializer = PublicationImportSerializer(data={'pmid': source_id})
            fields = ('pmid', 'title', 'abstract', 'journal', 'year', 'doi',
                      'first_author', 'authors_str', 'citation')
        else:
            raise ValidationError({'kind': 'Choose trials or publications.'})
        serializer.is_valid(raise_exception=True)
        try:
            if kind == 'trials':
                from lib.clinical_trials import fetch_study_v2
                data = Trial.parse_api_study(fetch_study_v2(serializer.validated_data['nct_id']))
            else:
                from lib.pubmed import PubMedFetcher
                article = PubMedFetcher().article_by_pmid(serializer.validated_data['pmid'])
                data = Publication.parse_article_data(article)
        except Exception:
            return Response({'error': 'Could not load source details. Select the row to retry.'}, status=502)
        result = {field: data[field] for field in fields}
        if kind == 'trials':
            result['publications'] = [
                {'pmid': str(ref['pmid']).strip(), 'citation': ref.get('citation', ''),
                 'type': ref.get('type', '')}
                for ref in data['references'] if isinstance(ref, dict)
                and str(ref.get('pmid') or '').strip()
            ]
            result['publication_count'] = len(result['publications'])
        model = Trial if kind == 'trials' else Publication
        identifier = 'nct_id' if kind == 'trials' else 'pmid'
        result['database_record_id'] = model.objects.filter(
            **{identifier: serializer.validated_data[identifier]}
        ).values_list('pk', flat=True).first()
        return Response(result)


class PublicationImportView(_ImportView):
    def post(self, request):
        serializer = PublicationImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pmid = serializer.validated_data['pmid']
        from lib.pubmed import fetch_and_upsert_publication

        logs = []
        with capture_lib_logs(logs.append):
            try:
                publication = fetch_and_upsert_publication(pmid)
            except Exception:
                return Response({'id': pmid, 'status': 'failed', 'error': 'Could not load publication. Retry this ID.',
                                 'logs': logs}, status=502)
        return Response({'id': pmid, 'record_id': publication.pk, 'status': 'ok', 'logs': logs})


class TrialImportView(_ImportView):
    def post(self, request):
        serializer = TrialImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nct_id = serializer.validated_data['nct_id']
        from lib.clinical_trials import fetch_and_upsert_trial, fetch_trial_publications

        logs = []
        with capture_lib_logs(logs.append):
            try:
                trial = fetch_and_upsert_trial(nct_id)
            except Exception:
                return Response({'id': nct_id, 'status': 'failed', 'error': 'Could not load trial. Retry this ID.',
                                 'logs': logs}, status=502)
            related_count = None
            related_ids = None
            if serializer.validated_data['load_related_publications']:
                try:
                    links = fetch_trial_publications(nct_id)
                    related_count = len(links)
                    related_ids = [link.publication.pmid for link in links]
                except Exception:
                    return Response({'id': nct_id, 'record_id': trial.pk, 'status': 'partial',
                                      'error': 'Trial saved, but related publications could not be loaded. Retry this ID.',
                                      'related_publications': None, 'related_publication_ids': None,
                                      'logs': logs}, status=502)
        return Response({'id': nct_id, 'record_id': trial.pk, 'status': 'ok',
                          'related_publications': related_count, 'related_publication_ids': related_ids,
                          'logs': logs})


class ClaimReviewSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=ClaimStatus.choices, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Claim
        fields = ('status', 'notes', 'modified')
        read_only_fields = ('modified',)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise ValidationError('Expected a JSON object.')
        unknown = sorted(set(data) - {'status', 'notes'})
        if unknown:
            raise ValidationError({key: 'This field cannot be updated.' for key in unknown})
        return super().to_internal_value(data)


@method_decorator(require_csrf_token, name='dispatch')
class ClaimViewSet(UpdateModelMixin, BaseReadOnlyViewSet):
    search_fields = ('=id', 'evidence', 'claim_type', 'section', 'trial__nct_id', 'publication__pmid')
    ordering_fields = ('id', 'created', 'modified', 'status', 'claim_type', 'section',
                       'evidence', 'source_sort', 'max_judgement_score')
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'partial_update':
            return ClaimReviewSerializer
        return ClaimListSerializer if self.action == 'list' else ClaimDetailSerializer

    @transaction.atomic
    def perform_update(self, serializer):
        claim = Claim.objects.select_for_update().get(pk=serializer.instance.pk)
        if not claim.trial_id and not claim.publication_id:
            raise ValidationError('A reviewed claim must belong to a trial or publication.')
        old_status = claim.status
        old_notes = claim.notes
        serializer.instance = claim
        updated_claim = serializer.save()
        if updated_claim.status != old_status or updated_claim.notes != old_notes:
            create_claim_trail(updated_claim, status_from=old_status)

    def get_queryset(self):
        qs = Claim.objects.all().select_related('trial', 'publication', 'chunk').order_by('-created', '-id')
        if self.action != 'list':
            return qs.prefetch_related('judgements', 'ners', 'diseases', 'interventions')
        chunk_conflict = Q(chunk_id__isnull=False) & (
            ~Q(section=F('chunk__section')) |
            (Q(trial_id__isnull=False) & ~Q(trial_id=F('chunk__trial_id'))) |
            (Q(publication_id__isnull=False) & ~Q(publication_id=F('chunk__publication_id')))
        )
        qs = qs.annotate(
            max_judgement_score=Max('judgements__score'),
            source_sort=Case(
                When(Q(trial_id__isnull=False, publication_id__isnull=False) | chunk_conflict,
                     then=Value('Ambiguous source')),
                When(trial_id__isnull=False, then=F('trial__nct_id')),
                When(publication_id__isnull=False, then=F('publication__pmid')),
                When(chunk_id__isnull=False, then=Concat(Value('Chunk #'), Cast('chunk_id', CharField()))),
                default=Value('No source'), output_field=CharField(),
            ),
        )
        params = self.request.query_params
        if 'status' in params:
            qs = qs.filter(status=params['status'])
        if 'claim_type' in params:
            qs = qs.filter(claim_type=params['claim_type'])
        for key in ('trial', 'publication'):
            if key in params:
                qs = qs.filter(**{f'{key}_id': _parse_int_param(key, params[key])})
        if 'claim_group' in params:
            qs = qs.filter(claim_group_id=_parse_int_param('claim_group', params['claim_group']))
        if 'disease' in params:
            qs = qs.filter(diseases__id=_parse_int_param('disease', params['disease']))
        if 'intervention' in params:
            qs = qs.filter(interventions__id=_parse_int_param('intervention', params['intervention']))
        if 'ner' in params:
            qs = qs.filter(ners__id=_parse_int_param('ner', params['ner']))
        return qs.distinct()


class ClaimTrailsViewSet(BaseReadOnlyViewSet):
    http_method_names = ['get', 'head', 'options']

    def get_serializer_class(self):
        return ClaimTrailsDetailSerializer if self.action == 'retrieve' else ClaimTrailsListSerializer

    def get_queryset(self):
        queryset = ClaimTrails.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return queryset
        params = self.request.query_params
        has_trial = 'trial' in params
        has_publication = 'publication' in params
        if has_trial == has_publication:
            raise ValidationError('Specify exactly one of trial or publication.')
        key = 'trial' if has_trial else 'publication'
        source_id = _parse_int_param(key, params[key])
        queryset = queryset.filter(**{f'{key}_id': source_id})
        if 'disease' in params:
            disease_id = _parse_int_param('disease', params['disease'])
            queryset = queryset.filter(diseases__contains=[disease_id])
        if 'intervention' in params:
            intervention_id = _parse_int_param('intervention', params['intervention'])
            queryset = queryset.filter(interventions__contains=[intervention_id])
        return queryset


@method_decorator(require_csrf_token, name='dispatch')
class ClaimGroupViewSet(UpdateModelMixin, BaseReadOnlyViewSet):
    search_fields = ('=id', 'evidence_summary',)
    ordering_fields = ('id', 'created', 'status', 'evidence_summary', 'claims_count', 'trials_count',
                       'publications_count', 'diseases_count', 'interventions_count', 'max_judgement_score')
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'partial_update':
            return ClaimGroupNotesSerializer
        return ClaimGroupListSerializer if self.action == 'list' else ClaimGroupDetailSerializer

    def get_queryset(self):
        qs = ClaimGroup.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs.prefetch_related('diseases', 'interventions')
        return qs.annotate(
            claims_count=Count('claims', distinct=True),
            trials_count=Count('claims__trial', distinct=True),
            publications_count=Count('claims__publication', distinct=True),
            diseases_count=Count('diseases', distinct=True),
            interventions_count=Count('interventions', distinct=True),
            max_judgement_score=Max('claims__judgements__score'),
        ).filter(claims_count__gte=2)


@method_decorator(require_csrf_token, name='dispatch')
class FocusViewSet(UpdateModelMixin, BaseReadOnlyViewSet):
    search_fields = ('=id', 'query', 'notes')
    ordering_fields = ('id', 'query', 'ingest_trials_count',
                       'ingest_publications_count', 'created', 'modified')
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def get_serializer_class(self):
        return FocusListSerializer if self.action == 'list' else FocusDetailSerializer

    def get_queryset(self):
        qs = Focus.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
        for field in ('ingest_trials_count', 'ingest_publications_count'):
            if field in self.request.query_params:
                value = _parse_int_param(field, self.request.query_params[field])
                if value < 0:
                    raise ValidationError({field: 'Enter a non-negative integer.'})
                qs = qs.filter(**{field: value})
        return qs

    @action(detail=False, methods=['post'], url_path='from-record')
    def from_record(self, request):
        payload = FocusSourceSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        kind = payload.validated_data['kind']
        model = Claim if kind == 'claims' else ClaimGroup
        source = model.objects.prefetch_related('diseases', 'interventions').filter(
            pk=payload.validated_data['id'],
        ).first()
        if source is None:
            raise Http404
        try:
            focus, created = get_or_create_focus(source)
        except ValueError as exc:
            raise ValidationError({'source': str(exc)})
        return Response(
            {'created': created, 'focus': FocusDetailSerializer(focus).data},
            status=201 if created else 200,
        )


class DiseaseViewSet(BaseReadOnlyViewSet):
    search_fields = ('=id', 'name', 'mesh')
    ordering_fields = ('id', 'name', 'mesh', 'created', 'modified', 'claims_count')

    def get_serializer_class(self):
        return DiseaseSerializer if self.action == 'list' else DiseaseDetailSerializer

    def get_queryset(self):
        qs = Disease.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
        qs = qs.annotate(claims_count=Count('claims', distinct=True))
        params = self.request.query_params
        if 'mesh' in params:
            qs = qs.filter(mesh=params['mesh'])
        return qs.distinct()


class InterventionViewSet(BaseReadOnlyViewSet):
    search_fields = ('=id', 'name', 'mesh')
    ordering_fields = ('id', 'name', 'mesh', 'created', 'modified', 'claims_count')

    def get_serializer_class(self):
        return InterventionSerializer if self.action == 'list' else InterventionDetailSerializer

    def get_queryset(self):
        qs = Intervention.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
        qs = qs.annotate(claims_count=Count('claims', distinct=True))
        params = self.request.query_params
        if 'mesh' in params:
            qs = qs.filter(mesh=params['mesh'])
        return qs.distinct()


class TrialViewSet(RefetchMixin, BaseReadOnlyViewSet):
    search_fields = ('=id', 'nct_id', 'title', 'official_title', 'acronym')
    ordering_fields = ('id', 'nct_id', 'title', 'status', 'phase', 'start_date', 'created',
                       'claims_count', 'publications_count')

    def get_serializer_class(self):
        return TrialListSerializer if self.action == 'list' else TrialDetailSerializer

    def get_queryset(self):
        qs = Trial.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
        qs = qs.annotate(claims_count=Count('claims', distinct=True),
                         publications_count=Count('publications', distinct=True))
        params = self.request.query_params
        if 'status' in params:
            qs = qs.filter(status=params['status'])
        if 'phase' in params:
            qs = qs.filter(phase=params['phase'])
        if 'has_results' in params:
            qs = qs.filter(has_results=_parse_bool_param('has_results', params['has_results']))
        if 'publication' in params:
            qs = qs.filter(publications__id=_parse_int_param('publication', params['publication']))
        return qs.distinct()


class PublicationViewSet(RefetchMixin, BaseReadOnlyViewSet):
    search_fields = ('=id', 'pmid', 'title', 'doi', 'journal', 'first_author')
    ordering_fields = ('id', 'pmid', 'title', 'journal', 'year', 'pub_date', 'created', 'claims_count')

    def get_serializer_class(self):
        return PublicationListSerializer if self.action == 'list' else PublicationDetailSerializer

    def get_queryset(self):
        qs = Publication.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
        qs = qs.annotate(claims_count=Count('claims', distinct=True))
        params = self.request.query_params
        if 'year' in params:
            qs = qs.filter(year=_parse_int_param('year', params['year']))
        if 'journal' in params:
            qs = qs.filter(journal=params['journal'])
        if 'trial' in params:
            qs = qs.filter(trials__id=_parse_int_param('trial', params['trial']))
        return qs.distinct()


class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chunk
        fields = '__all__'


class NerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ner
        fields = '__all__'


class NerListSerializer(serializers.ModelSerializer):
    models_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ner
        fields = ('id', 'text', 'label', 'score', 'section', 'models_count', 'modified')


class NerDetailSerializer(NerSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['claims'] = [
            {'id': claim.pk, 'claim_type': claim.claim_type,
             'evidence_excerpt': (claim.evidence or '')[:160],
             'section': claim.section, 'status': claim.status}
            for claim in instance.claims.all().order_by('pk')
        ]
        trial = instance.trial
        data['trial_preview'] = (
            {'id': trial.pk, 'nct_id': trial.nct_id, 'title': trial.title} if trial else None)
        publication = instance.publication
        data['publication_preview'] = (
            {'id': publication.pk, 'pmid': publication.pmid, 'title': publication.title}
            if publication else None)
        chunk = instance.chunk
        data['chunk_preview'] = (
            {'id': chunk.pk, 'section': chunk.section, 'body_excerpt': (chunk.body or '')[:160]}
            if chunk else None)
        disease = instance.disease
        data['disease_preview'] = (
            {'id': disease.pk, 'name': disease.name, 'mesh': disease.mesh} if disease else None)
        intervention = instance.intervention
        data['intervention_preview'] = (
            {'id': intervention.pk, 'name': intervention.name, 'mesh': intervention.mesh}
            if intervention else None)
        return data


class NerViewSet(BaseReadOnlyViewSet):
    search_fields = ('=id', 'text', 'section')
    ordering_fields = ('id', 'text', 'label', 'score', 'section', 'models_count', 'modified')

    def get_serializer_class(self):
        return NerListSerializer if self.action == 'list' else NerDetailSerializer

    def get_queryset(self):
        qs = Ner.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs.select_related('trial', 'publication', 'chunk', 'disease', 'intervention'
                                     ).prefetch_related('claims')
        qs = qs.annotate(models_count=Func('model_name', function='jsonb_array_length',
                                           output_field=IntegerField()))
        params = self.request.query_params
        for key in ('trial', 'publication', 'chunk', 'disease', 'intervention', 'claim'):
            if key in params:
                field = 'claims__id' if key == 'claim' else f'{key}_id'
                qs = qs.filter(**{field: _parse_int_param(key, params[key])})
        if 'label' in params:
            qs = qs.filter(label__icontains=params['label'])
        if 'section' in params:
            qs = qs.filter(section=params['section'])
        return qs.distinct()


class JudgementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Judgement
        fields = '__all__'


class BiomarkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Biomarker
        fields = '__all__'


class ObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Observation
        fields = '__all__'


class PublicationTrialSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicationTrial
        fields = '__all__'


SUPPORTING_RECORDS = {
    'chunks': (Chunk, ChunkSerializer),
    'ners': (Ner, NerSerializer),
    'judgements': (Judgement, JudgementSerializer),
    'biomarkers': (Biomarker, BiomarkerSerializer),
    'observations': (Observation, ObservationSerializer),
    'publication-trials': (PublicationTrial, PublicationTrialSerializer),
}


class SupportingRecordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, kind, pk):
        entry = SUPPORTING_RECORDS.get(kind)
        if entry is None:
            raise Http404
        model, serializer_class = entry
        try:
            obj = model.objects.get(pk=pk)
        except model.DoesNotExist:
            raise Http404
        return Response(serializer_class(obj).data)
