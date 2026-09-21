# backend/app/utils/codef_rsa.py
import base64
import textwrap

from app.config import CODEF_PUBLIC_KEY


def normalize_public_key_pem(raw_key: str) -> str:
    """
    CODEF 콘솔에서 복사한 공개키는 'MIIBIjANBg...' 처럼 헤더 없는 base64 한 줄인 경우가 많다.
    PEM 헤더가 없으면 붙이고, .env 에 넣을 때 쓴 '\\n' 문자열도 실제 개행으로 바꿔 준다.
    """
    key = (raw_key or "").strip().replace("\\n", "\n")
    if "BEGIN" in key:
        return key
    body = "".join(key.split())
    return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(textwrap.wrap(body, 64)) + "\n-----END PUBLIC KEY-----"


def encrypt_codef_password(password: str) -> str:
    """CODEF 비밀번호를 RSA 공개키로 암호화한다 (base64 문자열 반환)."""
    if not password:
        raise ValueError("CODEF_USER_PW 환경변수가 비어 있습니다.")
    if not CODEF_PUBLIC_KEY:
        raise ValueError("CODEF_PUBLIC_KEY 환경변수가 비어 있습니다.")

    from Crypto.Cipher import PKCS1_v1_5      # pycryptodome — 실제로 암호화할 때만 import
    from Crypto.PublicKey import RSA

    try:
        rsa_key = RSA.import_key(normalize_public_key_pem(CODEF_PUBLIC_KEY))
        cipher = PKCS1_v1_5.new(rsa_key)
        return base64.b64encode(cipher.encrypt(password.encode("utf-8"))).decode("utf-8")
    except Exception as e:
        # 비밀번호/키 내용이 오류 메시지에 섞이지 않도록 예외 종류만 알려 준다.
        raise ValueError(f"RSA 암호화 실패: {type(e).__name__}") from None
