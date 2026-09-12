import logging
import httpx
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
        "resend": {
            "configured": bool(settings.RESEND_API_KEY),
            "detail": {
                "from_email": settings.RESEND_FROM_EMAIL,
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


async def _test_resend() -> dict:
    if not settings.RESEND_API_KEY:
        return {"success": False, "message": "RESEND_API_KEY is not configured."}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                timeout=10.0,
            )
        if response.status_code == 200:
            return {"success": True, "message": "Resend API key is valid."}
        return {
            "success": False,
            "message": f"Resend responded with status {response.status_code}.",
        }
    except Exception as e:
        logger.warning("Resend connectivity test failed: %s", e)
        return {"success": False, "message": "Could not reach Resend."}


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
    if provider == "resend":
        return await _test_resend()
    if provider == "dograh":
        return await _test_dograh()
    raise HTTPException(status_code=404, detail=f"Unknown integration provider: {provider}")
