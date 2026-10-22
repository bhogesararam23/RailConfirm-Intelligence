"""Journey domain types for RailConfirm Intelligence.

Represents the train/route context for a reservation group.
Class codes and quota codes are validated against known IRCTC terminology.

Reference: IRCTC booking terminology (verified 2026-10-21).
Unknown codes are warned about but not rejected, to allow forward compatibility
with new classes or quotas introduced by Indian Railways.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date

from railconfirm.domain.exceptions import JourneyValidationError
from railconfirm.domain.validation import (
    validate_journey_date,
    validate_station_code,
    validate_train_number,
)

# ── Supported code registries ──────────────────────────────────────────────────

# Source: IRCTC booking class codes (verified 2026-10-21).
SUPPORTED_CLASS_CODES: dict[str, str] = {
    "1A": "First AC",
    "2A": "Second AC",
    "3A": "Third AC",
    "3E": "Third AC Economy",
    "SL": "Sleeper",
    "CC": "Chair Car",
    "EC": "Executive Chair Car",
    "2S": "Second Sitting",
    "FC": "First Class",
}

# Source: IRCTC quota codes (verified 2026-10-21).
SUPPORTED_QUOTA_CODES: dict[str, str] = {
    "GN": "General",
    "TQ": "Tatkal",
    "PT": "Premium Tatkal",
    "LD": "Ladies",
    "DF": "Defence",
    "SS": "Senior Citizen",
    "HP": "Handicapped",
    "PH": "Physically Handicapped",
    "YU": "Youth",
    "DU": "Duty",
}


# ── Domain type ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Journey:
    """Immutable representation of a journey segment context.

    Invariants
    ----------
    * ``train_number`` must be 4–6 digits (string, zero-padded).
    * ``boarding_station`` and ``destination_station`` must differ.
    * ``class_code`` and ``quota_code`` are validated against known codes;
      unknown codes emit a warning but are not rejected (forward compatibility).
    * ``journey_date`` is the departure date (not an arrival or booking date).

    Do not store passenger names or raw PNRs in this object.
    """

    train_number: str            # 4–6 digit string, e.g. "12301"
    journey_date: date           # Date of journey departure
    boarding_station: str        # Station code, uppercase
    destination_station: str     # Station code, uppercase
    class_code: str              # Validated against SUPPORTED_CLASS_CODES
    quota_code: str              # Validated against SUPPORTED_QUOTA_CODES

    # ── Validation via __post_init__ ───────────────────────────────────────────

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Raise for hard constraint violations; warn for soft ones."""
        validate_train_number(self.train_number)

        b = validate_station_code(self.boarding_station, "boarding_station")
        d = validate_station_code(self.destination_station, "destination_station")
        if b == d:
            raise JourneyValidationError(
                f"boarding_station and destination_station must differ, got {b!r} for both."
            )

        validate_journey_date(self.journey_date)

        # Soft validation — warn but accept unknown codes for forward compat
        if self.class_code not in SUPPORTED_CLASS_CODES:
            warnings.warn(
                f"class_code {self.class_code!r} is not in the known code list "
                f"({list(SUPPORTED_CLASS_CODES)}). Add it after verification.",
                UserWarning,
                stacklevel=4,
            )

        if self.quota_code not in SUPPORTED_QUOTA_CODES:
            warnings.warn(
                f"quota_code {self.quota_code!r} is not in the known code list "
                f"({list(SUPPORTED_QUOTA_CODES)}). Add it after verification.",
                UserWarning,
                stacklevel=4,
            )

    @property
    def boarding_station_upper(self) -> str:
        return str(self.boarding_station).strip().upper()

    @property
    def destination_station_upper(self) -> str:
        return str(self.destination_station).strip().upper()

    def is_class_supported(self) -> bool:
        """Return True if class_code is in the known supported set."""
        return self.class_code in SUPPORTED_CLASS_CODES

    def is_quota_supported(self) -> bool:
        """Return True if quota_code is in the known supported set."""
        return self.quota_code in SUPPORTED_QUOTA_CODES


def make_journey(
    train_number: str,
    journey_date: date,
    boarding_station: str,
    destination_station: str,
    class_code: str,
    quota_code: str,
) -> Journey:
    """Factory function: normalize station codes to uppercase before construction."""
    return Journey(
        train_number=str(train_number).strip(),
        journey_date=journey_date,
        boarding_station=str(boarding_station).strip().upper(),
        destination_station=str(destination_station).strip().upper(),
        class_code=str(class_code).strip().upper(),
        quota_code=str(quota_code).strip().upper(),
    )
