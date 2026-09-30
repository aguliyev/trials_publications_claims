from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views
from .api import (
    ClaimViewSet,
    DiseaseViewSet,
    InterventionViewSet,
    PublicationViewSet,
    SupportingRecordView,
    TrialViewSet,
)

router = SimpleRouter()
router.register('claims', ClaimViewSet, basename='claim')
router.register('diseases', DiseaseViewSet, basename='disease')
router.register('interventions', InterventionViewSet, basename='intervention')
router.register('trials', TrialViewSet, basename='trial')
router.register('publications', PublicationViewSet, basename='publication')

urlpatterns = [
    path('', views.index, name='index'),
    path('app/', views.workspace, name='workspace'),
    path('api/records/<str:kind>/<int:pk>/', SupportingRecordView.as_view(), name='supporting-record'),
    path('api/', include(router.urls)),
]
