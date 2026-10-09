from __future__ import annotations

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

            if not response_data.get("ok"):
                raise errors.ConnectionError(
                    f"Failed to download image: {response_data.get('failures')}"
                )

            data = base64.b64decode(response_data["data"])
            return io.BytesIO(data)
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
        guidance_scale: float = 7.0
    ) -> ImageResult:
        """
        Generate image.

        Parameters
        ----------
        prompt: str
            Image description.
        negative_prompt: str | None
            Things you do NOT want to see in the image.
        seed: int
            Generation seed.
        shape: str
            Aspect ratio / shape. Can be '1:1', 'square', '9:16', 'portrait', '16:9', 'landscape', etc.
        ratio: str | None
            Alias for shape/aspect ratio.
        style: str
            Art style. Defaults to 'professional_photo'. Options include 'professional_photo',
            'casual_photo', 'cinematic', 'anime', 'drawn_anime', 'digital_painting',
            'concept_art', 'oil_painting', 'watercolor', 'pixel_art', '3d_disney', 'none', etc.
        guidance_scale: float
            Accuracy of the prompt in range 1-30.
        """
        from .styles import apply_style, resolve_resolution

        resolution = resolve_resolution(ratio or shape)
        styled_prompt, effective_negative = apply_style(prompt, style, negative_prompt)
      
        browser_id, user_key = await self.ensure_verified(self.EMBED_DOMAIN, thread=0)

        url = (
            f"{self.BASE_URL}/generate"
            f"?userKey={user_key}"
            f"&requestId=aiImageCompletion{random.randint(0, 2**30)}"
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
            "guidanceScale": guidance_scale
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Referer": "https://image-generation.perchance.org/",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, json=body) as resp:
                if resp.status == 429:
                    raise errors.RateLimitError("Rate limit exceeded")
                if resp.status != 200:
                    text = await resp.text()
                    raise errors.ConnectionError(f"Generation failed with HTTP {resp.status}: {text}")

                response = await resp.json(content_type=None)

        if response.get("status") != "success":
            status = response.get("status")
            if status == "invalid_key":
                # invalidate cached key so next run reverifies
                self._user_keys.pop(self.EMBED_DOMAIN, None)
                raise errors.AuthenticationError("Invalid or expired userKey")
            raise errors.ConnectionError(f"Image generation failed: {status}")

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
