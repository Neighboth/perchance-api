from __future__ import annotations

import asyncio
import json
import random
from typing import AsyncGenerator

import aiohttp

from . import errors
from .generator import Generator


class TextGenerator(Generator):
    """AI text generator"""

    EMBED_DOMAIN = "text-generation.perchance.org"
    BASE_URL = "https://text-generation.perchance.org/api"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._lock: asyncio.Lock = asyncio.Lock()

    def is_running(self) -> bool:
        return self._lock.locked()

    async def stream(
        self,
        prompt: str,
        *,
        start_with: str | None = None,
        stop_sequences: list[str] | None = None,
        timeout: float | None = 180.0,
    ) -> AsyncGenerator[str, None]:
        """Stream generated text.

        Parameters
        ----------
        prompt: str
            The prompt to generate text from.
        start_with: str | None
            Text to start the generation with.
        stop_sequences: list[str] | None
            List of sequences to stop the generation at.
        timeout: float | None
            Waiting timeout in seconds (default: 180.0).
        """
        async with self._lock:
            browser_id, user_key = await self.ensure_verified(self.EMBED_DOMAIN, thread=0)

            url = (
                f"{self.BASE_URL}/generate"
                f"?browserId={browser_id}"
                f"&userKey={user_key}"
                f"&thread=0"
                f"&requestId=aiTextCompletion{random.randint(0, 2**30)}"
                f"&__cacheBust={random.random()}"
            )
            body = {
                "generatorName": "ai-text-generator",
                "instruction": prompt,
                "instructionTokenCount": 1,
                "startWith": start_with or "",
                "startWithTokenCount": 1,
                "stopSequences": stop_sequences or [],
            }

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                "Referer": "https://text-generation.perchance.org/",
            }

            total_timeout = timeout or 180.0
            client_timeout = aiohttp.ClientTimeout(total=total_timeout, sock_read=60.0)

            async with aiohttp.ClientSession(headers=headers, timeout=client_timeout) as session:
                async with session.post(url, json=body) as resp:
                    if resp.status == 429:
                        raise errors.RateLimitError("Rate limit exceeded")
                    if resp.status == 203:
                        text = await resp.text()
                        if "client_update_required" in text or "invalid_browser_id" in text or "invalid_key" in text:
                            self._user_keys.pop(self.EMBED_DOMAIN, None)
                            raise errors.AuthenticationError(f"Authentication invalid: {text}")

                    if resp.status != 200:
                        text = await resp.text()
                        raise errors.ConnectionError(f"HTTP {resp.status}: {text}")

                    async for line in resp.content:
                        decoded_line = line.decode('utf-8', errors='ignore').strip()
                        if not decoded_line:
                            continue
                        if decoded_line.startswith("t:"):
                            try:
                                yield json.loads(decoded_line[2:])
                            except Exception:
                                pass
                        elif decoded_line.startswith("data:"):
                            # Signal of stream finish
                            return
                        elif "client_update_required" in decoded_line or "invalid_key" in decoded_line:
                            self._user_keys.pop(self.EMBED_DOMAIN, None)
                            raise errors.AuthenticationError(decoded_line)

    async def text(
        self,
        prompt: str,
        *,
        start_with: str | None = None,
        stop_sequences: list[str] | None = None,
        timeout: float | None = 180.0,
    ) -> str:
        """Generate text.

        Parameters
        ----------
        prompt: str
            The prompt to generate text from.
        start_with: str | None
            Text to start the generation with.
        stop_sequences: list[str] | None
            List of sequences to stop the generation at.
        timeout: float | None
            Waiting timeout in seconds.
        """
        result = []
        async for chunk in self.stream(
            prompt,
            start_with=start_with,
            stop_sequences=stop_sequences,
            timeout=timeout,
        ):
            result.append(chunk)

        return "".join(result)
