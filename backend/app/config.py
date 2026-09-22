import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
if not DATABASE_URL or not SECRET_KEY:
    raise RuntimeError("DATABASE_URL과 SECRET_KEY 환경변수가 필요합니다")

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.6-luna")
HF_TOKEN = os.getenv("HF_TOKEN")

_chroma_path = Path(os.getenv("CHROMA_PERSIST_DIRECTORY", "chroma_data"))
if not _chroma_path.is_absolute():
    _chroma_path = BACKEND_DIR / _chroma_path
CHROMA_PERSIST_DIRECTORY = str(_chroma_path)

BASE_URL_BUILD = "https://apis.data.go.kr/1613000/BldRgstHubService"
SERVICE_KEY_BUILD = os.getenv("BUILDING_SERVICE_KEY")

# Codef 등기부 API
CODEF_CLIENT_ID = os.getenv("CODEF_CLIENT_ID")
CODEF_CLIENT_SECRET = os.getenv("CODEF_CLIENT_SECRET")
SECOND_CODEF_CLIENT_ID = os.getenv("SECOND_CODEF_CLIENT_ID")
SECOND_CODEF_CLIENT_SECRET = os.getenv("SECOND_CODEF_CLIENT_SECRET")
CODEF_PUBLIC_KEY = os.getenv("CODEF_PUBLIC_KEY")
CODEF_USER_ID = os.getenv("CODEF_USER_ID")
CODEF_USER_PW = os.getenv("CODEF_USER_PW")
CODEF_PHONE_NO = os.getenv("CODEF_PHONE_NO")
CODEF_API_HOST_DEV = os.getenv("CODEF_API_HOST_DEV")
CODEF_API_HOST = os.getenv("CODEF_API_HOST")

SERVICE_KEY = os.getenv("SERVICE_KEY")
JUSO_API_URL = os.getenv("JUSO_API_URL")
CONFM_KEY = os.getenv("CONFM_KEY")

APT_JEONSE_PRICE_URL = os.getenv("APT_JEONSE_PRICE_URL")
OFFI_JEONSE_PRICE_URL = os.getenv("OFFI_JEONSE_PRICE_URL")
RH_JEONSE_PRICE_URL = os.getenv("RH_JEONSE_PRICE_URL")
SH_JEONSE_PRICE_URL = os.getenv("SH_JEONSE_PRICE_URL")

APT_TRADE_PRICE_URL = os.getenv("APT_TRADE_PRICE_URL")
OFFI_TRADE_PRICE_URL = os.getenv("OFFI_TRADE_PRICE_URL")
RH_TRADE_PRICE_URL = os.getenv("RH_TRADE_PRICE_URL")
SH_TRADE_PRICE_URL = os.getenv("SH_TRADE_PRICE_URL")

REGISTRY_API_URL = os.getenv("REGISTRY_API_URL")
BUILDING_API_URL = os.getenv("BUILDING_API_URL")
API_KEY = os.getenv("API_KEY")

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NAVER_REDIRECT_URI = os.getenv("NAVER_REDIRECT_URI")


# ──────────────────────────────────────────────────────────────
# CODEF 호출 설정
#   CODEF_ENV=prod (기본): CODEF_API_HOST + SECOND_CODEF_CLIENT_ID/SECRET  (기존 등기부/건축물대장 호출과 동일)
#   CODEF_ENV=demo       : CODEF_API_HOST_DEV + CODEF_CLIENT_ID/SECRET    (데모 서버, 실제 발급 없이 흐름 확인용)
# ANALYSIS_DATA_SOURCE=codef (기본) 이면 CODEF 를 호출하고, sample 이면 CODEF_SAMPLE_DIR 의 응답 파일을 재생한다.
# ──────────────────────────────────────────────────────────────
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CodefSettings:
    env: str
    client_id: Optional[str]
    client_secret: Optional[str]
    public_key: Optional[str]
    api_host: Optional[str]
    oauth_url: str
    registry_path: str
    building_path: str
    registry_organization: str
    phone_no: Optional[str]
    user_id: Optional[str]
    user_pw: Optional[str]
    timeout_sec: int


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def load_codef_settings() -> CodefSettings:
    env = (_env("CODEF_ENV", "prod") or "prod").lower()
    if env == "demo":
        client_id, client_secret, host = _env("CODEF_CLIENT_ID"), _env("CODEF_CLIENT_SECRET"), _env("CODEF_API_HOST_DEV")
    else:
        client_id = _env("SECOND_CODEF_CLIENT_ID") or _env("CODEF_CLIENT_ID")
        client_secret = _env("SECOND_CODEF_CLIENT_SECRET") or _env("CODEF_CLIENT_SECRET")
        host = _env("CODEF_API_HOST")
    return CodefSettings(
        env=env,
        client_id=client_id,
        client_secret=client_secret,
        public_key=_env("CODEF_PUBLIC_KEY"),
        api_host=host,
        oauth_url=_env("CODEF_OAUTH_URL", "https://oauth.codef.io/oauth/token"),
        # ⚠ 아래 경로/기관코드는 CODEF 개발가이드에서 반드시 확인하세요. 틀리면 .env 만 바꾸면 됩니다.
        registry_path=_env("CODEF_REGISTRY_PATH", "/v1/kr/public/real-estate/register"),
        building_path=_env("CODEF_BUILDING_PATH", "/v1/kr/public/mw/building-register/general"),
        registry_organization=_env("CODEF_REGISTRY_ORGANIZATION", "0004"),
        phone_no=_env("CODEF_PHONE_NO"),
        user_id=_env("CODEF_USER_ID"),
        user_pw=_env("CODEF_USER_PW"),
        timeout_sec=int(_env("CODEF_TIMEOUT_SEC", "60")),
    )


codef_settings = load_codef_settings()

ANALYSIS_DATA_SOURCE = (_env("ANALYSIS_DATA_SOURCE", "sample") or "sample").lower()
_sample_dir = Path(_env("CODEF_SAMPLE_DIR", "sample_data"))
CODEF_SAMPLE_DIR = str(_sample_dir if _sample_dir.is_absolute() else BACKEND_DIR / _sample_dir)


# ──────────────────────────────────────────────────────────────
# 청킹 / 임베딩 / 검색 설정 (청크 크기·overlap·Top-K 는 나중에 비교 실험할 수 있도록 환경변수로 뺀다)
# ──────────────────────────────────────────────────────────────
def _env_int(name: str, default: int) -> int:
    value = _env(name)
    try:
        return int(value) if value is not None else default
    except ValueError:
        raise ValueError(f"환경변수 {name} 는 정수여야 합니다: {value!r}")


EMBEDDING_MODEL = _env("EMBEDDING_MODEL", "text-embedding-3-small")
CHROMA_CHUNK_COLLECTION = _env("CHROMA_CHUNK_COLLECTION", "property_chunks")
CHROMA_LEGAL_COLLECTION = _env("CHROMA_LEGAL_COLLECTION", "legal_chunks")
_legal_corpus_path = Path(_env("LEGAL_CORPUS_PATH", "legal_data/legal_sources.json"))
LEGAL_CORPUS_PATH = str(
    _legal_corpus_path if _legal_corpus_path.is_absolute() else BACKEND_DIR / _legal_corpus_path
)
CHUNK_SIZE = _env_int("CHUNK_SIZE", 600)
CHUNK_OVERLAP = _env_int("CHUNK_OVERLAP", 100)
RETRIEVAL_TOP_K = _env_int("RETRIEVAL_TOP_K", 3)
# plain: 질의와 가까운 순 Top-K / balanced: 등기부와 건축물대장 청크를 각각 하나 이상 포함 / adaptive: balanced + 항목별 Top-K (evidence.FIELD_TOP_K)
RETRIEVAL_STRATEGY = (_env("RETRIEVAL_STRATEGY", "adaptive") or "adaptive").lower()

# 근거 기반 설명(LLM) 설정. 프롬프트 버전은 v1(초기 단순 프롬프트) / v2(역할·조건·예시·검증 강화)
EXPLAIN_PROMPT_VERSION = (_env("EXPLAIN_PROMPT_VERSION", "v2") or "v2").lower()
LLM_REASONING_EFFORT = (_env("LLM_REASONING_EFFORT", "none") or "none").lower()
if LLM_REASONING_EFFORT not in {"none", "low", "medium", "high", "xhigh"}:
    raise ValueError(f"LLM_REASONING_EFFORT 값이 올바르지 않습니다: {LLM_REASONING_EFFORT!r}")
try:
    LLM_TEMPERATURE = float(_env("LLM_TEMPERATURE", "1"))     # 현재 모델은 1 만 허용한다 (기존 설정 유지)
except ValueError:
    LLM_TEMPERATURE = 1.0
