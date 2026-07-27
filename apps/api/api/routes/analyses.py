"""HTTP surface for contract analysis.

Thin by design: read the upload, hand it to the service, return the result.
No business rules and no try/except — domain errors are mapped centrally.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile

from api.deps import get_contracts_service
from domain.contracts import Analysis
from services.contracts import ContractsService

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("/", response_model=Analysis)
async def analyze_contract(
    file: UploadFile = File(..., description="A .pdf or .docx contract."),
    judge: bool = Query(
        default=True,
        description=(
            "Run the independent severity-judging pass. Disable to halve token "
            "spend when severity precision does not matter."
        ),
    ),
    service: ContractsService = Depends(get_contracts_service),
) -> Analysis:
    data = await file.read()
    return service.analyze_upload(file.filename or "upload", data, judge=judge)


@router.get("/{analysis_id}", response_model=Analysis)
def get_analysis(
    analysis_id: str, service: ContractsService = Depends(get_contracts_service)
) -> Analysis:
    return service.get(analysis_id)
