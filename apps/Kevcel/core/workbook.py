"""Workbook / Sheet / Cell model + formula recalc engine.

Design goals:

* **Sparse storage.** Only cells the user has touched occupy memory. Logical
  grid dimensions auto-grow as needed.
* **Separation of concerns.** Evaluation is delegated to ``evaluator`` which
  receives an adapter implementing :class:`EvalContext`. The workbook doesn't
  know anything about the parser/evaluator internals.
* **Targeted recalc.** On edit we compute the reverse-closure of the edited
  cell, topologically order it, and re-evaluate only that subset. If a cycle
  is detected the participants are marked ``#CIRC!``.
* **Observability.** A minimal listener interface lets the Qt layer react to
  cell/structure changes without coupling core state to Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

from apps.Kevcel.core.evaluator import evaluate
from apps.Kevcel.core.parser import ParseError, extract_refs, is_formula, parse
from apps.Kevcel.core.refs import CellRef, RangeRef
from apps.Kevcel.core.styles import DEFAULT_STYLE, CellStyle
from apps.Kevcel.core.values import (
    EmptyValue, ErrorCode, ErrorValue, Value, from_literal,
)


# ---- Cell / Sheet ---------------------------------------------------------


@dataclass
class Cell:
    """A single cell. ``source`` is the authoritative user input."""

    source: str = ""
    value: Value = field(default_factory=EmptyValue)
    style: CellStyle = DEFAULT_STYLE

    @property
    def is_formula(self) -> bool:
        return is_formula(self.source)


# Cell-identifier tuple used internally across the workbook: (sheet_idx, row, col).
CellId = tuple[int, int, int]


@dataclass
class Sheet:
    name: str
    cells: dict[tuple[int, int], Cell] = field(default_factory=dict)
    row_heights: dict[int, int] = field(default_factory=dict)
    col_widths: dict[int, int] = field(default_factory=dict)
    #: Logical viewport size. Grows automatically when cells are touched.
    logical_rows: int = 100
    logical_cols: int = 26

    def get(self, row: int, col: int) -> Cell | None:
        return self.cells.get((row, col))

    def get_or_empty(self, row: int, col: int) -> Cell:
        return self.cells.get((row, col), Cell())

    def ensure_bounds(self, row: int, col: int) -> None:
        if row + 1 > self.logical_rows:
            self.logical_rows = row + 1
        if col + 1 > self.logical_cols:
            self.logical_cols = col + 1


# ---- Workbook listener protocol ------------------------------------------


Listener = Callable[["WorkbookEvent"], None]


@dataclass(frozen=True)
class WorkbookEvent:
    """Emitted whenever the workbook's observable state changes."""

    kind: str                        # "cell", "structure", "sheet_renamed"
    sheet_idx: int | None = None
    cells: tuple[tuple[int, int], ...] = ()  # (row, col) pairs affected


# ---- Workbook -------------------------------------------------------------


class Workbook:
    """A collection of :class:`Sheet` instances with a live formula engine."""

    def __init__(self, sheet_names: list[str] | None = None) -> None:
        names = sheet_names or ["Sheet1"]
        self.sheets: list[Sheet] = [Sheet(name=n) for n in names]
        self.active_index: int = 0

        # Dependency graph keyed by (sheet_idx, row, col).
        # forward[c] = set of cells c *reads*
        # reverse[c] = set of cells that *read* c
        self._forward: dict[CellId, set[CellId]] = {}
        self._reverse: dict[CellId, set[CellId]] = {}

        # Parse cache: AST per formula cell, invalidated on source edit.
        self._ast_cache: dict[CellId, object | None] = {}

        self._listeners: list[Listener] = []

    # ----- Listener management -------------------------------------------

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Register a listener; returns an unsubscribe callable."""
        self._listeners.append(listener)

        def _unsub() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _unsub

    def _emit(self, event: WorkbookEvent) -> None:
        for listener in list(self._listeners):
            listener(event)

    # ----- Sheet management ----------------------------------------------

    @property
    def active_sheet(self) -> Sheet:
        return self.sheets[self.active_index]

    def add_sheet(self, name: str | None = None) -> int:
        existing = {s.name for s in self.sheets}
        if name is None or name in existing:
            base = name or "Sheet"
            i = len(self.sheets) + 1
            while f"{base}{i}" in existing:
                i += 1
            name = f"{base}{i}"
        self.sheets.append(Sheet(name=name))
        idx = len(self.sheets) - 1
        self._emit(WorkbookEvent(kind="structure"))
        return idx

    def remove_sheet(self, index: int) -> None:
        if len(self.sheets) <= 1:
            raise ValueError("A workbook must contain at least one sheet")
        # Drop dependency/AST state for the removed sheet.
        self._purge_sheet_state(index)
        del self.sheets[index]
        if self.active_index >= len(self.sheets):
            self.active_index = len(self.sheets) - 1
        self._emit(WorkbookEvent(kind="structure"))

    def rename_sheet(self, index: int, name: str) -> None:
        if not name:
            raise ValueError("Sheet name may not be empty")
        if any(s.name == name for i, s in enumerate(self.sheets) if i != index):
            raise ValueError(f"A sheet named {name!r} already exists")
        self.sheets[index].name = name
        self._emit(WorkbookEvent(kind="sheet_renamed", sheet_idx=index))

    def set_active(self, index: int) -> None:
        if not 0 <= index < len(self.sheets):
            raise IndexError(index)
        self.active_index = index

    # ----- Cell accessors -------------------------------------------------

    def get_cell(self, sheet_idx: int, row: int, col: int) -> Cell:
        return self.sheets[sheet_idx].get_or_empty(row, col)

    def set_cell_source(self, sheet_idx: int, row: int, col: int, source: str) -> None:
        """Set a cell's raw source (text or '=formula'); triggers recalc."""
        sheet = self.sheets[sheet_idx]
        key = (row, col)
        cid: CellId = (sheet_idx, row, col)
        if source == "":
            # Clearing a cell. Preserve style if the cell existed.
            existing = sheet.cells.get(key)
            if existing is None:
                return
            # Rebuild as empty but keep style.
            sheet.cells[key] = Cell(source="", value=EmptyValue(), style=existing.style)
        else:
            existing = sheet.cells.get(key)
            style = existing.style if existing else DEFAULT_STYLE
            sheet.cells[key] = Cell(source=source, value=EmptyValue(), style=style)
            sheet.ensure_bounds(row, col)

        self._refresh_dependencies(cid)
        affected = self._recalc_starting_from(cid)
        # Always include the edited cell itself in the notification.
        self._emit(WorkbookEvent(kind="cell", sheet_idx=sheet_idx, cells=tuple(
            (r, c) for (s, r, c) in affected if s == sheet_idx
        )))

    def set_cell_style(self, sheet_idx: int, row: int, col: int, style: CellStyle) -> None:
        sheet = self.sheets[sheet_idx]
        key = (row, col)
        cell = sheet.cells.get(key, Cell())
        sheet.cells[key] = replace(cell, style=style)
        sheet.ensure_bounds(row, col)
        self._emit(WorkbookEvent(kind="cell", sheet_idx=sheet_idx, cells=(key,)))

    def update_cell_style(
        self,
        sheet_idx: int,
        row: int,
        col: int,
        mutate: Callable[[CellStyle], CellStyle],
    ) -> None:
        """Apply a function that returns a new CellStyle for the given cell."""
        current = self.get_cell(sheet_idx, row, col).style
        self.set_cell_style(sheet_idx, row, col, mutate(current))

    # ----- Dependency management -----------------------------------------

    def _refresh_dependencies(self, cid: CellId) -> None:
        """Re-parse the cell's formula and rebuild graph edges for it."""
        sheet_idx, row, col = cid
        cell = self.sheets[sheet_idx].get(row, col)

        # Drop old forward edges and mirror-updates on reverse edges.
        for dep in self._forward.get(cid, set()):
            self._reverse.get(dep, set()).discard(cid)
        self._forward.pop(cid, None)
        self._ast_cache.pop(cid, None)

        if cell is None or not cell.is_formula:
            return
        try:
            ast = parse(cell.source[1:])  # strip '='
        except ParseError:
            # Leave the AST cache empty; the recalc pass will flag #NAME?/#VALUE!.
            self._ast_cache[cid] = None
            return
        self._ast_cache[cid] = ast
        deps_refs = extract_refs(ast)
        forward: set[CellId] = set()
        for r in deps_refs:
            if r.sheet:
                continue  # cross-sheet not supported yet; ignore for dep graph
            forward.add((sheet_idx, r.row, r.col))
        self._forward[cid] = forward
        for dep in forward:
            self._reverse.setdefault(dep, set()).add(cid)

    def _purge_sheet_state(self, sheet_idx: int) -> None:
        to_purge = [c for c in self._forward if c[0] == sheet_idx]
        for cid in to_purge:
            for dep in self._forward.get(cid, set()):
                self._reverse.get(dep, set()).discard(cid)
            self._forward.pop(cid, None)
            self._ast_cache.pop(cid, None)
        # Also scrub any edges pointing into the removed sheet.
        for cid, deps in list(self._forward.items()):
            filtered = {d for d in deps if d[0] != sheet_idx}
            if filtered != deps:
                self._forward[cid] = filtered
        for cid in [c for c in self._reverse if c[0] == sheet_idx]:
            self._reverse.pop(cid, None)

    # ----- Recalculation --------------------------------------------------

    def _recalc_starting_from(self, cid: CellId) -> set[CellId]:
        """Recompute ``cid`` and every cell that transitively depends on it.

        Returns the set of cell ids actually touched (useful for UI updates).
        """
        # Reverse-closure: cid plus all cells reachable along reverse edges.
        closure = self._reverse_closure(cid)
        order, cyclic = _topological_order(closure, self._forward)

        for c in cyclic:
            self._assign_error(c, ErrorValue(ErrorCode.CIRC))
        for c in order:
            self._recalculate_one(c)

        return closure

    def _reverse_closure(self, start: CellId) -> set[CellId]:
        seen: set[CellId] = set()
        stack: list[CellId] = [start]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self._reverse.get(cur, set()))
        return seen

    def _recalculate_one(self, cid: CellId) -> None:
        sheet_idx, row, col = cid
        sheet = self.sheets[sheet_idx]
        cell = sheet.get(row, col)
        if cell is None:
            return
        if not cell.is_formula:
            # Plain value cells: coerce source text to a Value.
            sheet.cells[(row, col)] = replace(cell, value=from_literal(cell.source))
            return
        ast = self._ast_cache.get(cid)
        if ast is None:
            # Parse failed earlier.
            sheet.cells[(row, col)] = replace(cell, value=ErrorValue(ErrorCode.NAME))
            return
        ctx = _SheetContext(self, sheet_idx)
        new_value = evaluate(ast, ctx)
        sheet.cells[(row, col)] = replace(cell, value=new_value)

    def _assign_error(self, cid: CellId, value: Value) -> None:
        sheet_idx, row, col = cid
        sheet = self.sheets[sheet_idx]
        cell = sheet.get(row, col)
        if cell is None:
            return
        sheet.cells[(row, col)] = replace(cell, value=value)

    # ----- Helpers for .kev save/load -------------------------------------

    def recalculate_all(self) -> None:
        """Re-parse + re-evaluate every cell (used after loading a file)."""
        # Clear dep graph, then walk all cells and re-register formulas first.
        self._forward.clear()
        self._reverse.clear()
        self._ast_cache.clear()
        for s_idx, sheet in enumerate(self.sheets):
            for (r, c), _ in sheet.cells.items():
                self._refresh_dependencies((s_idx, r, c))
        # Now evaluate in topological order across the whole graph.
        all_cells: set[CellId] = {
            (s_idx, r, c)
            for s_idx, sheet in enumerate(self.sheets)
            for (r, c) in sheet.cells
        }
        order, cyclic = _topological_order(all_cells, self._forward)
        for c in cyclic:
            self._assign_error(c, ErrorValue(ErrorCode.CIRC))
        for c in order:
            self._recalculate_one(c)
        self._emit(WorkbookEvent(kind="structure"))


# ---- EvalContext adapter --------------------------------------------------


class _SheetContext:
    """Adapter that resolves refs/ranges against a single sheet in the workbook."""

    def __init__(self, workbook: Workbook, sheet_idx: int) -> None:
        self._wb = workbook
        self._sheet_idx = sheet_idx

    def get_cell_value(self, ref: CellRef) -> Value:
        sheet = self._wb.sheets[self._sheet_idx]
        cell = sheet.get(ref.row, ref.col)
        if cell is None:
            return EmptyValue()
        return cell.value

    def get_range_values(self, rng: RangeRef) -> list[list[Value]]:
        sheet = self._wb.sheets[self._sheet_idx]
        top, left, bottom, right = rng.bounds
        grid: list[list[Value]] = []
        for r in range(top, bottom + 1):
            row: list[Value] = []
            for c in range(left, right + 1):
                cell = sheet.get(r, c)
                row.append(cell.value if cell else EmptyValue())
            grid.append(row)
        return grid


# ---- Topological sort with cycle detection -------------------------------


def _topological_order(
    nodes: set[CellId],
    forward: dict[CellId, set[CellId]],
) -> tuple[list[CellId], set[CellId]]:
    """Kahn-style topological sort over the subgraph induced by ``nodes``.

    Only edges whose endpoints are both in ``nodes`` participate. Returns the
    ordered list of cells plus the set of cells that participated in a cycle
    (these are excluded from ``order`` and should be flagged ``#CIRC!``).
    """
    # Build induced adjacency in the direction "needs before" -> "needs after",
    # where an edge a -> b means "b depends on a" (b reads a).
    in_deg: dict[CellId, int] = {c: 0 for c in nodes}
    successors: dict[CellId, list[CellId]] = {c: [] for c in nodes}
    for c in nodes:
        for dep in forward.get(c, ()):
            if dep in nodes:
                successors[dep].append(c)
                in_deg[c] += 1

    ready = [c for c, d in in_deg.items() if d == 0]
    order: list[CellId] = []
    while ready:
        cur = ready.pop()
        order.append(cur)
        for nxt in successors.get(cur, ()):
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                ready.append(nxt)
    cyclic = {c for c, d in in_deg.items() if d > 0}
    return order, cyclic
