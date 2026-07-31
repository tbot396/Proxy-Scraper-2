from __future__ import annotations

from proxyscraper.core.models import Proxy, RotationStrategy
from proxyscraper.server.proxy_server import ProxyPool


class TestProxyPool:
    def _make_proxies(self, n=5):
        return [Proxy(ip=f"1.2.3.{i}", port=8080 + i, alive=True) for i in range(n)]

    def test_per_request_rotates(self):
        proxies = self._make_proxies(3)
        pool = ProxyPool(proxies, RotationStrategy.PER_REQUEST)

        seen = set()
        for _ in range(6):
            p = pool.get_proxy()
            seen.add(p.address)
        assert len(seen) == 3

    def test_sticky_same_client(self):
        proxies = self._make_proxies(3)
        pool = ProxyPool(proxies, RotationStrategy.STICKY, sticky_ttl=300)

        first = pool.get_proxy("client1")
        for _ in range(5):
            assert pool.get_proxy("client1").address == first.address

    def test_on_failure_stays_until_fail(self):
        proxies = self._make_proxies(3)
        pool = ProxyPool(proxies, RotationStrategy.ON_FAILURE)

        first = pool.get_proxy()
        for _ in range(5):
            assert pool.get_proxy().address == first.address

        pool.mark_failed(first)
        second = pool.get_proxy()
        assert second.address != first.address

    def test_mark_failed(self):
        proxies = self._make_proxies(3)
        pool = ProxyPool(proxies, RotationStrategy.PER_REQUEST)
        assert pool.active_count == 3

        pool.mark_failed(proxies[0])
        assert pool.active_count == 2

    def test_mark_all_failed_resets(self):
        proxies = self._make_proxies(2)
        pool = ProxyPool(proxies, RotationStrategy.PER_REQUEST)

        pool.mark_failed(proxies[0])
        pool.mark_failed(proxies[1])

        # All failed, should reset and return a proxy
        p = pool.get_proxy()
        assert p is not None

    def test_empty_pool(self):
        pool = ProxyPool([], RotationStrategy.PER_REQUEST)
        assert pool.get_proxy() is None
        assert pool.active_count == 0

    def test_update_proxies(self):
        proxies = self._make_proxies(3)
        pool = ProxyPool(proxies, RotationStrategy.PER_REQUEST)

        new_proxies = self._make_proxies(5)
        pool.update_proxies(new_proxies)
        assert pool.active_count == 5
