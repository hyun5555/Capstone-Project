# app/api/endpoints/registry.py
from fastapi import APIRouter, HTTPException

from app.clients.codef_client import CodefError, http_status_for
from app.clients.registry_api import get_registry_info
from app.config import ANALYSIS_DATA_SOURCE, CODEF_SAMPLE_DIR
from app.schemas.registry import RegistryData, RegistryRequest
from app.services.codef_normalizer import normalize_registry_response
from app.services.document_source import SAMPLE_REGISTRY_FILE, SampleDataMissing, read_sample_response
from app.utils.masking import mask_person_name

from pathlib import Path

router = APIRouter(prefix="/registry", tags=["등기부등본"])


@router.post("/", response_model=RegistryData)
async def fetch_registry_api(data: RegistryRequest):
    try:
        if ANALYSIS_DATA_SOURCE == "sample":
            raw = read_sample_response(Path(CODEF_SAMPLE_DIR) / SAMPLE_REGISTRY_FILE)
        else:
            raw = await get_registry_info(data.address)
    except CodefError as e:
        raise HTTPException(status_code=http_status_for(e), detail=e.message)
    except SampleDataMissing as e:
        raise HTTPException(status_code=500, detail=str(e))

    doc = normalize_registry_response(raw, data.address)
    return RegistryData(
        propertyLocation=data.address,
        ownerName=", ".join(mask_person_name(n) for n in doc.owner_names) or None,
        buildingUse=doc.usage,
        structureType=doc.structure,
        exclusiveArea=None if doc.area_exclusive is None else f"{doc.area_exclusive:g}",
        totalArea=None if doc.area_total is None else f"{doc.area_total:g}",
        buildYear=None if doc.build_year is None else str(doc.build_year),
        hasMortgage=str(doc.max_claim_amount) if doc.max_claim_amount else None,
        hasRiskRights=", ".join(sorted({r.type for r in doc.active_rights})) or None,
    )
