from django.contrib import admin
from .models import (
    Trial,
    Publication,
    PublicationTrial,
    Disease,
    Intervention,
    Biomarker,
    Observation,
    Claim,
    ClaimTrails,
)


@admin.register(Disease)
class DiseaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'mesh', 'created', 'modified')
    search_fields = ('name', 'mesh')


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ('name', 'mesh', 'created', 'modified')
    search_fields = ('name', 'mesh')


@admin.register(Biomarker)
class BiomarkerAdmin(admin.ModelAdmin):
    list_display = ('name', 'gene', 'biomarker_type', 'created', 'modified')
    search_fields = ('name', 'gene', 'biomarker_type')


class PublicationTrialInline(admin.TabularInline):
    model = PublicationTrial
    extra = 1


@admin.register(Trial)
class TrialAdmin(admin.ModelAdmin):
    list_display = ('nct_id', 'title', 'phase', 'status', 'study_type', 'lead_sponsor', 'start_date', 'enrollment', 'created')
    list_filter = ('phase', 'status', 'study_type', 'has_results')
    search_fields = ('nct_id', 'title', 'official_title', 'lead_sponsor', 'acronym', 'org_study_id')
    filter_horizontal = ('diseases', 'interventions', 'biomarkers')
    inlines = [PublicationTrialInline]


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ('pmid', 'title', 'journal', 'year', 'first_author', 'doi', 'pmc', 'created')
    list_filter = ('journal', 'year', 'pubmed_type')
    search_fields = ('pmid', 'title', 'journal', 'abstract', 'first_author', 'doi', 'pmc')
    filter_horizontal = ('diseases', 'interventions', 'biomarkers')
    inlines = [PublicationTrialInline]


@admin.register(PublicationTrial)
class PublicationTrialAdmin(admin.ModelAdmin):
    list_display = ('publication', 'trial', 'relation', 'created', 'modified')
    list_filter = ('relation',)
    search_fields = ('publication__pmid', 'trial__nct_id')


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ('observation_type', 'summary', 'trial', 'publication', 'created', 'modified')
    search_fields = ('observation_type', 'summary')


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ('claim_type', 'section', 'trial', 'publication', 'chunk', 'created', 'modified')
    list_filter = ('claim_type', 'section')
    search_fields = ('trial__nct_id', 'publication__pmid')


@admin.register(ClaimTrails)
class ClaimTrailsAdmin(admin.ModelAdmin):
    list_display = ('id', 'trial', 'publication', 'status_from', 'new_status', 'created')
    list_filter = ('status_from', 'new_status', 'created')
    search_fields = ('trial__nct_id', 'publication__pmid', 'notes')
    readonly_fields = tuple(field.name for field in ClaimTrails._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
