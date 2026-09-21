"""실행 중인 API에 합성 시나리오 7개를 보내는 간단한 통합 스모크 테스트."""
import argparse
import json
from pathlib import Path

import requests


SCENARIO_FILE = Path(__file__).resolve().parents[1] / "sample_data" / "scenarios.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    scenarios = json.loads(SCENARIO_FILE.read_text(encoding="utf-8"))["scenarios"]

    for name, item in scenarios.items():
        payload = {"address": f"합성 테스트 주소 {name}", "scenario": name, **item["request"]}
        response = requests.post(f"{args.base_url.rstrip('/')}/analyze/", json=payload, timeout=90)
        response.raise_for_status()
        data, expected = response.json()["data"], item["expected"]
        assert data["risk_score"] == expected["risk_score"], (name, data["risk_score"], expected["risk_score"])
        assert data["risk_grade"] == expected["risk_grade"], (name, data["risk_grade"], expected["risk_grade"])
        assert data["data_source"] == "sample"
        assert sum(len(hits) for hits in data["evidence"].values()) > 0, name
        print(f"{name}: {data['risk_score']}점 / {data['risk_grade']} / 근거 검색 OK")


if __name__ == "__main__":
    main()
