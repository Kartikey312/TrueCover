import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.enums import DocumentType
from app.schemas.claim import ClaimCreate, ClaimRead
from app.schemas.decision import ClaimDecisionCreate
from app.schemas.document import ClaimDocumentRead
from app.schemas.recommendation import AIRecommendationRead
from app.schemas.request_info import RequestInfoCreate
from app.schemas.review import ClaimReviewPacket
from app.schemas.timeline import TimelineEvent
from app.services import claims_service, pipeline_service, storage_service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", response_model=ClaimRead, status_code=201)
async def create_claim(payload: ClaimCreate, db: AsyncSession = Depends(get_db)):
    return await claims_service.create_claim(db, payload)


@router.get("/{claim_id}", response_model=ClaimRead)
async def get_claim(claim_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await claims_service.get_claim(db, claim_id)


@router.post("/{claim_id}/documents", response_model=ClaimDocumentRead, status_code=201)
async def upload_document(
    claim_id: uuid.UUID,
    document_type: DocumentType = Form(...),
    uploaded_by: uuid.UUID | None = Form(default=None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    storage_path, size = await storage_service.save_claim_document(claim_id, file)
    return await claims_service.add_document(
        db,
        claim_id,
        document_type=document_type,
        file_name=file.filename,
        storage_path=storage_path,
        mime_type=file.content_type,
        file_size_bytes=size,
        uploaded_by=uploaded_by,
    )


@router.get("/{claim_id}/documents", response_model=list[ClaimDocumentRead])
async def list_documents(claim_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await claims_service.list_documents(db, claim_id)


@router.get("/{claim_id}/documents/{document_id}/file")
async def get_document_file(claim_id: uuid.UUID, document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    document = await claims_service.get_document(db, claim_id, document_id)
    # inline, not attachment -- the adjuster UI previews these in an
    # <img>/<iframe>; "attachment" would force a download instead.
    return FileResponse(
        document.storage_path,
        media_type=document.mime_type,
        filename=document.file_name,
        content_disposition_type="inline",
    )


@router.post("/{claim_id}/submit", response_model=ClaimRead)
async def submit_claim(claim_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Runs the claim through the AI pipeline now that documents (if any)
    are attached. Either auto-processes it immediately or pauses it for
    adjuster review -- see GET /claims/{id}/review for that packet.
    """
    return await pipeline_service.submit_claim_for_review(db, claim_id)


@router.get("/{claim_id}/review", response_model=ClaimReviewPacket)
async def get_review_packet(claim_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await pipeline_service.get_review_packet(db, claim_id)


@router.get("/{claim_id}/timeline", response_model=list[TimelineEvent])
async def get_timeline(claim_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await claims_service.get_timeline(db, claim_id)


@router.post("/{claim_id}/decision", response_model=ClaimRead)
async def record_decision(claim_id: uuid.UUID, payload: ClaimDecisionCreate, db: AsyncSession = Depends(get_db)):
    return await pipeline_service.resume_claim_decision(db, claim_id, payload)


@router.get("/{claim_id}/recommendation", response_model=AIRecommendationRead)
async def get_recommendation(claim_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await claims_service.get_latest_recommendation(db, claim_id)


@router.post("/{claim_id}/request-info", response_model=ClaimRead)
async def request_more_information(
    claim_id: uuid.UUID, payload: RequestInfoCreate, db: AsyncSession = Depends(get_db)
):
    """Marks the claim as waiting on the member for more information.
    Leaves final_decision untouched and the graph paused -- there's no
    member portal yet to receive this, so it's purely a queue-visibility
    signal until a real request/response loop exists.
    """
    return await claims_service.request_more_information(db, claim_id, payload)
