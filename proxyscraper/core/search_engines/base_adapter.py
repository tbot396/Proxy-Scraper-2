from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import ClassVar

logger = logging.getLogger(__name__)


class BaseSearchAdapter(ABC):
    name: ClassVar[str] = ""
    _registry: ClassVar[dict[str, type[BaseSearchAdapter]]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            BaseSearchAdapter._registry[cls.name] = cls
            logger.debug("Registered search adapter: %s", cls.name)

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[str]:
        ...

    @classmethod
    def get_adapter(cls, name: str, **kwargs: object) -> BaseSearchAdapter:
        adapter_cls = cls._registry.get(name)
        if adapter_cls is None:
            available = ", ".join(cls._registry.keys())
            raise ValueError(f"Unknown search engine '{name}'. Available: {available}")
        return adapter_cls(**kwargs)

    @classmethod
    def available_adapters(cls) -> list[str]:
        return list(cls._registry.keys())
