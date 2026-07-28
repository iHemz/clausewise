"""HTTP surface for contract analysis.

Thin by design: read the upload, hand it to the service, return the result.
No business rules and no try/except — domain errors are mapped centrally.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile

from api.deps import get_contracts_service
from domain.contracts import Analysis
from services.contracts import ContractsService

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("/", response_model=Analysis, status_code=202)
async def analyze_contract(
    background: BackgroundTasks,
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
    """Accept the upload and return a pending analysis immediately.

    202, not 200: the review has been accepted, not completed. The response
    already carries the extracted text and the clause list, so the client can
    show the document and a real clause count while the model passes run — then
    poll ``GET /analyses/{id}`` until ``stage`` reads ``done``.

    ``run_analysis`` is synchronous, so FastAPI runs it in a worker thread and
    the event loop stays free.
    """
    data = await file.read()
    analysis = service.begin_upload(file.filename or "upload", data)
    background.add_task(service.run_analysis, analysis.id, judge=judge)
    return analysis


@router.get("/{analysis_id}", response_model=Analysis)
def get_analysis(
    analysis_id: str, service: ContractsService = Depends(get_contracts_service)
) -> Analysis:
    return service.get(analysis_id)
