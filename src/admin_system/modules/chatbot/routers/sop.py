"""
SOP Document Management Router.

Provides CRUD operations for SOP documents and JSON import functionality.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session
from modules.chatbot.models import SOPDocument
from modules.chatbot.schemas import (
    SearchQuery,
    SearchResponse,
    SOPDocumentCreate,
    SOPDocumentResponse,
    SOPDocumentUpdate,
    SuccessResponse,
)
from modules.chatbot.services import (
    JsonImportService,
    JsonParseError,
    JsonValidationError,
    VectorService,
    get_json_import_service,
    get_vector_service,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sop", tags=["SOP Documents"])


@router.get("/", response_model=list[SOPDocumentResponse])
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    category: Annotated[str | None, Query()] = None,
    published_only: Annotated[bool, Query()] = True,
) -> list[SOPDocumentResponse]:
    query = select(SOPDocument)
    if published_only:
        query = query.where(SOPDocument.is_published == True)
    if category:
        query = query.where(SOPDocument.category == category)
    query = query.offset(skip).limit(limit).order_by(SOPDocument.created_at.desc())
    
    result = await db.execute(query)
    return [SOPDocumentResponse.model_validate(doc) for doc in result.scalars().all()]


@router.get("/categories", response_model=list[str])
async def list_categories(db: Annotated[AsyncSession, Depends(get_db_session)]) -> list[str]:
    result = await db.execute(
        select(SOPDocument.category)
        .where(SOPDocument.category.isnot(None), SOPDocument.is_published == True)
        .distinct()
    )
    return sorted([row[0] for row in result.fetchall() if row[0]])


@router.get("/{document_id}", response_model=SOPDocumentResponse)
async def get_document(
    document_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SOPDocumentResponse:
    result = await db.execute(select(SOPDocument).where(SOPDocument.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {document_id} not found")
    return SOPDocumentResponse.model_validate(doc)


@router.post("/", response_model=SOPDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    document_data: SOPDocumentCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    vector_service: Annotated[VectorService, Depends(get_vector_service)],
) -> SOPDocumentResponse:
    doc = SOPDocument(
        title=document_data.title,
        content=document_data.content,
        category=document_data.category,
        tags=document_data.tags,
        metadata_=document_data.metadata_,
        is_published=True,
    )
    await vector_service.index_document(doc, db)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return SOPDocumentResponse.model_validate(doc)


@router.put("/{document_id}", response_model=SOPDocumentResponse)
async def update_document(
    document_id: str,
    update_data: SOPDocumentUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    vector_service: Annotated[VectorService, Depends(get_vector_service)],
) -> SOPDocumentResponse:
    result = await db.execute(select(SOPDocument).where(SOPDocument.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {document_id} not found")
    
    content_changed = False
    for field, value in update_data.model_dump(exclude_unset=True).items():
        if field in ("title", "content") and value is not None:
            content_changed = True
        setattr(doc, field, value)
    
    if content_changed:
        await vector_service.index_document(doc, db)
    
    await db.commit()
    await db.refresh(doc)
    return SOPDocumentResponse.model_validate(doc)


@router.delete("/{document_id}", response_model=SuccessResponse)
async def delete_document(
    document_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    hard_delete: Annotated[bool, Query()] = False,
) -> SuccessResponse:
    result = await db.execute(select(SOPDocument).where(SOPDocument.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {document_id} not found")
    
    if hard_delete:
        await db.delete(doc)
        message = f"Document {document_id} permanently deleted"
    else:
        doc.is_published = False
        message = f"Document {document_id} unpublished"
    
    await db.commit()
    return SuccessResponse(message=message)


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    search_query: SearchQuery,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    vector_service: Annotated[VectorService, Depends(get_vector_service)],
) -> SearchResponse:
    return await vector_service.search(
        query=search_query.query,
        db=db,
        top_k=search_query.top_k,
        category=search_query.category,
        similarity_threshold=search_query.similarity_threshold,
    )


@router.post("/reindex", response_model=SuccessResponse)
async def reindex_documents(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    vector_service: Annotated[VectorService, Depends(get_vector_service)],
) -> SuccessResponse:
    count = await vector_service.reindex_all_documents(db)
    return SuccessResponse(message=f"Reindexed {count} documents")


@router.get("/stats/summary")
async def get_stats(db: Annotated[AsyncSession, Depends(get_db_session)]) -> dict:
    total_result = await db.execute(select(func.count(SOPDocument.id)))
    total = total_result.scalar() or 0
    
    published_result = await db.execute(select(func.count(SOPDocument.id)).where(SOPDocument.is_published == True))
    published = published_result.scalar() or 0
    
    indexed_result = await db.execute(select(func.count(SOPDocument.id)).where(SOPDocument.embedding.isnot(None)))
    indexed = indexed_result.scalar() or 0
    
    return {"total": total, "published": published, "unpublished": total - published, "indexed": indexed}


@router.post("/import")
async def import_sops_from_json(
    file: Annotated[UploadFile, File(description="JSON file")],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    import_service: Annotated[JsonImportService, Depends(get_json_import_service)],
    auto_publish: Annotated[bool, Query()] = True,
) -> dict:
    if file.content_type not in ("application/json", "text/plain"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid file type: {file.content_type}")
    
    try:
        content = await file.read()
        items = import_service.parse_json(content)
        result = await import_service.import_sops(db, items, auto_publish)
    except JsonParseError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except JsonValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"message": str(e), "errors": e.errors})
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Import failed: {e}")
    
    return {
        "success": True,
        "message": f"Imported {result.successful} of {result.total_items} documents",
        "created": result.created,
        "updated": result.updated,
        "failed": result.failed,
    }
