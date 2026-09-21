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
