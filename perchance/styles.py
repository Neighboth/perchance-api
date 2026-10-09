from __future__ import annotations

# Available aspect ratios and their pixel resolutions
SUPPORTED_RATIOS: dict[str, str] = {
    # 1:1 Square
    "1:1": "768x768",
    "square": "768x768",
    "512x512": "512x512",
    "768x768": "768x768",
    
    # Portrait
    "portrait": "512x768",
    "portrait(512x768)": "512x768",
    "9:16": "512x768",
    "2:3": "512x768",
    "512x768": "512x768",
    
    # Landscape
    "landscape": "768x512",
    "landscape(768x512)": "768x512",
    "16:9": "768x512",
    "3:2": "768x512",
    "768x512": "768x512",
}

# Guidance scale mappings
SUPPORTED_GUIDANCE_SCALES: dict[str, float] = {
    "default": 7.0,
    "default(7)": 7.0,
    "7": 7.0,
    "low": 4.0,
    "low(4)": 4.0,
    "4": 4.0,
    "medium": 7.0,
    "high": 10.0,
    "high(10)": 10.0,
    "10": 10.0,
    "very_high": 15.0,
    "very_high(15)": 15.0,
    "15": 15.0,
}

# Art Style Mixing Modes
SUPPORTED_STYLE_MIXING: dict[str, str] = {
    "not_mix": "Not Mix",
    "not mix": "Not Mix",
    "blend": "Blend",
    "alternate": "Alternate",
}

DEFAULT_NEGATIVE_PHOTO = "anime, cartoon, drawing, illustration, sketch, 3d render, painting, doll, cgi, low quality, bad anatomy, blurry, watermark"

SUPPORTED_STYLES: dict[str, dict[str, str]] = {
    "professional_photo": {
        "label": "Professional Photo",
        "prompt_template": "{prompt}, sharp focus, depth of field, 8k photo, HDR, professional lighting, taken with Canon EOS R5, DSLR, 75mm lens, photorealistic, realistic, 35mm photograph, master photography",
        "negative_prompt": DEFAULT_NEGATIVE_PHOTO,
    },
    "painted_anime": {
        "label": "Painted Anime",
        "prompt_template": "painted anime illustration of {prompt}, rich colors, anime aesthetic, painterly style, studio anime, masterpiece, clean lines, beautiful art",
        "negative_prompt": "low quality, photo, realistic, 3d render, blurry",
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
    "dark_fantasy": {
        "label": "Dark Fantasy",
        "prompt_template": "{prompt}, dark fantasy art, gothic, intricate gloomy details, dramatic moody lighting, atmospheric, epic masterpiece, 8k",
        "negative_prompt": "bright, cheerful, cartoon, low quality",
    },
    "cyberpunk": {
        "label": "Cyberpunk",
        "prompt_template": "{prompt}, cyberpunk aesthetic, neon lights, rainy reflection, high tech futuristic cityscape, hyper-detailed, octane render, 8k",
        "negative_prompt": "natural, historical, medieval, low quality",
    },
    "none": {
        "label": "No Style (Raw)",
        "prompt_template": "{prompt}",
        "negative_prompt": "",
    },
}


def apply_style(
    prompt: str,
    style_name: str | None,
    user_negative: str | None = None,
    style_mixing: str | None = None,
    secondary_style: str | None = None
) -> tuple[str, str]:
    """Apply style prompt template and negative prompt to the input prompt, supporting style mixing."""
    key = (style_name or "professional_photo").lower().replace(" ", "_").replace("-", "_")
    style_info = SUPPORTED_STYLES.get(key, SUPPORTED_STYLES["professional_photo"])

    styled_prompt = style_info["prompt_template"].format(prompt=prompt)
    default_negative = style_info["negative_prompt"]

    mixing_key = (style_mixing or "not_mix").lower().replace(" ", "_").replace("-", "_")
    if mixing_key not in ["not_mix", "none"] and secondary_style:
        sec_key = secondary_style.lower().replace(" ", "_").replace("-", "_")
        sec_info = SUPPORTED_STYLES.get(sec_key)
        if sec_info:
            styled_prompt = f"{styled_prompt}, mixed with {sec_info['label']} style"
            if sec_info["negative_prompt"]:
                default_negative = f"{default_negative}, {sec_info['negative_prompt']}"

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


def resolve_guidance_scale(scale: float | str | None) -> float:
    """Resolve guidance scale to a valid float (default 7.0)."""
    if scale is None:
        return 7.0
    if isinstance(scale, (int, float)):
        return float(scale)
    key = str(scale).lower().strip()
    return SUPPORTED_GUIDANCE_SCALES.get(key, 7.0)
