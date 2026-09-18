from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./waste2worth.db"
    upload_dir: str = "./uploads"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    # e.g. https://waste2worth.*\.vercel\.app to allow Vercel preview deployments
    cors_origin_regex: str | None = None

    # Photo storage: "local" (dev) or "supabase" (production; Railway's disk is wiped on every deploy)
    storage_backend: str = "local"
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_bucket: str = "listing-photos"

    # Vision: "groq" (free tier, fast), "gemini", "ollama" (local, offline), or "mock" (no AI, for dev/tests)
    vision_provider: str = "mock"
    groq_api_key: str | None = None
    groq_vision_model: str = "qwen/qwen3.8-27b"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    vision_timeout_s: float = 90.0

    # ElevenLabs
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_stt_model: str = "scribe_v1"
    elevenlabs_agent_id: str | None = None           # Conversational AI agent that calls NGOs
    elevenlabs_phone_number_id: str | None = None    # Twilio number imported into ElevenLabs

    # Vakh (MCP, OAuth). Run `python -m scripts.vakh_login` once to fill vakh_token_file.
    vakh_mcp_url: str = "https://xo.vakh.com/mcp"
    vakh_token_file: str = "./.vakh_tokens.json"
    vakh_tokens_json: str | None = None   # paste the token file's contents here on Railway
    vakh_post_tool: str | None = None   # tool name, discovered via GET /api/integrations/vakh/tools
    vakh_food_form_id: str | None = None

    # Image quality gates
    min_image_short_side: int = 720
    blur_threshold: float = 35.0
    max_upload_mb: int = 12

    # Business rules
    pool_max_radius_km: float = 15.0
    pool_max_delta_e: float = 6.0          # colour difference allowed between pooled items
    pool_reservation_minutes: int = 30
    ngo_dispatch_count: int = 3


settings = Settings()
