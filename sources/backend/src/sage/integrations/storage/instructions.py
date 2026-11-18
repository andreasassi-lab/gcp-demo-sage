"""Reads the additional model instructions from Cloud Storage."""

from functools import lru_cache

from google.cloud import storage

from sage.config import get_app_config

_INSTRUCTIONS_OBJECT = "istruzioni.md"


@lru_cache
def get_storage_client() -> storage.Client:
    config = get_app_config()
    return storage.Client(project=config.project_id)


def read_instructions() -> str:
    config = get_app_config()
    return (
        get_storage_client()
        .bucket(config.instructions_bucket)
        .blob(_INSTRUCTIONS_OBJECT)
        .download_as_text(encoding="utf-8")
    )
