# 분석 이력·위험코드 설계

## 데이터 흐름

PDF 업로드 → 텍스트 추출/OCR → 문서 정규화 → Chroma 근거 저장 → 규칙 기반 위험코드 계산 → analysis_jobs.result 저장 → 사용자별 이력 조회 순서로 처리한다.

analysis_jobs.user_id가 소유권 경계다. 이력 조회·수정·삭제와 벡터 검색은 모두 인증된 사용자 ID를 조건으로 사용한다. 결과에 저장하는 소유자명은 마스킹하며, 사용자가 정정 화면에 입력한 이름도 비교 직후 마스킹해 저장한다.

## API

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET | /analyze/history | 현재 사용자 분석 목록 |
| GET | /analyze/history/{job_id} | 현재 사용자 분석 결과 |
| PATCH | /analyze/history/{job_id}/corrections | OCR 추출값 정정 및 위험 규칙 재계산 |
| DELETE | /analyze/history/{job_id} | 분석 한 건 삭제 |
| DELETE | /analyze/history | 개인 분석 데이터 전체 삭제 |

계정 삭제도 사용자의 분석 이력을 함께 삭제한다. 동일 문서의 case_id가 다른 사용자의 유효 분석에서 참조되는 경우 Chroma 청크는 공유 참조가 끝날 때까지 유지한다.

Chroma 삭제 요청은 개인정보가 없는 case 해시만 vector_deletions 대기열에 같은 트랜잭션으로 기록한다. Chroma가 일시적으로 열리지 않아도 성공할 때까지 재시도한다.

## Chroma 보존

CHROMA_RETENTION_DAYS 기본값은 30일이다. 만료된 분석은 벡터 검색 권한이 즉시 거부되며, 실행 중인 API가 매시간 만료 청크를 물리적으로 정리한다. 이력 JSON은 사용자가 삭제하거나 계정을 삭제할 때까지 남고, 벡터 보존기간과 별도로 관리한다.

## OCR 신뢰도와 정정

document_processing은 문서·페이지별 confidence, confidence_basis=heuristic, needs_review를 제공한다. 이 값은 OCR 엔진이 제공한 확률이 아니라 읽힌 글자량과 문자 비율로 계산한 검토 우선순위다.

정정 가능한 값은 소유자 표시, 유효 권리 유형, 채권최고액, 위반건축물 표시, 건물 용도, 보증금, 시세다. 정정은 원문 PDF나 기존 근거를 바꾸지 않고 review_fields와 재계산 결과를 갱신한다.

## 위험 규칙

현재 규칙 버전은 2026.11-v1이다. 모든 코드는 detected, clear, unknown 중 하나를 반환한다.

| 코드 | 근거 |
| --- | --- |
| OWNER_MISMATCH | 등기부·건축물대장 소유자 비교 |
| REGISTRY_SEIZURE | 등기부의 말소되지 않은 압류 |
| REGISTRY_PROVISIONAL_SEIZURE | 등기부의 말소되지 않은 가압류 |
| REGISTRY_AUCTION | 등기부의 말소되지 않은 경매개시결정 |
| PRIOR_RIGHT_REVIEW | 기존 전세권·임차권 존재. 실제 선순위 여부는 접수일 등 추가 확인 필요 |
| MORTGAGE_DEPOSIT_RATIO | (채권최고액 + 보증금) / 시세, 80% 이상 감지 |
| BUILDING_VIOLATION | 건축물대장의 위반건축물 표시 |

등기부와 건축물대장만으로 임대인의 범죄 이력이나 범죄 가능성을 추정하지 않는다. 외부 공식 신호는 제공기관, 정확한 개인 식별키, 법적 처리 근거, 최신성·정정·삭제 절차가 확인되기 전에는 연결하지 않는다.

## 골든 평가

비식별 PDF 회귀셋은 backend/evaluation/pdf_golden_cases.json에 등록한다.

    cd backend
    venv/bin/python -m evaluation.pdf_golden

현재 저장소에는 개인정보가 제거된 안전 기준 문서 한 쌍만 포함한다. 실제 운영 문서는 이용 동의와 비식별 검수가 끝난 후 기대 위험코드를 사람이 확정해 추가해야 한다.
