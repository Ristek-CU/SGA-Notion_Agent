import asyncio
import time
from typing import Any, Dict, List, Optional
import httpx


class NotionClient:
    BASE_URL = "https://api.notion.com/v1"

    def __init__(
        self,
        api_key: str,
        version: str = "2022-06-28",
        max_rps: int = 3,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.version = version
        self._max_rps = max_rps
        self._max_retries = max_retries
        self._lock = asyncio.Lock()
        self._timestamps: List[float] = []
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Notion-Version": self.version,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _throttle(self):
        async with self._lock:
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < 1.0]
            if len(self._timestamps) >= self._max_rps:
                wait = 1.0 - (now - self._timestamps[0])
                if wait > 0:
                    await asyncio.sleep(wait)
            self._timestamps.append(time.monotonic())

    def clear_cache(self, prefix: Optional[str] = None):
        if prefix:
            keys_to_del = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_del:
                del self._cache[k]
        else:
            self._cache.clear()

    async def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        cache_key: Optional[str] = None,
        ttl_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        now = time.monotonic()
        if cache_key and cache_key in self._cache:
            data, expire_at = self._cache[cache_key]
            if now < expire_at:
                return data
            del self._cache[cache_key]

        client = self._get_client()
        url = path if path.startswith("http") else f"{self.BASE_URL}{path}"

        for attempt in range(self._max_retries + 1):
            await self._throttle()
            try:
                resp = await client.request(method, url, json=body)
                if resp.status_code == 429 and attempt < self._max_retries:
                    retry_after = float(resp.headers.get("Retry-After", 2 ** attempt))
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                data = resp.json()
                if cache_key and ttl_ms:
                    self._cache[cache_key] = (data, now + (ttl_ms / 1000.0))
                return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < self._max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        raise RuntimeError("Max retries reached for Notion API request")

    async def query_all(self, path: str, body: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        results = []
        cursor = None
        base_body = dict(body) if body else {}

        while True:
            req_body = dict(base_body)
            if cursor:
                req_body["start_cursor"] = cursor
            data = await self.request("POST", path, body=req_body)
            results.extend(data.get("results", []))
            cursor = data.get("next_cursor")
            if not cursor or not data.get("has_more", False):
                break

        return results
