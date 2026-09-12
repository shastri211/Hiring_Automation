from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
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
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=distance),
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

vector_store = QdrantVectorStore()
