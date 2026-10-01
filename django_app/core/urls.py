from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views
from .api import (
    ClaimViewSet,
    ClaimGroupViewSet,
    DiseaseViewSet,
    InterventionViewSet,
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
router.register('diseases', DiseaseViewSet, basename='disease')
router.register('interventions', InterventionViewSet, basename='intervention')
router.register('trials', TrialViewSet, basename='trial')
router.register('publications', PublicationViewSet, basename='publication')

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
