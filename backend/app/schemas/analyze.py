# app/schemas/analyze.py
from pydantic import BaseModel
from typing import Dict

class AnalyzeRequest(BaseModel):
    address: str
    deposit: int
    marketPrice: int

class AnalyzeResponse(BaseModel):
    address: str
    flags: Dict[str, str]
    explanations: Dict[str, str]
    report: str
