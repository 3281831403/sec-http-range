import pytest

from byterange.parse import (
    clamp,
    merge_overlaps,
    parse_set,
    parse_spec,
    parse_unit,
    range_batch,
    satisfiable,
    sort_specs,
)


def test_defect_01_suffix_range_uses_tail_bytes():
    spec = parse_spec("-4", 10)
    assert spec == {"start": 6, "end": 9}


def test_defect_02_inclusive_end_keeps_last_byte():
    spec = parse_spec("2-6", 10)
    assert spec == {"start": 2, "end": 6}
    assert spec["end"] - spec["start"] + 1 == 5


def test_defect_03_start_at_size_is_unsatisfiable():
    assert satisfiable([{"start": 10, "end": 10}], 10) is False


def test_defect_04_end_beyond_size_is_clamped():
    assert clamp({"start": 5, "end": 50}, 10) == {"start": 5, "end": 9}


def test_defect_05_negative_start_rejected():
    with pytest.raises(ValueError):
        parse_spec("-5-10", 20)


def test_defect_06_too_many_ranges_rejected():
    header = "bytes=" + ",".join(f"{index}-{index}" for index in range(17))
    with pytest.raises(ValueError):
        parse_set(header, 100)


def test_defect_07_overlapping_ranges_merged():
    specs = [
        {"start": 10, "end": 19},
        {"start": 0, "end": 4},
        {"start": 2, "end": 12},
        {"start": 20, "end": 21},
    ]
    assert merge_overlaps(specs) == [{"start": 0, "end": 21}]


def test_defect_08_multi_range_keeps_request_order():
    specs = [
        {"start": 0, "end": 1},
        {"start": 100, "end": 119},
        {"start": 50, "end": 54},
    ]
    assert sort_specs(specs) == specs


def test_defect_09_unknown_unit_rejected():
    assert parse_unit("BYTES") == "bytes"
    with pytest.raises(ValueError):
        parse_unit("items")


def test_defect_10_zero_length_is_unsatisfiable():
    assert satisfiable([{"start": 0, "end": 0}], 0) is False
    assert parse_set("bytes=0-0", 0) == []


def test_single_closed_range_parses():
    assert parse_spec("0-0", 1) == {"start": 0, "end": 0}
    assert parse_spec("3-7", 10) == {"start": 3, "end": 7}


def test_suffix_range_reaches_end_byte():
    assert parse_spec("-3", 10) == {"start": 7, "end": 9}
    assert parse_spec("-20", 10) == {"start": 0, "end": 9}


def test_out_of_bounds_range_is_clamped():
    clamped = clamp({"start": 8, "end": 99}, 10)
    assert clamped == {"start": 8, "end": 9}
    assert satisfiable([clamp({"start": 10, "end": 10}, 10)], 10) is False


def test_multi_range_preserves_request_order():
    ranges = parse_set("bytes=5-6,0-1,3-3", 10)
    assert ranges == [
        {"start": 5, "end": 6},
        {"start": 0, "end": 1},
        {"start": 3, "end": 3},
    ]


def test_two_batches_independent():
    requests = [
        {"id": "a", "header": "bytes=0-1", "size": 8},
        {"id": "b", "header": "bytes=-2", "size": 8},
        {"id": "bad", "header": "items=0-1", "size": 8},
    ]
    policy = {"max_ranges": 4, "merge": True}

    first = range_batch(requests, policy)
    second = range_batch(requests, policy)

    assert first == second
    assert first["a"]["status"] == 206
    assert first["a"]["ranges"] == parse_set("bytes=0-1", 8)
    assert first["b"]["status"] == 206
    assert first["b"]["ranges"] == parse_set("bytes=-2", 8)
    assert first["bad"]["ok"] is False
    assert first["bad"]["status"] == 400
    assert first["bad"]["error"] == "invalid_range"