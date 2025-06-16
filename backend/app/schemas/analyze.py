from pydantic import BaseModel
from typing import Dict

class AnalyzeRequest(BaseModel):
    address: str

class AnalyzeResponse(BaseModel):
    address: str
    flags: Dict[str, str]
    explanations: Dict[str, str]
    report: str
