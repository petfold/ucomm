"""Canonical encoding property tests (issue K-1)."""

from hypothesis import given
from hypothesis import strategies as st

from ucomm.encoding import canonical_bytes, content_hash

json_scalars = st.one_of(st.none(), st.booleans(), st.integers(), st.text())
json_values = st.recursive(
    json_scalars,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(), children, max_size=5),
    ),
    max_leaves=20,
)


@given(json_values)
def test_canonical_bytes_deterministic(value):
    assert canonical_bytes(value) == canonical_bytes(value)


@given(json_values)
def test_content_hash_deterministic(value):
    assert content_hash(value) == content_hash(value)


def test_key_order_does_not_affect_hash():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})


def test_different_values_differ():
    assert content_hash({"a": 1}) != content_hash({"a": 2})


def test_dataclass_field_order_does_not_affect_hash():
    from dataclasses import dataclass

    @dataclass
    class Pair:
        x: int
        y: int

    assert content_hash(Pair(1, 2)) == content_hash({"x": 1, "y": 2})
