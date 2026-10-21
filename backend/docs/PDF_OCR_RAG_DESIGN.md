# PDF 업로드·OCR·RAG 분석 구현 설계

## 1. 목표

사용자가 등기부등본 PDF와 건축물대장 PDF를 직접 올리면 서버가 문서를 읽고, 기존 위험 분석과 RAG 설명을 실행한다.

```text
Flutter
  └─ 등기부등본 PDF + 건축물대장 PDF + 주소 + 보증금
       ↓ multipart/form-data
FastAPI /analyze/pdf
  ├─ 파일 검증
  ├─ PDF 텍스트 추출
  ├─ 텍스트가 없는 페이지만 OCR
  ├─ PropertyDoc 정규화
  ├─ 문서 종류·주소·필수 항목 검증
  └─ 기존 분석 파이프라인
       ├─ 규칙 기반 비교와 위험 점수
       ├─ 개인정보 마스킹
       ├─ 청킹·ChromaDB 색인·검색
       └─ 검색 근거를 사용한 LLM 설명
```

PDF는 새로운 입력 형식일 뿐이다. 내부 공통 모델인 `PropertyDoc`, 위험 점수 규칙, ChromaDB 검색, LLM 설명 코드는 유지한다. LLM은 기존과 같이 판정을 설명할 뿐, OCR 결과에서 위험 점수를 직접 만들지 않는다.

## 2. 범위

### 이번 구현에 포함

1. 등기부등본 PDF 한 개와 건축물대장 PDF 한 개 업로드
2. 텍스트 PDF 우선 추출, 스캔 페이지만 한국어 OCR
3. 두 문서를 기존 `PropertyDoc`으로 정규화
4. 기존 문서 비교, 위험 점수, ChromaDB, RAG 설명 재사용
5. 파일 크기·페이지 수·문서 종류·주소·필수 항목 검증
6. 개인정보 마스킹 후 벡터 저장
7. Flutter PDF 선택 및 업로드 화면

### 이번 구현에서 제외

1. 여러 세대 문서 일괄 업로드
2. ZIP 파일과 이미지 파일 업로드
3. 문서 종류 자동 분류
4. PDF 원본 영구 보관
5. LLM을 이용한 위험 점수 산정

문서 종류는 사용자가 각각 지정해 올리므로 자동 분류가 필요 없다. 파일 내용이 선택한 종류와 맞는지는 서버가 핵심 표제로 검증한다.

## 3. API 계약

### 요청

`POST /analyze/pdf`

콘텐츠 형식은 `multipart/form-data`다.

| 필드 | 형식 | 필수 | 설명 |
| --- | --- | --- | --- |
| `registry_pdf` | PDF 파일 | 예 | 등기부등본 |
| `building_pdf` | PDF 파일 | 예 | 건축물대장 |
| `address` | 문자열 | 예 | 주소 검색에서 선택한 분석 대상 주소 |
| `deposit` | 정수 문자열 | 예 | 전세보증금, 원 단위 |
| `marketPrice` | 정수 문자열 | 아니요 | 사용자가 아는 시세, 원 단위 |

주소는 PDF에서 추출한 주소를 대신하지 않는다. 외부 시세 조회의 기준이자, 잘못된 문서를 올렸는지 확인하는 비교값으로 사용한다.

### 성공 응답

기존 `/analyze/` 응답을 유지하고 문서 처리 결과만 추가한다.

```json
{
  "success": true,
  "data": {
    "address": "서울특별시 ...",
    "risk_score": 42.1,
    "risk_grade": "위험",
    "risk_items": [],
    "case_id": "case-...",
    "data_source": "pdf",
    "document_processing": {
      "registry": {
        "pages": 6,
        "text_pages": 5,
        "ocr_pages": [4],
        "warnings": []
      },
      "building": {
        "pages": 3,
        "text_pages": 3,
        "ocr_pages": [],
        "warnings": []
      }
    }
  }
}
```

`risk_items[].evidence[]`에는 기존 메타데이터에 `page_no`를 추가해 사용자가 원본의 근거 페이지를 확인할 수 있게 한다.

### 오류 응답

| 상태 | 조건 |
| --- | --- |
| `400` | PDF가 아니거나 암호화된 PDF, 손상된 PDF |
| `413` | 파일당 20MB 초과 또는 문서당 50페이지 초과 |
| `422` | 문서 종류 불일치, 주소 불일치, 필수 항목 추출 실패 |
| `503` | OCR이 필요한데 Tesseract 또는 한국어 데이터가 없음 |

추출 실패, OCR 실패, 필수 항목 누락은 정상 결과나 `안전` 등급으로 바꾸지 않는다.

## 4. 백엔드 설계

### 4.1 새 파일

#### `app/services/pdf_extractor.py`

역할은 PDF 검증과 페이지별 텍스트 생성까지다.

```python
@dataclass
class ExtractedPage:
    page_no: int
    text: str
    method: str  # "text" | "ocr"


@dataclass
class ExtractedPdf:
    pages: list[ExtractedPage]
    warnings: list[str]
```

처리 규칙:

1. MIME 타입만 믿지 않고 파일 첫 바이트가 `%PDF-`인지 확인한다.
2. PyMuPDF로 암호화 여부와 페이지 수를 확인한다.
3. 각 페이지에서 위치 순서가 반영된 텍스트를 먼저 추출한다.
4. 공백을 뺀 글자가 50자 미만인 페이지만 `kor+eng`, 300dpi로 OCR한다.
5. OCR 결과도 50자 미만이면 경고를 남긴다.
6. 원본 파일은 요청 처리 중에만 사용하고 응답 전 닫는다.

페이지별 OCR을 사용하는 이유는 일부 페이지만 스캔 이미지인 혼합 PDF를 처리하면서 전체 OCR 비용과 지연을 줄이기 위해서다.

#### `app/services/pdf_normalizer.py`

역할은 페이지 텍스트를 `PropertyDoc`으로 만드는 것이다.

등기부등본:

1. 표제부, 갑구, 을구 표제를 기준으로 구획을 나눈다.
2. 소유권이전·소유권보존 중 마지막 유효 항목에서 현재 소유자를 추출한다.
3. 근저당권, 압류, 가압류, 가처분, 가등기, 신탁, 전세권, 임차권, 경매개시결정을 추출한다.
4. 말소 등기는 같은 구의 순위번호와 연결한다.
5. 채권최고액은 기존 `parse_amount_won()`을 재사용한다.

건축물대장:

1. 대장종류, 대지위치·도로명주소, 주용도, 구조, 면적, 사용승인일을 추출한다.
2. 소유자현황에서 이름을 추출한다.
3. 위반건축물 표시를 `True`, 명시적 정상 표시를 `False`, 확인하지 못하면 `None`으로 둔다.
4. 값이 없는 항목은 추측하지 않고 `None`으로 둔다.

OCR 오타를 LLM으로 보정하지 않는다. 숫자, 이름, 순위번호의 자동 보정은 잘못된 위험 판정으로 이어질 수 있다.

### 4.2 기존 파일 변경

#### `app/services/documents.py`

`Section`에 선택 필드를 하나 추가한다.

```python
page_no: Optional[int] = None
```

기존 JSON 경로는 `None`, PDF 경로는 실제 페이지 번호를 넣는다.

#### `app/services/chunker.py`

청크 머리말과 Chroma 메타데이터에 `page_no`를 넣는다.

```text
[등기부 을구 4페이지 순위 2] ...
```

청크 본문은 현재처럼 `mask_text()`를 거친 뒤에만 임베딩하고 저장한다.

#### `app/services/document_source.py`

다음 함수를 추가한다.

```python
def load_pdf_documents(registry_file, building_file, address) -> LoadedDocs:
    ...
```

반환 형식은 기존 `LoadedDocs`이며 `source="pdf"`, OCR 페이지와 경고를 `notes` 및 별도 처리 메타데이터로 돌려준다.

`LoadedDocs`에는 응답 전달용 선택 필드를 추가한다.

```python
processing: dict = field(default_factory=dict)
```

기존 CODEF와 sample 경로에서는 빈 객체이므로 동작이 바뀌지 않는다.

#### `app/api/endpoints/analyze.py`

현재 `analyze_property()` 안의 공통 분석 부분을 한 번만 재사용하도록 같은 파일의 작은 함수로 옮긴다.

```python
async def _analyze_loaded_docs(docs, address, deposit, market_price):
    ...
```

기존 JSON/CODEF 경로와 새 PDF 경로가 모두 이 함수를 호출한다. 별도 서비스 계층이나 분석 클래스는 만들지 않는다.

새 엔드포인트는 `UploadFile` 두 개와 `Form` 필드를 받은 뒤 PDF 추출처럼 CPU를 쓰는 작업을 `run_in_threadpool()`에서 실행한다.

#### `app/services/rag_explain.py`

공개 근거에 `page_no`를 포함한다. 나머지 프롬프트와 검증 규칙은 변경하지 않는다.

#### `requirements.txt`

다음 패키지만 추가한다.

```text
python-multipart
PyMuPDF
```

PyMuPDF의 OCR은 서버에 설치된 Tesseract를 사용한다. Docker 이미지에는 Tesseract와 한국어 학습 데이터를 설치한다.

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-kor \
    && rm -rf /var/lib/apt/lists/*
```

클라우드 OCR은 추가하지 않는다. 실제 문서 평가에서 로컬 OCR 정확도가 부족할 때만 교체한다.

## 5. 문서 검증

### 문서 종류

추출 텍스트에 다음 핵심 표제가 있는지 확인한다.

| 문서 | 필수 표제 |
| --- | --- |
| 등기부등본 | `등기사항전부증명서` 또는 `등기사항증명서`, 그리고 갑구·을구 중 하나 |
| 건축물대장 | `건축물대장`, 그리고 `주용도`·`구조`·`면적` 중 둘 이상 |

파일 이름은 검증에 사용하지 않는다.

### 주소

사용자 입력 주소와 두 PDF에서 추출한 주소를 공백, 괄호, `특별시/광역시`, 도로명 표기 차이를 정리한 뒤 비교한다.

1. 두 PDF 주소가 서로 다르면 분석을 중단한다.
2. PDF 주소와 사용자 입력 주소가 명확히 다르면 분석을 중단한다.
3. OCR 때문에 주소를 추출하지 못하면 `422`로 분석을 중단하고 사용자에게 문서 주소 확인을 요구한다.

### 위험 분석 필수 항목

등기부에서 표제부와 현재 소유자, 건축물대장에서 주소와 주용도를 읽지 못하면 점수를 반환하지 않는다. 면적, 구조, 준공년도처럼 일부 항목만 누락된 경우에는 기존 비교 규칙대로 해당 항목을 `비교불가`로 둔다.

## 6. 개인정보와 보관 정책

1. PDF 원본과 원문 OCR 텍스트는 DB, 로그, ChromaDB에 저장하지 않는다.
2. 문서 비교에 필요한 원문 이름은 요청 처리 중 서버 메모리에서만 사용한다.
3. ChromaDB에는 현재 `mask_text()`를 통과한 청크만 저장한다.
4. 주민등록번호, 전화번호, 소유자명, 주민번호 뒤 주소가 남아 있으면 색인을 중단한다.
5. API 오류 메시지와 로그에는 파일 내용, 이름, 주소를 넣지 않는다.
6. LLM과 임베딩 API에는 마스킹된 청크와 표시용 비교값만 전달한다.

색인 직전에 금지 패턴 검사를 한 번 더 수행한다. 마스킹 후에도 주민등록번호 형태가 남아 있으면 요청 전체를 실패시키며 원문을 로그로 출력하지 않는다.

## 7. Flutter 변경

### `pubspec.yaml`

PDF 선택을 위해 `file_picker`를 추가한다. 구현 시점에 현재 Flutter/Dart SDK와 호환되는 버전을 `flutter pub add file_picker`로 결정한다.

### `lib/screens/risk_analysis.dart`

현재 입력 흐름을 다음 순서로 바꾼다.

1. 전세보증금
2. 분석 대상 주소
3. 등기부등본 PDF 선택
4. 건축물대장 PDF 선택
5. 분석 시작

각 파일 항목은 파일명, 제거 버튼, 다시 선택 버튼만 표시한다. PDF 미리보기는 이번 범위에서 제외한다.

현재 분석 전에 `/building/title-info`를 호출하는 단계는 PDF 경로에서 제거한다. 사용자가 확인할 정보는 서버가 PDF에서 추출한 뒤 결과 화면의 문서 처리 안내로 보여준다.

### `lib/services/api_service.dart`

`http.MultipartRequest`를 사용한 함수를 추가한다.

```dart
static Future<Map<String, dynamic>> analyzeJeonsePdf({
  required PlatformFile registryPdf,
  required PlatformFile buildingPdf,
  required String address,
  required int deposit,
  int? marketPrice,
})
```

두 파일은 플랫폼별 경로 분기를 만들지 않고 `readAsBytes()` 결과로 첨부한다. 서버 제한이 파일당 20MB이므로 두 파일을 메모리에 올리는 단순한 구현으로 충분하다.

### `lib/screens/risk_result.dart`

기존 위험 결과 위에 다음 안내만 추가한다.

```text
문서 처리: 등기부 6쪽(1쪽 OCR), 건축물대장 3쪽
```

항목별 근거에는 문서 종류, 구획, 페이지를 표시한다. OCR을 사용한 페이지가 있으면 `OCR 결과는 원본과 함께 확인하세요`라는 안내를 표시한다.

## 8. 테스트 설계

### 단위 테스트

`tests/test_pdf_extractor.py`

1. 텍스트 PDF는 OCR을 호출하지 않는다.
2. 빈 이미지 페이지는 OCR을 한 번 호출한다.
3. 손상·암호화·용량 초과·페이지 초과 PDF를 거절한다.
4. OCR 결과가 비어 있으면 명시적으로 실패한다.

`tests/test_pdf_normalizer.py`

1. 등기부 표제부·갑구·을구와 페이지 번호를 보존한다.
2. 말소된 권리를 현재 권리에서 제외한다.
3. 채권최고액을 원 단위로 추출한다.
4. 건축물대장의 용도·구조·면적·사용승인일·위반 여부를 추출한다.
5. 읽지 못한 값을 추측하지 않고 `None`으로 둔다.

`tests/test_pdf_analyze.py`

1. 두 PDF가 기존 분석 공통 함수까지 전달된다.
2. 다른 주소의 문서 조합을 거절한다.
3. ChromaDB에 전달되는 청크에 주민번호와 원문 소유자명이 없다.
4. 근거 응답에 정확한 `page_no`가 포함된다.
5. OCR·파싱 실패가 `안전` 점수로 변환되지 않는다.

### 테스트 자료

저장소에는 개인정보가 없는 합성 PDF만 넣는다. 실제 등기부등본과 건축물대장은 커밋하지 않고, 주민번호·소유자명·주소를 제거한 별도 수동 검증 자료로만 사용한다.

OCR 자체의 정확도는 단위 테스트에서 Tesseract를 모킹하고, Docker 스모크 테스트 한 건에서만 실제 `kor` 데이터를 확인한다.

## 9. 구현 순서

1. `python-multipart`, PyMuPDF, Tesseract 의존성 추가
2. PDF 검증·텍스트 추출·OCR 서비스와 단위 테스트 구현
3. 두 문서 정규화와 합성 PDF 테스트 구현
4. `Section.page_no`와 Chroma 근거 메타데이터 확장
5. 분석 공통 함수를 분리하고 `/analyze/pdf` 연결
6. Flutter 파일 선택과 multipart 업로드 연결
7. 합성 PDF 통합 테스트
8. 개인정보를 제거한 실제 문서로 파서와 OCR 정확도 확인

기존 `/analyze/`와 CODEF/sample 경로는 PDF 경로가 검증될 때까지 유지한다. PDF 경로가 안정된 뒤에도 데모·회귀 테스트용 sample 경로는 남기고, 운영 UI만 PDF 업로드를 사용한다.

## 10. 완료 기준

1. 텍스트 PDF는 OCR 없이 분석된다.
2. 스캔 PDF는 필요한 페이지만 OCR된다.
3. 등기부와 건축물대장이 같은 주소인지 검증된다.
4. 기존 비교·점수·RAG 출력 형식을 유지한다.
5. 근거에 문서 종류, 구획, 페이지 번호가 표시된다.
6. ChromaDB와 외부 LLM에 주민번호와 원문 소유자명이 저장·전송되지 않는다.
7. OCR 또는 필수 필드 추출 실패 시 점수를 반환하지 않는다.
8. 업로드한 원본 PDF가 서버에 남지 않는다.

## 11. 구현 참고 문서

1. FastAPI `UploadFile`과 multipart 업로드: <https://fastapi.tiangolo.com/tutorial/request-files/>
2. PyMuPDF의 Tesseract OCR 연동: <https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html>
3. Flutter `file_picker`: <https://pub.dev/packages/file_picker>
