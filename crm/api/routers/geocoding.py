"""Endpoint that extracts city, province and country from an address."""

from fastapi import APIRouter, Query

from ... import schemas as s
from ...services import geocoding as svc

router = APIRouter(prefix="/geocoding", tags=["geocoding"])


@router.get("/address", response_model=s.AddressParts)
def parse_address(q: str = Query(min_length=1, max_length=300)):
    """Return the city, province and country found in the address `q` (empty fields if unknown)."""
    return svc.parse_address(q)
