"""
Module 5: Dynamic Activity Engine — shared form helpers.

Everything here is deliberately generic so that Modules 6-8 reuse it as-is:
they register fields via `app.utils.activity_registry.register_activity_type`
and get station-scoping, required-field validation, and clean error
messages for free — without writing per-type validation code.

Server-side validation is authoritative. The client-side JS
(`app/static/js/activity_form.js`) mirrors these rules for a responsive UI,
but every rule here is re-checked on the server regardless of what the
client sent, per spec ("never trust client-side validation alone").
"""

from datetime import datetime, date

from app.extensions import db
from app.models.activity import ActivityStatus, ActivityType
from app.models.shift import Shift
from app.models.station import Station
from app.models.user import Role
from app.utils.activity_registry import get_spec


def get_selectable_stations(user):
    """
    Stations `user` is allowed to log an activity against.

      SUPER_ADMIN, CE_QA -> any active station (Pakistan-wide).
      DCE_QA, AIRCRAFT_ENGINEER -> only their own assigned station.

    Returns a list of Station objects (empty if the user has no station and
    isn't Pakistan-wide — that's a data-setup problem the form surfaces as
    a validation error rather than silently guessing a station).
    """
    if user.role in (Role.SUPER_ADMIN, Role.CE_QA):
        return Station.query.filter_by(is_active=True).order_by(Station.code).all()

    if user.station_id:
        station = db.session.get(Station, user.station_id)
        return [station] if station and station.is_active else []

    return []


def default_station_id(user):
    """The station the form should pre-select for `user`, or None."""
    if user.role in (Role.SUPER_ADMIN, Role.CE_QA):
        return None
    return user.station_id


def station_field_is_locked(user) -> bool:
    """
    True when the Station field should be rendered read-only (auto-filled
    from the logged-in user, per spec) rather than as a picker.
    """
    return user.role in (Role.DCE_QA, Role.AIRCRAFT_ENGINEER)


def _parse_date(raw: str):
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_activity_form(form, user):
    """
    Validate a submitted Add Activity form.

    `form` is a `request.form`-like mapping (MultiDict). Returns
    `(cleaned, errors)`:
      - `cleaned`: dict of validated values, keyed by field name, ready to
        build an `Activity` row (and, once a specialized table exists for
        the chosen type, its detail row too).
      - `errors`: dict of field name -> single human-readable message.
        Empty dict means the submission is valid.

    This function re-validates everything the client-side JS already
    checked — required fields, valid choices, station scope — because the
    client can always be bypassed (a hand-crafted POST, a disabled-JS
    browser, a modified <select> value, etc).
    """
    errors = {}
    cleaned = {}

    # --- Date -----------------------------------------------------------
    activity_date = _parse_date(form.get("activity_date", ""))
    if activity_date is None:
        errors["activity_date"] = "Date is required and must be a valid date."
    else:
        cleaned["activity_date"] = activity_date

    # --- Shift ------------------------------------------------------------
    shift_raw = (form.get("shift_id") or "").strip()
    shift = None
    if not shift_raw:
        errors["shift_id"] = "Shift is required."
    else:
        try:
            shift = db.session.get(Shift, int(shift_raw))
        except (TypeError, ValueError):
            shift = None
        if shift is None or not shift.is_active:
            errors["shift_id"] = "Select a valid, active shift."
        else:
            cleaned["shift_id"] = shift.id

    # --- Activity type ------------------------------------------------------
    activity_type = (form.get("activity_type") or "").strip().upper()
    if not activity_type:
        errors["activity_type"] = "Activity Type is required."
    elif activity_type not in ActivityType.ALL:
        errors["activity_type"] = "Select a valid activity type."
    else:
        cleaned["activity_type"] = activity_type

    # --- Station (server-enforced scope, not just the client's <select>) ---
    allowed_stations = {s.id: s for s in get_selectable_stations(user)}
    station_raw = (form.get("station_id") or "").strip()
    if not station_raw:
        errors["station_id"] = "Station is required."
    else:
        try:
            station_id = int(station_raw)
        except ValueError:
            station_id = None
        if station_id is None or station_id not in allowed_stations:
            errors["station_id"] = "Select a station you're authorized to log activities for."
        else:
            cleaned["station_id"] = station_id
    if not allowed_stations and "station_id" not in errors:
        errors["station_id"] = "Your account has no station assigned. Contact an administrator."

    # --- Status -------------------------------------------------------------
    status = (form.get("status") or ActivityStatus.OPEN).strip().upper()
    if status not in ActivityStatus.ALL:
        errors["status"] = "Select a valid status."
    else:
        cleaned["status"] = status

    # --- Remarks (optional) ---------------------------------------------
    remarks = (form.get("remarks") or "").strip()
    if len(remarks) > 4000:
        errors["remarks"] = "Remarks must be 4000 characters or fewer."
    else:
        cleaned["remarks"] = remarks or None

    # --- Type-specific fields (generic; empty for every type in Module 5) -
    # Modules 6-8 register fields via activity_registry.register_activity_type
    # and this loop starts validating them with zero changes here.
    extra = {}
    if activity_type in ActivityType.ALL:
        spec = get_spec(activity_type)
        for f in spec.fields:
            raw = form.get(f.name)
            if f.field_type == "checkbox":
                extra[f.name] = bool(raw)
                continue
            raw = (raw or "").strip() if isinstance(raw, str) else raw
            if f.required and not raw:
                errors[f.name] = f"{f.label} is required."
                continue
            if raw and f.max_length and len(raw) > f.max_length:
                errors[f.name] = f"{f.label} must be {f.max_length} characters or fewer."
                continue
            if raw and f.field_type == "select" and f.choices:
                valid_values = {c[0] for c in f.choices}
                if raw not in valid_values:
                    errors[f.name] = f"Select a valid {f.label.lower()}."
                    continue
            extra[f.name] = raw
    cleaned["extra_fields"] = extra

    return cleaned, errors
