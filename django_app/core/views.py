from django.http import JsonResponse
from .models import (
    Trial,
    Publication,
    PublicationTrial,
    Disease,
    Intervention,
    Biomarker,
    Observation,
    Claim,
)


def index(request):
    """Status endpoint returning counts of stored records."""
    return JsonResponse({
        'status': 'ok',
        'service': '1FL Clinical Knowledge Platform',
        'counts': {
            'trials': Trial.objects.count(),
            'publications': Publication.objects.count(),
            'publication_trials': PublicationTrial.objects.count(),
            'diseases': Disease.objects.count(),
            'interventions': Intervention.objects.count(),
            'biomarkers': Biomarker.objects.count(),
            'observations': Observation.objects.count(),
            'claims': Claim.objects.count(),
        }
    })
