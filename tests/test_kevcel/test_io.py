"""Round-trip tests for Kevcel I/O."""

from __future__ import annotations

import pytest

from apps.Kevcel.core.styles import CellStyle, HAlign
from apps.Kevcel.core.values import NumberValue, TextValue
from apps.Kevcel.core.workbook import Workbook
from apps.Kevcel.io.csv_io import export_csv, import_csv
from apps.Kevcel.io.html_io import sheet_to_html
from apps.Kevcel.io.kev_format import load_workbook, save_workbook, sniff_kev_file


def _seed(wb: Workbook) -> None:
    wb.set_cell_source(0, 0, 0, "1")
    wb.set_cell_source(0, 0, 1, "2")
    wb.set_cell_source(0, 0, 2, "=A1+B1")
    wb.set_cell_source(0, 1, 0, "hello")
    wb.set_cell_style(0, 1, 0, CellStyle(bold=True, h_align=HAlign.CENTER))


class TestKevFormat:
    def test_save_and_load_roundtrip(self, tmp_path):
        wb = Workbook()
        _seed(wb)
        path = tmp_path / "demo.kev"
        save_workbook(wb, path)

        loaded = load_workbook(path)
        assert loaded.get_cell(0, 0, 2).value == NumberValue(3.0)
        assert loaded.get_cell(0, 1, 0).value == TextValue("hello")
        assert loaded.get_cell(0, 1, 0).style.bold is True
        assert loaded.get_cell(0, 1, 0).style.h_align is HAlign.CENTER

    def test_sniff_returns_sheet_for_kevcel_file(self, tmp_path):
        wb = Workbook()
        _seed(wb)
        path = tmp_path / "demo.kev"
        save_workbook(wb, path)
        assert sniff_kev_file(path) == "sheet"

    def test_sniff_returns_document_for_weiword_file(self, tmp_path):
        doc_path = tmp_path / "doc.kev"
        doc_path.write_text("<!-- kev:1.0 -->\n<html></html>", encoding="utf-8")
        assert sniff_kev_file(doc_path) == "document"

    def test_load_rejects_missing_header(self, tmp_path):
        bad = tmp_path / "bad.kev"
        bad.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError):
            load_workbook(bad)

    def test_multiple_sheets_persist(self, tmp_path):
        wb = Workbook(["A", "B"])
        wb.set_cell_source(0, 0, 0, "1")
        wb.set_cell_source(1, 0, 0, "=2*2")
        path = tmp_path / "multi.kev"
        save_workbook(wb, path)

        loaded = load_workbook(path)
        assert [s.name for s in loaded.sheets] == ["A", "B"]
        assert loaded.get_cell(1, 0, 0).value == NumberValue(4.0)


class TestCsv:
    def test_export_writes_displayed_values(self, tmp_path):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "hi")
        wb.set_cell_source(0, 0, 1, "=1+2")
        path = tmp_path / "out.csv"
        export_csv(wb.active_sheet, path)
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        assert content == "hi,3\n"

    def test_import_populates_cells(self, tmp_path):
        path = tmp_path / "in.csv"
        path.write_text("1,2,3\nfoo,bar,baz\n", encoding="utf-8")
        wb = import_csv(path)
        assert wb.get_cell(0, 0, 0).value == NumberValue(1.0)
        assert wb.get_cell(0, 1, 2).value == TextValue("baz")


class TestHtml:
    def test_empty_sheet_produces_empty_table(self):
        wb = Workbook()
        assert sheet_to_html(wb.active_sheet) == (
            '<table class="kevcel-sheet"></table>'
        )

    def test_contains_values_and_styles(self):
        wb = Workbook()
        _seed(wb)
        html = sheet_to_html(wb.active_sheet)
        assert "<table" in html and "</table>" in html
        assert "hello" in html
        assert "font-weight:bold" in html
        assert "text-align:center" in html

    def test_with_headers_adds_column_labels(self):
        wb = Workbook()
        wb.set_cell_source(0, 0, 0, "x")
        html = sheet_to_html(wb.active_sheet, include_headers=True)
        assert ">A<" in html
        assert ">1<" in html
