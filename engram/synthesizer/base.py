"""Abstract LLM interface for the Synthesizer.

Designed to be swappable between Ollama models or any other local backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """Abstract interface for LLM backends used by the Synthesizer."""

    @abstractmethod
    async def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt to the LLM and return the text response.

        Args:
            prompt: The user/content prompt.
            system: Optional system prompt for context.

        Returns:
            The LLM's text response.
        """

    @abstractmethod
    async def extract_json(self, prompt: str, system: str = "") -> dict | list:
        """Send a prompt and parse the response as JSON.

        The LLM should be instructed to return valid JSON.
        This method handles parsing and basic error recovery.

        Args:
            prompt: The user/content prompt.
            system: Optional system prompt.

        Returns:
            Parsed JSON as a dict or list.
        """
