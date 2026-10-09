from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from perchance import ImageGenerator, TextGenerator
from perchance.styles import SUPPORTED_RATIOS, SUPPORTED_STYLES

# Load environment variables from .env file
load_dotenv()

PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")

app = FastAPI(
    title="Perchance OpenAI-Compatible API",
    description="OpenAI API compatible server powered by Perchance AI (Text & Image Generation)",
    version="0.2.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared global generators
_text_generator: TextGenerator | None = None
_image_generator: ImageGenerator | None = None
_lock = asyncio.Lock()


async def get_text_generator() -> TextGenerator:
    global _text_generator
    async with _lock:
        if _text_generator is None:
            _text_generator = TextGenerator()
            await _text_generator._start()
        return _text_generator


async def get_image_generator() -> ImageGenerator:
    global _image_generator
    async with _lock:
        if _image_generator is None:
            _image_generator = ImageGenerator()
            await _image_generator._start()
        return _image_generator


# ---------------------------------------------------------
# Models Schema
# ---------------------------------------------------------
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "perchance-text"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = 0.7
    max_tokens: int | None = None
    stop: list[str] | str | None = None


class ImageGenerationRequest(BaseModel):
    prompt: str
    model: str = "perchance-image"
    n: int = 1
    size: str = "1024x1024"
    response_format: str = "url"  # "url" or "b64_json"
    style: str | None = "professional_photo"  # default photo style
    ratio: str | None = None  # e.g. "1:1", "16:9", "9:16"
    negative_prompt: str | None = None


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@app.get("/v1/models")
async def list_models():
    """List available models."""
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": "perchance-text",
                "object": "model",
                "created": now,
                "owned_by": "salihsimsek",
                "permission": [],
                "root": "perchance-text",
                "parent": None
            },
            {
                "id": "perchance-image",
                "object": "model",
                "created": now,
                "owned_by": "salihsimsek",
                "permission": [],
                "root": "perchance-image",
                "parent": None
            }
        ]
    }


@app.get("/v1/options")
async def list_options():
    """List all available image styles and aspect ratios."""
    return {
        "styles": {
            k: v["label"] for k, v in SUPPORTED_STYLES.items()
        },
        "default_style": "professional_photo",
        "ratios": list(SUPPORTED_RATIOS.keys()),
        "default_ratio": "1:1 (square)"
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible Chat Completion endpoint."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")

    # Combine message history into an instruction prompt
    prompt_lines = []
    for msg in request.messages:
        if msg.role == "system":
            prompt_lines.append(f"Instructions: {msg.content}")
        elif msg.role == "user":
            prompt_lines.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            prompt_lines.append(f"Assistant: {msg.content}")

    full_prompt = "\n\n".join(prompt_lines)
    stop_seqs = [request.stop] if isinstance(request.stop, str) else (request.stop or [])

    gen = await get_text_generator()
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_time = int(time.time())

    if request.stream:
        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                # First chunk with role
                first_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": request.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant"},
                            "finish_reason": None
                        }
                    ]
                }
                yield f"data: {json.dumps(first_chunk)}\n\n"

                async for token in gen.stream(full_prompt, stop_sequences=stop_seqs):
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": None
                            }
                        ]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Final chunk
                final_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": request.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }
                    ]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                err_chunk = {"error": str(e)}
                yield f"data: {json.dumps(err_chunk)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # Non-streaming response
    try:
        response_text = await gen.text(full_prompt, stop_sequences=stop_seqs)
        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created_time,
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(full_prompt.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(full_prompt.split()) + len(response_text.split())
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "perchance-openai-api",
        "endpoints": [
            "/v1/models",
            "/v1/chat/completions",
            "/v1/images/generations",
            "/v1/options",
            "/docs"
        ]
    }


@app.post("/v1/images/generations")
@app.post("/v1/images/generation")
@app.post("/v1/image/generations")
@app.post("/v1/image/generation")
async def image_generations(request: ImageGenerationRequest):
    """OpenAI-compatible Image Generation endpoint."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    # Map ratio / size
    chosen_ratio = request.ratio
    if not chosen_ratio:
        if request.size in ["1024x1024", "512x512", "768x768"]:
            chosen_ratio = "1:1"
        elif request.size in ["1024x1792", "512x768", "768x1344"]:
            chosen_ratio = "9:16"
        elif request.size in ["1792x1024", "768x512", "1344x768"]:
            chosen_ratio = "16:9"
        else:
            chosen_ratio = "1:1"

    style_name = request.style or "professional_photo"
    gen = await get_image_generator()

    results_data = []
    created_time = int(time.time())

    for _ in range(max(1, request.n)):
        result = await gen.image(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            ratio=chosen_ratio,
            style=style_name
        )

        binary = await result.download()
        img_bytes = binary.getvalue()

        if request.response_format == "b64_json":
            b64_data = base64.b64encode(img_bytes).decode("utf-8")
            results_data.append({"b64_json": b64_data})
        else:
            # Data URI format for direct preview/URL usage
            b64_data = base64.b64encode(img_bytes).decode("utf-8")
            data_url = f"data:image/{result.file_extension};base64,{b64_data}"
            results_data.append({"url": data_url})

    return {
        "created": created_time,
        "data": results_data
    }


if __name__ == "__main__":
    import uvicorn
    print(f"Starting Perchance OpenAI-Compatible Server on http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
