"""Ollama (local model) implementation of the LLM interface."""

from __future__ import annotations

import json
import re

import ollama as _ollama_lib

from engram.synthesizer.base import BaseLLM


class OllamaLLM(BaseLLM):
    """Ollama local model backend for the Synthesizer."""

    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434") -> None:
        self._ollama = _ollama_lib
        self._model = model
        self._host = host

    async def complete(self, prompt: str, system: str = "") -> str:
        response = self._ollama.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system or "You are a precise memory extraction assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.message.content

    async def extract_json(self, prompt: str, system: str = "") -> dict | list:
        sys_prompt = system or (
            "You are a precise memory extraction assistant. "
            "Always respond with valid JSON only, no markdown fences, no explanation."
        )
        text = await self.complete(prompt, sys_prompt)
        text = text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)

        # Try to find JSON in the response if it has extra text
        if not text.startswith(("[", "{")):
            # Look for first [ or {
            for i, ch in enumerate(text):
                if ch in ("[", "{"):
                    text = text[i:]
                    break

        # Trim trailing text after JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find the matching closing bracket
            bracket = text[0] if text and text[0] in ("[", "{") else None
            if bracket:
                close = "]" if bracket == "[" else "}"
                depth = 0
                for i, ch in enumerate(text):
                    if ch == bracket:
                        depth += 1
                    elif ch == close:
                        depth -= 1
                        if depth == 0:
                            return json.loads(text[: i + 1])
            raise
