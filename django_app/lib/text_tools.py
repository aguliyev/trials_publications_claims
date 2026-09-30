from langchain_text_splitters import RecursiveCharacterTextSplitter
from lib.logs import get_logger, logged

logger = get_logger(__name__)


TRIAL_FIELDS_TO_CHUNK = ('summary', 'detailed_description', 'eligibility_criteria')
PUBLICATION_FIELDS_TO_CHUNK = ('abstract',)
TRIAL_FIELDS_NOT_TO_CHUNK = ('title', 'official_title')
PUBLICATION_FIELDS_NOT_TO_CHUNK = ('title',)


@logged
def split_ner_text(text: str, chunk_size: int = 1200, chunk_overlap: int = 200) -> list[str]:
    """Split text at natural boundaries with overlap to retain edge entities."""
    logger.debug("Splitting source text length=%s", len(text))
    result = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
    ).split_text(text)
    logger.debug("Split source text chunks=%s", len(result))
    return result


@logged
def _replace_chunks(source, sections: tuple[str, ...], owner: str, chunk_size: int, chunk_overlap: int):
    from django.db import transaction
    from core.models import Chunk

    chunks = [
        Chunk(**{owner: source}, section=section, sequ=sequ, body=body)
        for section in sections
        for sequ, body in enumerate(split_ner_text(getattr(source, section), chunk_size, chunk_overlap))
    ]
    with transaction.atomic():
        logger.debug("Replacing chunks owner=%s id=%s count=%s", owner, source.pk, len(chunks))
        source.chunks.filter(section__in=sections).delete()
        saved = Chunk.objects.bulk_create(chunks)
        logger.debug("Replaced chunks owner=%s id=%s count=%s", owner, source.pk, len(saved))
        return saved


@logged
def save_publication_chunks(publication, chunk_size: int = 1200, chunk_overlap: int = 200):
    return _replace_chunks(publication, PUBLICATION_FIELDS_TO_CHUNK, 'publication', chunk_size, chunk_overlap)


@logged
def save_trial_chunks(trial, chunk_size: int = 1200, chunk_overlap: int = 200):
    return _replace_chunks(trial, TRIAL_FIELDS_TO_CHUNK, 'trial', chunk_size, chunk_overlap)
