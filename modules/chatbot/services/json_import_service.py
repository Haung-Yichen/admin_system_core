"""
JSON Import Service Module.

Handles parsing and importing SOP documents from uploaded JSON files.
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from modules.chatbot.core.config import get_chatbot_settings
from modules.chatbot.models import SOPDocument
from modules.chatbot.services.vector_service import VectorService, get_vector_service


logger = logging.getLogger(__name__)


class SOPImportItem(BaseModel):
    """Schema for a single SOP item in the import JSON."""

    id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=512)
    category: str | None = Field(None, max_length=128)
    tags: list[str] | None = Field(None)
    content: str = Field(..., min_length=1)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(",") if tag.strip()]
        if isinstance(v, list):
            return [str(tag).strip() for tag in v if tag]
        return None


@dataclass
class ImportItemResult:
    """Result of importing a single SOP item."""
    sop_id: str
    title: str
    success: bool
    created: bool
    error: str | None = None


@dataclass
class ImportResult:
    """Overall result of a JSON import operation."""
    total_items: int
    successful: int
    failed: int
    created: int
    updated: int
    errors: list[str]
    items: list[ImportItemResult]
    duration_seconds: float


class JsonImportError(Exception):
    """Base exception for JSON import errors."""
    pass


class JsonParseError(JsonImportError):
    """Raised when JSON parsing fails."""
    pass


class JsonValidationError(JsonImportError):
    """Raised when JSON validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class SOPContentTooLongError(JsonValidationError):
    """Raised when SOP content exceeds maximum length."""

    def __init__(self, violations: list[dict]) -> None:
        self.violations = violations
        error_details = [
            f"SOP '{v['sop_id']}': {v['length']} chars (max {v['max_length']})"
            for v in violations
        ]
        super().__init__(
            f"{len(violations)} SOPs exceed content length limit",
            errors=error_details
        )


class JsonImportService:
    """Service for importing SOP documents from JSON files."""

    def __init__(self, vector_service: VectorService | None = None) -> None:
        self._vector_service = vector_service or get_vector_service()

    def parse_json(self, json_content: str | bytes) -> list[SOPImportItem]:
        try:
            if isinstance(json_content, bytes):
                json_content = json_content.decode("utf-8")
            data = json.loads(json_content)
        except json.JSONDecodeError as e:
            raise JsonParseError(f"Invalid JSON: {e}") from e
        except UnicodeDecodeError as e:
            raise JsonParseError(f"Invalid encoding: {e}") from e

        if not isinstance(data, list):
            raise JsonValidationError("JSON must be an array", errors=["Root must be array"])

        if len(data) == 0:
            raise JsonValidationError("JSON array is empty")

        items: list[SOPImportItem] = []
        errors: list[str] = []

        for idx, item_data in enumerate(data):
            try:
                item = SOPImportItem.model_validate(item_data)
                items.append(item)
            except Exception as e:
                errors.append(f"Item {idx}: {e}")

        if errors and len(errors) == len(data):
            raise JsonValidationError("All items failed validation", errors=errors)

        self._validate_content_length(items)
        return items

    def _validate_content_length(self, items: list[SOPImportItem]) -> None:
        settings = get_chatbot_settings()
        max_length = settings.sop_content_max_length
        if max_length <= 0:
            return

        violations = []
        for item in items:
            if len(item.content) > max_length:
                violations.append({
                    "sop_id": item.id,
                    "title": item.title,
                    "length": len(item.content),
                    "max_length": max_length,
                })

        if violations:
            raise SOPContentTooLongError(violations)

    async def import_sops(
        self,
        db: AsyncSession,
        items: list[SOPImportItem],
        auto_publish: bool = True,
    ) -> ImportResult:
        start_time = time.time()
        results: list[ImportItemResult] = []
        errors: list[str] = []
        created_count = 0
        updated_count = 0

        for item in items:
            try:
                upsert_result = await self._vector_service.upsert_document(
                    db=db,
                    ragic_record_id=item.id,
                    title=item.title,
                    content=item.content,
                    category=item.category,
                    tags=item.tags,
                    is_published=auto_publish,
                )

                doc = upsert_result.document
                metadata = doc.metadata_ or {}
                metadata["source"] = "json_import"
                metadata["sop_id"] = item.id
                doc.metadata_ = metadata

                results.append(ImportItemResult(
                    sop_id=item.id, title=item.title, success=True, created=upsert_result.created
                ))

                if upsert_result.created:
                    created_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                errors.append(f"{item.id}: {e}")
                results.append(ImportItemResult(
                    sop_id=item.id, title=item.title, success=False, created=False, error=str(e)
                ))

        await db.commit()
        duration = time.time() - start_time

        return ImportResult(
            total_items=len(items),
            successful=created_count + updated_count,
            failed=len(items) - (created_count + updated_count),
            created=created_count,
            updated=updated_count,
            errors=errors,
            items=results,
            duration_seconds=round(duration, 2),
        )


# Singleton
_json_import_service: JsonImportService | None = None


def get_json_import_service() -> JsonImportService:
    global _json_import_service
    if _json_import_service is None:
        _json_import_service = JsonImportService()
    return _json_import_service
