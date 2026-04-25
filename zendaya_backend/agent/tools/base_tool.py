# In zendaya_backend/agent/tools/base_tool.py

from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseTool(ABC):
    """Abstract base class for all tools."""

    @abstractmethod
    async def arun(self, *args, **kwargs) -> Any:
        """
        Asynchronously run the tool. Must be implemented by subclasses.
        """
        pass