from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Self

from playwright.async_api import Browser, BrowserContext, async_playwright, Playwright

from . import errors


DEFAULT_PROFILE_DIR = Path.home() / ".perchance_profile"


_SHARED_BROWSER: tuple[Playwright, Browser] | None = None
_BROWSER_LOCK = asyncio.Lock()


class Generator:
    """Base Generator for Perchance services using Playwright with stealth session support."""

    def __init__(
        self,
        *,
        user_data_dir: str | Path | None = None,
        headless: bool = True,
        context: BrowserContext | None = None,
    ) -> None:
        super().__init__()

        self.user_data_dir = Path(user_data_dir or DEFAULT_PROFILE_DIR)
        self.headless = bool(headless)

        self._pw: Playwright | None = None
        self._browser: Browser | None = None
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

        async with _BROWSER_LOCK:
            global _SHARED_BROWSER
            if force_headful and _SHARED_BROWSER:
                try:
                    await _SHARED_BROWSER[1].close()
                except Exception:
                    pass
                _SHARED_BROWSER = None
                self._browser = None
                self._context = None

            if not _SHARED_BROWSER:
                pw = await async_playwright().start()

                if force_headful:
                    # Visible window for manual CAPTCHA solving
                    browser_args = [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ]
                elif self.headless:
                    # Stealth off-screen window: completely invisible to user, yet Turnstile solves!
                    browser_args = [
                        "--window-position=-32000,-32000",
                        "--window-size=1280,800",
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ]
                else:
                    browser_args = [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ]

                browser = await pw.chromium.launch(
                    headless=False,
                    args=browser_args,
                )
                _SHARED_BROWSER = (pw, browser)

            self._pw, self._browser = _SHARED_BROWSER

            if not self._context:
                storage_state_file = self.user_data_dir / "storage_state.json"
                storage_param = str(storage_state_file) if storage_state_file.exists() else None

                self._context = await self._browser.new_context(
                    storage_state=storage_param,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                )
                self._owns_context = True

    async def ensure_verified(
        self,
        embed_domain: str,
        thread: int = 0,
        timeout: float = 30.0,
    ) -> tuple[str, str]:
        """Ensure that the browser session is verified and return (browser_id, user_key)."""
        async with self._auth_lock:
            await self._start()

            page = await self._context.new_page()
            try:
                embed_url = f"https://{embed_domain}/embed#%7B%7D"
                await page.goto(embed_url)

                # Wait for title to confirm page bypassed Turnstile
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < timeout:
                    title = await page.title()
                    if title and title != "Just a moment...":
                        break
                    await asyncio.sleep(0.5)

                # Call embed verifyUser()
                try:
                    await page.evaluate(f"""async () => {{
                        if (typeof verifyUser === 'function') {{
                            try {{
                                return await verifyUser({thread});
                            }} catch(e) {{
                                return await verifyUser('default');
                            }}
                        }}
                        return null;
                    }}""")
                except Exception:
                    pass

                # Poll userKey from generationIdentity and localStorage
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < timeout:
                    info = await page.evaluate(f"""() => {{
                        let id = window.generationIdentity ? window.generationIdentity.id : null;
                        let key = null;
                        if (window.generationIdentity && window.generationIdentity.storage) {{
                            key = window.generationIdentity.storage['userKey-{thread}'] || null;
                        }}
                        if (!key) {{
                            for (let k in localStorage) {{
                                if (k.includes('userKey-{thread}')) {{
                                    key = localStorage[k];
                                    break;
                                }}
                            }}
                        }}
                        return {{ id: id, key: key }};
                    }}""")

                    if info and info.get("id") and info.get("key"):
                        # Ensure we give the verification network roundtrip a moment
                        await asyncio.sleep(1.0)
                        # Re-read key to ensure it is the freshly verified one
                        fresh_key = await page.evaluate(f"""() => {{
                            if (window.generationIdentity && window.generationIdentity.storage && window.generationIdentity.storage['userKey-{thread}']) {{
                                return window.generationIdentity.storage['userKey-{thread}'];
                            }}
                            for (let k in localStorage) {{
                                if (k.includes('userKey-{thread}')) return localStorage[k];
                            }}
                            return null;
                        }}""")
                        effective_key = fresh_key or info["key"]
                        self._browser_id = info["id"]
                        self._user_keys[embed_domain] = effective_key

                        # Save storage state to profile directory
                        try:
                            self.user_data_dir.mkdir(parents=True, exist_ok=True)
                            await self._context.storage_state(path=str(self.user_data_dir / "storage_state.json"))
                        except Exception:
                            pass

                        return self._browser_id, effective_key

                    await asyncio.sleep(0.5)

                raise errors.AuthenticationError(
                    f"Authentication timed out on {embed_domain} in stealth mode."
                )
            except errors.AuthenticationError:
                if self.headless:
                    # Stealth mode hit an unsolved human puzzle: notify user in console and open visible window
                    print(
                        f"[Perchance] Tarayici acildi: '{embed_domain}' adresindeki insan dogrulamasi (Cloudflare / Turnstile) "
                        f"otomatik olarak cozulmedi. Dogrulamayi elle tamamlamaniz icin gorunur pencere acildi."
                    )
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
                                let id = window.generationIdentity ? window.generationIdentity.id : null;
                                let key = null;
                                if (window.generationIdentity && window.generationIdentity.storage) {{
                                    key = window.generationIdentity.storage['userKey-{thread}'] || null;
                                }}
                                if (!key) {{
                                    for (let k in localStorage) {{
                                        if (k.includes('userKey-{thread}')) {{
                                            key = localStorage[k];
                                            break;
                                        }}
                                    }}
                                }}
                                return {{ id: id, key: key }};
                            }}""")
                            if info and info.get("id") and info.get("key"):
                                self._browser_id = info["id"]
                                self._user_keys[embed_domain] = info["key"]
                                try:
                                    self.user_data_dir.mkdir(parents=True, exist_ok=True)
                                    await self._context.storage_state(path=str(self.user_data_dir / "storage_state.json"))
                                except Exception:
                                    pass
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
        global _SHARED_BROWSER
        if _SHARED_BROWSER:
            pw, browser = _SHARED_BROWSER
            try:
                await browser.close()
            except Exception:
                pass
            try:
                await pw.stop()
            except Exception:
                pass
            _SHARED_BROWSER = None
            self._browser = None
            self._pw = None