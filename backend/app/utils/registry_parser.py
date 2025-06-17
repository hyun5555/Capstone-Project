import re

# 정규표현식 패턴 정의
patterns = {
    "ownerName": r"소유자[:：]?\s*([^,\n]+)",
    "buildingUse": r"용도[:：]?\s*([^,\n]+)",
    "structureType": r"구조[:：]?\s*([^,\n]+)",
    "exclusiveArea": r"전용면적[:：]?\s*([^,\n]+)",
    "sharedArea": r"공유면적[:：]?\s*([^,\n]+)",
    "totalArea": r"연면적[:：]?\s*([^,\n]+)",
    "buildYear": r"준공년도[:：]?\s*([^,\n]+)",
    "hasMortgage": r"채권최고액[:：]?\s*([^,\n]+)",
    "hasRiskRights": r"권리[:：]?\s*([^,\n]+)",
}

def extract_fields_from_rescontents(text: str) -> dict:
    extracted = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        extracted[key] = match.group(1).strip() if match else None
    return extracted
