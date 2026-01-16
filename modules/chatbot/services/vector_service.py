"""
Vector Service Module.

Handles embedding generation and vector similarity search.
"""

import logging
import time
from typing import Any

from sentence_transformers import SentenceTransformer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.app_context import ConfigLoader
from modules.chatbot.core.config import ChatbotSettings, get_chatbot_settings
from modules.chatbot.models import SOPDocument
from modules.chatbot.schemas import SearchResponse, SearchResult, SOPDocumentResponse


logger = logging.getLogger(__name__)


class VectorServiceError(Exception):
    """Base exception for vector service errors."""
    pass


class EmbeddingError(VectorServiceError):
    """Raised when embedding generation fails."""
    pass


class SearchError(VectorServiceError):
    """Raised when vector search fails."""
    pass


class UpsertResult:
    """Result of an upsert operation."""

    def __init__(
        self,
        document: SOPDocument,
        created: bool,
        ragic_record_id: str,
    ) -> None:
        self.document = document
        self.created = created
        self.ragic_record_id = ragic_record_id

    @property
    def action(self) -> str:
        return "created" if self.created else "updated"


class VectorService:
    """
    Service for embedding generation and vector similarity search.
    """

    def __init__(self, settings: ChatbotSettings | None = None) -> None:
        self._settings = settings or get_chatbot_settings()
        
        # Load global vector config
        config_loader = ConfigLoader()
        config_loader.load()
        self._vector_config = config_loader.get("vector", {})
        
        self._model_name = self._vector_config.get("model_name", "paraphrase-multilingual-MiniLM-L12-v2")
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"Loading embedding model: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)
            logger.info(f"Model loaded: {self._model_name}")
        return self._model

    def get_device(self) -> str:
        """Get the device (cpu/cuda) the model is running on."""
        if self._model is None:
            return "N/A"
        try:
            return str(self._model.device).upper()
        except Exception:
            return "CPU"

    def generate_embedding(self, text: str) -> list[float]:
        try:
            model = self._get_model()
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        try:
            model = self._get_model()
            embeddings = model.encode(texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise EmbeddingError(f"Failed to generate embeddings: {e}") from e

    async def search(
        self,
        query: str,
        db: AsyncSession,
        top_k: int | None = None,
        category: str | None = None,
        similarity_threshold: float | None = None,
    ) -> SearchResponse:
        start_time = time.time()

        top_k = top_k or int(self._vector_config.get("top_k", 3))
        similarity_threshold = similarity_threshold or float(self._vector_config.get("similarity_threshold", 0.3))

        logger.info(f"Searching: '{query}' (top_k={top_k}, threshold={similarity_threshold})")

        try:
            query_embedding = self.generate_embedding(query)
            results = await self._execute_vector_search(
                db=db,
                query_embedding=query_embedding,
                top_k=top_k,
                category=category,
                similarity_threshold=similarity_threshold,
            )

            search_results: list[SearchResult] = []

            for doc, similarity in results:
                snippet = self._generate_snippet(doc.content, max_length=200)
                search_results.append(SearchResult(
                    document=SOPDocumentResponse.model_validate(doc),
                    similarity_score=similarity,
                    snippet=snippet,
                ))

            elapsed_ms = (time.time() - start_time) * 1000

            return SearchResponse(
                query=query,
                results=search_results,
                total_count=len(search_results),
                search_time_ms=round(elapsed_ms, 2),
            )

        except EmbeddingError:
            raise
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise SearchError(f"Search failed: {e}") from e

    async def _execute_vector_search(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        top_k: int,
        category: str | None,
        similarity_threshold: float,
    ) -> list[tuple[SOPDocument, float]]:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        query_parts = [
            f"SELECT *, (1 - (embedding <=> '{embedding_str}'::vector)) as similarity",
            "FROM sop_documents",
            "WHERE is_published = true",
            "AND embedding IS NOT NULL",
        ]

        params: dict[str, Any] = {
            "threshold": similarity_threshold,
            "limit": top_k,
        }

        if category:
            query_parts.append("AND category = :category")
            params["category"] = category

        query_parts.extend([
            f"AND (1 - (embedding <=> '{embedding_str}'::vector)) >= :threshold",
            f"ORDER BY embedding <=> '{embedding_str}'::vector",
            "LIMIT :limit",
        ])

        full_query = "\n".join(query_parts)
        result = await db.execute(text(full_query), params)
        rows = result.fetchall()

        documents_with_scores: list[tuple[SOPDocument, float]] = []

        for row in rows:
            doc = SOPDocument(
                id=str(row.id),
                title=row.title,
                content=row.content,
                embedding=row.embedding,
                category=row.category,
                tags=row.tags,
                metadata_=row.metadata,
                is_published=row.is_published,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            documents_with_scores.append((doc, row.similarity))

        return documents_with_scores

    @staticmethod
    def _generate_snippet(content: str, max_length: int = 200) -> str:
        cleaned = " ".join(content.split())
        if len(cleaned) <= max_length:
            return cleaned
        truncated = cleaned[:max_length].rsplit(" ", 1)[0]
        return f"{truncated}..."

    async def get_best_match(
        self,
        query: str,
        db: AsyncSession,
    ) -> tuple[SOPDocument, float] | None:
        response = await self.search(query, db, top_k=1)
        if response.results:
            result = response.results[0]
            doc_result = await db.execute(
                select(SOPDocument).where(SOPDocument.id == result.document.id)
            )
            doc = doc_result.scalar_one_or_none()
            if doc:
                return (doc, result.similarity_score)
        return None

    async def index_document(
        self,
        document: SOPDocument,
        db: AsyncSession,
    ) -> None:
        text_to_embed = f"{document.title}\n\n{document.content}"
        logger.info(f"Indexing: {document.title[:50]}... (length={len(text_to_embed)})")
        embedding = self.generate_embedding(text_to_embed)
        document.embedding = embedding

    async def upsert_document(
        self,
        db: AsyncSession,
        ragic_record_id: str,
        title: str,
        content: str,
        category: str | None = None,
        tags: list[str] | None = None,
        is_published: bool = True,
    ) -> UpsertResult:
        logger.info(f"Upserting: record_id={ragic_record_id}, title={title[:50]}...")

        result = await db.execute(
            select(SOPDocument).where(
                SOPDocument.metadata_["ragic_record_id"].astext == ragic_record_id
            )
        )
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            content_changed = (
                existing_doc.title != title or
                existing_doc.content != content
            )

            existing_doc.title = title
            existing_doc.content = content
            existing_doc.category = category
            existing_doc.tags = tags
            existing_doc.is_published = is_published

            existing_metadata = existing_doc.metadata_ or {}
            existing_metadata["ragic_record_id"] = ragic_record_id
            existing_metadata["last_synced_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            existing_doc.metadata_ = existing_metadata

            if content_changed or existing_doc.embedding is None:
                await self.index_document(existing_doc, db)

            await db.flush()
            return UpsertResult(document=existing_doc, created=False, ragic_record_id=ragic_record_id)
        else:
            new_doc = SOPDocument(
                title=title,
                content=content,
                category=category,
                tags=tags,
                is_published=is_published,
                metadata_={
                    "ragic_record_id": ragic_record_id,
                    "source": "json_import",
                    "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
            await self.index_document(new_doc, db)
            db.add(new_doc)
            await db.flush()
            return UpsertResult(document=new_doc, created=True, ragic_record_id=ragic_record_id)

    async def reindex_all_documents(self, db: AsyncSession, batch_size: int = 50) -> int:
        logger.info("Starting full reindex")
        result = await db.execute(
            select(SOPDocument).where(SOPDocument.is_published == True)
        )
        documents = result.scalars().all()
        total = len(documents)

        for i in range(0, total, batch_size):
            batch = documents[i:i + batch_size]
            texts = [f"{doc.title}\n\n{doc.content}" for doc in batch]
            embeddings = self.generate_embeddings(texts)
            for doc, embedding in zip(batch, embeddings):
                doc.embedding = embedding
            logger.info(f"Indexed {min(i + batch_size, total)}/{total}")

        await db.commit()
        return total


# Singleton
_vector_service: VectorService | None = None


def get_vector_service() -> VectorService:
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service
