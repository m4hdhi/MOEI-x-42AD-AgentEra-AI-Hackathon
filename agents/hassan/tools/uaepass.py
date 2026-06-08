"""UAE PASS lookup. Synthetic for demo; sandbox in production.

Returns the citizen profile that the supervisor uses to anchor cross-channel memory.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UaePassProfile:
    emirates_id: str
    full_name_en: str
    full_name_ar: str
    nationality: str
    date_of_birth: str
    mobile: str
    email: str
    verified: bool = True


_SYNTHETIC = {
    "784-2002-1102000-2": UaePassProfile(
        emirates_id="784-2002-1102000-2",
        full_name_en="Ali Al Rumaithi",
        full_name_ar="علي الرميثي",
        nationality="UAE",
        date_of_birth="2002-04-11",
        mobile="+971515851616",
        email="ali.alrumaithi@example.ae",
    ),
    "784-1990-1181000-4": UaePassProfile(
        emirates_id="784-1990-1181000-4",
        full_name_en="Fatima Al Mansouri",
        full_name_ar="فاطمة المنصوري",
        nationality="UAE",
        date_of_birth="1990-11-18",
        mobile="+971530843221",
        email="fatima.almansouri@example.ae",
    ),
}


def uaepass_lookup(emirates_id: str) -> UaePassProfile | None:
    """Synthetic UAE PASS lookup. Returns None if unknown."""
    return _SYNTHETIC.get(emirates_id)
