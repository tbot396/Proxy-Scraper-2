from __future__ import annotations

import logging
import os

import httpx

from .base_adapter import BaseSearchAdapter

logger = logging.getLogger(__name__)


class BingSearchAdapter(BaseSearchAdapter):
    name = "bing"

    def __init__(self, api_key: str = "", **kwargs: object) -> None:
        self.api_key = api_key or os.environ.get("BING_API_KEY", "")

    async def search(self, query: str, max_results: int = 10) -> list[str]:
        if not self.api_key:
            logger.warning("Bing API key not configured, skipping")
            return []

        results: list[str] = []
        offset = 0

        async with httpx.AsyncClient(timeout=15) as client:
            while len(results) < max_results:
                count = min(max_results - len(results), 50)
                headers = {"Ocp-Apim-Subscription-Key": self.api_key}
                params = {
                    "q": query,
                    "count": count,
                    "offset": offset,
                    "mkt": "en-US",
                }
                try:
                    resp = await client.get(
                        "https://api.bing.microsoft.com/v7.0/search",
                        headers=headers,
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError as e:
                    logger.error("Bing search error: %s", e)
                    break

                pages = data.get("webPages", {}).get("value", [])
                if not pages:
                    break

                for page in pages:
                    url = page.get("url", "")
                    if url and url not in results:
                        results.append(url)

                offset += count

        logger.info("Bing returned %d results for '%s'", len(results), query)
        return results[:max_results]
