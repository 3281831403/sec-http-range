"""Range request parsing stubs for the sec-http-range exercise.

A range spec is represented by a dict with two integer keys: ``start`` and
``end``.  Both endpoints are inclusive.  An unsatisfiable result is encoded
as ``end < start``; callers must not slice the resource with such a range.
"""

MAX_RANGES = 16


def parse_unit(text: str) -> str:
    """Return the normalized range unit from *text*.

    *text* may be a bare unit or the prefix of a Range header such as
    ``BYTES=0-1``.  Only the byte unit is accepted, case-insensitively, and
    the return value is the lowercase string ``bytes``.  Every other unit
    raises ``ValueError`` instead of falling back to bytes.
    """
    raise NotImplementedError


def parse_spec(spec: str, size: int) -> dict:
    """Parse one range spec into an inclusive ``{"start": int, "end": int}``.

    Accepted forms are ``first-last`` (both endpoints inclusive), ``-suffix``
    (the last *suffix* bytes), and ``first-`` (from *first* through the end).
    A suffix longer than *size* starts at zero.  For an empty resource, an
    open-ended spec has ``end == -1``.  An empty suffix, a missing endpoint, a
    non-digit component, or a negative first position such as ``-5-10`` is
    invalid and raises ``ValueError``.  This function does not clamp a last
    position that is beyond *size*; that is ``clamp``'s job.
    """
    raise NotImplementedError


def clamp(spec: dict, size: int) -> dict:
    """Clamp *spec* to *size* bytes and return an inclusive range dict.

    A missing or negative start raises ``ValueError``.  A last position at or
    beyond *size* becomes ``size - 1``.  A start at or beyond *size* is
    unsatisfiable and is represented by ``{"start": size, "end": size - 1}``.
    A zero-length resource therefore yields ``{"start": 0, "end": -1}``.
    """
    raise NotImplementedError


def parse_set(text: str, size: int) -> list:
    """Parse a complete Range header such as ``bytes=0-1,4-5``.

    The unit is validated through ``parse_unit``.  More than
    ``MAX_RANGES`` comma-separated specs raises ``ValueError`` before any
    merging, and an empty or malformed member also raises ``ValueError``.
    The returned specs are clamped, unsatisfiable members are dropped, and
    the surviving ranges stay in request order.  This function does not merge
    overlaps; call ``merge_overlaps`` when that is wanted.  A request with no
    satisfiable member returns an empty list.
    """
    raise NotImplementedError


def merge_overlaps(specs: list) -> list:
    """Merge overlapping or adjacent inclusive ranges.

    The merged list keeps the position of the earliest input range that
    contributed to each merged range.  Input order is otherwise preserved;
    ranges that do not touch remain separate, and empty ranges are ignored.
    For example, 10-19, 0-4, and 2-12 all merge into one 0-19 range at the
    first position.
    """
    raise NotImplementedError


def sort_specs(specs: list) -> list:
    """Return specs in request order, never in size or offset order.

    If a spec carries an integer ``order`` key it is used as the request
    position; specs without one retain their current relative order.  Ties
    are stable.  The function deliberately does not sort by range length or
    by ``start``.
    """
    raise NotImplementedError


def satisfiable(specs: list, size: int) -> bool:
    """Return whether every supplied range can select at least one byte.

    A non-positive *size* makes every request unsatisfiable, including a
    zero-length resource.  An empty spec list is also unsatisfiable.  Each
    range must have ``0 <= start <= end < size``.
    """
    raise NotImplementedError


def range_batch(requests: list, policy: dict) -> dict:
    """Parse independent Range requests and classify each outcome.

    Each request is a dict with ``id``, ``header``, and ``size``, plus an
    optional ``if_range`` validator.  The policy may contain ``max_ranges``
    (default ``MAX_RANGES``; values above it are capped), ``merge`` (default
    True), and ``etag``.  When ``if_range`` is present and does not equal the
    policy etag, the range is ignored and the whole resource is returned.

    The result maps each request id to one of these shapes::

        {"ok": True,  "status": 206, "ranges": [...]}
        {"ok": True,  "status": 200, "ranges": [], "ignored": True}
        {"ok": False, "status": 400, "error": "invalid_range"}
        {"ok": False, "status": 416, "error": "unsatisfiable"}

    Malformed syntax, an unsupported unit, or too many ranges is a 400;
    a zero-length resource or a request with no satisfiable range is a 416.
    Requests never share state, so an error in one does not affect another.
    """
    raise NotImplementedError