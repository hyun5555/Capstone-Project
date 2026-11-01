"""비식별 PDF 골든셋으로 OCR→정규화→위험규칙 회귀를 검사한다."""
from __future__ import annotations

import json
from pathlib import Path

from app.services.document_compare import build_findings, compare_documents
from app.services.document_source import load_pdf_documents
from app.services.risk_score import RISK_RULE_VERSION, calculate_risk_score

DEFAULT_MANIFEST = Path(__file__).with_name("pdf_golden_cases.json")


def run_pdf_golden(manifest_path: Path = DEFAULT_MANIFEST) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for case in manifest["cases"]:
        registry_path = (manifest_path.parent / case["registry_pdf"]).resolve()
        building_path = (manifest_path.parent / case["building_pdf"]).resolve()
        docs = load_pdf_documents(registry_path.read_bytes(), building_path.read_bytes(), case["address"])
        findings = build_findings(docs.registry, docs.building, compare_documents(docs.registry, docs.building))
        risk = calculate_risk_score(
            findings,
            {"보증금": case["deposit"], "시세": case["market_price"]},
        )
        actual_codes = {item["code"]: item["status"] for item in risk["codes"]}
        checks = {
            "grade": risk["grade"] == case["expected_grade"],
            "codes": all(actual_codes.get(code) == value for code, value in case["expected_codes"].items()),
            "rule_version": risk["rule_version"] == RISK_RULE_VERSION,
        }
        results.append({"name": case["name"], "ok": all(checks.values()), "checks": checks})
    return results


if __name__ == "__main__":
    output = run_pdf_golden()
    print(json.dumps(output, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(item["ok"] for item in output) else 1)
