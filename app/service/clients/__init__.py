from abc import ABC, abstractmethod
from typing import Any


class PlatformClient(ABC):
    @abstractmethod
    async def fetch_profile_data(self, identifier: str) -> dict[str, Any]:
        ...

    async def close(self) -> None:  # noqa: B027
        pass
