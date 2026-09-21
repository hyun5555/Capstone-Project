# sample_data (데모용 CODEF 응답)

`ANALYSIS_DATA_SOURCE=sample` 일 때 CODEF 대신 이 폴더의 응답 파일을 읽어 분석합니다.

- `registry_response.json` / `building_response.json` : **가상 데이터**입니다 (실제 등기부/건축물대장 아님, `_note` 참고).
- `scenarios.json`: Swagger의 `/analyze/` 요청에 `scenario`를 넣어 선택할 수 있는 7가지 가상 계약 상황입니다.
- 실제 CODEF 응답을 저장했다면 (`python scripts/capture_codef.py ...`) 개인정보가 마스킹된 파일로 이 이름 그대로 교체하면 그 응답으로 재생됩니다.
- 실제 응답 원본(`codef_captures/` 폴더)은 개인정보가 들어 있으므로 git 에 올리지 마세요. (.gitignore 에 등록됨)

| scenario | 검증 상황 | 보증금 / 시세 | 예상 등급 |
| --- | --- | ---: | --- |
| `safe` | 소유자·건물 정보 일치, 위험 권리 없음 | 3억 / 5억 | 안전 |
| `owner_mismatch` | 두 문서의 소유자 불일치 | 2.5억 / 5억 | 주의 |
| `active_seizure` | 유효한 압류·경매개시결정 | 2억 / 5억 | 주의 |
| `excessive_mortgage` | 채권최고액 3억 + 보증금 2억 | 2억 / 5억 | 위험 |
| `cancelled_rights` | 과거 가압류·근저당이 모두 말소됨 | 2.5억 / 5억 | 안전 |
| `violation_nonresidential` | 근린생활시설 + 위반건축물 | 1억 / 3억 | 위험 |
| `lease_rights` | 전세권·임차권등기명령 존재 | 1.5억 / 5억 | 주의 |

예시 요청:

```json
{
  "address": "서울특별시 강남구 테스트로 4",
  "deposit": 200000000,
  "marketPrice": 500000000,
  "scenario": "excessive_mortgage"
}
```

Docker API를 켠 뒤 전체 시나리오를 한 번에 검증하려면 `docker compose -f backend/docker-compose.yml exec -T api python scripts/smoke_sample_scenarios.py`를 실행합니다.
