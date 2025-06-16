from pydantic import BaseModel, Field

class ConnectedIdRequest(BaseModel):
    realEstateName: str = Field(..., description="부동산 전체 주소")
    password: str = Field(..., description="공인인증서 비밀번호")
    organization: str = Field(default="0004", description="기관 코드 (기본: 0004)")
