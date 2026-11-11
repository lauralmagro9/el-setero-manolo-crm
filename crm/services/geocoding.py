"""Find the city, province and country of a free-text address (best effort, never blocking)."""

import json
import logging
import urllib.parse
import urllib.request

from .. import schemas as s
from ..config import settings

logger = logging.getLogger(__name__)


def _first_value(address: dict, keys: list[str]) -> str | None:
    """Return the first non-empty value of `address` among `keys`, in order."""
    return next((address[key] for key in keys if address.get(key)), None)


def _search(query: str) -> list[dict]:
    """Ask the geocoding server for the best match of `query`; return its raw result list."""
    cfg = settings.geocoding
    params = urllib.parse.urlencode({
        "q": query, "format": "jsonv2", "addressdetails": 1, "limit": 1,
        "accept-language": cfg.language,
    })
    request = urllib.request.Request(
        f"{cfg.url}?{params}", headers={"User-Agent": cfg.user_agent}
    )
    with urllib.request.urlopen(request, timeout=cfg.timeout_seconds) as response:  # noqa: S310
        return json.load(response)


def parse_address(query: str) -> s.AddressParts:
    """Return the city, province and country of `query`.

    Lookup is a convenience: when it is disabled, the address is not found or the server is
    unreachable, an empty result comes back and the user fills the fields by hand.
    """
    cfg = settings.geocoding
    if not cfg.enabled or not query.strip():
        return s.AddressParts()
    try:
        results = _search(query.strip())
    except (OSError, ValueError) as exc:  # network errors, timeouts and malformed JSON
        logger.warning("Address lookup failed: %s", exc)
        return s.AddressParts()
    if not results:
        logger.info("Address lookup: no match")
        return s.AddressParts()
    address = results[0].get("address", {})
    parts = s.AddressParts(
        city=_first_value(address, cfg.city_keys),
        region=_first_value(address, cfg.region_keys),
        country=address.get("country"),
    )
    logger.info("Address lookup: %s, %s, %s", parts.city, parts.region, parts.country)
    return parts
