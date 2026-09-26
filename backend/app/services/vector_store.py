from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PayloadSchemaType
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class VectorStore(ABC):
    @abstractmethod
    async def create_collection(self, collection_name: str, vector_size: int, metric: str = "Cosine"):
        pass

    @abstractmethod
    async def add_points(self, collection_name: str, ids: List[str], vectors: List[List[float]], payloads: List[Dict[str, Any]]):
        pass

    @abstractmethod
    async def search(self, collection_name: str, query_vector: List[float], limit: int = 10, query_filter: dict = None) -> List[Tuple[str, float, Dict[str, Any]]]:
        pass

    @abstractmethod
    async def delete_points_by_filter(self, collection_name: str, query_filter: dict):
        pass

    @abstractmethod
    async def get_vector(self, collection_name: str, point_id) -> Optional[List[float]]:
        pass

class QdrantVectorStore(VectorStore):
    def __init__(self):
        url = settings.QDRANT_URL
        api_key = settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None
        
        if url.startswith("http://localhost") or url.startswith("http://127.0.0.1"):
            self.client = AsyncQdrantClient(url=url)
        else:
            self.client = AsyncQdrantClient(url=url, api_key=api_key, timeout=30.0)
            
    async def create_collection(self, collection_name: str, vector_size: int = None, metric: str = "Cosine"):
        if vector_size is None:
            vector_size = settings.EMBEDDING_DIMENSION

        # Check if collection exists
        collections = await self.client.get_collections()
        exists = any(c.name == collection_name for c in collections.collections)

        if not exists:
            distance = getattr(Distance, metric.upper(), Distance.COSINE)
            logger.info(f"Creating Qdrant collection: {collection_name} with size {vector_size}, distance {distance}")
            try:
                await self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=distance),
                )
            except Exception:
                # WORKER_CONCURRENCY > 1 means multiple resumes for a brand-
                # new job can reach here at once, all seeing exists=False in
                # the same race window - only one create_collection() call
                # actually wins, and the rest previously failed the whole
                # resume outright (retried, but a wasted attempt every time).
                # Confirm before swallowing, so a genuine failure still
                # raises instead of being masked.
                refreshed = await self.client.get_collections()
                if not any(c.name == collection_name for c in refreshed.collections):
                    raise
                logger.info(
                    f"Qdrant collection {collection_name} was created concurrently "
                    "by another worker; continuing."
                )
        else:
            collection_info = await self.client.get_collection(collection_name)
            # collection_info.config.params.vectors might be dict or VectorParams depending on version, check carefully
            existing_size = None
            if hasattr(collection_info.config.params, 'vectors'):
                vectors_config = collection_info.config.params.vectors
                if hasattr(vectors_config, 'size'):
                    existing_size = vectors_config.size
                elif isinstance(vectors_config, dict) and 'size' in vectors_config:
                    existing_size = vectors_config['size']
            
            if existing_size and existing_size != vector_size:
                error_msg = f"Incompatible dimension in Qdrant collection '{collection_name}'. Expected {vector_size}, found {existing_size}. Please migrate your data or use a different collection."
                logger.error(error_msg)
                raise ValueError(error_msg)

        # Every point's payload carries job_id/resume_id (see add_points call
        # sites) and both are filtered on - job_id by search()'s query_filter
        # and every delete_points_by_filter({"job_id": ...}) call, resume_id
        # by any per-resume cleanup. Qdrant rejects a filter on a field with
        # no payload index ("Index required but not found"), so both must
        # exist before either kind of filter is ever issued. Called every
        # time create_collection() runs (idempotent - Qdrant no-ops a
        # create_payload_index() for a field that's already indexed with the
        # same schema), so a collection created before this existed gets
        # backfilled the next time it's used rather than needing a one-off
        # migration.
        for field_name in ("job_id", "resume_id"):
            try:
                await self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=PayloadSchemaType.INTEGER,
                )
            except Exception as e:
                logger.warning(
                    "Failed to ensure payload index on '%s' for collection '%s': %s",
                    field_name, collection_name, e,
                )

    async def add_points(self, collection_name: str, ids: List[str], vectors: List[List[float]], payloads: List[Dict[str, Any]]):
        if not vectors:
            return
        points = [
            PointStruct(id=uid, vector=vector, payload=payload)
            for uid, vector, payload in zip(ids, vectors, payloads)
        ]
        await self.client.upsert(
            collection_name=collection_name,
            wait=True,
            points=points
        )
        
    async def search(self, collection_name: str, query_vector: List[float], limit: int = 10, query_filter: dict = None) -> List[Tuple[str, float, Dict[str, Any]]]:
        if not query_vector:
            raise ValueError("Query vector cannot be empty")
        
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        qdrant_filter = None
        if query_filter:
            conditions = []
            for k, v in query_filter.items():
                conditions.append(FieldCondition(key=k, match=MatchValue(value=v)))
            qdrant_filter = Filter(must=conditions)
            
        results = await self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            query_filter=qdrant_filter,
            with_payload=True
        )
        return [(str(res.id), res.score, res.payload) for res in results.points]

    async def delete_points_by_filter(self, collection_name: str, query_filter: dict):
        if not query_filter:
            return
            
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        conditions = []
        for k, v in query_filter.items():
            conditions.append(FieldCondition(key=k, match=MatchValue(value=v)))
        qdrant_filter = Filter(must=conditions)
        
        await self.client.delete(
            collection_name=collection_name,
            points_selector=qdrant_filter,
            wait=True
        )

    async def get_vector(self, collection_name: str, point_id) -> Optional[List[float]]:
        """Fetches a previously-stored point's vector, for reuse (Phase 3:
        global file_hash reuse) instead of recomputing an embedding for
        content that's already been embedded under this exact collection.
        Returns None if the collection or point doesn't exist (including
        when this job's embedding profile has never been used before -
        that's an expected, non-error case, not a failure)."""
        try:
            collections = await self.client.get_collections()
            if not any(c.name == collection_name for c in collections.collections):
                return None

            points = await self.client.retrieve(
                collection_name=collection_name,
                ids=[point_id],
                with_vectors=True,
            )
        except Exception as e:
            logger.warning(f"get_vector failed for {collection_name}/{point_id}: {e}")
            return None

        if not points:
            return None

        vector = points[0].vector
        if not isinstance(vector, list):
            # Named-vector collections aren't used by this app; guard anyway
            # rather than reuse something we can't be sure is the plain vector.
            return None
        return vector

vector_store = QdrantVectorStore()
