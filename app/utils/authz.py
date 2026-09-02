"""
Authorization: role decorators + data-scoping helpers.

Security principle (per spec): authorization is enforced here, in backend
route guards, never by hiding UI elements. Every protected view must be
wrapped with `roles_required` (or another guard from this module) so that
a manually-typed URL from an unauthorized role returns 403, not a
rendered page.

Scoping rules (used by later modules once the Activity UI exists, and
already enforced today wherever a station-scoped resource exists):

  SUPER_ADMIN         -> full access, everywhere.
  CE_QA               -> Pakistan-wide: any station's data.
  DCE_QA              -> only their own assigned station's data,
                          plus anything with status OPEN (per spec).
  AIRCRAFT_ENGINEER    -> only their own records, plus anything OPEN.

These rules are centralized here so route code and future modules share
one definition instead of re-implementing the logic ad hoc.
"""

from functools import wraps

from flask import abort
from flask_login import current_user

from app.models.user import Role


def roles_required(*roles):
    """
    Restrict a view to the given roles. Returns 401 if not authenticated,
    403 if authenticated but not in an allowed role. Use this on every
    route instead of relying on nav links being hidden.

        @bp.route("/admin")
        @login_required
        @roles_required(Role.SUPER_ADMIN)
        def admin():
            ...
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def station_scope_required(get_station_id):
    """
    Decorator factory for routes whose URL identifies a specific station
    (e.g. /stations/<int:station_id>). Enforces:

      SUPER_ADMIN, CE_QA -> any station.
      DCE_QA             -> only their own assigned station_id. Requesting
                             any other station_id via the URL (or a
                             manually-modified query param) is a 403 -
                             this is the exact bypass the spec calls out.
      AIRCRAFT_ENGINEER   -> not station-scoped; denied here (403).

    `get_station_id(*args, **kwargs)` must return the station_id being
    requested, computed from the same view arguments the route receives
    (e.g. `lambda station_id: station_id`), so the check always looks at
    what's actually in the URL/request rather than a trusted client value.
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            if current_user.role in (Role.SUPER_ADMIN, Role.CE_QA):
                return view(*args, **kwargs)

            if current_user.role == Role.DCE_QA:
                requested_station_id = get_station_id(*args, **kwargs)
                if (
                    requested_station_id is None
                    or current_user.station_id is None
                    or int(requested_station_id) != int(current_user.station_id)
                ):
                    abort(403)
                return view(*args, **kwargs)

            abort(403)

        return wrapped

    return decorator


# --- Scaffolding for the Activity module (Module 3+) -----------------------
#
# Not wired to any route yet - Module 2 explicitly excludes the activity
# system. Defined here now so the permission rule lives in one place and
# later modules import it instead of re-deriving it.

def apply_activity_scope(query, user, include_open_pool=True):
    """
    Narrow an `Activity.query`-style query to what `user` is allowed to see,
    mirroring `can_view_activity` but as a SQL-level filter so dashboard
    counts and list pages stay consistent with the per-row permission rule
    (and so counts always come from the database, never computed in Python
    over an unscoped result set).

      SUPER_ADMIN, CE_QA -> unrestricted (Pakistan-wide).
      DCE_QA             -> own station's activities, plus any OPEN activity.
      AIRCRAFT_ENGINEER   -> own activities, plus (when `include_open_pool`
                             is True) any OPEN activity from any engineer.

    `include_open_pool` (AIRCRAFT_ENGINEER only): callers building the
    "My/Station Activities" default list must pass False so one engineer's
    own list never mixes in another engineer's OPEN task - per spec, the
    shared OPEN pool is only ever shown through the dedicated Open Tasks
    tab/filter, which passes True. DCE_QA/CE_QA/SUPER_ADMIN are unaffected
    by this flag (their visibility isn't scoped down to peers' privacy).
    """
    from app.extensions import db
    from app.models.activity import Activity, ActivityStatus

    if user.role in (Role.SUPER_ADMIN, Role.CE_QA):
        return query

    if user.role == Role.DCE_QA:
        if user.station_id is None:
            return query.filter(Activity.status == ActivityStatus.OPEN)
        return query.filter(
            db.or_(Activity.station_id == user.station_id, Activity.status == ActivityStatus.OPEN)
        )

    if user.role == Role.AIRCRAFT_ENGINEER:
        if include_open_pool:
            return query.filter(
                db.or_(Activity.created_by == user.id, Activity.status == ActivityStatus.OPEN)
            )
        return query.filter(Activity.created_by == user.id)

    return query.filter(db.false())


def can_view_activity(user, activity) -> bool:
    """
    SUPER_ADMIN / CE_QA: any activity (Pakistan-wide).
    DCE_QA: activities at their own station, plus any OPEN activity.
    AIRCRAFT_ENGINEER: activities they created, plus any OPEN activity.
    """
    from app.models.activity import ActivityStatus

    if user.role in (Role.SUPER_ADMIN, Role.CE_QA):
        return True

    if activity.status == ActivityStatus.OPEN:
        return True

    if user.role == Role.DCE_QA:
        return user.station_id is not None and activity.station_id == user.station_id

    if user.role == Role.AIRCRAFT_ENGINEER:
        return activity.created_by == user.id

    return False
