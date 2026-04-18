"""Workbook integration tests — formulas, recalc, dep graph, cycles."""

import pytest

from apps.Kevcel.core.values import (
    BoolValue, ErrorCode, ErrorValue, NumberValue, TextValue,
)
from apps.Kevcel.core.workbook import Workbook


def _val(wb: Workbook, a1: str, sheet_idx: int = 0):
    """Fetch a cell's evaluated value by A1 reference."""
    from apps.Kevcel.core.refs import CellRef
    ref = CellRef.parse(a1)
    return wb.get_cell(sheet_idx, ref.row, ref.col).value


class TestLiteralCells:
    def test_number_literal(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "42")
        assert _val(wb, "A1") == NumberValue(42.0)

    def test_text_literal(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "hello")
        assert _val(wb, "A1") == TextValue("hello")

    def test_bool_literal(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "TRUE")
        assert _val(wb, "A1") == BoolValue(True)


class TestArithmetic:
    def test_simple_sum(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "2")
        wb.set_cell_source(0, 0, 1, "3")
        wb.set_cell_source(0, 0, 2, "=A1+B1")
        assert _val(wb, "C1") == NumberValue(5.0)

    def test_div_by_zero(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=1/0")
        v = _val(wb, "A1")
        assert isinstance(v, ErrorValue) and v.code is ErrorCode.DIV_ZERO

    def test_precedence(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=1+2*3")
        assert _val(wb, "A1") == NumberValue(7.0)

    def test_unary_and_percent(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=-5%")
        assert _val(wb, "A1") == NumberValue(-0.05)


class TestFunctions:
    def test_sum_range(self):
        wb = Workbook()
        for r, v in enumerate([1, 2, 3, 4]):
            wb.set_cell_source(0, r, 0, str(v))
        wb.set_cell_source(0, 0, 1, "=SUM(A1:A4)")
        assert _val(wb, "B1") == NumberValue(10.0)

    def test_average_of_empty_is_divzero(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=AVERAGE(B1:B5)")
        v = _val(wb, "A1")
        assert isinstance(v, ErrorValue) and v.code is ErrorCode.DIV_ZERO

    def test_if_branches(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "10")
        wb.set_cell_source(0, 0, 1, "=IF(A1>5,\"big\",\"small\")")
        assert _val(wb, "B1") == TextValue("big")

    def test_concat(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=CONCAT(\"hi\",\" \",\"world\")")
        assert _val(wb, "A1") == TextValue("hi world")

    def test_unknown_function_is_name_error(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=BOGUS(1)")
        v = _val(wb, "A1")
        assert isinstance(v, ErrorValue) and v.code is ErrorCode.NAME

    def test_sqrt_negative_is_num_error(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=SQRT(-1)")
        v = _val(wb, "A1")
        assert isinstance(v, ErrorValue) and v.code is ErrorCode.NUM


class TestRecalc:
    def test_dependent_cell_updates_on_source_change(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "2")
        wb.set_cell_source(0, 0, 1, "=A1*10")
        assert _val(wb, "B1") == NumberValue(20.0)
        wb.set_cell_source(0, 0, 0, "5")
        assert _val(wb, "B1") == NumberValue(50.0)

    def test_diamond_dependency(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "1")            # A1 = 1
        wb.set_cell_source(0, 1, 0, "=A1*2")        # A2 = 2
        wb.set_cell_source(0, 2, 0, "=A1*3")        # A3 = 3
        wb.set_cell_source(0, 3, 0, "=A2+A3")       # A4 = 5
        assert _val(wb, "A4") == NumberValue(5.0)
        wb.set_cell_source(0, 0, 0, "10")
        assert _val(wb, "A2") == NumberValue(20.0)
        assert _val(wb, "A3") == NumberValue(30.0)
        assert _val(wb, "A4") == NumberValue(50.0)

    def test_self_cycle_detected(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=A1+1")
        v = _val(wb, "A1")
        assert isinstance(v, ErrorValue) and v.code is ErrorCode.CIRC

    def test_mutual_cycle_detected(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=B1")
        wb.set_cell_source(0, 0, 1, "=A1")
        assert _val(wb, "A1").code is ErrorCode.CIRC
        assert _val(wb, "B1").code is ErrorCode.CIRC

    def test_breaking_cycle_restores_evaluation(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "=B1")
        wb.set_cell_source(0, 0, 1, "=A1")
        # Break the cycle by overwriting B1 with a literal
        wb.set_cell_source(0, 0, 1, "42")
        assert _val(wb, "B1") == NumberValue(42.0)
        assert _val(wb, "A1") == NumberValue(42.0)


class TestSheetManagement:
    def test_add_and_rename_sheet(self):
        wb = Workbook()
        idx = wb.add_sheet("Taxes")
        assert wb.sheets[idx].name == "Taxes"
        wb.rename_sheet(idx, "Revenue")
        assert wb.sheets[idx].name == "Revenue"

    def test_remove_sheet_requires_at_least_one(self):
        wb = Workbook()
        wb.add_sheet()
        wb.remove_sheet(1)
        with pytest.raises(ValueError):
            wb.remove_sheet(0)

    def test_cross_sheet_ref_is_ref_error(self):
        """v1 policy: sheet-qualified refs are intentionally unsupported."""
        wb = Workbook(["Sheet1", "Sheet2"])
        wb.set_cell_source(1, 0, 0, "100")
        wb.set_cell_source(0, 0, 0, "=Sheet2!A1")
        v = _val(wb, "A1", sheet_idx=0)
        assert isinstance(v, ErrorValue) and v.code is ErrorCode.REF
