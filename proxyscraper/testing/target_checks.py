from __future__ import annotations

import logging

import httpx

from proxyscraper.core.config import TargetCheck
from proxyscraper.core.models import Proxy

logger = logging.getLogger(__name__)


class TargetChecker:
    def __init__(self, checks: list[TargetCheck]) -> None:
        self.checks = checks

    async def run_checks(self, proxy: Proxy, timeout: float | None = None) -> dict[str, str]:
        results: dict[str, str] = {}

        for check in self.checks:
            result = await self._run_single(proxy, check, timeout)
            results[check.name] = result

        proxy.target_checks = results
        return results

    async def _run_single(
        self, proxy: Proxy, check: TargetCheck, timeout: float | None = None,
    ) -> str:
        t = timeout or check.timeout_seconds
        try:
            async with httpx.AsyncClient(
                proxy=f"http://{proxy.address}",
                timeout=t,
            ) as client:
                resp = await client.get(check.url)

                if resp.status_code != check.expect_status:
                    return "failed"

                if check.expect_contains and check.expect_contains not in resp.text:
                    return "failed"

                return "passed"
        except httpx.HTTPError:
            return "failed"
        except Exception as e:
            logger.debug("Target check '%s' error for %s: %s", check.name, proxy.address, e)
            return "failed"
