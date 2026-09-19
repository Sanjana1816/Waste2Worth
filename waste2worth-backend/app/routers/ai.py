import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.schemas import SpeakRequest
from app.services import vision, voice

router = APIRouter(prefix="/api/ai", tags=["AI & voice"])


@router.post("/analyze")
async def analyze(files: list[UploadFile] = File(...), hint_category: str | None = Form(None),
                  manufacturer_color: str | None = Form(None), notes: str | None = Form(None)):
    """Identify the item from 1-4 photos and prefill the listing form. The seller still confirms everything."""
    if not 1 <= len(files) <= 4:
        raise HTTPException(422, "send 1 to 4 photos")
    blobs = [await f.read() for f in files]
    result = await vision.analyze(blobs, hint_category, manufacturer_color, notes, [f.filename or "" for f in files])
    return {
        "analysis": result,
        "form_prefill": {"category": result.category, "condition": result.condition,
                         "attributes": result.suggested_attributes},
        "color_warning": (
            f"The colour in the photo looks different from \"{manufacturer_color}\". Check the lighting, or the "
            "manufacturer colour you entered." if result.color_matches_manufacturer == "no" else None),
    }


@router.post("/speak")
async def speak(body: SpeakRequest):
    """Read text aloud (e.g. reuse-idea steps) with ElevenLabs. Returns audio/mpeg."""
    try:
        audio = await voice.speak(body.text, body.voice_id)
    except voice.NotConfigured as e:
        raise HTTPException(503, str(e))
    except httpx.HTTPError as e:
        raise HTTPException(502, f"text-to-speech failed: {e}")
    return Response(content=audio, media_type="audio/mpeg")
