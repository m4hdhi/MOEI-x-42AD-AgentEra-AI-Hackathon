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
    "784-2004-6541442-1": UaePassProfile(
        emirates_id="784-2004-6541442-1",
        full_name_en="Mahdhi Muzammil",
        full_name_ar="مهدي مزمل",
        nationality="UAE",
        date_of_birth="2004-08-15",
        mobile="+971556673050",
        email="mahdhi@example.ae",
    ),
    "784-1985-0000002-3": UaePassProfile(
        emirates_id="784-1985-0000002-3",
        full_name_en="Ahmed Al Suwaidi",
        full_name_ar="أحمد السويدي",
        nationality="UAE",
        date_of_birth="1985-09-03",
        mobile="+971502345678",
        email="ahmed.s@example.ae",
    ),
}


def uaepass_lookup(emirates_id: str) -> UaePassProfile | None:
    """Synthetic UAE PASS lookup. Returns None if unknown."""
    return _SYNTHETIC.get(emirates_id)
