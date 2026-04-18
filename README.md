# OpenKev

A desktop suite of small "Kev-branded" productivity apps, written in Python
with [PySide6](https://doc.qt.io/qtforpython-6/). Each app is a self-contained
module that can run standalone today and will be embedded inside a shared
tabbed navigator later.

## Status at a glance

| Module             | Purpose                                     | State                              |
| ------------------ | ------------------------------------------- | ---------------------------------- |
| Wei Word           | Rich-text editor for `.kev` documents       | **Working** (launches, edits, saves, exports) |
| KevPilot (`KevAI`) | Ollama-backed AI chat                       | **Working** (real token streaming) |
| KevPoint           | PowerPoint clone                            | Not started                        |
| Kevcel             | Excel clone                                 | **Working** (formulas, sheets, styles, CSV/XLSX/PDF/HTML I/O) |
| Kev Teams          | SimpleX-based messaging                     | Not started                        |
| Kev Calendar       | Calendar                                    | Not started                        |
| Kevin Compressor   | Image compressor (DCT + Huffman, grayscale) | **Working** (PySide6 front-end over external compression.py backend) |
| Navigator shell    | Top-level app switcher                      | Not started (`apps/main.py` empty) |

## Repository layout

```
OpenKev/
├── README.md               ← you are here
├── requirements.txt
└── apps/
    ├── __init__.py
    ├── main.py             ← future navigator entry point (empty today)
    ├── kev_module.py       ← abstract base class for every app module
    ├── WeiWord/
    │   ├── main.py         ← standalone launcher (python -m apps.WeiWord.main)
    │   └── weiword.py      ← WeiWord module (KevModule subclass)
    ├── KevAI/
    │   ├── main.py         ← standalone launcher (python -m apps.KevAI.main)
    │   ├── kevai.py        ← KevPilot module (KevModule subclass)
    │   ├── chatwindow.py   ← scrollable transcript widget
    │   ├── chatbar.py      ← input bar + send button
    │   ├── message.py      ← chat bubble widget
    │   ├── handleai.py     ← QThread worker that streams Ollama output
    │   └── static/kev.png  ← default avatar asset
    └── Kevcel/
        ├── main.py         ← standalone launcher (python -m apps.Kevcel.main)
        ├── kevcel.py       ← Kevcel module (KevModule subclass)
        ├── core/           ← pure-Python spreadsheet engine
        │   ├── refs.py     ← A1 parsing + column/row conversions
        │   ├── values.py   ← Value types (Number/Text/Bool/DateTime/Error)
        │   ├── styles.py   ← immutable CellStyle + number formatting
        │   ├── tokenizer.py← formula tokenizer
        │   ├── parser.py   ← recursive-descent parser producing an AST
        │   ├── evaluator.py← AST evaluator + EvalContext protocol
        │   ├── functions.py← built-in function registry (SUM, IF, …)
        │   └── workbook.py ← Workbook/Sheet/Cell + dep graph + recalc
        ├── io/             ← format conversion
        │   ├── kev_format.py ← .kev spreadsheet serializer
        │   ├── csv_io.py   ← CSV import/export
        │   ├── xlsx_io.py  ← openpyxl-backed XLSX import/export
        │   ├── html_io.py  ← static HTML table renderer
        │   └── pdf_io.py   ← QTextDocument + QPrinter PDF export
        └── ui/             ← PySide6 adapters
            ├── table_model.py ← QAbstractTableModel over a Sheet
            ├── formula_bar.py ← active-cell reference + formula editor
            ├── toolbar.py     ← formatting toolbar
            └── workbook_view.py ← per-workbook container
    └── KevinCompressor/
        ├── main.py         ← standalone launcher (python -m apps.KevinCompressor.main)
        ├── kevin_compressor.py ← KevModule subclass (Compress/Decompress tabs)
        └── backend.py      ← subprocess wrapper + QThread worker over compression.py

tests/                      ← pytest suite (see "Testing" below)
├── conftest.py
├── test_kevcel/            ← Kevcel core + I/O
└── test_kevin_compressor/  ← Kevin Compressor backend adapter
```

## Module contract

Every app subclasses `apps.kev_module.KevModule`, which is an abstract
`QWidget` enforcing two methods:

* `open_files` — property returning the list of absolute paths currently open
  in this module (untitled docs excluded). Used by the navigator to prevent
  opening the same file twice.
* `focus_file(filepath)` — bring the view for that file into focus. No-op for
  modules that don't deal with files (e.g. KevPilot).

Missing implementations raise `TypeError` at instantiation time. The base
combines `ABCMeta` with Qt's shiboken metaclass and adds a manual
`__abstractmethods__`-style check in `__init__`, because shiboken's metaclass
swallows the normal ABC guard.

### Per-module conventions

Every app folder contains:

* `main.py` — standalone entry point wrapping the module in a `QMainWindow`.
  Launch with `python -m apps.<AppName>.main`.
* `<appname>.py` — the `KevModule` subclass itself (no `QMainWindow`), so the
  future navigator can embed it directly.

## Running

```bash
# Install deps (use a virtualenv)
pip install -r requirements.txt

# Wei Word
python -m apps.WeiWord.main

# KevPilot — requires `ollama serve` running locally with a pulled model
ollama pull llama3.2:latest
ollama serve &
python -m apps.KevAI.main

# Kevcel
python -m apps.Kevcel.main

# Kevin Compressor — requires the external codec (see below)
python -m apps.KevinCompressor.main
```

## Testing

A `pytest` suite lives under `tests/`. Coverage currently includes the full
Kevcel core engine + I/O layer and the Kevin Compressor backend adapter,
including an end-to-end compress/decompress round-trip that is auto-skipped
if the external codec isn't installed. New apps should add their own
`tests/test_<name>/` subdirectory as they land.

```bash
python -m pytest tests          # run everything
python -m pytest tests/test_kevcel -v
```

## File format: `.kev`

All OpenKev apps share the `.kev` extension. The loader sniffs the first
line to determine the variant:

* **WeiWord document** — `<!-- kev:1.0 -->` on line 1, followed by HTML.
* **Kevcel spreadsheet** — `<!-- kev-sheet:1.0 -->` on line 1, followed by
  UTF-8 JSON describing the workbook.

### WeiWord `.kev`
```
<!-- kev:1.0 -->
<!DOCTYPE html><html>…</html>
```
* Images embedded as base64 `data:` URIs inside the HTML.
* Spreadsheets pasted in from Kevcel arrive as static `<table>` HTML.
* On load, the header is stripped before handing the HTML to Qt.

### Kevcel `.kev`
```
<!-- kev-sheet:1.0 -->
{ "version": "1.0", "active": 0, "sheets": [ ... ] }
```
* JSON body stores workbook metadata, sparse cells (row/col/source/style),
  row heights, and column widths.
* Cached evaluated values are **not** serialized — the engine re-evaluates
  every formula on load, so disk state cannot drift from engine semantics.
* Use `apps.Kevcel.io.kev_format.sniff_kev_file(path)` to detect the variant
  before opening.

## WeiWord behavior

* Opens with one blank untitled sub-tab.
* Multiple open documents are shown as sub-tabs inside the WeiWord module.
* Unsaved-changes prompt is per document (not per app).
* All saving is manual — no autosave.
* `WeiWord.open_files` exposes the list of currently open saved documents.
* Exports: PDF via `QPrinter`; DOCX via `python-docx`.

## Kevcel behavior

* Multiple workbooks open as sibling tabs; each workbook owns inner sheet
  tabs (Excel-style).
* Per-cell styling: bold/italic/underline, font family/size, text & fill
  color, horizontal alignment, plus number formats (General / Integer /
  Decimal / Percent / Currency / Date / Date+Time / Text).
* Tier-2 formula engine: arithmetic, comparisons, `&` concatenation, ranges,
  right-associative `^`, and the built-in function set
  `SUM AVERAGE MIN MAX COUNT COUNTA ABS ROUND SQRT POW MOD INT IF AND OR NOT
  CONCAT LEN UPPER LOWER TRIM LEFT RIGHT MID TODAY NOW`.
* Dependency-graph-driven recalc: editing a cell re-evaluates only its
  reverse-closure. Cycles produce `#CIRC!` on every participant until broken.
* Cross-sheet references (`Sheet2!A1`) parse but evaluate to `#REF!` — v1
  does not yet execute them.
* Imports: CSV, XLSX (via `openpyxl`). Exports: `.kev`, CSV, XLSX, PDF, and
  an HTML table fragment intended for embedding inside a WeiWord document.
* Unsaved-changes prompt is per workbook; dirty workbooks show a ``*``
  marker on their outer tab title.

## Kevin Compressor behavior

Kevin Compressor is a thin **front-end** over the pre-existing
`Image-Compression-Project/compression.py` codec. OpenKev doesn't re-implement
compression — it shells out to that script via `subprocess`.

* Two inner tabs: **Compress** and **Decompress**.
* Compress tab offers a format picker (`ICJ` Huffman container or raw `NPZ`)
  and a `[1, 100]` JPEG-style quality slider.
* Every job runs on a `QThread` so the UI stays responsive on large images.
* After a successful compression, the file is automatically round-tripped
  back to a temp PNG so the "Reconstructed" preview shows the actual lossy
  output at the chosen quality.
* The backend is **grayscale-only** — color inputs are flattened to `L` mode
  by the codec; this is surfaced in the banner.

### Backend path resolution

The module looks for `compression.py` in this order:

1. `$KEVIN_COMPRESSOR_SCRIPT` environment variable (absolute path).
2. `~/Coding_Projects/Image-Compression-Project/compression.py` (default).
3. `<sibling-of-OpenKev>/Image-Compression-Project/compression.py`.

If none exist, the status bar shows an actionable error describing where it
looked. Set `KEVIN_COMPRESSOR_SCRIPT` to force a specific path.

## KevPilot behavior

* Single-turn or multi-turn chat against a local Ollama server
  (`http://127.0.0.1:11434` by default).
* Real token streaming — each delta is emitted via `AIWorker.token_received`
  and appended to the pending message bubble.
* Connection failures (Ollama not running) are surfaced inline in the chat as
  a red ⚠️ bubble rather than a Python traceback.
* Model is configurable per `ChatBar` instance; default is `llama3.2:latest`.

## Notes / known follow-ups

* `apps/main.py` (the navigator) is the next architectural piece. It will host
  `KevModule` instances as top-level tabs and coordinate `open_files` /
  `focus_file` calls across modules. The navigator should use
  `apps.Kevcel.io.kev_format.sniff_kev_file` to dispatch `.kev` files to the
  right module.
* The `reportlab` requirement is still listed in `requirements.txt` but
  WeiWord currently uses Qt's built-in PDF pipeline (which preserves rich
  formatting, inline images, etc). Re-evaluate before adding it as a hard dep.
* `python-docx` export does not yet carry embedded images through to DOCX.
* Kevcel deliberately omits merged cells, borders, named ranges, array
  formulas, and true cross-sheet evaluation in v1. The architecture leaves
  seams for each of these without baking them into the initial release.
* WeiWord's Insert-Spreadsheet flow isn't wired up yet; `Kevcel.sheet_to_html`
  already produces the embeddable fragment when needed.

## Gotchas encountered (for future maintainers)

* **`QTextCharFormat.fontFamily()` segfaults in PySide6 6.11.** Always use the
  plural `fontFamilies()` / `setFontFamilies([...])` API. Observed as an
  instant core dump on WeiWord startup before the switch.
* **Shiboken's metaclass bypasses `ABCMeta`.** The abstract-method check in
  `KevModule.__init__` compensates; don't assume `__abstractmethods__` is
  populated on a QWidget-derived class.
* **Old `Qt.X` enum aliases are deprecated** in Qt 6 and slated for removal.
  Always fully qualify: `Qt.ScrollBarPolicy.ScrollBarAlwaysOff`,
  `QSizePolicy.Policy.Expanding`, `Qt.CursorShape.PointingHandCursor`, etc.
