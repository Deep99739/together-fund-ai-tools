"""
Provider configuration for local LLM-backed workflows.

Centralizes provider ordering, Gemini key rotation, and OpenAI-compatible
fallbacks so each tool can use the same request path without duplicating
credential or retry handling.
"""

import os
import time
import itertools
from typing import Optional


TRANSIENT_ERROR_MARKERS = (
    "429",
    "503",
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
    "rate limit",
    "quota",
)


class LLMConfig:
    """Small provider client with ordered fallback and key rotation."""

    def __init__(self):
        self._gemini_keys = self._load_gemini_keys()
        self._gemini_key_cycle = itertools.cycle(self._gemini_keys) if self._gemini_keys else None
        self._nvidia_key = os.getenv("NVIDIA_API_KEY", "")
        self._groq_key = os.getenv("GROQ_API_KEY", "")

        self._providers = self._build_provider_chain()
        if not self._providers:
            raise RuntimeError("No LLM API keys found. Set GEMINI_API_KEY, NVIDIA_API_KEY, or GROQ_API_KEY.")

    def _load_gemini_keys(self) -> list[str]:
        """Read the configured Gemini key pool in priority order."""
        keys = []
        primary = os.getenv("GEMINI_API_KEY", "")
        if primary:
            keys.append(primary)
        for i in range(2, 10):
            key = os.getenv(f"GEMINI_API_KEY_{i}", "")
            if key:
                keys.append(key)
        return keys

    def _build_provider_chain(self) -> list[dict]:
        """Build the provider chain used by runtime requests."""
        providers = []

        if self._gemini_keys:
            providers.append({
                "name": "Google Gemini",
                "type": "gemini",
                "model": "gemini-2.5-flash",
            })

        if self._nvidia_key:
            providers.append({
                "name": "NVIDIA NIM (DeepSeek V4 Flash)",
                "type": "openai_compat",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "model": "deepseek-ai/deepseek-v4-flash",
                "api_key": self._nvidia_key,
            })

        if self._groq_key:
            providers.append({
                "name": "Groq",
                "type": "openai_compat",
                "base_url": "https://api.groq.com/openai/v1",
                "model": "llama-3.3-70b-versatile",
                "api_key": self._groq_key,
            })

        return providers

    def _call_gemini(self, provider: dict, messages: list[dict], temperature: float, max_tokens: int) -> str:
        """Submit a request through the native Gemini client."""
        from google import genai

        api_key = next(self._gemini_key_cycle)
        client = genai.Client(api_key=api_key)

        # Preserve the shared chat-call shape while adapting to Gemini's API.
        system_instruction = None
        contents = []

        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                contents.append(msg["content"])
            elif msg["role"] == "assistant":
                contents.append(msg["content"])

        # Gemini receives the conversation turns as one ordered text payload.
        if len(contents) == 1:
            prompt = contents[0]
        else:
            prompt = "\n\n".join(contents)

        config = genai.types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        response = client.models.generate_content(
            model=f"models/{provider['model']}",
            contents=prompt,
            config=config,
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response")

        return response.text

    def _call_openai_compat(
        self,
        provider: dict,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        response_format: Optional[dict] = None,
    ) -> str:
        """Submit a request to an OpenAI-compatible provider."""
        from openai import OpenAI

        client = OpenAI(
            api_key=provider["api_key"],
            base_url=provider["base_url"],
            timeout=45.0,
        )

        request_kwargs = {
            "model": provider["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            request_kwargs["response_format"] = response_format

        response = client.chat.completions.create(
            **request_kwargs,
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(f"{provider['name']} returned an empty response")

        return content

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
    ) -> str:
        """
        Send a chat request through the configured provider chain.

        Provider order is Gemini, NVIDIA NIM, then Groq. Gemini keys are rotated
        on transient provider failures before the request falls through to the
        next provider.
        """
        last_error = None
        provider_errors: list[str] = []

        for provider in self._providers:
            # Gemini capacity is spread across the configured key pool.
            if provider["type"] == "gemini":
                max_retries = len(self._gemini_keys)
                for attempt in range(max_retries):
                    try:
                        return self._call_gemini(provider, messages, temperature, max_tokens)
                    except Exception as e:
                        last_error = e
                        error_str = str(e)
                        provider_errors.append(f"Gemini key {attempt + 1}/{max_retries}: {error_str[:180]}")
                        if any(marker in error_str for marker in TRANSIENT_ERROR_MARKERS):
                            print(f"  ⚠ Gemini key {attempt+1}/{max_retries} got rate limited/503. Rotating key...")
                            time.sleep(min(1 + attempt, 3))
                            continue
                        else:
                            print(f"  ⚠ {provider['name']} failed: {error_str[:120]}. Trying next provider...")
                            break
                continue

            # NVIDIA and Groq share the OpenAI-compatible request path.
            try:
                return self._call_openai_compat(provider, messages, temperature, max_tokens, response_format)
            except Exception as e:
                last_error = e
                error_str = str(e)
                provider_errors.append(f"{provider['name']} ({provider['model']}): {error_str[:180]}")
                print(f"  ⚠ {provider['name']} failed: {error_str[:120]}. Trying next provider...")
                time.sleep(0.5)
                continue

        attempts = " | ".join(provider_errors[-8:])
        raise RuntimeError(f"All LLM providers failed. Attempts: {attempts}. Last error: {last_error}")

    def get_active_provider(self) -> str:
        """Return the first configured provider name."""
        if self._providers:
            return self._providers[0]["name"]
        return "None"

    def get_provider_chain(self) -> list[str]:
        """Return provider labels without exposing credentials."""
        return [f"{provider['name']}:{provider.get('model', 'unknown')}" for provider in self._providers]


# Process-local client cache.
_llm_instance: Optional[LLMConfig] = None


def get_llm() -> LLMConfig:
    """Return the shared provider client for the current process."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMConfig()
    return _llm_instance
