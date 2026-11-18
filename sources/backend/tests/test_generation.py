"""Tests for prompt assembly and per-request instruction loading."""

from types import SimpleNamespace

import pytest

from sage.config import AppConfig
from sage.domain.qa import generation
from sage.domain.qa.models import Chunk
from sage.webapp.apis.qa import service
from sage.webapp.app import app


@pytest.mark.asyncio
async def test_generate_answer_reads_and_includes_instructions_each_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instructions = iter(["Prima istruzione", "Seconda istruzione"])
    prompts: list[str] = []

    async def fake_generate_text(prompt: str) -> str:
        prompts.append(prompt)
        return "answer"

    monkeypatch.setattr(generation, "read_instructions", lambda: next(instructions))
    monkeypatch.setattr(generation, "generate_text", fake_generate_text)

    assert await generation.generate_answer("question", []) == "answer"
    assert await generation.generate_answer("question", []) == "answer"

    assert len(prompts) == 2
    assert "Prima istruzione" in prompts[0]
    assert "Seconda istruzione" in prompts[1]


def test_read_instructions_downloads_the_configured_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage.integrations.storage import instructions

    class FakeBlob:
        def download_as_text(self, *, encoding: str) -> str:
            assert encoding == "utf-8"
            return "Istruzioni dal bucket"

    class FakeBucket:
        def blob(self, name: str) -> FakeBlob:
            assert name == "istruzioni.md"
            return FakeBlob()

    class FakeClient:
        def bucket(self, name: str) -> FakeBucket:
            assert name == "student-instructions"
            return FakeBucket()

    monkeypatch.setattr(
        instructions,
        "get_app_config",
        lambda: SimpleNamespace(instructions_bucket="student-instructions"),
    )
    monkeypatch.setattr(instructions, "get_storage_client", FakeClient)

    assert instructions.read_instructions() == "Istruzioni dal bucket"


def test_instructions_bucket_uses_the_configured_name() -> None:
    shared = AppConfig(project_id="shared-project", resource_prefix="student")
    dedicated = AppConfig(project_id="dedicated-project", resource_prefix="")
    bucket_name = "its-ict-sage-andrea-sassi-instructions"

    assert shared.instructions_bucket == bucket_name
    assert dedicated.instructions_bucket == bucket_name


def test_ask_response_schema_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    async def fake_retrieve(question: str) -> list[Chunk]:
        return []

    async def fake_generate(question: str, chunks: list[Chunk]) -> str:
        return "answer"

    monkeypatch.setattr(service, "retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr(service, "generate_answer", fake_generate)
    monkeypatch.setattr(service, "log_question", lambda *args: None)

    response = TestClient(app).post("/api/ask", json={"question": "question"})

    assert response.status_code == 200
    assert response.json() == {"answer": "answer", "sources": []}
