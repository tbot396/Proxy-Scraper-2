from __future__ import annotations

import logging
import os

import httpx

from .base_adapter import BaseSearchAdapter

logger = logging.getLogger(__name__)


class GoogleSearchAdapter(BaseSearchAdapter):
    name = "google"

    def __init__(self, api_key: str = "", cx: str = "", **kwargs: object) -> None:
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.cx = cx or os.environ.get("GOOGLE_CX", "")

    async def search(self, query: str, max_results: int = 10) -> list[str]:
        if not self.api_key or not self.cx:
            logger.warning("Google API key or CX not configured, skipping")
            return []

        results: list[str] = []
        start = 1
        per_page = min(max_results, 10)

        async with httpx.AsyncClient(timeout=15) as client:
            while len(results) < max_results:
                params = {
                    "key": self.api_key,
                    "cx": self.cx,
                    "q": query,
                    "num": per_page,
                    "start": start,
                }
                try:
                    resp = await client.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError as e:
                    logger.error("Google search error: %s", e)
                    break

                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    link = item.get("link", "")
                    if link and link not in results:
                        results.append(link)

                start += per_page
                if start > 100:
                    break

        logger.info("Google returned %d results for '%s'", len(results), query)
        return results[:max_results]
