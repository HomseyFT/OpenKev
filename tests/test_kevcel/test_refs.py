"""Tests for apps/Kevcel/core/refs.py."""

import pytest

from apps.Kevcel.core.refs import (
    CellRef, RangeRef, column_letters_to_index, index_to_column_letters,
)


class TestColumnLetters:
    @pytest.mark.parametrize("letters,expected", [
        ("A", 0), ("B", 1), ("Z", 25),
        ("AA", 26), ("AZ", 51), ("BA", 52),
        ("ZZ", 701), ("AAA", 702),
    ])
    def test_letters_to_index(self, letters, expected):
        assert column_letters_to_index(letters) == expected

    @pytest.mark.parametrize("index,expected", [
        (0, "A"), (1, "B"), (25, "Z"),
        (26, "AA"), (51, "AZ"), (52, "BA"),
        (701, "ZZ"), (702, "AAA"),
    ])
    def test_index_to_letters(self, index, expected):
        assert index_to_column_letters(index) == expected

    def test_roundtrip(self):
        for i in range(0, 2000):
            assert column_letters_to_index(index_to_column_letters(i)) == i


class TestCellRef:
    def test_parse_simple(self):
        ref = CellRef.parse("A1")
        assert ref.row == 0 and ref.col == 0
        assert not ref.row_absolute and not ref.col_absolute
        assert ref.sheet is None

    def test_parse_absolute(self):
        ref = CellRef.parse("$B$10")
        assert ref.row == 9 and ref.col == 1
        assert ref.row_absolute and ref.col_absolute

    def test_parse_mixed_absolute(self):
        ref = CellRef.parse("A$5")
        assert ref.row == 4 and ref.col == 0
        assert ref.row_absolute and not ref.col_absolute

    def test_parse_with_sheet(self):
        ref = CellRef.parse("Sheet1!C7")
        assert ref.sheet == "Sheet1"
        assert ref.row == 6 and ref.col == 2

    def test_parse_rejects_garbage(self):
        with pytest.raises(ValueError):
            CellRef.parse("not-a-ref")

    def test_roundtrip_preserves_markers(self):
        for src in ["A1", "$A1", "A$1", "$A$1", "AA27", "Sheet1!B2"]:
            assert CellRef.parse(src).to_a1() == src


class TestRangeRef:
    def test_parse_basic(self):
        rng = RangeRef.parse("A1:B3")
        assert rng.bounds == (0, 0, 2, 1)

    def test_iter_cells_preserves_row_then_col_order(self):
        rng = RangeRef.parse("A1:B2")
        cells = rng.iter_cells()
        assert [(c.row, c.col) for c in cells] == [(0, 0), (0, 1), (1, 0), (1, 1)]

    def test_sheet_propagates_to_end(self):
        rng = RangeRef.parse("Sheet1!A1:B2")
        assert rng.sheet == "Sheet1"
        assert rng.end.sheet == "Sheet1"

    def test_reversed_endpoints_are_normalized(self):
        rng = RangeRef.parse("B3:A1")
        # bounds should still be correctly ordered
        assert rng.bounds == (0, 0, 2, 1)
