from __future__ import annotations

from proxyscraper.core.events import EventBus, EventType


class TestEventBus:
    def test_subscribe_and_emit(self, event_bus):
        received = []
        event_bus.subscribe(EventType.PROXY_FOUND, lambda **kw: received.append(kw))
        event_bus.emit(EventType.PROXY_FOUND, ip="1.2.3.4", port=80)

        assert len(received) == 1
        assert received[0]["ip"] == "1.2.3.4"
        assert received[0]["port"] == 80

    def test_multiple_subscribers(self, event_bus):
        count = [0, 0]
        event_bus.subscribe(EventType.SCAN_COMPLETE, lambda **kw: count.__setitem__(0, count[0] + 1))
        event_bus.subscribe(EventType.SCAN_COMPLETE, lambda **kw: count.__setitem__(1, count[1] + 1))
        event_bus.emit(EventType.SCAN_COMPLETE)

        assert count == [1, 1]

    def test_unsubscribe(self, event_bus):
        received = []
        cb = lambda **kw: received.append(1)
        event_bus.subscribe(EventType.ERROR, cb)
        event_bus.emit(EventType.ERROR)
        assert len(received) == 1

        event_bus.unsubscribe(EventType.ERROR, cb)
        event_bus.emit(EventType.ERROR)
        assert len(received) == 1

    def test_unsubscribe_nonexistent(self, event_bus):
        event_bus.unsubscribe(EventType.ERROR, lambda: None)  # should not raise

    def test_emit_no_subscribers(self, event_bus):
        event_bus.emit(EventType.LOG, message="test")  # should not raise

    def test_handler_exception_doesnt_break_others(self, event_bus):
        results = []

        def bad_handler(**kw):
            raise ValueError("boom")

        def good_handler(**kw):
            results.append("ok")

        event_bus.subscribe(EventType.LOG, bad_handler)
        event_bus.subscribe(EventType.LOG, good_handler)
        event_bus.emit(EventType.LOG)

        assert results == ["ok"]

    def test_clear(self, event_bus):
        received = []
        event_bus.subscribe(EventType.PROXY_FOUND, lambda **kw: received.append(1))
        event_bus.clear()
        event_bus.emit(EventType.PROXY_FOUND)
        assert received == []
