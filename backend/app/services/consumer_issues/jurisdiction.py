"""Trusted jurisdiction resolution and authoritative LGD directory validation.

This module provides server-controlled, trusted jurisdiction resolution for consumer
issues and complaints, ensuring that untrusted client input (such as client-supplied
request fields, GPS coordinates, or image EXIF metadata) cannot fabricate verification.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone
import logging
import threading
from typing import Any

from backend.app.api.session_store import InspectionSession

logger = logging.getLogger(__name__)

# =====================================================================
# Canonical ISO 3166-2:IN States and Local Government Directory (LGD) Districts
# =====================================================================

CANONICAL_LGD_JURISDICTIONS: dict[str, frozenset[str]] = {
    "MH": frozenset({
        "PUNE",
        "MUMBAI",
        "MUMBAI_SUBURBAN",
        "SATARA",
        "NAGPUR",
        "NASHIK",
        "THANE",
        "AURANGABAD",
        "SOLAPUR",
        "KOLHAPUR",
        "AMRAVATI",
        "JALGAON",
        "NANDED",
        "AKOLA",
        "PALGHAR",
        "RAIGAD",
        "RATNAGIRI",
        "SANGLI",
        "AHMEDNAGAR",
        "CHANDRAPUR",
        "BHANDARA",
        "DHULE",
        "GADCHIROLI",
        "GONDIA",
        "HINGOLI",
        "JALNA",
        "LATUR",
        "NANDURBAR",
        "OSMANABAD",
        "PARBHANI",
        "SINDHUDURG",
        "WARDHA",
        "WASHIM",
        "YAVATMAL",
    }),
    "DL": frozenset({
        "NEW_DELHI",
        "CENTRAL_DELHI",
        "NORTH_DELHI",
        "SOUTH_DELHI",
        "EAST_DELHI",
        "WEST_DELHI",
        "NORTH_WEST_DELHI",
        "NORTH_EAST_DELHI",
        "SOUTH_WEST_DELHI",
        "SOUTH_EAST_DELHI",
        "SHAHDARA",
    }),
    "KA": frozenset({
        "BENGALURU_URBAN",
        "BENGALURU_RURAL",
        "MYSURU",
        "DHARWAD",
        "BELAGAVI",
        "MANGALURU",
        "BALLARI",
        "UDUPI",
        "KALABURAGI",
        "SHIVAMOGGA",
        "TUMAKURU",
        "HASSAN",
    }),
    "TN": frozenset({
        "CHENNAI",
        "COIMBATORE",
        "MADURAI",
        "TIRUCHIRAPPALLI",
        "SALEM",
        "TIRUPPUR",
        "KANCHEEPURAM",
        "VELLORE",
        "ERODE",
        "TIRUNELVELI",
    }),
    "GJ": frozenset({
        "AHMEDABAD",
        "SURAT",
        "VADODARA",
        "RAJKOT",
        "GANDHINAGAR",
        "BHAVNAGAR",
        "JAMNAGAR",
        "JUNAGADH",
        "KUTCH",
        "ANAND",
    }),
    "UP": frozenset({
        "LUCKNOW",
        "KANPUR_NAGAR",
        "GAUTAM_BUDDHA_NAGAR",
        "VARANASI",
        "AGRA",
        "PRAYAGRAJ",
        "GHAZIABAD",
        "MEERUT",
        "BAREILLY",
        "ALIGARH",
        "MORADABAD",
        "GORAKHPUR",
    }),
    "WB": frozenset({
        "KOLKATA",
        "NORTH_24_PARGANAS",
        "SOUTH_24_PARGANAS",
        "HOWRAH",
        "HOOGHLY",
        "PASCHIM_BARDHAMAN",
        "PURBA_BARDHAMAN",
        "DARJEELING",
    }),
    "HR": frozenset({
        "GURUGRAM",
        "FARIDABAD",
        "PANCHKULA",
        "AMBALA",
        "KARNAL",
        "PANIPAT",
        "SONIPAT",
        "ROHTAK",
        "HISAR",
    }),
    "TS": frozenset({
        "HYDERABAD",
        "RANGAREDDY",
        "MEDCHAL_MALKAJGIRI",
        "WARANGAL_URBAN",
        "SANGAREDDY",
        "NIZAMABAD",
        "KARIMNAGAR",
    }),
    "RJ": frozenset({
        "JAIPUR",
        "JODHPUR",
        "KOTA",
        "UDAIPUR",
        "AJMER",
        "BIKANER",
        "ALWAR",
        "BHILWARA",
    }),
    "MP": frozenset({
        "BHOPAL",
        "INDORE",
        "GWALIOR",
        "JABALPUR",
        "UJJAIN",
        "SAGAR",
    }),
    "KL": frozenset({
        "THIRUVANANTHAPURAM",
        "ERNAKULAM",
        "KOZHIKODE",
        "THRISSUR",
        "MALAPPURAM",
        "KANNUR",
        "KOLLAM",
    }),
    "AP": frozenset({
        "VISAKHAPATNAM",
        "VIJAYAWADA",
        "GUNTUR",
        "NELLORE",
        "KURNOOL",
        "TIRUPATI",
    }),
    "PB": frozenset({
        "LUDHIANA",
        "AMRITSAR",
        "JALANDHAR",
        "PATIALA",
        "BATHINDA",
        "SAS_NAGAR",
    }),
    "CH": frozenset({"CHANDIGARH"}),
    "GA": frozenset({"NORTH_GOA", "SOUTH_GOA"}),
    "UK": frozenset({"DEHRADUN", "HARIDWAR", "NAINITAL", "UDHAM_SINGH_NAGAR"}),
    "UT": frozenset({"DEHRADUN", "HARIDWAR", "NAINITAL", "UDHAM_SINGH_NAGAR"}),
}


def validate_canonical_jurisdiction(
    state_code: str | None,
    district_code: str | None,
) -> tuple[str | None, str | None, bool]:
    """Validate and normalize candidate state and district codes against canonical LGD definitions.

    Returns:
        (canonical_state, canonical_district, is_verified)
        - If both state and district are valid: (STATE, DISTRICT, True)
        - If only state is valid: (STATE, None, False)
        - If state is unknown or invalid: (None, None, False)
    """
    if not state_code or not isinstance(state_code, str):
        return None, None, False

    clean_state = state_code.strip().upper()
    if clean_state not in CANONICAL_LGD_JURISDICTIONS:
        logger.debug("Jurisdiction validation rejected non-canonical state_code: %s", state_code)
        return None, None, False

    if not district_code or not isinstance(district_code, str):
        logger.debug("State '%s' recognized, but district_code is missing or empty.", clean_state)
        return clean_state, None, False

    clean_dist = district_code.strip().upper()
    valid_districts = CANONICAL_LGD_JURISDICTIONS[clean_state]

    if clean_dist not in valid_districts:
        logger.debug(
            "State '%s' recognized, but district '%s' is not in canonical LGD list for state.",
            clean_state,
            clean_dist,
        )
        return clean_state, None, False

    return clean_state, clean_dist, True


# =====================================================================
# Server-Controlled Verified Location Registry
# =====================================================================

class ServerVerifiedLocationRegistry:
    """Thread-safe authoritative server-side registry of verified inspection/retailer locations.

    Enforces that trusted inspection locations must be explicitly registered by an authoritative
    server process or certified field inspection record, rather than client-submitted data.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._locations: dict[str, dict[str, Any]] = {}

    def register_verified_location(
        self,
        inspection_id: str,
        state_code: str,
        district_code: str,
        verification_source: str = "OFFICIAL_ESTABLISHMENT_REGISTRY",
    ) -> None:
        """Register a verified location for an inspection from an authoritative source."""
        with self._lock:
            self._locations[inspection_id] = {
                "inspection_id": inspection_id,
                "state_code": state_code.strip().upper() if state_code else "",
                "district_code": district_code.strip().upper() if district_code else "",
                "verification_source": verification_source,
                "verified_at": datetime.now(timezone.utc),
            }

    def get_verified_location(self, inspection_id: str) -> dict[str, Any] | None:
        """Retrieve verified location for inspection_id if one has been authoritatively registered."""
        with self._lock:
            rec = self._locations.get(inspection_id)
            return dict(rec) if rec else None

    def remove_location(self, inspection_id: str) -> bool:
        """Remove a location record from the registry."""
        with self._lock:
            return self._locations.pop(inspection_id, None) is not None

    def clear(self) -> None:
        """Clear all location records (primarily for testing)."""
        with self._lock:
            self._locations.clear()


# =====================================================================
# Trusted Jurisdiction Resolver Interface & Default Implementation
# =====================================================================

class TrustedJurisdictionResolver(abc.ABC):
    """Abstract interface for server-side trusted jurisdiction resolution."""

    @abc.abstractmethod
    def resolve_jurisdiction(
        self,
        inspection_id: str,
        session: InspectionSession | None = None,
        untrusted_payload: dict[str, Any] | None = None,
    ) -> tuple[str | None, str | None, bool]:
        """Resolve canonical jurisdiction (state_code, district_code, is_verified).

        CRITICAL SAFETY CONSTRAINTS:
        1. Must NEVER treat client-submitted request fields, GPS coordinates, or EXIF metadata as proof.
        2. Must ONLY resolve from server-controlled, authoritative sources.
        3. Must validate candidate codes against canonical state and LGD district definitions.
        4. If trusted source cannot establish jurisdiction, return unverified state.
        """
        pass


class DefaultTrustedJurisdictionResolver(TrustedJurisdictionResolver):
    """Default server-side jurisdiction resolver enforcing strict trust boundaries."""

    def __init__(
        self,
        registry: ServerVerifiedLocationRegistry | None = None,
    ) -> None:
        self.registry = registry or ServerVerifiedLocationRegistry()

    def resolve_jurisdiction(
        self,
        inspection_id: str,
        session: InspectionSession | None = None,
        untrusted_payload: dict[str, Any] | None = None,
    ) -> tuple[str | None, str | None, bool]:
        # Rule: Client-supplied payload fields, GPS coordinates, and EXIF metadata
        # are explicitly UNTRUSTED and cannot be used as proof of jurisdiction.

        # 1. Query authoritative server-side location registry
        trusted_record = self.registry.get_verified_location(inspection_id)
        if not trusted_record:
            # No authoritative location registered for this inspection
            return None, None, False

        raw_state = trusted_record.get("state_code")
        raw_dist = trusted_record.get("district_code")

        # 2. Validate against canonical LGD directory
        canonical_state, canonical_dist, is_verified = validate_canonical_jurisdiction(
            state_code=raw_state,
            district_code=raw_dist,
        )

        return canonical_state, canonical_dist, is_verified
