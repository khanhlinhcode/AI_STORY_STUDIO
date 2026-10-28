from __future__ import annotations

import json

import httpx
import pytest

from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.models.adapters.fake import FakeAdapter
from studio_api.modules.models.adapters.ollama import (
    OllamaAdapter,
    _has_repeated_scenes,
    _has_unsupported_source_claim,
)
from studio_api.modules.narrative.source_evidence import (
    SourceEvidence,
    ground_source_evidence,
    validate_geography_claims,
)

SOURCE = {
    "title": "A-81 Reaches South Georgia",
    "summary": (
        "The iceberg A-81 has drifted to South Georgia Island in the South Atlantic Ocean. "
        "Scientists tracked it from the Weddell Sea. "
        "The iceberg originated near Antarctica's Brunt Ice Shelf."
    ),
    "source_url": "https://science.nasa.gov/earth/earth-observatory/a-81/",
    "published_at": "2026-10-27T00:00:00+00:00",
}
EVIDENCE = {
    "subject_name": "A-81",
    "subject_type": "iceberg",
    "verified_location": "South Georgia Island",
    "verified_facts": ["The iceberg A-81 has drifted to South Georgia Island"],
    "forbidden_locations": [],
}


def test_evidence_requires_source_quotations_and_blocks_opposite_pole() -> None:
    evidence = ground_source_evidence(EVIDENCE, SOURCE)
    assert evidence.subject_name == "A-81"
    assert "Bắc Cực" in evidence.forbidden_locations
    with pytest.raises(StudioError) as failure:
        ground_source_evidence({**EVIDENCE, "verified_location": "Arctic Ocean"}, SOURCE)
    assert failure.value.code == ErrorCode.FACTUAL_VALIDATION_FAILED
    unrelated = ground_source_evidence({**EVIDENCE, "subject_name": "Weddell Sea"}, SOURCE)
    assert unrelated.subject_name == SOURCE["title"]


def test_geography_validator_catches_forbidden_location_and_bad_phrase() -> None:
    evidence = SourceEvidence(
        subject_name="A-81",
        subject_type="iceberg",
        verified_location="South Georgia Island",
        verified_facts=["The iceberg A-81 has drifted to South Georgia Island"],
        forbidden_locations=["Bắc Cực"],
        source_url=SOURCE["source_url"],
        source_date=SOURCE["published_at"],
    )
    violations = validate_geography_claims(
        {"title": "A-81", "scenes": [{"id": 1, "narration": "Tảng băng đến Bắc Cực."}]},
        evidence,
    )
    assert len(violations) == 1
    assert "Bắc Cực" in violations[0]
    assert (
        validate_geography_claims(
            {"title": "A-81", "scenes": [{"id": 1, "narration": "Tảng băng ở Nam Cực."}]},
            evidence,
        )
        == []
    )


def test_quality_gate_rejects_observed_repetition_and_source_misread() -> None:
    assert _has_repeated_scenes(
        {
            "scenes": [
                {"narration": "Bạn Thỏ nhìn tảng băng A-81 trôi trên biển."},
                {"narration": "Bạn Thỏ nhìn tảng băng A-81 trôi trên biển!"},
            ]
        }
    )
    assert _has_unsupported_source_claim(
        {"scenes": [{"narration": "Tảng băng A-81 đến gần bờ đảo South Georgia."}]},
        "The iceberg approached South Georgia and bumped its underwater shelf.",
    )
    assert _has_unsupported_source_claim(
        {"scenes": [{"narration": "Lá này sẽ được vệ tinh NASA theo dõi."}]},
        "NASA observes forests from satellites.",
    )
    assert _has_unsupported_source_claim(
        {"scenes": [{"narration": "A-81 đã va chạm với thềm ngầm."}]},
        "It appeared to be bumping along the underwater shelf.",
    )


@pytest.mark.asyncio
async def test_ollama_retries_bad_geography_then_accepts_grounded_story() -> None:
    story = await FakeAdapter().generate_script("A-81", source_context=SOURCE)
    for scene, narration in zip(
        story["scenes"],
        [
            "Mimi xem ảnh vệ tinh về tảng băng A-81 ở Nam Cực.",
            "Tí đọc tên tảng băng trên tấm bản đồ bên cạnh.",
            "Các bạn tìm hiểu biển Weddell trong bài báo NASA.",
            "Mimi thấy tảng băng trôi về phía bắc trên bản đồ.",
            "Cả nhóm nhìn ảnh đảo South Georgia trong nguồn.",
            "Các bạn kể lại điều đã học rồi cất tấm bản đồ.",
        ],
        strict=True,
    ):
        scene["narration"] = narration
    wrong = json.loads(json.dumps(story, ensure_ascii=False))
    wrong["scenes"][0]["narration"] = "Mimi nhìn thấy tảng băng tại Bắc Cực."
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content)
        requests.append(data)
        output = EVIDENCE if len(requests) == 1 else wrong if len(requests) == 2 else story
        return httpx.Response(200, json={"response": json.dumps(output, ensure_ascii=False)})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        generated = await OllamaAdapter(client).generate_script("A-81", source_context=SOURCE)
    assert len(requests) == 3
    assert "South Georgia Island" in str(requests[1]["system"])
    assert generated["scenes"][0]["narration"] == story["scenes"][0]["narration"]


@pytest.mark.asyncio
async def test_ollama_fails_closed_after_three_geography_violations() -> None:
    story = await FakeAdapter().generate_script("A-81", source_context=SOURCE)
    story["scenes"][0]["narration"] = "Mimi đến Bắc Cực để xem tảng băng."
    count = 0

    def respond(_request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        output = EVIDENCE if count == 1 else story
        return httpx.Response(200, json={"response": json.dumps(output, ensure_ascii=False)})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(StudioError) as failure:
            await OllamaAdapter(client).generate_script("A-81", source_context=SOURCE)
    assert count == 4
    assert failure.value.code == ErrorCode.FACTUAL_VALIDATION_FAILED
