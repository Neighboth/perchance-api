from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Self

from playwright.async_api import BrowserContext, async_playwright, Playwright

from . import errors


DEFAULT_PROFILE_DIR = Path.home() / ".perchance_profile"


_SHARED_CONTEXTS: dict[str, tuple[Playwright, BrowserContext]] = {}
_CONTEXT_LOCK = asyncio.Lock()


class Generator:
    """Base Generator for Perchance services using Playwright with persistent session support."""

    def __init__(
        self,
        *,
        user_data_dir: str | Path | None = None,
        headless: bool = False,
        context: BrowserContext | None = None,
    ) -> None:
        super().__init__()

        self.user_data_dir = Path(user_data_dir or DEFAULT_PROFILE_DIR)
        self.headless = headless if headless is not None else True

        self._pw: Playwright | None = None
        self._context: BrowserContext | None = context
        self._owns_context: bool = context is None
        self._browser_id: str | None = None
        self._user_keys: dict[str, str] = {}
        self._auth_lock: asyncio.Lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        await self._start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()

    async def _start(self, force_headful: bool = False) -> None:
        if self._context and not force_headful:
            return

        key = str(self.user_data_dir.resolve())
        async with _CONTEXT_LOCK:
            if force_headful and self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass
                self._context = None
                _SHARED_CONTEXTS.pop(key, None)

            if not force_headful and key in _SHARED_CONTEXTS:
                pw, ctx = _SHARED_CONTEXTS[key]
                self._pw = pw
                self._context = ctx
                self._owns_context = False
                return

            if not self._pw:
                self._pw = await async_playwright().start()

            self.user_data_dir.mkdir(parents=True, exist_ok=True)
            is_headless = False if force_headful else self.headless
            self._context = await self._pw.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=is_headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            _SHARED_CONTEXTS[key] = (self._pw, self._context)
            self._owns_context = True

    async def ensure_verified(
        self,
        embed_domain: str,
        thread: int = 0,
        timeout: float = 30.0,
    ) -> tuple[str, str]:
        """Ensure that the browser session is verified and return (browser_id, user_key).
        
        Parameters
        ----------
        embed_domain : str
            Domain for the embed service (e.g. 'image-generation.perchance.org' or 'text-generation.perchance.org')
        thread : int
            Thread index to verify (default 0).
        timeout : float
            Maximum seconds to wait for verification/Turnstile to resolve.
        """
        async with self._auth_lock:
            await self._start()

            page = await self._context.new_page()
            try:
                embed_url = f"https://{embed_domain}/embed#%7B%7D"
                await page.goto(embed_url)

                # Call the embed's internal verifyUser()
                try:
                    await page.evaluate(f"""async () => {{
                        if (typeof verifyUser === 'function') {{
                            try {{
                                return await verifyUser({thread});
                            }} catch(e) {{
                                return await verifyUser();
                            }}
                        }}
                        return null;
                    }}""")
                except Exception:
                    pass

                # Poll generationIdentity until userKey is ready
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < timeout:
                    info = await page.evaluate(f"""() => {{
                        if (!window.generationIdentity) return null;
                        return {{
                            id: window.generationIdentity.id,
                            key: window.generationIdentity.storage['userKey-{thread}'] || null
                        }};
                    }}""")

                    if info and info.get("id") and info.get("key"):
                        self._browser_id = info["id"]
                        self._user_keys[embed_domain] = info["key"]
                        return self._browser_id, info["key"]

                    await asyncio.sleep(0.5)

                raise errors.AuthenticationError(
                    f"Authentication timed out on {embed_domain} in headless mode."
                )
            except errors.AuthenticationError:
                if self.headless:
                    # Headless mode hit a challenge: relaunch headful once so Turnstile can solve
                    await self._start(force_headful=True)
                    headful_page = await self._context.new_page()
                    try:
                        await headful_page.goto(f"https://{embed_domain}/embed#%7B%7D")
                        try:
                            await headful_page.evaluate(f"""async () => {{
                                if (typeof verifyUser === 'function') {{
                                    try {{ return await verifyUser({thread}); }} catch(e) {{ return await verifyUser(); }}
                                }}
                                return null;
                            }}""")
                        except Exception:
                            pass

                        start_time = asyncio.get_event_loop().time()
                        while asyncio.get_event_loop().time() - start_time < timeout:
                            info = await headful_page.evaluate(f"""() => {{
                                if (!window.generationIdentity) return null;
                                return {{
                                    id: window.generationIdentity.id,
                                    key: window.generationIdentity.storage['userKey-{thread}'] || null
                                }};
                            }}""")
                            if info and info.get("id") and info.get("key"):
                                self._browser_id = info["id"]
                                self._user_keys[embed_domain] = info["key"]
                                return self._browser_id, info["key"]
                            await asyncio.sleep(0.5)
                    finally:
                        await headful_page.close()

                raise errors.AuthenticationError(
                    f"Authentication timed out on {embed_domain}. Please complete verification in browser."
                )
            finally:
                if not page.is_closed():
                    await page.close()

    async def close(self) -> None:
        """Close the generator and release resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._pw:
            await self._pw.stop()
            self._pw = None