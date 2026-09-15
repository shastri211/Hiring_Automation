from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Resume Screener"
    
    # Database
    POSTGRES_USER: str = "screener"
    POSTGRES_PASSWORD: str = "screener_password"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "resume_screener"
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        import urllib.parse
        encoded_password = urllib.parse.quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        
    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    
    # Embedding Configuration
    # (These represent the active default profile, fallback is managed via EmbeddingRouter)
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    EMBEDDING_DIMENSION: int = 768
    SENTENCE_TRANSFORMERS_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    QDRANT_COLLECTION: str = "resume_candidates_768"
    QDRANT_COLLECTION_V2: str = "resume_candidates_v2_768"
    QDRANT_COLLECTION_LOCAL_V2: str = "resume_candidates_local_v2_384"
    
    # LLM Providers (API Keys)
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    NVIDIA_API_KEY: str | None = None
    
    # LLM Providers (Models - comma separated)
    GROQ_MODELS: str = "qwen/qwen3.8-27b"
    GEMINI_MODELS: str = "gemini-3.6-flash"
    OPENROUTER_MODELS: str = "google/gemma-4-31b-it:free"
    NVIDIA_MODELS: str = "nvidia/llama-3.1-nemotron-70b-instruct"

    # Gemini OCR / document-extraction model.
    # This is the model used by GeminiOCREngine (image → text), which requires a
    # multimodal-capable Gemini model.  It is intentionally separate from the LLM
    # screening pool (GEMINI_MODELS) so the two roles can be configured independently.
    # Defaults to the first model listed in GEMINI_MODELS.
    GEMINI_OCR_MODEL: str = ""

    # Email Settings (SMTP)
    # Standard SMTP works with any mail server - a free Gmail/Outlook account,
    # a self-hosted relay, a local dev catcher like Mailpit, etc. - so nothing
    # needs to be purchased or signed up for. Zero-config by default: with
    # SMTP_HOST unset, EmailProviderAdapter simulates sends (logs only, no
    # network call) instead of failing, so outreach works out of the box.
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "noreply@hiring.automation.com"

    # Dograh voice-interview integration (browser/web widget, not phone — see
    # app/services/dograh.py and app/api/public_interview.py for the full
    # architecture note). DOGRAH_BASE_URL/DOGRAH_EMBED_TOKEN/PUBLIC_APP_BASE_URL
    # are the three fields actually needed to produce a working candidate link
    # + widget (checked by DograhClient.is_configured); the rest support the
    # manual resync endpoint and the outbound webhook receiver.
    DOGRAH_BASE_URL: str | None = None
    # Base URL that actually serves the embeddable widget <script> file
    # (/embed/dograh-widget.js). In a production deployment behind Dograh's
    # nginx, this is the same origin as DOGRAH_BASE_URL - but a local
    # self-hosted Dograh (docker compose without --profile remote, i.e. no
    # nginx) serves that static file from the Next.js UI app's own origin
    # (default http://localhost:3010), not from the API (DOGRAH_BASE_URL,
    # default http://localhost:8000). Falls back to DOGRAH_BASE_URL when
    # unset so single-origin deployments need no extra config.
    DOGRAH_WIDGET_BASE_URL: str | None = None
    DOGRAH_EMBED_TOKEN: str | None = None
    DOGRAH_WEBHOOK_SECRET: str | None = None
    DOGRAH_API_KEY: str | None = None
    DOGRAH_WORKFLOW_ID: str | None = None
    # "production" or "development" per whatever the target Dograh instance
    # expects for its embed widget script (?environment= query param). Most
    # deployments can leave this at the default.
    DOGRAH_ENVIRONMENT: str = "production"
    # none | api_key | bearer_token | basic_auth | custom_header — matches
    # Dograh's real webhook credential enum.
    DOGRAH_WEBHOOK_AUTH_TYPE: str = "none"
    DOGRAH_WEBHOOK_HEADER_NAME: str = "X-API-Key"
    # Our deployed frontend's public origin (e.g. https://app.example.com, or
    # a dev ngrok URL) — used to build the candidate-facing interview link and
    # must be registered in Dograh's Allowed Domains for the embed token to work.
    PUBLIC_APP_BASE_URL: str | None = None
    DOGRAH_INTERVIEW_LINK_TTL_HOURS: int = 168


    @property
    def gemini_ocr_model(self) -> str:
        """Effective Gemini model for document OCR/image extraction.

        Uses GEMINI_OCR_MODEL from the environment when explicitly set.
        Falls back to the first model in GEMINI_MODELS so that the default
        runtime value remains unchanged after the Phase 10 pool migration.
        """
        explicit = self.GEMINI_OCR_MODEL.strip()
        if explicit:
            return explicit
        # Fall back to the first model in the GEMINI LLM pool.
        # The pool is comma-separated; the first entry is the highest-priority model.
        first = next(
            (m.strip() for m in self.GEMINI_MODELS.split(",") if m.strip()),
            None,
        )
        if first:
            return first
        raise ValueError(
            "No Gemini OCR model configured. Set GEMINI_OCR_MODEL or GEMINI_MODELS in your environment."
        )
    
    # LLM Routing Priority
    # Example: "groq,gemini,openrouter,nvidia"
    LLM_PROVIDER_PRIORITY: str = "groq,gemini,openrouter,nvidia"
    
    # Resilience Settings
    LLM_COOLDOWN_SECONDS: int = 60
    LLM_TIMEOUT_SECONDS: int = 30
    # Caps the output tokens requested from Groq so a single call can't exceed
    # low-tier OTPM (output-tokens-per-minute) limits on models like the qwen3 preview tier.
    GROQ_MAX_OUTPUT_TOKENS: int = 1000
    
    # Storage & Screening Config
    STORAGE_LOCAL_DIR: str = "uploads"
    RETRIEVAL_TOP_K: int = 50

    # Resume upload limits (defense against disk-fill DoS / accidental huge batches).
    MAX_RESUME_FILE_SIZE_MB: int = 15
    MAX_RESUMES_PER_UPLOAD: int = 200
    
    # Adaptive Semantic Gate
    MIN_CANDIDATES_TO_SCREEN: int = 5
    MAX_CANDIDATES_TO_SCREEN: int = 20
    SEMANTIC_GAP_THRESHOLD: float = 0.05

    # Local (deterministic) resume profiler: confidence score (0-95) below which
    # extraction is considered insufficient and an LLM enrichment fallback is used.
    LOCAL_PROFILE_CONFIDENCE_THRESHOLD: int = 45

    # CORS: comma-separated list of allowed origins for the frontend.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    WORKER_ID: str = "resume-worker-1"
    WORKER_MAX_RETRIES: int = 3
    WORKER_RETRY_BACKOFF_SECONDS: int = 60
    WORKER_CONSUMER_GROUP: str = "resume-screeners"
    WORKER_CONCURRENCY: int = 5

    # -------------------------
    # Authentication (HR user sessions)
    # -------------------------
    # Signing key for JWT session tokens (app/services/auth.py). The default
    # below is fine for local dev only.
    # *** MUST be overridden via .env with a long random value in any real
    # *** deployment - anyone who knows this value can forge login sessions.
    SECRET_KEY: str = "dev-only-insecure-secret-key-change-me"
    # How long an issued session cookie/token stays valid, in minutes.
    # Default: 1440 (24 hours).
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    # Whether the session cookie is marked Secure (HTTPS-only). Must be False
    # for plain-HTTP local dev; flip to True in .env once the app is served
    # over HTTPS, or browsers will silently refuse to store the cookie.
    COOKIE_SECURE: bool = False

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

settings = Settings()
