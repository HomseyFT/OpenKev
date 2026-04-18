"""Tokenizer for Kevcel formula expressions.

Tokenizes an expression *without* the leading ``=`` (callers should strip it
before handing the source over). The parser consumes the produced token stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    NUMBER = auto()
    STRING = auto()
    BOOL = auto()
    IDENT = auto()       # function name or bareword (e.g. TRUE/FALSE before bool lookup)
    REF = auto()         # A1, $B$10, Sheet!A1, $A$1
    RANGE = auto()       # A1:B10, Sheet!A1:B2
    OP = auto()          # + - * / ^ & = <> < > <= >= %
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    pos: int


class TokenizeError(ValueError):
    """Raised when the tokenizer hits an unrecognizable character."""


_BOOL_LITERALS = {"TRUE", "FALSE"}
_TWO_CHAR_OPS = {"<>", "<=", ">="}
_ONE_CHAR_OPS = set("+-*/^&=<>%")


def _is_ref_start(ch: str) -> bool:
    return ch.isalpha() or ch == "$"


def tokenize(source: str) -> list[Token]:
    """Produce a list of tokens for a formula (without leading '=')."""
    tokens: list[Token] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        # Whitespace
        if ch.isspace():
            i += 1
            continue
        # Numbers: 1, 1.5, .5, 1e6
        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            start = i
            has_dot = ch == "."
            i += 1
            while i < n and (source[i].isdigit() or (source[i] == "." and not has_dot)):
                if source[i] == ".":
                    has_dot = True
                i += 1
            if i < n and source[i] in ("e", "E"):
                i += 1
                if i < n and source[i] in ("+", "-"):
                    i += 1
                while i < n and source[i].isdigit():
                    i += 1
            tokens.append(Token(TokenKind.NUMBER, source[start:i], start))
            continue
        # Strings: "quoted" with "" escape
        if ch == '"':
            start = i
            i += 1
            parts: list[str] = []
            while i < n:
                if source[i] == '"':
                    if i + 1 < n and source[i + 1] == '"':
                        parts.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                parts.append(source[i])
                i += 1
            else:
                raise TokenizeError(f"Unterminated string at position {start}")
            tokens.append(Token(TokenKind.STRING, "".join(parts), start))
            continue
        # References / idents / bools / ranges
        if _is_ref_start(ch):
            start = i
            # Gather the first identifier-like segment. This may be a sheet
            # name ("Sheet1") followed by '!', a function name, a bool literal,
            # or the column-letter part of a cell reference.
            while i < n and (source[i].isalnum() or source[i] in ("_", "$")):
                i += 1
            first = source[start:i]

            # Sheet-qualified reference: consume '!' and continue parsing a ref
            if i < n and source[i] == "!":
                i += 1
                sheet_end = i
                while i < n and (source[i].isalnum() or source[i] in ("_", "$")):
                    i += 1
                sub = source[sheet_end:i]
                # Must look like a ref (contains a digit for the row part)
                if not any(c.isdigit() for c in sub):
                    raise TokenizeError(
                        f"Expected cell reference after '{first}!' at {start}"
                    )
                ref_text = f"{first}!{sub}"
                # Optional ':CELL' range extension
                if i < n and source[i] == ":":
                    i += 1
                    range_end_start = i
                    while i < n and (source[i].isalnum() or source[i] in ("_", "$")):
                        i += 1
                    end_text = source[range_end_start:i]
                    if not any(c.isdigit() for c in end_text):
                        raise TokenizeError(
                            f"Expected cell reference after ':' at {range_end_start}"
                        )
                    tokens.append(
                        Token(TokenKind.RANGE, f"{ref_text}:{end_text}", start)
                    )
                    continue
                tokens.append(Token(TokenKind.REF, ref_text, start))
                continue

            # No sheet qualifier. Decide: ref, range, bool, or bare ident.
            # A segment is a cell reference if it either starts with '$'
            # (absolute marker) or starts with a letter *and* contains a digit
            # (i.e. letters followed by a row number like ``A1``).
            starts_with_dollar = first.startswith("$")
            looks_like_ref = starts_with_dollar or (
                first[0].isalpha() and any(c.isdigit() for c in first)
            )
            if looks_like_ref:
                # Check for ':CELL' range extension
                if i < n and source[i] == ":":
                    i += 1
                    range_end_start = i
                    while i < n and (source[i].isalnum() or source[i] in ("_", "$")):
                        i += 1
                    end_text = source[range_end_start:i]
                    if not any(c.isdigit() for c in end_text):
                        raise TokenizeError(
                            f"Expected cell reference after ':' at {range_end_start}"
                        )
                    tokens.append(
                        Token(TokenKind.RANGE, f"{first}:{end_text}", start)
                    )
                    continue
                tokens.append(Token(TokenKind.REF, first, start))
                continue

            # Bool literal
            if first.upper() in _BOOL_LITERALS:
                tokens.append(Token(TokenKind.BOOL, first.upper(), start))
                continue

            # Plain identifier (function name)
            tokens.append(Token(TokenKind.IDENT, first, start))
            continue
        # Punctuation / operators
        if ch == "(":
            tokens.append(Token(TokenKind.LPAREN, "(", i))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token(TokenKind.RPAREN, ")", i))
            i += 1
            continue
        if ch == ",":
            tokens.append(Token(TokenKind.COMMA, ",", i))
            i += 1
            continue
        # Two-char ops
        if i + 1 < n and source[i : i + 2] in _TWO_CHAR_OPS:
            tokens.append(Token(TokenKind.OP, source[i : i + 2], i))
            i += 2
            continue
        if ch in _ONE_CHAR_OPS:
            tokens.append(Token(TokenKind.OP, ch, i))
            i += 1
            continue
        raise TokenizeError(f"Unexpected character {ch!r} at position {i}")
    tokens.append(Token(TokenKind.EOF, "", n))
    return tokens
