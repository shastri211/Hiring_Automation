"""Dograh browser/web-interview integration client.

Dograh has no hosted "join URL" API for browser calls — its browser-call
capability is an embeddable JS widget that must run on a page we host,
authenticating via a workflow-scoped embed token (safe to expose to the
browser). This client therefore has a narrow job:

- Tell the rest of the backend whether enough config exists to produce a
  *working* candidate link + widget (``is_configured``).
- Fetch a completed run's data for the manual resync safety-net endpoint
  (``get_run``), confirmed against the local Dograh source
  (``api/routes/workflow.py::get_workflow_run``, X-API-Key auth via
  ``api/services/auth/depends.py::get_user``).
- Provide a best-effort connectivity check for the Integrations page
  (``test_connection``), using the confirmed read-only "list runs" endpoint
  with ``limit=1`` since Dograh exposes no dedicated ping/health endpoint.

No outbound Dograh call ever happens at interview-trigger time — the widget
itself lazily creates the Dograh workflow run when the candidate opens our
page (see app/services/interview.py::InterviewIntegrationAdapter.trigger_interview).
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class DograhClient:
    """Thin async HTTP client for the confirmed Dograh API surface we use."""

    @property
    def is_configured(self) -> bool:
        """Whether enough config exists to produce a working candidate link + widget.

        Deliberately checks only the three fields actually needed for that
        (base URL to build the widget script src, embed token for the widget
        itself, and our own public base URL to build the candidate-facing
        link) — not DOGRAH_API_KEY/DOGRAH_WORKFLOW_ID, which are only used by
        the polling-only get_run/test_connection paths below.
        """
        return bool(
            settings.DOGRAH_BASE_URL
            and settings.DOGRAH_EMBED_TOKEN
            and settings.PUBLIC_APP_BASE_URL
        )

    async def get_run(self, workflow_id: str, run_id: str) -> dict:
        """Fetch a workflow run's post-call data.

        Confirmed contract: GET {base_url}/api/v1/workflow/{workflow_id}/runs/{run_id}
        with an X-API-Key header, returning Dograh's WorkflowRunResponseSchema
        (is_completed, transcript_url, recording_url, user_recording_url,
        bot_recording_url, cost_info, initial_context, gathered_context,
        call_type, annotations).
        """
        if not settings.DOGRAH_BASE_URL or not settings.DOGRAH_API_KEY:
            raise ValueError(
                "DOGRAH_BASE_URL and DOGRAH_API_KEY must both be configured to fetch a Dograh run."
            )

        url = f"{settings.DOGRAH_BASE_URL.rstrip('/')}/api/v1/workflow/{workflow_id}/runs/{run_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"X-API-Key": settings.DOGRAH_API_KEY},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    async def test_connection(self) -> dict:
        """Best-effort authenticated connectivity check for the Integrations page.

        Dograh exposes no dedicated "ping" endpoint. The local source confirms
        GET {base_url}/api/v1/workflow/{workflow_id}/runs (list, paginated) is
        X-API-Key-authenticated and safe/read-only, so we use it with
        limit=1 against the configured workflow as the minimal authenticated
        read. Returns {"success": bool, "message": str} — the exact shape
        app/api/integrations_status.py::_test_dograh expects.
        """
        if not settings.DOGRAH_BASE_URL or not settings.DOGRAH_API_KEY:
            return {
                "success": False,
                "message": "DOGRAH_BASE_URL/DOGRAH_API_KEY is not configured.",
            }
        if not settings.DOGRAH_WORKFLOW_ID:
            return {
                "success": False,
                "message": "DOGRAH_WORKFLOW_ID is not configured; cannot verify without a workflow to query.",
            }

        url = f"{settings.DOGRAH_BASE_URL.rstrip('/')}/api/v1/workflow/{settings.DOGRAH_WORKFLOW_ID}/runs"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"X-API-Key": settings.DOGRAH_API_KEY},
                    params={"page": 1, "limit": 1},
                    timeout=10.0,
                )
            if response.status_code == 200:
                return {"success": True, "message": "Dograh API key is valid."}
            if response.status_code in (401, 403):
                return {"success": False, "message": "Dograh rejected the configured API key."}
            return {
                "success": False,
                "message": f"Dograh responded with status {response.status_code}.",
            }
        except Exception as e:
            logger.warning("Dograh connectivity test failed: %s", e)
            return {"success": False, "message": "Could not reach Dograh."}


dograh_client = DograhClient()
