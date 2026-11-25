"""Range request parsing stubs for the sec-http-range exercise.

A range spec is represented by a dict with two integer keys: ``start`` and
``end``.  Both endpoints are inclusive.  An unsatisfiable result is encoded
as ``end < start``; callers must not slice the resource with such a range.
"""

MAX_RANGES = 16


def _non_negative_int(token) -> int:
    """Parse *token* as a strict non-negative decimal integer.

    Unlike :class:`int`, this rejects signs, whitespace-only values, empty
    strings, and any non-digit character.
    """
    if not isinstance(token, str):
        raise ValueError("range endpoint must be a string of digits")
    token = token.strip()
    if not token or not all("0" <= char <= "9" for char in token):
        raise ValueError("range endpoint must be non-negative digits")
    return int(token)


def parse_unit(text: str) -> str:
    """Return the normalized range unit from *text*.

    *text* may be a bare unit or the prefix of a Range header such as
    ``BYTES=0-1``.  Only the byte unit is accepted, case-insensitively, and
    the return value is the lowercase string ``bytes``.  Every other unit
    raises ``ValueError`` instead of falling back to bytes.
    """
    if not isinstance(text, str) or not text:
        raise ValueError("unsupported range unit")
    unit = text.split("=", 1)[0].strip()
    if unit.lower() != "bytes":
        raise ValueError("unsupported range unit: %r" % (unit,))
    return "bytes"


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
    if not isinstance(spec, str):
        raise ValueError("range spec must be a string")
    token = spec.strip()
    if not token:
        raise ValueError("empty range spec")

    # Suffix form: "-N" where N is digits only.  Anything else beginning with
    # '-' (e.g. "-5-10", an attempt at a negative start) is invalid.
    if token[0] == "-":
        suffix_text = token[1:].strip()
        suffix = _non_negative_int(suffix_text)
        start = max(size - suffix, 0)
        end = size - 1
        return {"start": start, "end": end}

    # Every other legal form contains exactly one '-' separating first/last.
    parts = token.split("-")
    if len(parts) != 2:
        raise ValueError("malformed range spec: %r" % (spec,))

    first_text, last_text = parts[0].strip(), parts[1].strip()
    first = _non_negative_int(first_text)

    if last_text == "":
        # Open-ended "first-": through the final byte.  For size == 0 this
        # naturally yields end == -1.
        last = size - 1
    else:
        last = _non_negative_int(last_text)

    return {"start": first, "end": last}


def clamp(spec: dict, size: int) -> dict:
    """Clamp *spec* to *size* bytes and return an inclusive range dict.

    A missing or negative start raises ``ValueError``.  A last position at or
    beyond *size* becomes ``size - 1``.  A start at or beyond *size* is
    unsatisfiable and is represented by ``{"start": size, "end": size - 1}``.
    A zero-length resource therefore yields ``{"start": 0, "end": -1}``.
    """
    if not isinstance(spec, dict) or "start" not in spec:
        raise ValueError("range spec is missing a start")
    start = spec["start"]
    if isinstance(start, bool) or not isinstance(start, int) or start < 0:
        raise ValueError("range start must be a non-negative integer")
    if "end" not in spec:
        raise ValueError("range spec is missing an end")
    end = spec["end"]
    if isinstance(end, bool) or not isinstance(end, int):
        raise ValueError("range end must be an integer")

    if start >= size:
        return {"start": size, "end": size - 1}

    if end >= size:
        end = size - 1

    return {"start": start, "end": end}


def _parse_set_with_limit(text: str, size: int, max_ranges: int) -> list:
    """Shared parse_set implementation with a caller-selected count cap."""
    # 1. Unit is validated before anything else.  parse_unit also understands
    #    the "bytes=..." header prefix form, so this rejects unknown units.
    parse_unit(text)

    if not isinstance(text, str) or "=" not in text:
        raise ValueError("missing range set")

    _, range_text = text.split("=", 1)

    # 2. Count comma-separated members before parsing or merging anything.
    members = range_text.split(",")
    if len(members) > max_ranges:
        raise ValueError("too many ranges: %d" % len(members))

    # 3. Parse and clamp each member, dropping unsatisfiable ones.
    specs = []
    for member in members:
        token = member.strip()
        if not token:
            raise ValueError("empty range member")
        parsed = parse_spec(token, size)
        bounded = clamp(parsed, size)
        if bounded["end"] < bounded["start"]:
            continue
        specs.append(bounded)

    # parse_set deliberately does not merge overlaps.
    return specs


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
    return _parse_set_with_limit(text, size, MAX_RANGES)


def merge_overlaps(specs: list) -> list:
    """Merge overlapping or adjacent inclusive ranges.

    The merged list keeps the position of the earliest input range that
    contributed to each merged range.  Input order is otherwise preserved;
    ranges that do not touch remain separate, and empty ranges are ignored.
    For example, 10-19, 0-4, and 2-12 all merge into one 0-19 range at the
    first position.
    """
    # Keep only non-empty ranges, remembering each one's original index.
    valid = []
    for index, spec in enumerate(specs):
        start = spec["start"]
        end = spec["end"]
        if end < start:
            continue
        valid.append((index, start, end))

    count = len(valid)
    parent = list(range(count))

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a, b):
        root_a = find(a)
        root_b = find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    # Two inclusive ranges touch when they overlap or are adjacent
    # (e.g. 0-1 and 2-3 leave no gap and merge into 0-3).
    for i in range(count):
        _, start_i, end_i = valid[i]
        for j in range(i + 1, count):
            _, start_j, end_j = valid[j]
            if start_i <= end_j + 1 and start_j <= end_i + 1:
                union(i, j)

    components = {}
    for node, (original_index, start, end) in enumerate(valid):
        root = find(node)
        component = components.get(root)
        if component is None:
            components[root] = {
                "start": start,
                "end": end,
                "position": original_index,
            }
        else:
            component["start"] = min(component["start"], start)
            component["end"] = max(component["end"], end)
            component["position"] = min(component["position"], original_index)

    ordered = sorted(components.values(), key=lambda item: item["position"])
    return [
        {"start": item["start"], "end": item["end"]}
        for item in ordered
    ]


def sort_specs(specs: list) -> list:
    """Return specs in request order, never in size or offset order.

    If a spec carries an integer ``order`` key it is used as the request
    position; specs without one retain their current relative order.  Ties
    are stable.  The function deliberately does not sort by range length or
    by ``start``.
    """
    has_explicit_order = any(
        isinstance(spec, dict) and "order" in spec for spec in specs
    )
    if not has_explicit_order:
        return list(specs)

    # An explicit order is an absolute request position; a spec without one
    # keeps its current enumeration index as its key.  Python's sort is
    # stable, so equal keys preserve original relative order.
    indexed = list(enumerate(specs))
    indexed.sort(key=lambda pair: pair[1].get("order", pair[0]))
    return [spec for _, spec in indexed]


def satisfiable(specs: list, size: int) -> bool:
    """Return whether every supplied range can select at least one byte.

    A non-positive *size* makes every request unsatisfiable, including a
    zero-length resource.  An empty spec list is also unsatisfiable.  Each
    range must have ``0 <= start <= end < size``.
    """
    if size <= 0:
        return False
    if not specs:
        return False
    for spec in specs:
        start = spec["start"]
        end = spec["end"]
        if not (0 <= start <= end < size):
            return False
    return True


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
    policy = policy if isinstance(policy, dict) else {}
    configured_cap = policy.get("max_ranges", MAX_RANGES)
    max_ranges = min(configured_cap, MAX_RANGES)
    merge_enabled = policy.get("merge", True)
    etag = policy.get("etag")

    results = {}

    for request in requests:
        request_id = request["id"]

        # A mismatching If-Range means "send the whole representation"; the
        # Range header is ignored without validating its syntax.
        if "if_range" in request and request.get("if_range") != etag:
            results[request_id] = {
                "ok": True,
                "status": 200,
                "ranges": [],
                "ignored": True,
            }
            continue

        try:
            size = request["size"]
            header = request["header"]
            ranges = _parse_set_with_limit(header, size, max_ranges)
        except (ValueError, KeyError, TypeError):
            results[request_id] = {
                "ok": False,
                "status": 400,
                "error": "invalid_range",
            }
            continue

        if not ranges:
            results[request_id] = {
                "ok": False,
                "status": 416,
                "error": "unsatisfiable",
            }
            continue

        if merge_enabled:
            ranges = merge_overlaps(ranges)

        results[request_id] = {
            "ok": True,
            "status": 206,
            "ranges": ranges,
        }

    return results
