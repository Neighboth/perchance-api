from __future__ import annotations

import asyncio
import base64
import io
import random
from typing import Any, Literal
from urllib.parse import urljoin

import aiofiles
import aiohttp

from . import errors
from .generator import Generator


def _find_proxy_download(value: Any) -> str | None:
    """Find the proxy image download path or token in a generate response."""
    if isinstance(value, str):
        if "downloadTemporaryImageViaProxy" in value:
            return value
        if value.startswith("v1.") and len(value) > 80:
            return f"/api/downloadTemporaryImageViaProxy?t={value}"
        return None

    if isinstance(value, dict):
        for item in value.values():
            result = _find_proxy_download(item)
            if result:
                return result
        return None

    if isinstance(value, list):
        for item in value:
            result = _find_proxy_download(item)
            if result:
                return result

    return None


class ImageResult:
    """Image generation result."""

    def __init__(
        self, 
        *, 
        generator: ImageGenerator,
        image_id: str,
        file_extension: str,
        seed: int,
        prompt: str,
        width: int,
        height: int,
        guidance_scale: float,
        negative_prompt: str | None,
        maybe_nsfw: bool,
        proxy_download: str | None = None,
    ) -> None:
        self._generator: ImageGenerator = generator

        self.image_id: str = image_id
        """Image ID."""
        self.file_extension: str = file_extension
        """File extension."""
        self.seed: int = seed
        """Generation seed."""
        self.prompt: str = prompt
        """Image prompt."""
        self.width: int = width
        """Image width."""
        self.height: int = height
        """Image height."""
        self.guidance_scale: float = guidance_scale
        """Guidance scale."""
        self.negative_prompt: str | None = negative_prompt
        """Negative prompt."""
        self.maybe_nsfw: bool = maybe_nsfw
        """Whether the image may be NSFW."""
        self.proxy_download: str | None = proxy_download
        """Proxy download URL or token returned by Perchance, when available."""
    
    def __str__(self) -> str:
        return f"{self.image_id}.{self.file_extension}"

    @property
    def size(self) -> tuple[int, int]:
        """Image size as (width, height)."""
        return self.width, self.height

    async def download(self) -> io.BytesIO:
        """Download the image binary."""
        urls = []
        if self.proxy_download:
            if self.proxy_download.startswith("http"):
                urls.append(self.proxy_download)
            else:
                base = "https://image-generation.perchance.org"
                if not self.proxy_download.startswith("/"):
                    urls.append(f"{base}/{self.proxy_download}")
                else:
                    urls.append(f"{base}{self.proxy_download}")

        urls.append(
            f"{self._generator.BASE_URL}/downloadTemporaryImage?imageId={self.image_id}"
        )

        await self._generator._start()
        page = await self._generator._context.new_page()
        try:
            if not page.url.startswith("https://image-generation.perchance.org"):
                await page.goto("https://image-generation.perchance.org/embed#%7B%7D")

            max_download_attempts = 4
            for d_attempt in range(max_download_attempts):
                response_data = await page.evaluate("""
                    async (urls) => {
                        const failures = [];
                        for (const url of urls) {
                            try {
                                const response = await fetch(url);
                                if (!response.ok) {
                                    failures.push(`${response.status} ${url}`);
                                    continue;
                                }
                                const blob = await response.blob();
                                const base64 = await new Promise(resolve => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => resolve(reader.result.split(",")[1]);
                                    reader.readAsDataURL(blob);
                                });
                                return { ok: true, data: base64 };
                            } catch (e) {
                                failures.push(`${e.message} ${url}`);
                            }
                        }
                        return { ok: false, failures };
                    }
                """, urls)

                if response_data.get("ok"):
                    data = base64.b64decode(response_data["data"])
                    return io.BytesIO(data)

                # Wait slightly for proxy image upload to settle
                await asyncio.sleep(1.0 + d_attempt * 0.5)

            raise errors.ConnectionError(
                f"Failed to download image after retries: {response_data.get('failures')}"
            )
        finally:
            await page.close()
 
    async def save(self, filename: str | None = None) -> None:
        """Download and save the image.

        Parameters
        ----------
        filename: str | None
            Name of the output file.
        """
        file = filename or f"{self.image_id}.{self.file_extension}" 

        async with aiofiles.open(file, 'wb') as f:
            img = await self.download()
            await f.write(img.read())


class ImageGenerator(Generator):
    """AI image generator"""

    EMBED_DOMAIN = "image-generation.perchance.org"
    BASE_URL = "https://image-generation.perchance.org/api"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    async def image(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        seed: int = -1,
        shape: str = "square",
        ratio: str | None = None,
        style: str = "professional_photo",
        style_mixing: str | None = "not_mix",
        secondary_style: str | None = None,
        guidance_scale: float | str | None = 7.0,
    ) -> ImageResult:
        """
        Generate image with Perchance professional options.

        Parameters
        ----------
        prompt: str
            Image description (required).
        negative_prompt: str | None
            Things you do NOT want to see in the image (optional).
        seed: int
            Generation seed (-1 for random).
        shape: str
            Aspect ratio / shape ('square', 'portrait(512x768)', 'landscape(768x512)', etc.).
        ratio: str | None
            Alias for shape/aspect ratio ('1:1', '9:16', '16:9').
        style: str
            Primary art style ('professional_photo', 'painted_anime', 'cinematic', etc.).
        style_mixing: str | None
            Art style mixing mode ('not_mix', 'blend', 'alternate').
        secondary_style: str | None
            Secondary art style when style mixing is enabled.
        guidance_scale: float | str | None
            Prompt adherence accuracy (e.g. 7.0, 'default(7)', 'low(4)', 'high(10)', 'very_high(15)').
        """
        from .styles import apply_style, resolve_resolution, resolve_guidance_scale

        resolution = resolve_resolution(ratio or shape)
        effective_scale = resolve_guidance_scale(guidance_scale)
        styled_prompt, effective_negative = apply_style(
            prompt=prompt,
            style_name=style,
            user_negative=negative_prompt,
            style_mixing=style_mixing,
            secondary_style=secondary_style,
        )
      
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Referer": "https://image-generation.perchance.org/",
        }

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            browser_id, user_key = await self.ensure_verified(self.EMBED_DOMAIN, thread=0)

            # Retrieve fresh adAccessCode from perchance.org
            ad_access_code = ""
            try:
                ad_url = f"https://perchance.org/api/getAccessCodeForAdPoweredStuff?__cacheBust={random.random()}"
                ad_headers = {
                    "User-Agent": headers["User-Agent"],
                    "Referer": "https://perchance.org/",
                }
                async with aiohttp.ClientSession(headers=ad_headers) as ad_session:
                    async with ad_session.get(ad_url, timeout=aiohttp.ClientTimeout(total=5.0)) as ad_resp:
                        if ad_resp.status == 200:
                            ad_access_code = (await ad_resp.text()).strip()
            except Exception:
                pass

            url = (
                f"{self.BASE_URL}/generate"
                f"?userKey={user_key}"
                f"&requestId=aiImageCompletion{random.randint(0, 2**30)}"
                f"&adAccessCode={ad_access_code}"
                f"&__cacheBust={random.random()}"
            )
            body = {
                "generatorName": "ai-image-generator",
                "channel": "ai-text-to-image-generator",
                "subChannel": "public",
                "prompt": styled_prompt,
                "negativePrompt": effective_negative,
                "seed": seed,
                "resolution": resolution,
                "guidanceScale": effective_scale
            }

            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.post(url, json=body) as resp:
                        if resp.status == 429:
                            raise errors.RateLimitError("Rate limit exceeded")
                        if resp.status != 200:
                            text = await resp.text()
                            raise errors.ConnectionError(f"Generation failed with HTTP {resp.status}: {text}")

                        response = await resp.json(content_type=None)

                status = response.get("status")
                if status == "success":
                    proxy_dl = response.get("imageDownloadUrl") or _find_proxy_download(response)
                    return ImageResult(
                        generator=self,
                        image_id=response['imageId'],
                        file_extension=response['fileExtension'],
                        seed=response['seed'],
                        prompt=response['prompt'],
                        width=response['width'],
                        height=response['height'],
                        guidance_scale=response['guidanceScale'],
                        negative_prompt=response.get('negativePrompt'),
                        maybe_nsfw=response.get('maybeNsfw', False),
                        proxy_download=proxy_dl,
                    )

                if status in ["invalid_key", "invalid_ad_access_code", "client_update_required"]:
                    # Invalidate cached key and retry
                    self._user_keys.pop(self.EMBED_DOMAIN, None)
                    await asyncio.sleep(1.0 + attempt)
                    continue

                raise errors.ConnectionError(f"Image generation failed: {status}")

            except (aiohttp.ClientError, asyncio.TimeoutError, errors.ConnectionError) as e:
                last_error = e
                self._user_keys.pop(self.EMBED_DOMAIN, None)
                await asyncio.sleep(1.0 + attempt)

        raise errors.ConnectionError(f"Image generation failed after {max_retries} retries: {last_error}")
