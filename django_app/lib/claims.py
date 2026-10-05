"""Extract evidence-backed scientific claims from NER-annotated source sections."""

import json
import time
from collections.abc import Iterable, Sequence
from typing import Any, Literal

from django.db import transaction
from pydantic import BaseModel

from core.models import Chunk, Claim, Ner, Publication, Trial
from lib.llm import extract_structured
from lib.logs import get_logger, logged
from lib.prompts.claims import CLAIM_PROMPTS, CLAIM_PROMPT_TEMPLATE

logger = get_logger(__name__)


@transaction.atomic
def create_claim(
    *,
    ners: Iterable[Ner] = (),
    diseases: Iterable[Any] = (),
    interventions: Iterable[Any] = (),
    **fields: Any,
) -> Claim:
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


class SuggestedClaim(BaseModel):
    evidence: str
    ner_ids: list[int]


class ClaimSuggestions(BaseModel):
    claims: list[SuggestedClaim]


def _source_bundles(
    source: Publication | Trial,
    fields: Sequence[str],
    ners: Sequence[Ner],
) -> list[tuple[str, str, Chunk | None, list[Ner]]]:
    """Return source fields and chunks paired with their matching NERs."""
    bundles = [
        (getattr(source, field), field, None,
         [ner for ner in ners if ner.chunk_id is None and ner.section == field])
        for field in fields
    ]
    bundles.extend(
        (chunk.body, chunk.section, chunk,
         [ner for ner in ners if ner.chunk_id == chunk.pk])
        for chunk in source.chunks.all()
    )
    return bundles


def _save_suggested_claim(
    suggestion: SuggestedClaim,
    *,
    entities: Sequence[Ner],
    text: str,
    section: str,
    chunk: Chunk | None,
    claim_type: str,
    owner: Literal["publication", "trial"],
    source: Publication | Trial,
) -> Claim | None:
    """Persist a suggestion only when its evidence and NER references are valid."""
    if not suggestion.evidence.strip() or suggestion.evidence not in text:
        logger.warning("Skipping claim with missing or invalid evidence owner=%s id=%s", owner, source.pk)
        return None

    selected_ids = set(suggestion.ner_ids)
    selected = [ner for ner in entities if ner.pk in selected_ids]
    if not selected:
        logger.warning("Skipping claim without matching NER IDs owner=%s id=%s", owner, source.pk)
        return None

    claim = create_claim(
        section=section, claim_type=claim_type, chunk=chunk,
        evidence=suggestion.evidence, ners=selected,
        diseases=(ner.disease_id for ner in selected if ner.disease_id),
        interventions=(ner.intervention_id for ner in selected if ner.intervention_id),
        meta={"ner_ids": [ner.pk for ner in selected]}, **{owner: source},
    )
    logger.debug("Saved claim pk=%s owner=%s id=%s", claim.pk, owner, source.pk)
    return claim


def _extract_bundle_claims(
    *,
    text: str,
    section: str,
    chunk: Chunk | None,
    entities: Sequence[Ner],
    owner: Literal["publication", "trial"],
    source: Publication | Trial,
) -> list[Claim]:
    """Request each configured claim type for a source section and save valid results."""
    if not text or not entities:
        return []

    mentions = [
        {"id": ner.pk, "text": ner.text, "label": ner.label}
        for ner in entities
    ]
    created = []
    for claim_type, instruction in CLAIM_PROMPTS.items():
        prompt = CLAIM_PROMPT_TEMPLATE.format(
            instruction=instruction, section=section, text=text, mentions=json.dumps(mentions))
        logger.info("Requesting LLM claims owner=%s id=%s section=%s type=%s prompt_chars=%s",
                    owner, source.pk, section, claim_type, len(prompt))
        call_started = time.monotonic()
        suggestions = extract_structured(ClaimSuggestions, prompt)
        logger.info("Received LLM claims owner=%s id=%s count=%s elapsed_s=%.1f",
                    owner, source.pk, len(suggestions.claims), time.monotonic() - call_started)
        for suggestion in suggestions.claims:
            claim = _save_suggested_claim(
                suggestion, entities=entities, text=text, section=section, chunk=chunk,
                claim_type=claim_type, owner=owner, source=source)
            if claim is not None:
                created.append(claim)
    return created


def _process_source(
    source: Publication | Trial,
    fields: Sequence[str],
    owner: Literal["publication", "trial"],
) -> list[Claim]:
    """Extract claims from a source's NER-bearing fields and chunks."""
    ners = list(source.ners.all())
    created = []
    for text, section, chunk, entities in _source_bundles(source, fields, ners):
        created.extend(_extract_bundle_claims(
            text=text, section=section, chunk=chunk, entities=entities,
            owner=owner, source=source))
    return created


@logged
def save_claims() -> list[Claim]:
    """Analyze NER-bearing sections of publications and trials not yet processed."""
    created = []
    started = time.monotonic()
    for model, fields, owner in ((Publication, ("title",), "publication"),
                                 (Trial, ("title", "official_title"), "trial")):
        sources = model.objects.filter(claims_generated=False, ners__isnull=False).distinct().prefetch_related("chunks", "ners")
        total = sources.count()
        logger.info("Starting claim extraction owner=%s pending=%s", owner, total)
        for index, source in enumerate(sources, start=1):
            logger.info("Processing claims owner=%s id=%s progress=%s/%s", owner, source.pk, index, total)
            created.extend(_process_source(source, fields, owner))
            model.objects.filter(pk=source.pk).update(claims_generated=True)
    logger.info("Claim extraction complete created=%s elapsed_s=%.1f", len(created), time.monotonic() - started)
    return created
