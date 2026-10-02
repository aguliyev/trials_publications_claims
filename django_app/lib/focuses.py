from core.models import Claim, ClaimGroup, Focus


FocusSource = Claim | ClaimGroup


def _ordered_names(manager) -> list[str]:
    names = [name.strip() for name in manager.values_list('name', flat=True)]
    return sorted((name for name in names if name), key=str.casefold)


def build_focus_query(source: FocusSource) -> str:
    if not isinstance(source, (Claim, ClaimGroup)):
        raise TypeError('Focus source must be a Claim or ClaimGroup.')
    terms = _ordered_names(source.diseases) + _ordered_names(source.interventions)
    return ' '.join(terms)


def focus_state(source: FocusSource) -> dict[str, object]:
    query = build_focus_query(source)
    focus_id = Focus.objects.filter(query=query).values_list('pk', flat=True).first() if query else None
    return {'query': query, 'exists': focus_id is not None, 'focus_id': focus_id}


def get_or_create_focus(source: FocusSource) -> tuple[Focus, bool]:
    query = build_focus_query(source)
    if not query:
        raise ValueError('No disease or intervention terms are available for this focus.')
    return Focus.objects.get_or_create(query=query)
