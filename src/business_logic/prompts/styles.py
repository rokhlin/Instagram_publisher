"""
AI Style Catalog, prompt directives, Instagram music recommendations,
and intelligent style variant selection.
Derived from QuestStudio Instagram Creator benchmarks.
"""

from typing import Dict, Any, List, Optional
import re


AI_STYLES_CATALOG: Dict[str, Dict[str, Any]] = {
    "CLEAN_COMMERCIAL": {
        "id": "CLEAN_COMMERCIAL",
        "name_en": "Clean Commercial",
        "name_ru": "Чистый коммерческий",
        "vibe": "Minimalist, high clarity, beige/neutral studio",
        "prompt_directive": (
            "Apply clean commercial styling: soft diffused studio lighting, neutral minimalist background, "
            "realistic textures, balanced exposure, sharp visual focus. Leave clean space for overlay text. "
            "Avoid clutter, plastic skin, oversaturation, fake text, distorted objects."
        ),
        "negative_constraints": "clutter, plastic skin, oversaturation, fake text, distorted objects, heavy grain",
        "music": {
            "genres": ["Minimal Electronic", "Modern Chillwave", "Downtempo"],
            "tempo": "Medium (90-110 BPM)",
            "keywords": ["minimal chill", "clean beat", "modern aesthetic", "ambient focus"]
        }
    },
    "WARM_CAFE": {
        "id": "WARM_CAFE",
        "name_en": "Warm Cafe Lifestyle",
        "name_ru": "Теплый кофейный уют",
        "vibe": "Cozy, morning window light, coffee & wood tones",
        "prompt_directive": (
            "Enhance as cozy cafe lifestyle photography: soft morning window light, warm earthy shadows, "
            "subtle background blur, authentic textures, cozy mood. Leave clean space at the top for text. "
            "Avoid oversaturated yellow/orange, fake text, blown highlights, distorted anatomy."
        ),
        "negative_constraints": "oversaturated yellow, fake text, blown highlights, distorted anatomy, cold tones",
        "music": {
            "genres": ["Lo-Fi Study Beats", "Acoustic Indie", "Coffeehouse Acoustic"],
            "tempo": "Slow to Medium (75-90 BPM)",
            "keywords": ["coffeehouse", "morning lo-fi", "warm acoustic", "cozy vibes"]
        }
    },
    "STREET_35MM": {
        "id": "STREET_35MM",
        "name_en": "35mm Editorial Street",
        "name_ru": "35мм уличный эдиториал",
        "vibe": "Subdued contrast, 35mm film grain, candid city fashion",
        "prompt_directive": (
            "Transform with 35mm street photography aesthetic: soft overcast daylight, authentic film grain, "
            "muted urban color palette, candid posture, realistic fabric texture, natural skin tones. "
            "Avoid plastic skin, excessive smoothing, cartoon effects, fake logos."
        ),
        "negative_constraints": "plastic skin, excessive smoothing, cartoon effects, fake logos, high gloss",
        "music": {
            "genres": ["Neo-Soul", "Chill R&B", "Underground Hip-Hop Instrumental"],
            "tempo": "Medium (85-95 BPM)",
            "keywords": ["urban chill", "city walk", "street style", "night drive beats"]
        }
    },
    "GOLDEN_HOUR": {
        "id": "GOLDEN_HOUR",
        "name_en": "Golden Hour Travel",
        "name_ru": "Золотой час путешествий",
        "vibe": "Sunset rim light, scenic outdoors, atmospheric haze",
        "prompt_directive": (
            "Render in golden hour adventure aesthetic: warm low-angle sunlight, natural rim lighting, "
            "scenic outdoor backdrop with gentle atmospheric depth, true-to-life colors, realistic textures. "
            "Avoid excessive lens flare, blown highlights, cartoon saturation."
        ),
        "negative_constraints": "excessive lens flare, blown highlights, cartoon saturation, muddy shadows",
        "music": {
            "genres": ["Indie Folk", "Uplifting Pop", "Cinematic Ambient"],
            "tempo": "Medium (100-118 BPM)",
            "keywords": ["travel vibes", "golden hour", "wanderlust", "sunset roadtrip"]
        }
    },
    "ATHLETIC_DRIVE": {
        "id": "ATHLETIC_DRIVE",
        "name_en": "High-Energy Fitness",
        "name_ru": "Спортивный драйв",
        "vibe": "Dynamic side rim lighting, high micro-contrast, athletic",
        "prompt_directive": (
            "Style with energetic athletic photography: dramatic directional side lighting, realistic skin sheen "
            "and texture, crisp details, high micro-contrast, motivational fitness atmosphere. "
            "Avoid anatomical distortion, plastic skin, cartoon muscles, muddy shadows."
        ),
        "negative_constraints": "anatomical distortion, plastic skin, cartoon muscles, muddy shadows, flat light",
        "music": {
            "genres": ["Phonk", "Workout Trap", "Driving EDM"],
            "tempo": "Fast (125-140 BPM)",
            "keywords": ["gym motivation", "workout phonk", "athletic bass", "power run"]
        }
    },
    "GOURMET_FOODIE": {
        "id": "GOURMET_FOODIE",
        "name_en": "Gourmet Foodie",
        "name_ru": "Аппетитный гурман",
        "vibe": "45° angle, appetizing textures, culinary props",
        "prompt_directive": (
            "Enhance as artisanal gourmet food photography: soft directional window lighting, appetizing realistic food textures "
            "and glazes, shallow depth of field, warm balanced colors, clean culinary presentation. "
            "Avoid fake steam, plastic food look, oversaturation, messy composition."
        ),
        "negative_constraints": "fake steam, plastic food look, oversaturation, messy composition, dull grey food",
        "music": {
            "genres": ["Bossa Nova", "Parisian Cafe Jazz", "Upbeat Acoustic Grooves"],
            "tempo": "Medium (95-110 BPM)",
            "keywords": ["foodie jazz", "acoustic cafe", "bossa nova kitchen", "sweet morning"]
        }
    },
    "LUXURY_STUDIO": {
        "id": "LUXURY_STUDIO",
        "name_en": "Dark & Moody Luxury",
        "name_ru": "Темный люкс и премиум",
        "vibe": "Chiaroscuro, dark gradient, controlled reflections",
        "prompt_directive": (
            "Style as high-end luxury editorial: deep moody gradient backdrop, precision rim lighting, controlled highlights, "
            "rich deep blacks, elegant composition, immaculate product and material details. "
            "Avoid muddy darkness, blown highlights, artificial glare, fake labels."
        ),
        "negative_constraints": "muddy darkness, blown highlights, artificial glare, fake labels, washed out blacks",
        "music": {
            "genres": ["Deep House", "Cinematic Downtempo", "Elegant Strings / Cello"],
            "tempo": "Medium (115-122 BPM)",
            "keywords": ["luxury ambient", "dark editorial", "catwalk lounge", "night glamour"]
        }
    },
    "TECH_CREATOR": {
        "id": "TECH_CREATOR",
        "name_en": "Tech Creator Workspace",
        "name_ru": "Техно-креатор",
        "vibe": "Modern desk, subtle LED accents, sleek textures",
        "prompt_directive": (
            "Transform into modern tech creator workspace: balanced studio lighting with subtle ambient accents, "
            "clean minimalist desk setup, sharp gadget textures, organized depth of field, professional creator vibe. "
            "Avoid messy cable clutter, fake screen text, oversaturated neon."
        ),
        "negative_constraints": "messy cable clutter, fake screen text, oversaturated neon, distorted gadgets",
        "music": {
            "genres": ["Synthwave", "Chillwave", "Future Bass"],
            "tempo": "Medium (100-115 BPM)",
            "keywords": ["tech lo-fi", "creator beats", "desk setup vibes", "digital pulse"]
        }
    },
    "BOTANICAL_SPA": {
        "id": "BOTANICAL_SPA",
        "name_en": "Fresh Botanical Spa",
        "name_ru": "Свежий спа и органика",
        "vibe": "Bright daylight, organic stone/foliage, zen calm",
        "prompt_directive": (
            "Apply fresh botanical spa aesthetic: bright soft natural daylight, clean neutral stone and water textures, "
            "subtle green botanical accents, soothing balanced tones, serene wellness atmosphere. "
            "Avoid warped packaging, cartoon flora, unnatural skin smoothing."
        ),
        "negative_constraints": "warped packaging, cartoon flora, unnatural skin smoothing, harsh neon, clutter",
        "music": {
            "genres": ["Spa Meditation", "Gentle Piano", "Ambient Nature"],
            "tempo": "Slow (60-75 BPM)",
            "keywords": ["wellness zen", "calm acoustic", "spa morning", "mindful breathing"]
        }
    },
    "VINTAGE_FILM": {
        "id": "VINTAGE_FILM",
        "name_en": "Nostalgic Vintage Film",
        "name_ru": "Винтажная ностальгия",
        "vibe": "Warm analog tones, gentle film fade, cozy nostalgic",
        "prompt_directive": (
            "Render in nostalgic vintage film aesthetic: warm analog color toning, gentle film grain, soft faded shadows, "
            "cozy tactile textures, timeless nostalgic mood. "
            "Avoid oversaturated yellow wash, heavy digital noise, distorted faces."
        ),
        "negative_constraints": "oversaturated yellow wash, heavy digital noise, distorted faces, digital artifacts",
        "music": {
            "genres": ["70s Soft Rock", "Vintage Motown / Soul", "Dream Pop"],
            "tempo": "Medium (85-105 BPM)",
            "keywords": ["vintage dreams", "retro vinyl", "analog memory", "nostalgia pop"]
        }
    }
}


def get_style(style_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves style details by ID (case-insensitive)."""
    return AI_STYLES_CATALOG.get(style_id.upper())


def select_style_variants(
    media_items: Optional[List[Dict[str, Any]]] = None,
    instructions: str = "",
    count: int = 3
) -> List[Dict[str, Any]]:
    """
    Intelligently analyzes content instructions and media context to select
    `count` distinct styles from the 10 catalog entries.
    Falls back to a balanced creator trio if no explicit match is detected.
    """
    text = (instructions or "").lower()

    # Domain keyword mapping
    keyword_map = [
        (["спорт", "зал", "тренировк", "фитнес", "бег", "мышц", "gym", "fitness", "workout", "athletic"], "ATHLETIC_DRIVE"),
        (["кофе", "кафе", "уют", "завтрак", "книга", "плед", "утро", "coffee", "cafe", "cozy", "breakfast"], "WARM_CAFE"),
        (["еда", "блюдо", "ресторан", "кухн", "вкусно", "десерт", "food", "gourmet", "restaurant", "chef", "cook"], "GOURMET_FOODIE"),
        (["закат", "море", "горы", "путешеств", "поход", "пляж", "природ", "travel", "sunset", "mountain", "beach", "roadtrip"], "GOLDEN_HOUR"),
        (["город", "улиц", "стиль", "лук", "образ", "одежд", "street", "fashion", "ootd", "city"], "STREET_35MM"),
        (["спа", "уход", "крем", "косметик", "йога", "релакс", "spa", "wellness", "skincare", "yoga", "organic"], "BOTANICAL_SPA"),
        (["люкс", "вечер", "премиум", "роскош", "черный", "парфюм", "luxury", "glamour", "dark", "perfume", "gold"], "LUXURY_STUDIO"),
        (["код", "ноут", "компьютер", "гаджет", "подкаст", "техно", "tech", "creator", "workspace", "desk", "setup"], "TECH_CREATOR"),
        (["память", "ретро", "детств", "пленк", "винтаж", "старин", "vintage", "retro", "memory", "nostalgic"], "VINTAGE_FILM"),
        (["продукт", "минимал", "бизнес", "коммерц", "студи", "minimal", "commercial", "clean", "profile"], "CLEAN_COMMERCIAL"),
    ]

    selected_ids: List[str] = []

    for keywords, style_id in keyword_map:
        if any(kw in text for kw in keywords):
            if style_id not in selected_ids:
                selected_ids.append(style_id)
        if len(selected_ids) >= count:
            break

    # Balanced diverse fallbacks if fewer than `count` were matched
    default_rotation = [
        "GOLDEN_HOUR",
        "CLEAN_COMMERCIAL",
        "WARM_CAFE",
        "STREET_35MM",
        "VINTAGE_FILM",
        "BOTANICAL_SPA",
        "LUXURY_STUDIO",
        "ATHLETIC_DRIVE",
        "GOURMET_FOODIE",
        "TECH_CREATOR"
    ]

    for fallback in default_rotation:
        if len(selected_ids) >= count:
            break
        if fallback not in selected_ids:
            selected_ids.append(fallback)

    return [AI_STYLES_CATALOG[sid] for sid in selected_ids[:count]]


def recommend_music_for_content(style_id: str) -> Dict[str, Any]:
    """
    Returns Instagram Music Library recommendations (genres, tempo, search keywords)
    for a chosen style or video content.
    """
    style = get_style(style_id) or AI_STYLES_CATALOG["GOLDEN_HOUR"]
    return style["music"]


def format_music_recommendation_text(style_id: str, lang: str = "ru") -> str:
    """
    Formats an Instagram Music Library guide caption for user messages.
    """
    music = recommend_music_for_content(style_id)
    style = get_style(style_id)
    style_name = style["name_ru"] if lang.startswith("ru") else style["name_en"]

    if lang.startswith("ru"):
        keywords_str = ", ".join([f"`{kw}`" for kw in music["keywords"]])
        genres_str = ", ".join(music["genres"])
        return (
            f"🎵 *Музыка для Instagram Reels / видео:*\n"
            f"• Стиль: *{style_name}*\n"
            f"• Жанры: _{genres_str}_\n"
            f"• Темп: {music['tempo']}\n"
            f"• 🔍 *Поиск в музыке Instagram:* {keywords_str}\n"
        )
    else:
        keywords_str = ", ".join([f"`{kw}`" for kw in music["keywords"]])
        genres_str = ", ".join(music["genres"])
        return (
            f"🎵 *Instagram Reels / Video Music:*\\n"
            f"• Style: *{style_name}*\n"
            f"• Genres: _{genres_str}_\n"
            f"• Tempo: {music['tempo']}\n"
            f"• 🔍 *Search in Instagram Music:* {keywords_str}\n"
        )
