"""
Module 5: Dynamic Activity Engine — extension registry.

This is the single extension point that Modules 6-8 use to attach the
per-type detail fields (and, eventually, the specialized detail tables) for
each of the 14 activity types, WITHOUT touching the add-activity route,
template, or JS engine.

Why this exists
----------------
Module 5 intentionally does not implement the 14 activity-detail forms. But
the engine that will render/validate them has to exist now so later modules
only need to do one thing: call `register_activity_type()` with a list of
`ActivityField` objects (and, optionally, the SQLAlchemy model that stores
them). Everything else — conditional show/hide, server-side required-field
validation, error rendering — is handled generically by
`app/utils/activity_forms.py` and `app/static/js/activity_form.js`.

Usage (future module, e.g. Module 6 — Ramp Inspection)::

    from app.utils.activity_registry import register_activity_type, ActivityField
    from app.models.activity import ActivityType

    register_activity_type(
        ActivityType.RAMP_INSPECTION,
        fields=[
            ActivityField("flight_number", "Flight Number", "text", required=True),
            ActivityField("aircraft_reg", "Aircraft Registration", "text", required=True),
            ActivityField("findings", "Findings", "textarea", required=False),
        ],
        detail_model=RampInspectionDetail,  # optional, added when the table exists
    )

Nothing above is invoked yet — every activity type currently resolves to an
empty field list, i.e. "no extra fields beyond the common ones", which is
exactly correct for Module 5's scope.
"""

from dataclasses import dataclass, field
from typing import Optional


# Field types the generic renderer/validator understand out of the box.
# Later modules aren't limited to these — an unrecognized `field_type` just
# falls back to plain text handling — but sticking to this set keeps the
# generic <-> specific split clean.
FIELD_TYPES = ("text", "textarea", "number", "date", "select", "checkbox")


@dataclass
class ActivityField:
    """
    Declarative description of a single type-specific field. The generic
    engine (template partial + JS + server validator) knows how to render
    and validate any field described this way, so later modules never have
    to write their own show/hide JS or their own required-field checks.
    """

    name: str  # form field name, e.g. "flight_number"
    label: str
    field_type: str = "text"  # one of FIELD_TYPES
    required: bool = False
    choices: Optional[list] = None  # list of (value, label) for "select"
    help_text: Optional[str] = None
    max_length: Optional[int] = None


@dataclass
class ActivityTypeSpec:
    code: str
    fields: list = field(default_factory=list)
    detail_model = None  # set via register_activity_type(); SQLAlchemy model


# code -> ActivityTypeSpec. Populated lazily/idempotently by
# `register_activity_type`, seeded with an empty spec for every known type
# so lookups never have to special-case "not registered yet".
_REGISTRY: dict[str, ActivityTypeSpec] = {}


def _ensure_seeded():
    if _REGISTRY:
        return
    from app.models.activity import ActivityType

    for code in ActivityType.ALL:
        _REGISTRY[code] = ActivityTypeSpec(code=code)


def register_activity_type(code: str, fields: list = None, detail_model=None) -> ActivityTypeSpec:
    """
    Attach type-specific fields (and, optionally, the detail table) for a
    single activity type. Safe to call multiple times for the same code
    (e.g. re-imported during tests) — the latest call wins.
    """
    _ensure_seeded()
    spec = ActivityTypeSpec(code=code, fields=list(fields or []))
    spec.detail_model = detail_model
    _REGISTRY[code] = spec
    return spec


def get_spec(code: str) -> ActivityTypeSpec:
    _ensure_seeded()
    return _REGISTRY.get(code) or ActivityTypeSpec(code=code)


def all_specs() -> dict:
    _ensure_seeded()
    return dict(_REGISTRY)
