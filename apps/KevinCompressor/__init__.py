"""Kevin Compressor — image compression module for OpenKev.

Thin wrapper around the standalone Image-Compression-Project codec that lives
in a sibling directory. All real compression work happens in that backend; the
module here is a PySide6 front-end that invokes the backend via ``subprocess``.
"""
