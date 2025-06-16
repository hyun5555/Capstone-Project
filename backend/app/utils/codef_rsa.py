# backend/app/utils/codef_rsa.py

import os
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from dotenv import load_dotenv

load_dotenv()

def encrypt_codef_password(password: str) -> str:
    """
    CODEF 비밀번호를 RSA 공개키로 암호화 (base64 인코딩 결과 반환)
    공개키는 .env의 CODEF_PUBLIC_KEY에 PEM 형식(\\n 포함 문자열)으로 저장되어 있어야 함
    """
    if not password:
        raise ValueError("CODEF_USER_PW 환경변수가 비어 있습니다.")

    public_key_env = os.getenv("CODEF_PUBLIC_KEY")
    if not public_key_env:
        raise ValueError("CODEF_PUBLIC_KEY 환경변수가 비어 있습니다.")

    try:
        public_key = public_key_env.replace("\\n", "\n")
        rsa_key = RSA.import_key(public_key)
        cipher = PKCS1_v1_5.new(rsa_key)
        encrypted = cipher.encrypt(password.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as e:
        raise ValueError(f"RSA 암호화 실패: {e}")