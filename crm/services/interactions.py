"""Business logic for interactions (calls, visits, WhatsApp, voice notes...)."""

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import enums as e
from .. import models as m
from .. import schemas as s
from ..utils import paginate
from .companies import get_company, get_contact
from .errors import InvalidReferenceError, NotFoundError


def list_interactions(
    session: Session,
    *,
    company_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    type: e.InteractionType | None = None,
    processing_status: e.ProcessingStatus | None = None,
    source: e.InteractionSource | None = None,
    unassigned: bool = False,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
):
    """Return (interactions, total) matching the filters, newest first."""
    query = select(m.Interaction).order_by(m.Interaction.occurred_at.desc(), m.Interaction.id)
    if company_id:
        query = query.where(m.Interaction.company_id == company_id)
    if contact_id:
        query = query.where(m.Interaction.contact_id == contact_id)
    if type:
        query = query.where(m.Interaction.type == type)
    if processing_status:
        query = query.where(m.Interaction.processing_status == processing_status)
    if source:
        query = query.where(m.Interaction.source == source)
    if unassigned:
        query = query.where(m.Interaction.company_id.is_(None))
    if search:
        like = f"%{search.strip()}%"
        query = query.where(or_(
            m.Interaction.summary.ilike(like), m.Interaction.notes.ilike(like),
            m.Interaction.transcript.ilike(like),
        ))
    return paginate(session, query, page, page_size)


def get_interaction(session: Session, interaction_id: uuid.UUID) -> m.Interaction:
    """Return an interaction or raise NotFoundError."""
    interaction = session.get(m.Interaction, interaction_id)
    if interaction is None:
        raise NotFoundError("Interacción no encontrada")
    return interaction


def _check_links(
    session: Session, company_id: uuid.UUID | None, contact_id: uuid.UUID | None
) -> uuid.UUID | None:
    """Validate the company/contact pair and return the company id to store.

    A contact without company implies the company of that contact; a contact of another
    company is rejected.
    """
    if company_id:
        get_company(session, company_id)
    if contact_id:
        contact = get_contact(session, contact_id)
        if company_id and contact.company_id != company_id:
            raise InvalidReferenceError("El contacto no pertenece a la empresa indicada")
        company_id = company_id or contact.company_id
    return company_id


def create_interaction(session: Session, data: s.InteractionIn, created_by: str | None) -> m.Interaction:
    """Register an interaction typed by hand (source: manual)."""
    company_id = _check_links(session, data.company_id, data.contact_id)
    interaction = m.Interaction(
        company_id=company_id,
        contact_id=data.contact_id,
        occurred_at=data.occurred_at or datetime.now().replace(microsecond=0),
        type=data.type,
        direction=data.direction,
        summary=data.summary,
        notes=data.notes,
        source=e.InteractionSource.MANUAL,
        processing_status=e.ProcessingStatus.PROCESSED,  # already structured: no agent needed
        created_by=created_by,
    )
    session.add(interaction)
    session.commit()
    return interaction


def create_voice_note(
    session: Session,
    *,
    transcript: str,
    created_by: str | None,
    company_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    type: e.InteractionType = e.InteractionType.OTHER,
    occurred_at: datetime | None = None,
) -> m.Interaction:
    """Save a transcribed voice note as a pending interaction (the signal for the agents)."""
    company_id = _check_links(session, company_id, contact_id)
    interaction = m.Interaction(
        company_id=company_id,
        contact_id=contact_id,
        occurred_at=occurred_at or datetime.now().replace(microsecond=0),
        type=type,
        source=e.InteractionSource.VOICE_NOTE,
        transcript=transcript,
        processing_status=e.ProcessingStatus.PENDING,
        created_by=created_by,
    )
    session.add(interaction)
    session.commit()
    return interaction


def update_interaction(
    session: Session, interaction_id: uuid.UUID, data: s.InteractionUpdate
) -> m.Interaction:
    """Apply the fields sent in `data` to an interaction."""
    interaction = get_interaction(session, interaction_id)
    changes = data.model_dump(exclude_unset=True)
    company_id = changes.get("company_id", interaction.company_id)
    contact_id = changes.get("contact_id", interaction.contact_id)
    if "contact_id" in changes and changes["contact_id"] is None:
        contact_id = None
    changes["company_id"] = _check_links(session, company_id, contact_id)
    for key, value in changes.items():
        setattr(interaction, key, value)
    session.commit()
    session.refresh(interaction)
    return interaction


def count_pending(session: Session) -> int:
    """Return how many interactions wait for an agent."""
    return session.scalar(
        select(func.count()).select_from(m.Interaction).where(
            m.Interaction.processing_status == e.ProcessingStatus.PENDING
        )
    ) or 0
