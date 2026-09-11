from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import (
    ProfessionalContext, authorize_public_conversation, current_professional, professional_space,
)
from ..live_voice import issue_ticket, request_origin, run_voice
from ..rate_limit import client_ip
from .studio import _studio_conversation, _studio_turn_lock
from .public import _public_turn_lock

router = APIRouter(tags=["voice"])
logger = logging.getLogger(__name__)


@router.get("/voice/capabilities")
def capabilities(request: Request):
    settings = request.app.state.settings
    return {"enabled": bool(settings.live_voice_enabled and settings.openai_api_key)}


@router.post("/studio/voice/sessions")
async def studio_session(request: Request, db: Session = Depends(get_db),
                   context: ProfessionalContext = Depends(current_professional)):
    space = professional_space(db, context)
    conversation = _studio_conversation(db, context.account_id, space.id)
    return issue_ticket(request, db, conversation, context.member.id)


@router.post("/public/conversations/{conversation_id}/voice/sessions")
async def public_session(conversation_id: str, request: Request, db: Session = Depends(get_db)):
    conversation = authorize_public_conversation(request, db, conversation_id)
    if not conversation.automatic_ai_enabled:
        raise HTTPException(409, "Il professionista gestisce la conversazione: la voce AI è in pausa.")
    return issue_ticket(request, db, conversation)


@router.websocket("/voice/connect")
async def connect_voice(websocket: WebSocket):
    ticket = None
    accepted = False
    try:
        origin = request_origin(websocket)
        websocket.app.state.rate_limiter.check(
            f"voice-connect:{client_ip(websocket)}", limit=12, window_seconds=60,
        )
        await websocket.accept()
        accepted = True
        raw = await asyncio.wait_for(websocket.receive_text(), 5)
        if len(raw) > 100:
            raise HTTPException(403, "Sessione vocale non valida")
        ticket = websocket.app.state.voice_registry.claim(raw, origin)
        lock = (_studio_turn_lock if ticket.kind == "studio" else _public_turn_lock)(
            ticket.account_id, ticket.conversation_id,
        )
        if lock.locked():
            raise HTTPException(409, "Attendi la risposta al messaggio prima di avviare la voce.")
        async with lock:
            await run_voice(websocket, ticket)
        await websocket.send_json({"type": "stopped"})
    except (WebSocketDisconnect, RuntimeError) as exc:
        # No provider payloads, credentials, or transcript text in application logs.
        logger.info("Voice connection ended: %s", type(exc).__name__)
        if accepted:
            try:
                await websocket.send_json({"type": "error", "message": "La connessione vocale si è interrotta. Puoi riprovare o scrivere."})
            except (RuntimeError, WebSocketDisconnect):
                pass
    except Exception as exc:
        logger.info("Voice connection failed: %s", type(exc).__name__)
        if accepted:
            try:
                await websocket.send_json({"type": "error", "message": exc.detail if isinstance(exc, HTTPException) else "Voce non disponibile. Puoi riprovare o scrivere."})
            except (RuntimeError, WebSocketDisconnect):
                pass
    finally:
        if ticket:
            websocket.app.state.voice_registry.active.discard((ticket.account_id, ticket.conversation_id))
        try:
            await websocket.close(code=1000 if accepted else 1008)
        except (RuntimeError, WebSocketDisconnect):
            pass
