"""Recursive-descent parser that produces a typed AST.

Grammar (Excel-ish precedence, lowest to highest):

    expr        ::= compare
    compare     ::= concat ( ( '=' | '<>' | '<' | '>' | '<=' | '>=' ) concat )*
    concat      ::= additive ( '&' additive )*
    additive    ::= multiplicative ( ('+' | '-') multiplicative )*
    multiplicative ::= exponent ( ('*' | '/') exponent )*
    exponent    ::= percent ( '^' exponent )?           # right-assoc
    percent     ::= unary ( '%' )*
    unary       ::= ('+' | '-') unary | primary
    primary     ::= NUMBER | STRING | BOOL | REF | RANGE
                  | IDENT '(' args? ')'
                  | '(' expr ')'
    args        ::= expr ( ',' expr )*
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from apps.Kevcel.core.refs import CellRef, RangeRef
from apps.Kevcel.core.tokenizer import Token, TokenKind, tokenize


# ---- AST node types -------------------------------------------------------


@dataclass(frozen=True)
class NumberLit:
    value: float


@dataclass(frozen=True)
class StringLit:
    value: str


@dataclass(frozen=True)
class BoolLit:
    value: bool


@dataclass(frozen=True)
class RefNode:
    ref: CellRef


@dataclass(frozen=True)
class RangeNode:
    range: RangeRef


@dataclass(frozen=True)
class UnaryOp:
    op: str
    operand: "Expr"


@dataclass(frozen=True)
class BinOp:
    op: str
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class FunctionCall:
    name: str
    args: tuple["Expr", ...] = field(default_factory=tuple)


Expr = Union[
    NumberLit, StringLit, BoolLit, RefNode, RangeNode,
    UnaryOp, BinOp, FunctionCall,
]


class ParseError(ValueError):
    """Raised when the parser cannot consume the token stream."""


# ---- Parser ---------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # Stream helpers
    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _match(self, kind: TokenKind, *texts: str) -> Token | None:
        tok = self._peek()
        if tok.kind is not kind:
            return None
        if texts and tok.text not in texts:
            return None
        return self._advance()

    def _expect(self, kind: TokenKind, *texts: str) -> Token:
        tok = self._match(kind, *texts)
        if tok is None:
            actual = self._peek()
            raise ParseError(
                f"Expected {kind.name}{' ' + str(texts) if texts else ''} at "
                f"position {actual.pos}, got {actual.kind.name} {actual.text!r}"
            )
        return tok

    # Grammar productions (ordered: weakest to strongest precedence)
    def expr(self) -> Expr:
        return self._compare()

    def _compare(self) -> Expr:
        left = self._concat()
        while True:
            tok = self._match(TokenKind.OP, "=", "<>", "<", ">", "<=", ">=")
            if tok is None:
                return left
            right = self._concat()
            left = BinOp(tok.text, left, right)

    def _concat(self) -> Expr:
        left = self._additive()
        while True:
            tok = self._match(TokenKind.OP, "&")
            if tok is None:
                return left
            right = self._additive()
            left = BinOp("&", left, right)

    def _additive(self) -> Expr:
        left = self._multiplicative()
        while True:
            tok = self._match(TokenKind.OP, "+", "-")
            if tok is None:
                return left
            right = self._multiplicative()
            left = BinOp(tok.text, left, right)

    def _multiplicative(self) -> Expr:
        left = self._exponent()
        while True:
            tok = self._match(TokenKind.OP, "*", "/")
            if tok is None:
                return left
            right = self._exponent()
            left = BinOp(tok.text, left, right)

    def _exponent(self) -> Expr:
        left = self._percent()
        tok = self._match(TokenKind.OP, "^")
        if tok is None:
            return left
        # Right-associative: ``2^3^2`` parses as ``2^(3^2)``.
        right = self._exponent()
        return BinOp("^", left, right)

    def _percent(self) -> Expr:
        node = self._unary()
        while self._match(TokenKind.OP, "%") is not None:
            node = UnaryOp("%", node)
        return node

    def _unary(self) -> Expr:
        tok = self._match(TokenKind.OP, "+", "-")
        if tok is not None:
            return UnaryOp(tok.text, self._unary())
        return self._primary()

    def _primary(self) -> Expr:
        tok = self._peek()
        if tok.kind is TokenKind.NUMBER:
            self._advance()
            return NumberLit(float(tok.text))
        if tok.kind is TokenKind.STRING:
            self._advance()
            return StringLit(tok.text)
        if tok.kind is TokenKind.BOOL:
            self._advance()
            return BoolLit(tok.text == "TRUE")
        if tok.kind is TokenKind.REF:
            self._advance()
            return RefNode(CellRef.parse(tok.text))
        if tok.kind is TokenKind.RANGE:
            self._advance()
            return RangeNode(RangeRef.parse(tok.text))
        if tok.kind is TokenKind.LPAREN:
            self._advance()
            inner = self.expr()
            self._expect(TokenKind.RPAREN)
            return inner
        if tok.kind is TokenKind.IDENT:
            self._advance()
            self._expect(TokenKind.LPAREN)
            args: list[Expr] = []
            if self._peek().kind is not TokenKind.RPAREN:
                args.append(self.expr())
                while self._match(TokenKind.COMMA) is not None:
                    args.append(self.expr())
            self._expect(TokenKind.RPAREN)
            return FunctionCall(tok.text.upper(), tuple(args))
        raise ParseError(
            f"Unexpected {tok.kind.name} {tok.text!r} at position {tok.pos}"
        )


def parse(source: str) -> Expr:
    """Parse a formula expression (WITHOUT the leading '=') into an AST."""
    tokens = tokenize(source)
    parser = _Parser(tokens)
    node = parser.expr()
    if parser._peek().kind is not TokenKind.EOF:
        tok = parser._peek()
        raise ParseError(
            f"Trailing tokens after expression at position {tok.pos}: {tok.text!r}"
        )
    return node


def is_formula(source: str) -> bool:
    """Return True if ``source`` should be treated as a formula (leading '=')."""
    return source.startswith("=")


def extract_refs(node: Expr) -> list[CellRef]:
    """Walk an AST and return every single-cell reference it touches.

    Range references are expanded to their constituent cells here so callers
    (like the dependency graph) can reason in terms of individual cells.
    """
    collected: list[CellRef] = []
    _walk_refs(node, collected)
    return collected


def _walk_refs(node: Expr, out: list[CellRef]) -> None:
    if isinstance(node, RefNode):
        out.append(node.ref.without_absolutes())
        return
    if isinstance(node, RangeNode):
        out.extend(c.without_absolutes() for c in node.range.iter_cells())
        return
    if isinstance(node, UnaryOp):
        _walk_refs(node.operand, out)
        return
    if isinstance(node, BinOp):
        _walk_refs(node.left, out)
        _walk_refs(node.right, out)
        return
    if isinstance(node, FunctionCall):
        for a in node.args:
            _walk_refs(a, out)
