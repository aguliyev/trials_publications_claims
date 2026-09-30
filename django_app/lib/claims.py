"""Extract evidence-backed scientific claims from NER-annotated source sections."""

import json

from django.db import transaction
from pydantic import BaseModel

from core.models import Claim, Publication, Trial
from lib.llm import extract_structured


CLAIM_PROMPTS = {
    "intervention_worked_for_disease": (
        "Identify only reported positive treatment outcomes where an intervention worked for a disease. "
        "A study objective, hypothesis, ongoing trial, negative result, or mere co-mention is not evidence of efficacy. "
        "Use the NER mentions as context, not proof. Return zero claims if there is no explicit positive result. "
        "For each claim return a verbatim evidence excerpt and the IDs of NER mentions supporting it. "
        "Only use NER IDs provided in this section; do not invent entities or results."
    ),
}


class SuggestedClaim(BaseModel):
    evidence: str
    ner_ids: list[int]


class ClaimSuggestions(BaseModel):
    claims: list[SuggestedClaim]


def save_claims():
    """Analyze NER-bearing sections of publications and trials without claims."""
    created = []
    for model, fields, owner in ((Publication, ("title",), "publication"),
                                 (Trial, ("title", "official_title"), "trial")):
        sources = model.objects.filter(ners__isnull=False, claims__isnull=True).distinct().prefetch_related("chunks", "ners")
        for source in sources:
            ners = list(source.ners.all())
            bundles = [(getattr(source, field), field, None,
                        [ner for ner in ners if ner.chunk_id is None and ner.meta.get("section") == field])
                       for field in fields]
            bundles.extend((chunk.body, chunk.section, chunk,
                            [ner for ner in ners if ner.chunk_id == chunk.pk])
                           for chunk in source.chunks.all())
            for text, section, chunk, entities in bundles:
                if not text or not entities:
                    continue
                mentions = [{"id": ner.pk, "text": ner.text, "label": ner.label, "links": ner.links}
                            for ner in entities]
                for claim_type, instruction in CLAIM_PROMPTS.items():
                    prompt = (f"{instruction}\nSection: {section}\nText: {text}\n"
                              f"NER mentions: {json.dumps(mentions)}")
                    suggestions = extract_structured(ClaimSuggestions, prompt)
                    for suggestion in suggestions.claims:
                        if not suggestion.evidence.strip() or suggestion.evidence not in text:
                            continue
                        selected_ids = set(suggestion.ner_ids)
                        selected = [ner for ner in entities if ner.pk in selected_ids]
                        if not selected:
                            continue
                        with transaction.atomic():
                            claim = Claim.objects.create(
                                section=section, claim_type=claim_type, chunk=chunk,
                                meta={"evidence": suggestion.evidence,
                                      "ner_ids": [ner.pk for ner in selected]}, **{owner: source},
                            )
                            claim.ners.add(*selected)
                            claim.diseases.add(*(ner.disease_id for ner in selected if ner.disease_id))
                            claim.interventions.add(*(ner.intervention_id for ner in selected if ner.intervention_id))
                        created.append(claim)
    return created
