"""Extract evidence-backed scientific claims from NER-annotated source sections."""

import json
import time

from django.db import transaction
from pydantic import BaseModel

from core.models import Claim, Publication, Trial
from lib.llm import extract_structured
from lib.logs import get_logger, logged

logger = get_logger(__name__)


@transaction.atomic
def create_claim(*, ners=(), diseases=(), interventions=(), **fields):
    """Create a fully linked claim before attempting group membership."""
    from lib.claim_groups import add_claim_to_existing_or_new_claim_group

    claim = Claim.objects.create(**fields)
    claim._grouping_entities = True
    try:
        claim.ners.add(*ners)
        claim.diseases.add(*diseases)
        claim.interventions.add(*interventions)
    finally:
        del claim._grouping_entities
    add_claim_to_existing_or_new_claim_group(claim)
    return claim


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


@logged
def save_claims():
    """Analyze NER-bearing sections of publications and trials without claims."""
    created = []
    started = time.monotonic()
    for model, fields, owner in ((Publication, ("title",), "publication"),
                                 (Trial, ("title", "official_title"), "trial")):
        sources = model.objects.filter(ners__isnull=False, claims__isnull=True).distinct().prefetch_related("chunks", "ners")
        total = sources.count()
        logger.info("Starting claim extraction owner=%s pending=%s", owner, total)
        for index, source in enumerate(sources, start=1):
            logger.info("Processing claims owner=%s id=%s progress=%s/%s", owner, source.pk, index, total)
            ners = list(source.ners.all())
            bundles = [(getattr(source, field), field, None,
                        [ner for ner in ners if ner.chunk_id is None and ner.section == field])
                       for field in fields]
            bundles.extend((chunk.body, chunk.section, chunk,
                            [ner for ner in ners if ner.chunk_id == chunk.pk])
                           for chunk in source.chunks.all())
            for text, section, chunk, entities in bundles:
                if not text or not entities:
                    continue
                mentions = [
                    {"id": ner.pk, "text": ner.text, "label": ner.label}
                    for ner in entities
                ]
                for claim_type, instruction in CLAIM_PROMPTS.items():
                    prompt = (f"{instruction}\nSection: {section}\nText: {text}\n"
                              f"NER mentions: {json.dumps(mentions)}")
                    logger.info("Requesting LLM claims owner=%s id=%s section=%s type=%s prompt_chars=%s",
                                owner, source.pk, section, claim_type, len(prompt))
                    call_started = time.monotonic()
                    suggestions = extract_structured(ClaimSuggestions, prompt)
                    logger.info("Received LLM claims owner=%s id=%s count=%s elapsed_s=%.1f",
                                owner, source.pk, len(suggestions.claims), time.monotonic() - call_started)
                    for suggestion in suggestions.claims:
                        if not suggestion.evidence.strip() or suggestion.evidence not in text:
                            logger.warning("Skipping claim with missing or invalid evidence owner=%s id=%s", owner, source.pk)
                            continue
                        selected_ids = set(suggestion.ner_ids)
                        selected = [ner for ner in entities if ner.pk in selected_ids]
                        if not selected:
                            logger.warning("Skipping claim without matching NER IDs owner=%s id=%s", owner, source.pk)
                            continue
                        claim = create_claim(
                            section=section, claim_type=claim_type, chunk=chunk,
                            evidence=suggestion.evidence, ners=selected,
                            diseases=(ner.disease_id for ner in selected if ner.disease_id),
                            interventions=(ner.intervention_id for ner in selected if ner.intervention_id),
                            meta={"ner_ids": [ner.pk for ner in selected]}, **{owner: source},
                        )
                        created.append(claim)
                        logger.debug("Saved claim pk=%s owner=%s id=%s", claim.pk, owner, source.pk)
    logger.info("Claim extraction complete created=%s elapsed_s=%.1f", len(created), time.monotonic() - started)
    return created
