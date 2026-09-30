"""LLM and Instructor helpers for structured extraction."""

import os
import time
from pathlib import Path
from typing import Type, TypeVar
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
import instructor
from openai import OpenAI
from pydantic import BaseModel
from lib.logs import get_logger, logged

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@logged
def _load_secrets() -> None:
    """Optionally load environment variables and secrets if python-dotenv is available."""
    if not load_dotenv:
        return
    try:
        # Check standard project locations for etc/.env and etc/secrets/.env
        candidates = [
            Path("/home/jovyan/work/etc/.env"),
            Path("/workspace/etc/.env"),
            Path(__file__).resolve().parent.parent.parent / "etc" / ".env",
            Path("/home/jovyan/work/etc/secrets/.env"),
            Path("/workspace/etc/secrets/.env"),
            Path(__file__).resolve().parent.parent.parent / "etc" / "secrets" / ".env",
        ]
        for env_file in candidates:
            if env_file.is_file():
                load_dotenv(env_file, override=False)
    except Exception as exc:
        logger.error("Unable to load optional environment files error_type=%s", type(exc).__name__)


# Ensure environment variables and secrets are loaded if present
_load_secrets()


@logged
def get_llm_uri() -> str | None:
    """Return configured LLM URI/base URL from environment."""
    return (
        os.environ.get("LLM_URI")
        or os.environ.get("LLM_BASE_URL")
        or None
    )


@logged
def get_llm_api_key() -> str:
    """Return configured LLM API key from environment."""
    return os.environ.get("LLM_API_KEY") or "dummy_key"


@logged
def get_default_model() -> str | None:
    """Return configured LLM model name from environment."""
    return os.environ.get("LLM_MODEL")


@logged
def get_instructor_client(
    api_key: str | None = None,
    base_url: str | None = None,
    mode: instructor.Mode = instructor.Mode.MD_JSON,
) -> instructor.Instructor:
    """
    Create and return an Instructor client patched over OpenAI.
    Picks up LLM_URI/LLM_BASE_URL and LLM_API_KEY from environment by default.
    Defaults to Mode.MD_JSON for compatibility with OpenAI-compatible APIs (e.g. Meta Spark Muse).
    """
    key = api_key or get_llm_api_key()
    url = base_url or get_llm_uri()

    client_kwargs: dict = {"api_key": key}
    if url:
        client_kwargs["base_url"] = url

    logger.debug("Creating OpenAI client")
    client = OpenAI(**client_kwargs)
    logger.debug("Created OpenAI client; initializing Instructor")
    inst_client = instructor.from_openai(client, mode=mode)
    logger.debug("Initialized Instructor client")
    return inst_client


@logged
def extract_structured(
    response_model: Type[T],
    prompt: str,
    model: str | None = None,
    client: instructor.Instructor | None = None,
    mode: instructor.Mode = instructor.Mode.MD_JSON,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    max_retries: int = 2,
) -> T:
    """Extract structured data conforming to a Pydantic model using Instructor."""
    inst_client = client or get_instructor_client(mode=mode)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    target_model = model or get_default_model()
    if not target_model:
        raise ValueError(
            "No LLM model specified. Please set the LLM_MODEL environment variable or pass `model` explicitly."
        )

    logger.info("Requesting structured LLM extraction model=%s response_model=%s prompt_chars=%s",
                target_model, response_model.__name__, len(prompt))
    started = time.monotonic()
    result = inst_client.chat.completions.create(
        model=target_model,
        response_model=response_model,
        messages=messages,
        temperature=temperature,
        max_retries=max_retries,
    )
    logger.info("Structured LLM extraction completed model=%s response_model=%s elapsed_s=%.1f",
                target_model, response_model.__name__, time.monotonic() - started)
    return result
