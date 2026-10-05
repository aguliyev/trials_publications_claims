from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views
from .api import (
    ClaimViewSet,
    ClaimTrailsViewSet,
    ClaimGroupViewSet,
    DiseaseViewSet,
    FocusViewSet,
    GeneticViewSet,
    InterventionViewSet,
    NerViewSet,
    PublicationImportView,
    PublicationViewSet,
    SourceDetailView,
    SourceSearchView,
    SupportingRecordView,
    TrialImportView,
    TrialViewSet,
)

router = SimpleRouter()
router.register('claim-groups', ClaimGroupViewSet, basename='claim-group')
router.register('claims', ClaimViewSet, basename='claim')
router.register('claim-trails', ClaimTrailsViewSet, basename='claim-trail')
router.register('diseases', DiseaseViewSet, basename='disease')
router.register('interventions', InterventionViewSet, basename='intervention')
router.register('genetics', GeneticViewSet, basename='genetic')
router.register('ners', NerViewSet, basename='ner')
router.register('trials', TrialViewSet, basename='trial')
router.register('publications', PublicationViewSet, basename='publication')
router.register('focuses', FocusViewSet, basename='focus')

urlpatterns = [
    path('', views.workspace, name='index'),
    path('app/', views.workspace, name='workspace'),
    path('status/', views.status, name='status'),
    path('api/sources/', SourceSearchView.as_view(), name='source-search'),
    path('api/sources/<str:kind>/<str:source_id>/', SourceDetailView.as_view(), name='source-detail'),
    path('api/import/publications/', PublicationImportView.as_view(), name='import-publications'),
    path('api/import/trials/', TrialImportView.as_view(), name='import-trials'),
    path('api/records/<str:kind>/<int:pk>/', SupportingRecordView.as_view(), name='supporting-record'),
    path('api/', include(router.urls)),
]
