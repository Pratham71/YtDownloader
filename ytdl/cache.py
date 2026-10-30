"""A small on-disk cache of recent search results."""

from __future__ import annotations

import json
import time

from .config import cache_dir, write_json


SEARCH_TTL_SECONDS = 60 * 60
MAX_QUERIES = 50


def _path():
    return cache_dir() / "search-cache.json"


def _load() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _key(query: str) -> str:
    return " ".join(query.lower().split())


def cached_search(query: str, limit: int) -> list[dict] | None:
    entry = _load().get(_key(query))
    if not isinstance(entry, dict) or time.time() - entry.get("time", 0) > SEARCH_TTL_SECONDS:
        return None
    results = entry.get("results") or []
    # A shorter list is still complete when the search had no more results.
    if len(results) >= limit or entry.get("limit", 0) >= limit:
        return results[:limit]
    return None


def store_search(query: str, limit: int, results: list[dict]) -> None:
    data = _load()
    data[_key(query)] = {"time": time.time(), "limit": limit, "results": results}
    newest = sorted(data.items(), key=lambda item: item[1].get("time", 0), reverse=True)
    try:
        write_json(_path(), dict(newest[:MAX_QUERIES]))
    except OSError:
        pass


def clear() -> None:
    _path().unlink(missing_ok=True)
