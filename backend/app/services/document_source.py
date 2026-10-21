# backend/app/services/document_source.py
"""
분석에 쓸 등기부/건축물대장을 가져온다.

- source="codef":  CODEF 를 호출한다 (기본).
- source="sample": sample_data/ 폴더에 저장해 둔 CODEF 응답(JSON)을 재생한다 (CODEF 를 쓸 수 없을 때의 데모용).
  실제 응답을 capture_codef.py 로 저장해 두면 그 응답으로 재생된다. 자동 폴백은 하지 않는다 — 설정으로만 켠다.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.services.codef_normalizer import (
    decode_codef_body, normalize_building_response, normalize_registry_response,
)
from app.services.documents import PropertyDoc

SAMPLE_REGISTRY_FILE = "registry_response.json"
SAMPLE_BUILDING_FILE = "building_response.json"
SAMPLE_SCENARIOS_FILE = "scenarios.json"


class SampleDataMissing(Exception):
    pass


class MissingAddressParts(Exception):
    pass


@dataclass
class LoadedDocs:
    registry: PropertyDoc
    building: PropertyDoc
    source: str                                 # "codef" | "sample"
    notes: list = field(default_factory=list)
    processing: dict = field(default_factory=dict)


def read_sample_response(path: Path) -> dict:
    if not path.exists():
        raise SampleDataMissing(f"샘플 응답 파일이 없습니다: {path.name} (CODEF_SAMPLE_DIR={path.parent})")
    envelope = decode_codef_body(path.read_text(encoding="utf-8"))
    data = envelope.get("data", envelope) if isinstance(envelope, dict) else envelope
    if not isinstance(data, dict):
        raise SampleDataMissing(f"샘플 응답 형식이 올바르지 않습니다: {path.name}")
    return data


def load_sample_documents(address: str, sample_dir: str, scenario: Optional[str] = None) -> LoadedDocs:
    d = Path(sample_dir)
    if scenario:
        path = d / SAMPLE_SCENARIOS_FILE
        if not path.exists():
            raise SampleDataMissing(f"시나리오 파일이 없습니다: {path.name}")
        item = json.loads(path.read_text(encoding="utf-8")).get("scenarios", {}).get(scenario)
        if not item:
            raise SampleDataMissing(f"알 수 없는 샘플 시나리오입니다: {scenario}")
        registry_data, building_data = item.get("registry"), item.get("building")
        if not isinstance(registry_data, dict) or not isinstance(building_data, dict):
            raise SampleDataMissing(f"샘플 시나리오 형식이 올바르지 않습니다: {scenario}")
    else:
        registry_data = read_sample_response(d / SAMPLE_REGISTRY_FILE)
        building_data = read_sample_response(d / SAMPLE_BUILDING_FILE)

    registry = normalize_registry_response(registry_data, address)
    building = normalize_building_response(building_data, address)
    label = f" ({scenario})" if scenario else ""
    return LoadedDocs(registry, building, "sample", [f"데모 데이터입니다{label}. 입력한 주소의 실제 문서가 아닙니다."])


async def load_codef_documents(client, address: str, road_name: Optional[str],
                               main_no: Optional[str], sub_no: Optional[str]) -> LoadedDocs:
    from app.clients.codef_client import fetch_building, fetch_registry

    if not road_name or not main_no:
        raise MissingAddressParts("건축물대장 조회에는 roadName, mainAddressNo 가 필요합니다. (부번은 없으면 '0')")

    reg_raw, bld_raw = await asyncio.gather(
        fetch_registry(client, address),
        fetch_building(client, road_name, main_no, sub_no or "0"),
    )
    return LoadedDocs(
        normalize_registry_response(reg_raw, address),
        normalize_building_response(bld_raw, address),
        "codef",
    )


def load_pdf_documents(registry_data: bytes, building_data: bytes, address: str) -> LoadedDocs:
    """업로드한 두 PDF를 읽어 기존 분석용 PropertyDoc 두 개로 바꾼다."""
    from app.services.pdf_extractor import extract_pdf
    from app.services.pdf_normalizer import normalize_building_pdf, normalize_registry_pdf

    registry_pdf = extract_pdf(registry_data)
    building_pdf = extract_pdf(building_data)
    processing = {
        "registry": registry_pdf.processing(),
        "building": building_pdf.processing(),
    }
    notes = []
    for label, result in (("등기부등본", processing["registry"]), ("건축물대장", processing["building"])):
        if result["ocr_pages"]:
            pages = ", ".join(map(str, result["ocr_pages"]))
            notes.append(f"{label} {pages}페이지는 OCR로 읽었습니다. 원본과 함께 확인하세요.")
        notes.extend(result["warnings"])
    return LoadedDocs(
        normalize_registry_pdf(registry_pdf, address),
        normalize_building_pdf(building_pdf, address),
        "pdf",
        notes,
        processing,
    )
