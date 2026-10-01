"""
CampusGrid AI: Trusted Regulation Source Registry
The publishers whose documents may enter the regulation corpus. A submission must name one of
them, give a citable reference (gazette / decision / circular number), and — if it gives a web
address — that address must be HTTPS on the publisher's own domain. This does not prove a
document is genuine; it makes the claimed origin explicit and checkable by the second reviewer.
"""

from typing import Dict, List, Optional
from urllib.parse import urlparse

TRUSTED_SOURCES: Dict[str, Dict[str, object]] = {
    "PUCSL": {"name": "Public Utilities Commission of Sri Lanka", "domains": ["pucsl.gov.lk"], "covers": "Electricity tariffs and decisions"},
    "CEB": {"name": "Ceylon Electricity Board", "domains": ["ceb.lk"], "covers": "Bulk-supply tariffs, billing and metering rules"},
    "LECO": {"name": "Lanka Electricity Company", "domains": ["leco.lk"], "covers": "Distribution tariffs and billing"},
    "SLSEA": {"name": "Sri Lanka Sustainable Energy Authority", "domains": ["energy.gov.lk"], "covers": "Energy-efficiency codes and guidelines"},
    "SLSI": {"name": "Sri Lanka Standards Institution", "domains": ["slsi.lk"], "covers": "National standards"},
    "ASHRAE": {"name": "ASHRAE", "domains": ["ashrae.org"], "covers": "Thermal comfort (Standard 55) and HVAC standards"},
    "UGC": {"name": "University Grants Commission", "domains": ["ugc.ac.lk"], "covers": "Circulars to state universities"},
    "UNIVERSITY": {"name": "This university (internal policy)", "domains": [], "covers": "Council / Works Department policies and circulars"},
}


def list_sources() -> List[Dict[str, object]]:
    return [{"code": code, **info} for code, info in TRUSTED_SOURCES.items()]


def source_problems(publisher: str, source_url: Optional[str]) -> List[str]:
    """Why a claimed origin is not acceptable (empty list = acceptable)."""
    info = TRUSTED_SOURCES.get((publisher or "").upper())
    if info is None:
        return [f"'{publisher}' is not a registered publisher; use one of {', '.join(TRUSTED_SOURCES)}."]
    if not source_url:
        return []
    parsed = urlparse(source_url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return ["The source address must be an https:// link."]
    domains = info["domains"]
    if domains and not any(host == d or host.endswith("." + d) for d in domains):
        return [f"{host} is not a {publisher.upper()} address (expected {', '.join(domains)})."]
    return []
