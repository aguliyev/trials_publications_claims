"""Read-only DRF workspace API (Phase 1 backend)."""

from django.http import Http404
from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Biomarker,
    Chunk,
    Claim,
    Disease,
    Intervention,
    Judgement,
    Ner,
    Observation,
    Publication,
    PublicationTrial,
    Trial,
)


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

    class Meta:
        model = Claim
        fields = ('id', 'claim_type', 'evidence_excerpt', 'source_kind',
                  'source_id', 'source_label', 'section', 'status', 'created')

    def get_evidence_excerpt(self, obj):
        return (obj.evidence or '')[:160]

    def get_source_kind(self, obj):
        return resolve_claim_source(obj)[0]

    def get_source_id(self, obj):
        return resolve_claim_source(obj)[1]

    def get_source_label(self, obj):
        return resolve_claim_source(obj)[2]


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


class ClaimDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
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
        ners = instance.ners.all() if hasattr(instance, 'ners') else []
        data['ners'] = [{
            'id': n.pk, 'text': n.text, 'label': n.label, 'score': n.score,
            'section': n.section, 'start': n.start, 'end': n.end,
            'disease_id': n.disease_id, 'intervention_id': n.intervention_id,
        } for n in ners]
        data['section_text'] = resolve_section_text(instance)
        return data


class DiseaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disease
        fields = ('id', 'name', 'mesh', 'created')


class DiseaseDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disease
        fields = '__all__'


class InterventionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intervention
        fields = ('id', 'name', 'mesh', 'created')


class InterventionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intervention
        fields = '__all__'


class TrialListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trial
        fields = ('id', 'nct_id', 'title', 'status', 'phase', 'start_date')


class TrialDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trial
        fields = '__all__'


class PublicationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = ('id', 'pmid', 'title', 'journal', 'year', 'pub_date')


class PublicationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = '__all__'


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


class ClaimViewSet(BaseReadOnlyViewSet):
    search_fields = ('evidence', 'claim_type', 'section', 'trial__nct_id', 'publication__pmid')
    ordering_fields = ('id', 'created', 'status', 'claim_type', 'section')

    def get_serializer_class(self):
        return ClaimListSerializer if self.action == 'list' else ClaimDetailSerializer

    def get_queryset(self):
        qs = Claim.objects.all().select_related('trial', 'publication', 'chunk').order_by('-created', '-id')
        if self.action != 'list':
            return qs.prefetch_related('judgements', 'ners', 'diseases', 'interventions')
        params = self.request.query_params
        if 'status' in params:
            qs = qs.filter(status=params['status'])
        if 'claim_type' in params:
            qs = qs.filter(claim_type=params['claim_type'])
        for key in ('trial', 'publication'):
            if key in params:
                qs = qs.filter(**{f'{key}_id': _parse_int_param(key, params[key])})
        if 'disease' in params:
            qs = qs.filter(diseases__id=_parse_int_param('disease', params['disease']))
        if 'intervention' in params:
            qs = qs.filter(interventions__id=_parse_int_param('intervention', params['intervention']))
        return qs.distinct()


class DiseaseViewSet(BaseReadOnlyViewSet):
    search_fields = ('name', 'mesh')
    ordering_fields = ('id', 'name', 'mesh', 'created')

    def get_serializer_class(self):
        return DiseaseSerializer if self.action == 'list' else DiseaseDetailSerializer

    def get_queryset(self):
        qs = Disease.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
        params = self.request.query_params
        if 'mesh' in params:
            qs = qs.filter(mesh=params['mesh'])
        return qs.distinct()


class InterventionViewSet(BaseReadOnlyViewSet):
    search_fields = ('name', 'mesh')
    ordering_fields = ('id', 'name', 'mesh', 'created')

    def get_serializer_class(self):
        return InterventionSerializer if self.action == 'list' else InterventionDetailSerializer

    def get_queryset(self):
        qs = Intervention.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
        params = self.request.query_params
        if 'mesh' in params:
            qs = qs.filter(mesh=params['mesh'])
        return qs.distinct()


class TrialViewSet(BaseReadOnlyViewSet):
    search_fields = ('nct_id', 'title', 'official_title', 'acronym')
    ordering_fields = ('id', 'nct_id', 'title', 'status', 'phase', 'start_date', 'created')

    def get_serializer_class(self):
        return TrialListSerializer if self.action == 'list' else TrialDetailSerializer

    def get_queryset(self):
        qs = Trial.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
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


class PublicationViewSet(BaseReadOnlyViewSet):
    search_fields = ('pmid', 'title', 'doi', 'journal', 'first_author')
    ordering_fields = ('id', 'pmid', 'title', 'journal', 'year', 'pub_date', 'created')

    def get_serializer_class(self):
        return PublicationListSerializer if self.action == 'list' else PublicationDetailSerializer

    def get_queryset(self):
        qs = Publication.objects.all().order_by('-created', '-id')
        if self.action != 'list':
            return qs
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
