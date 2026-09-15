import asyncio
import logging
import smtplib
from fastapi import APIRouter, HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def get_integrations_status():
    dograh_base_url = getattr(settings, "DOGRAH_BASE_URL", None)
    dograh_embed_token = getattr(settings, "DOGRAH_EMBED_TOKEN", None)
    dograh_webhook_secret = getattr(settings, "DOGRAH_WEBHOOK_SECRET", None)
    public_app_base_url = getattr(settings, "PUBLIC_APP_BASE_URL", None)

    return {
        "smtp": {
            "configured": bool(settings.SMTP_HOST),
            "detail": {
                "from_email": settings.SMTP_FROM_EMAIL,
                "host": settings.SMTP_HOST,
            },
        },
        "dograh": {
            "configured": bool(dograh_base_url and dograh_embed_token),
            "detail": {
                "base_url": dograh_base_url,
                "embed_token_set": bool(dograh_embed_token),
                "webhook_secret_set": bool(dograh_webhook_secret),
                "public_app_url": public_app_base_url,
            },
        },
    }


async def _test_smtp() -> dict:
    if not settings.SMTP_HOST:
        return {
            "success": False,
            "message": "SMTP_HOST is not configured - emails are currently simulated (logged, not sent).",
        }

    def _connect() -> None:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as client:
            client.ehlo()
            if settings.SMTP_USE_TLS:
                client.starttls()
                client.ehlo()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

    try:
        await asyncio.to_thread(_connect)
        return {"success": True, "message": "SMTP connection succeeded."}
    except Exception as e:
        logger.warning("SMTP connectivity test failed: %s", e)
        return {"success": False, "message": f"Could not connect to SMTP server: {e}"}


async def _test_dograh() -> dict:
    try:
        from app.services.dograh import dograh_client  # noqa: PLC0415 - may not exist yet (A10)
    except ImportError:
        return {
            "success": False,
            "message": "Dograh integration not yet configured on this backend.",
        }

    test_fn = getattr(dograh_client, "test_connection", None)
    if test_fn is None:
        return {
            "success": False,
            "message": "Dograh integration not yet configured on this backend.",
        }

    try:
        result = await test_fn()
        if isinstance(result, dict):
            return result
        return {"success": bool(result), "message": "Dograh connectivity check completed."}
    except Exception as e:
        logger.warning("Dograh connectivity test failed: %s", e)
        return {"success": False, "message": "Could not verify Dograh connectivity."}


@router.post("/{provider}/test")
async def test_integration(provider: str):
    provider = provider.lower()
    if provider == "smtp":
        return await _test_smtp()
    if provider == "dograh":
        return await _test_dograh()
    raise HTTPException(status_code=404, detail=f"Unknown integration provider: {provider}")
