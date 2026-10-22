"""
CodeMind AI — Embedding Generator.

Generates vector embeddings for code chunks using the configured
embedding model (NightOwl-CodeEmbedding or similar).

Supports:
  • Self-hosted models via HTTP API
  • HuggingFace Inference API
  • Batch processing for efficiency
"""

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

import os

logger = get_logger(__name__)

_LOCAL_MODEL = None


def _get_sentence_transformer(
    model_name: str = "Shuu12121/NightOwl-CodeEmbedding",
    token: Optional[str] = None,
):
    """Singleton loader for local SentenceTransformer model with HF_TOKEN support."""
    global _LOCAL_MODEL
    if _LOCAL_MODEL is None:
        if token:
            os.environ["HF_TOKEN"] = token
            os.environ["HUGGING_FACE_HUB_TOKEN"] = token
        from sentence_transformers import SentenceTransformer
        logger.info("loading_embedding_model", model=model_name, has_hf_token=bool(token))
        _LOCAL_MODEL = SentenceTransformer(model_name, token=token if token else None)
    return _LOCAL_MODEL


class EmbeddingGenerator:
    """
    Generates embeddings for code chunks using Shuu12121/NightOwl-CodeEmbedding.
    
    Usage:
        embedder = EmbeddingGenerator()
        embeddings = await embedder.embed_batch(["def hello():", "class Foo:"])
        # Returns list of 768-dimensional float vectors
    """

    def __init__(self):
        self.settings = get_settings()
        self.model_name = self.settings.embedding_model_name or "Shuu12121/NightOwl-CodeEmbedding"
        self.dimension = self.settings.embedding_dimension
        self.api_url = self.settings.embedding_api_url
        self.api_key = self.settings.embedding_api_key

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text string."""
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        Splits into sub-batches if needed.
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await self._embed_request(batch)
            all_embeddings.extend(batch_embeddings)
            
            if len(texts) > batch_size:
                logger.info(
                    "embedding_progress",
                    completed=min(i + batch_size, len(texts)),
                    total=len(texts),
                )
        
        return all_embeddings

    async def _embed_request(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using local NightOwl SentenceTransformer model,
        or fallback to external API if EMBEDDING_API_URL is configured.
        """
        # 1. External API (if explicitly configured)
        if self.api_url:
            return await self._embed_via_api(texts)

        # 2. Local SentenceTransformer (NightOwl-CodeEmbedding)
        try:
            model = _get_sentence_transformer(self.model_name, self.settings.hf_token)

            def _run_encode():
                # NightOwl requires normalize_embeddings=True for cosine similarity
                embs = model.encode(
                    texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                return embs.tolist()

            return await asyncio.to_thread(_run_encode)
        except Exception as e:
            logger.error("sentence_transformer_error", error=str(e), model=self.model_name)
            return self._dev_embeddings(texts)

    async def _embed_via_api(self, texts: List[str]) -> List[List[float]]:
        """Send embedding request to an external OpenAI or HuggingFace API."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                
                response = await client.post(
                    f"{self.api_url.rstrip('/')}/v1/embeddings",
                    headers=headers,
                    json={
                        "input": texts,
                        "model": self.model_name,
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data:
                        return [item["embedding"] for item in data["data"]]
                    if isinstance(data, list):
                        return data
                
                # Try HuggingFace pipeline format
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json={"inputs": texts},
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        import numpy as np
                        embeddings = []
                        for item in data:
                            if isinstance(item[0], list):
                                embedding = list(np.mean(item, axis=0))
                            else:
                                embedding = item
                            embeddings.append(embedding)
                        return embeddings
                
                raise RuntimeError(f"Embedding API returned {response.status_code}: {response.text[:200]}")
                
        except httpx.TimeoutException:
            raise RuntimeError("Embedding API timed out")
        except Exception as e:
            logger.error("embedding_request_failed", error=str(e))
            raise

    def _dev_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate deterministic pseudo-embeddings for development/testing.
        NOT for production — these have no semantic meaning.
        """
        import hashlib
        
        embeddings = []
        for text in texts:
            # Use hash to generate deterministic but meaningless vector
            h = hashlib.sha256(text.encode()).digest()
            # Expand hash to fill dimension
            vector = []
            for i in range(self.dimension):
                byte_idx = i % len(h)
                # Normalize to [-1, 1]
                val = (h[byte_idx] / 255.0) * 2 - 1
                vector.append(round(val, 6))
            embeddings.append(vector)
        
        return embeddings

    async def embed_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for a list of chunk dicts.
        
        Each chunk dict should have a 'content' and 'context_header' key.
        Returns the same chunks with an 'embedding' key added.
        """
        # Prepare texts: use context_header + content for richer embeddings
        texts = []
        for chunk in chunks:
            header = chunk.get("context_header", "")
            content = chunk.get("content", "")
            # Format: "file.py :: ClassName :: method_name\n\ndef method_name(...):"
            combined = f"{header}\n\n{content}" if header else content
            texts.append(combined)
        
        embeddings = await self.embed_batch(texts)
        
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding
        
        return chunks
