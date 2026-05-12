"""Embedding generation via SiliconFlow (OpenAI-compatible)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from gmind.config import Config

MAX_BATCH_SIZE = 32
MAX_RETRIES = 3
MAX_CHARS_PER_TEXT = 15000  # Approximate token limit safety margin


def embed_texts(texts: list[str], cfg: Config) -> list[list[float]]:
    """Embed a list of texts, returning a list of 1024-dim vectors."""
    if not texts:
        return []

    # Truncate to avoid API token limits
    truncated = [t[:MAX_CHARS_PER_TEXT] for t in texts]

    headers = {
        "Authorization": f"Bearer {cfg.embedding_api_key}",
        "Content-Type": "application/json",
    }

    results: list[list[float]] = []
    for i in range(0, len(truncated), MAX_BATCH_SIZE):
        batch = truncated[i : i + MAX_BATCH_SIZE]
        batch_results = _embed_batch(batch, cfg, headers)
        results.extend(batch_results)

    return results


def _embed_batch(
    batch: list[str], cfg: Config, headers: dict[str, str]
) -> list[list[float]]:
    payload = {
        "model": cfg.embedding_model,
        "input": batch,
        "encoding_format": "float",
    }

    last_exception: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    f"{cfg.embedding_base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                # Sort by index because API may reorder
                embeddings = sorted(data["data"], key=lambda x: x["index"])
                return [[float(v) for v in item["embedding"]] for item in embeddings]
        except Exception as exc:
            last_exception = exc
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)  # exponential backoff

    raise RuntimeError(
        f"Embedding failed after {MAX_RETRIES} attempts: {last_exception}"
    )
