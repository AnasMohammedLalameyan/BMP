"""Search index for Capability 4. One Chroma collection PER COMPANY plus one for the statute library, so a question is
only ever searched in the signed-in company's collection and the library: another company's text is not reachable.
Embeddings are computed locally (sentence-transformers); if that model cannot load, questions are unavailable and the
rest of the dashboard is unaffected."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Callable

from ..errors import ApiError
from .reader import read_pages
from .settings import AiSettings

log = logging.getLogger("bmp.ai")

_embedder: Callable[[list[str]], list[list[float]]] | None = None
_model = None


def set_embedder(fn: Callable | None) -> None:
    """Tests install a small deterministic embedder so no model download is needed."""
    global _embedder
    _embedder = fn


def _embed(s: AiSettings, texts: list[str]) -> list[list[float]]:
    global _model
    if _embedder is not None:
        return _embedder(texts)
    try:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(s.embedding_model)
        return _model.encode(texts, normalize_embeddings=True).tolist()
    except Exception as e:                                                      # noqa: BLE001
        log.warning("embedding model unavailable (%s)", type(e).__name__)
        raise ApiError(503, "ask_unavailable", "Questions are unavailable right now.")


def _client(s: AiSettings):
    import chromadb
    s.index_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(s.index_dir))


def _split(text: str) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    return [c for c in RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120).split_text(text) if c.strip()]


def _fresh(client, name: str, signature: str):
    """The collection for `name` if it was built from exactly `signature`; otherwise an empty new one (rebuild needed)."""
    try:
        col = client.get_collection(name)
        if (col.metadata or {}).get("sig") == signature:
            return col, False
        client.delete_collection(name)
    except Exception:                                                           # noqa: BLE001
        pass
    return client.create_collection(name, metadata={"sig": signature, "hnsw:space": "cosine"}), True


def _add(s: AiSettings, col, rows: list[tuple[str, str, dict]]) -> None:
    for i in range(0, len(rows), 64):
        batch = rows[i:i + 64]
        col.add(ids=[r[0] for r in batch], documents=[r[1] for r in batch], metadatas=[r[2] for r in batch],
                embeddings=_embed(s, [r[1] for r in batch]))


def ensure_company(s: AiSettings, company_id: int, docs: list[dict], storage_dir: Path) -> int:
    """Index the company's documents (each {id, filename, storage_path, updated_at}); re-index when they change.
    Returns how many documents could not be read (scans, unsupported types)."""
    sig = hashlib.sha256("|".join(sorted(f"{d['id']}:{d['updated_at']}" for d in docs)).encode()).hexdigest()
    col, rebuild = _fresh(_client(s), f"company_{company_id}", sig)
    skipped = 0
    if rebuild:
        rows = []
        for d in docs:
            try:
                path = (storage_dir / d["storage_path"]).resolve()
                if storage_dir.resolve() not in path.parents:
                    raise ValueError("outside storage")
                pages = read_pages(path, d["filename"])
            except Exception:                                                   # noqa: BLE001
                skipped += 1
                continue
            for pno, text in enumerate(pages, 1):
                for n, chunk in enumerate(_split(text)):
                    rows.append((f"d{d['id']}-p{pno}-{n}", chunk,
                                 {"filename": d["filename"], "page": pno, "section_ref": "", "source": "company"}))
        if rows:
            _add(s, col, rows)
    return skipped


def ensure_library(s: AiSettings) -> bool:
    folder = s.library_dir
    files = sorted(folder.glob("*.txt")) if folder.is_dir() else []
    if not files:
        return False
    sig = hashlib.sha256("|".join(f"{f.name}:{f.stat().st_mtime_ns}" for f in files).encode()).hexdigest()
    col, rebuild = _fresh(_client(s), "library", sig)
    if rebuild:
        rows = []
        for f in files:
            for n, chunk in enumerate(_split(f.read_text(encoding="utf-8", errors="replace"))):
                rows.append((f"lib-{f.stem}-{n}", chunk,
                             {"filename": f.stem.replace("_", " "), "page": 0, "section_ref": f.stem.replace("_", " "),
                              "source": "library"}))
        if rows:
            _add(s, col, rows)
    return True


def query(s: AiSettings, company_id: int, question: str, k: int = 6) -> list[dict]:
    """The best passages from THIS company's collection and the library. No other collection is ever opened."""
    client = _client(s)
    vec = _embed(s, [question])
    found = []
    for name in (f"company_{company_id}", "library"):
        try:
            col = client.get_collection(name)
        except Exception:                                                       # noqa: BLE001
            continue
        if col.count() == 0:
            continue
        res = col.query(query_embeddings=vec, n_results=min(k, col.count()))
        for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            found.append({"text": text, "meta": meta, "distance": dist})
    found.sort(key=lambda x: x["distance"])
    return found[:k]
