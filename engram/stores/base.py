"""Abstract base interfaces for Engram stores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStore(ABC):
    """Base interface all stores must implement."""

    @abstractmethod
    def initialize(self) -> None:
        """Set up the store (create tables, connect, etc.)."""

    @abstractmethod
    def close(self) -> None:
        """Clean up resources."""
