# perchance-python

[![PyPI version](https://img.shields.io/pypi/v/perchance-python)](https://pypi.org/project/perchance-python)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

Modern, reliable, and unofficial Python client and OpenAI-compatible API server for [Perchance](https://perchance.org) AI text and image generation services.

Built with persistent browser sessions, automated Cloudflare Turnstile token handling, and direct asynchronous streaming endpoints.

---

## Features

- Asynchronous text generation with live real-time token streaming.
- High-resolution text-to-image generation with customizable artistic styles and aspect ratios.
- OpenAI-compatible API server out of the box (`/v1/chat/completions`, `/v1/images/generations`, `/v1/models`).
- Configurable environment options (`.env` file with `PORT` and `HOST`).
- Default realistic photography style (not anime by default).
- Automated generation identity and session validation with persistent state caching.
- Direct image download capability via verified browser context sessions.
- Full type hints and modern Python 3.11+ async/await syntax.

---

## Installation

Install the package via pip:

```bash
pip install perchance-python
```

Ensure Playwright browser dependencies are installed:

```bash
playwright install chromium
```

---

## Styles and Ratios

### Supported Art Styles

By default, images are generated in **`professional_photo`** (photorealistic photography). You can customize this by passing the `style` parameter:

| Style Key | Description |
|---|---|
| `professional_photo` | Realistic, high detail DSLR 8K photography **(Default)** |
| `casual_photo` | Candid everyday snapshot, natural lighting |
| `cinematic` | Movie film aesthetic with dramatic color grading |
| `anime` | Stylized anime artwork |
| `drawn_anime` | Hand-drawn traditional anime illustration |
| `digital_painting` | Digital art trending on Artstation |
| `concept_art` | Video game / movie concept art |
| `oil_painting` | Classical alla prima museum oil painting |
| `watercolor` | Artistic watercolor on textured paper |
| `pixel_art` | 16-bit retro neo-geo pixel art |
| `3d_disney` | 3D Pixar/Disney style CGI animation render |
| `vintage_comic` | 1960s retro comic book with halftone dots |
| `none` | Raw user prompt without additional styling |

### Supported Aspect Ratios

By default, images are generated in **`1:1`** (`square`, 768x768). You can customize this via the `ratio` or `shape` parameter:

| Ratio Key | Alias | Pixel Resolution | Orientation |
|---|---|---|---|
| `1:1` | `square` | 768 x 768 | Square **(Default)** |
| `16:9` | `landscape`, `3:2` | 768 x 512 | Wide Landscape |
| `9:16` | `portrait`, `2:3` | 512 x 768 | Tall Portrait |

---

## Quickstart

### Text Generation (Streaming)

```python
import asyncio
from perchance import TextGenerator

async def main():
    async with TextGenerator() as gen:
        prompt = "Explain quantum computing in two simple sentences."
        
        async for chunk in gen.stream(prompt):
            print(chunk, end="", flush=True)
        print()

if __name__ == "__main__":
    asyncio.run(main())
```

### Image Generation

```python
import asyncio
from PIL import Image
from perchance import ImageGenerator

async def main():
    async with ImageGenerator() as gen:
        prompt = "Elderly fisherman repairing nets by the sea at sunrise"
        
        result = await gen.image(
            prompt,
            style="professional_photo",  # Defaults to professional_photo
            ratio="16:9",               # Defaults to 1:1
            guidance_scale=7.0
        )
        
        print(f"Generated Image ID: {result.image_id}")
        binary = await result.download()
        
        image = Image.open(binary)
        image.save(f"{result.image_id}.jpg")
        image.show()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## OpenAI API Compatible Server

The project includes a ready-to-use API server that mirrors the official OpenAI API format.

### 1. Configuration (`.env`)

Create a `.env` file in your root folder:

```env
PORT=8000
HOST=0.0.0.0
```

### 2. Start the Server

```bash
python examples/server.py
```

### 3. Usage with OpenAI Python Client

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"
)

# Chat Completion (Streaming supported)
response = client.chat.completions.create(
    model="perchance-text",
    messages=[{"role": "user", "content": "Tell me a joke."}]
)
print(response.choices[0].message.content)

# Image Generation
img_response = client.images.generate(
    model="perchance-image",
    prompt="A futuristic cyberpunk train traveling across neon mountains",
    size="1792x1024",  # Automatically mapped to 16:9 landscape
    extra_body={
        "style": "cinematic",
        "ratio": "16:9"
    }
)
print(img_response.data[0].url)
```

---

## API Reference

### `TextGenerator`

- `stream(prompt: str, start_with: str = None, stop_sequences: list = None, timeout: float = 15.0) -> AsyncGenerator[str, None]`
  Streams token chunks as they are generated by the model.
- `text(prompt: str, start_with: str = None, stop_sequences: list = None, timeout: float = 30.0) -> str`
  Convenience method that collects all chunks and returns the full generated text string.

### `ImageGenerator`

- `image(prompt: str, negative_prompt: str = None, seed: int = -1, shape: str = 'square', ratio: str = None, style: str = 'professional_photo', guidance_scale: float = 7.0) -> ImageResult`
  Generates an image according to the specified prompt, art style, and aspect ratio.

### `ImageResult`

- `download() -> io.BytesIO`
  Downloads and returns an in-memory byte buffer of the generated image.
- `save(filename: str = None) -> None`
  Downloads and writes the image directly to disk.
- Properties: `image_id`, `file_extension`, `prompt`, `seed`, `width`, `height`, `guidance_scale`, `maybe_nsfw`.

---

## License

This project is licensed under the Apache 2.0 License. See the [LICENSE](LICENSE) file for details.