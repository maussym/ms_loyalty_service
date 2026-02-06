from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

from .config import Settings
from .moysklad import MoySkladClient
from .processor import process_document

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

settings = Settings.from_env()
logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")

client = MoySkladClient(settings)
app = FastAPI(title="MoySklad Loyalty Discounts")


def _extract_doc_ref(event: dict[str, Any]) -> tuple[str | None, str | None]:
    meta = event.get("meta") or {}
    href = meta.get("href")
    if href and "/entity/" in href:
        tail = href.split("/entity/", 1)[1]
        parts = tail.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    doc_type = meta.get("type") or event.get("entityType")
    doc_id = meta.get("id") or event.get("id")
    return doc_type, doc_id


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "moysklad_loyalty_service",
        "status": "ok",
        "health": "/health",
        "webhook": "/webhook",
    }


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    if settings.webhook_bearer_token:
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {settings.webhook_bearer_token}"
        if auth != expected:
            raise HTTPException(status_code=401, detail="Unauthorized")

    payload = await request.json()
    events = payload.get("events") if isinstance(payload, dict) else None
    if not events:
        events = [payload]

    results = []
    for event in events:
        if not isinstance(event, dict):
            continue
        doc_type, doc_id = _extract_doc_ref(event)
        if not doc_type or not doc_id:
            logging.warning("Skipping event without document reference: %s", event)
            continue
        if doc_type not in settings.document_types:
            logging.info("Skipping document type %s", doc_type)
            continue
        try:
            result = process_document(client, settings, doc_type, doc_id)
            results.append({
                "doc_type": doc_type,
                "doc_id": doc_id,
                "updated": result.updated,
                "reason": result.reason,
                "positions": result.updated_positions,
                "loyalty_discount_sum": result.loyalty_discount_sum,
            })
        except Exception as exc:
            logging.exception("Failed to process %s %s", doc_type, doc_id)
            results.append({
                "doc_type": doc_type,
                "doc_id": doc_id,
                "updated": False,
                "reason": "error",
                "error": str(exc),
            })

    return {"results": results}
