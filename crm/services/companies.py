"""Business logic for companies and their contacts."""

import logging
import uuid

from sqlalchemy import Select, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import enums as e
from .. import models as m
from .. import schemas as s
from ..utils import paginate
from . import deletion
from .errors import ConflictError, NotFoundError

logger = logging.getLogger(__name__)


def list_companies(
    session: Session,
    *,
    search: str | None = None,
    role: e.Role | None = None,
    company_type: e.CompanyType | None = None,
    customer_status: e.CustomerStatus | None = None,
    city: str | None = None,
    page: int = 1,
    page_size: int = 25,
):
    """Return (companies, total) matching the filters, ordered by name."""
    query = select(m.Company).order_by(func.lower(m.Company.name), m.Company.id)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(or_(
            m.Company.name.ilike(like), m.Company.city.ilike(like),
            m.Company.tax_id.ilike(like), m.Company.phone.ilike(like),
        ))
    if role:
        query = query.where(cast(m.Company.roles, JSONB).contains([role.value]))
    if company_type:
        query = query.where(cast(m.Company.type, JSONB).contains([company_type.value]))
    if customer_status:
        query = query.where(m.Company.customer_status == customer_status)
    if city:
        query = query.where(m.Company.city.ilike(city.strip()))
    return paginate(session, query, page, page_size)


def get_company(session: Session, company_id: uuid.UUID) -> m.Company:
    """Return a company with its contacts or raise NotFoundError."""
    company = session.scalar(
        select(m.Company).where(m.Company.id == company_id).options(selectinload(m.Company.contacts))
    )
    if company is None:
        raise NotFoundError("Empresa no encontrada")
    return company


def _save(session: Session, what: str) -> None:
    """Commit, turning a uniqueness violation into ConflictError."""
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(f"{what} duplicado") from exc


def create_company(session: Session, data: s.CompanyIn) -> m.Company:
    """Create a company."""
    company = m.Company(**data.model_dump(mode="json"))
    session.add(company)
    _save(session, "CIF/NIF")
    logger.info("Company created: %s (%s)", company.name, company.id)
    return get_company(session, company.id)


def update_company(session: Session, company_id: uuid.UUID, data: s.CompanyUpdate) -> m.Company:
    """Apply the fields sent in `data` to a company."""
    company = get_company(session, company_id)
    for key, value in data.model_dump(mode="json", exclude_unset=True).items():
        setattr(company, key, value)
    _save(session, "CIF/NIF")
    return get_company(session, company_id)


def set_customer_status(
    session: Session, company_id: uuid.UUID, status: e.CustomerStatus | None
) -> m.Company:
    """Move a company along the customer pipeline."""
    company = get_company(session, company_id)
    company.customer_status = status
    session.commit()
    return company


# --------------------------------------------------------------------- Contacts


def list_contacts(
    session: Session,
    *,
    company_id: uuid.UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
):
    """Return (contacts, total), optionally of one company, ordered by name."""
    query = select(m.Contact).order_by(func.lower(m.Contact.first_name), m.Contact.id)
    if company_id:
        query = query.where(m.Contact.company_id == company_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(or_(
            m.Contact.first_name.ilike(like), m.Contact.last_name.ilike(like),
            m.Contact.phone.ilike(like), m.Contact.email.ilike(like),
        ))
    return paginate(session, query, page, page_size)


def get_contact(session: Session, contact_id: uuid.UUID) -> m.Contact:
    """Return a contact or raise NotFoundError."""
    contact = session.get(m.Contact, contact_id)
    if contact is None:
        raise NotFoundError("Contacto no encontrado")
    return contact


def _unset_other_primaries(session: Session, company_id: uuid.UUID, keep: uuid.UUID | None) -> None:
    """Make sure a company has a single primary contact."""
    for other in session.scalars(
        select(m.Contact).where(m.Contact.company_id == company_id, m.Contact.is_primary)
    ).unique():
        if other.id != keep:
            other.is_primary = False


def create_contact(session: Session, data: s.ContactIn) -> m.Contact:
    """Create a contact in an existing company."""
    get_company(session, data.company_id)
    contact = m.Contact(**data.model_dump())
    session.add(contact)
    session.flush()
    if contact.is_primary:
        _unset_other_primaries(session, contact.company_id, keep=contact.id)
    session.commit()
    return get_contact(session, contact.id)


def update_contact(session: Session, contact_id: uuid.UUID, data: s.ContactUpdate) -> m.Contact:
    """Apply the fields sent in `data` to a contact."""
    contact = get_contact(session, contact_id)
    changes = data.model_dump(exclude_unset=True)
    if "company_id" in changes:
        get_company(session, changes["company_id"])
    for key, value in changes.items():
        setattr(contact, key, value)
    session.flush()
    if contact.is_primary:
        _unset_other_primaries(session, contact.company_id, keep=contact.id)
    session.commit()
    session.refresh(contact)
    return contact


def delete_contact(session: Session, contact_id: uuid.UUID) -> None:
    """Soft-delete a contact; the interactions and orders that mention it are kept without contact."""
    deletion.delete_record(session, m.Contact, contact_id)
