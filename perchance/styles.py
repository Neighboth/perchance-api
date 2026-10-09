from __future__ import annotations

# Available aspect ratios and their pixel resolutions
SUPPORTED_RATIOS: dict[str, str] = {
    "1:1": "768x768",
    "square": "768x768",
    "9:16": "512x768",
    "2:3": "512x768",
    "portrait": "512x768",
    "16:9": "768x512",
    "3:2": "768x512",
    "landscape": "768x512",
}

DEFAULT_NEGATIVE_PHOTO = "anime, cartoon, drawing, illustration, sketch, 3d render, painting, doll, cgi, low quality, bad anatomy, blurry, watermark"

SUPPORTED_STYLES: dict[str, dict[str, str]] = {
    "professional_photo": {
        "label": "Professional Photo",
        "prompt_template": "{prompt}, sharp focus, depth of field, 8k photo, HDR, professional lighting, taken with Canon EOS R5, DSLR, 75mm lens, photorealistic, realistic, 35mm photograph, master photography",
        "negative_prompt": DEFAULT_NEGATIVE_PHOTO,
    },
    "casual_photo": {
        "label": "Casual Photo",
        "prompt_template": "A casual real-life photograph. A casual photo of {prompt}. It's a casual photo. Overall it's an actual real-life photograph, natural lighting, iPhone photo, candid shot",
        "negative_prompt": DEFAULT_NEGATIVE_PHOTO,
    },
    "cinematic": {
        "label": "Cinematic",
        "prompt_template": "{prompt}, cinematic shot, dynamic lighting, 75mm, Technicolor, Panavision, cinemascope, sharp focus, fine details, 8k, HDR, film still, cinematic color grading, depth of field",
        "negative_prompt": "cartoon, 3d, anime, low quality, blurry, deformed",
    },
    "anime": {
        "label": "Anime",
        "prompt_template": "anime art of {prompt}, world-class masterpiece, 4k, best quality, beautiful anime artwork, high resolution, aesthetic anime visual",
        "negative_prompt": "low quality, bad anatomy, worst quality, blurry",
    },
    "drawn_anime": {
        "label": "Drawn Anime",
        "prompt_template": "hand drawn anime illustration of {prompt}, Japanese manga style, vibrant colors, clean lineart, studio anime",
        "negative_prompt": "photo, photorealistic, 3d render, low quality",
    },
    "digital_painting": {
        "label": "Digital Painting",
        "prompt_template": "{prompt}, breathtaking digital art, trending on artstation, 8k, high resolution, best quality, intricate details, fantasy concept art",
        "negative_prompt": "low quality, photo, blurry",
    },
    "concept_art": {
        "label": "Concept Art",
        "prompt_template": "{prompt}, concept art, digital art, illustration, inspired by wlop style, 8k, fine details, sharp, very detailed, high resolution",
        "negative_prompt": "low quality, blurry, watermark",
    },
    "oil_painting": {
        "label": "Oil Painting",
        "prompt_template": "breathtaking alla prima oil painting, {prompt}, close up, alla prima, impasto, visible brush strokes, fine art, museum masterpiece",
        "negative_prompt": "photo, 3d render, anime, blurry",
    },
    "watercolor": {
        "label": "Watercolor",
        "prompt_template": "{prompt}, watercolor painting, high resolution, intricate details, 4k, watercolor on textured cold press paper, wet on wet, artistic",
        "negative_prompt": "photo, 3d, dark, blurry",
    },
    "pixel_art": {
        "label": "Pixel Art",
        "prompt_template": "(pixel art), {prompt}, best pixel art, neo-geo graphical style, retro nostalgic masterpiece, 16-bit pixel art, 2D pixel art style",
        "negative_prompt": "photo, 3d, smooth, high resolution modern art",
    },
    "3d_disney": {
        "label": "3D Disney Character",
        "prompt_template": "3D cartoon Disney character portrait render. {prompt}, bokeh, 4k, highly detailed, Pixar render, CGI Animation, Disney, octane render",
        "negative_prompt": "photo, anime, flat drawing, low quality",
    },
    "vintage_comic": {
        "label": "Vintage Comic",
        "prompt_template": "comic book style art of {prompt}, vintage comic art, 1960s comic, retro halftone dots, ink lines",
        "negative_prompt": "photo, 3d render, blurry",
    },
    "none": {
        "label": "No Style (Raw)",
        "prompt_template": "{prompt}",
        "negative_prompt": "",
    },
}


def apply_style(prompt: str, style_name: str | None, user_negative: str | None = None) -> tuple[str, str]:
    """Apply style prompt template and negative prompt to the input prompt."""
    key = (style_name or "professional_photo").lower().replace(" ", "_").replace("-", "_")
    style_info = SUPPORTED_STYLES.get(key, SUPPORTED_STYLES["professional_photo"])

    styled_prompt = style_info["prompt_template"].format(prompt=prompt)
    default_negative = style_info["negative_prompt"]

    if user_negative:
        if default_negative:
            combined_negative = f"{user_negative}, {default_negative}"
        else:
            combined_negative = user_negative
    else:
        combined_negative = default_negative

    return styled_prompt, combined_negative


def resolve_resolution(ratio_or_shape: str | None) -> str:
    """Resolve aspect ratio or shape to supported pixel resolution string."""
    key = (ratio_or_shape or "square").lower().strip()
    return SUPPORTED_RATIOS.get(key, "768x768")
