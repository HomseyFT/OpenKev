"""Tests for the tokenizer and parser."""

import pytest

from apps.Kevcel.core.parser import (
    BinOp, BoolLit, FunctionCall, NumberLit, ParseError, RangeNode, RefNode,
    StringLit, UnaryOp, parse,
)
from apps.Kevcel.core.tokenizer import TokenKind, TokenizeError, tokenize


class TestTokenizer:
    def test_numbers(self):
        t = tokenize("1 2.5 .75 3e2 1.5e-3")
        assert [tok.kind for tok in t[:-1]] == [TokenKind.NUMBER] * 5

    def test_string_with_escaped_quote(self):
        t = tokenize('"he said ""hi"""')
        assert t[0].kind is TokenKind.STRING
        assert t[0].text == 'he said "hi"'

    def test_unterminated_string_raises(self):
        with pytest.raises(TokenizeError):
            tokenize('"unfinished')

    def test_refs_and_ranges(self):
        t = tokenize("A1 + $B$10 - A1:B10")
        kinds = [tok.kind for tok in t[:-1]]
        assert TokenKind.REF in kinds
        assert TokenKind.RANGE in kinds

    def test_sheet_qualified_ref(self):
        t = tokenize("Sheet1!A1")
        assert t[0].kind is TokenKind.REF
        assert t[0].text == "Sheet1!A1"

    def test_bool_literal(self):
        t = tokenize("TRUE FALSE")
        assert t[0].kind is TokenKind.BOOL
        assert t[1].kind is TokenKind.BOOL

    def test_operators(self):
        t = tokenize("<>  <=  >=  <  >  =  + - * / ^ & %")
        assert all(tok.kind is TokenKind.OP for tok in t[:-1])


class TestParser:
    def test_simple_number(self):
        assert parse("42") == NumberLit(42.0)

    def test_string_literal(self):
        assert parse('"hi"') == StringLit("hi")

    def test_bool_literal(self):
        assert parse("TRUE") == BoolLit(True)

    def test_cell_ref(self):
        node = parse("A1")
        assert isinstance(node, RefNode)
        assert node.ref.row == 0 and node.ref.col == 0

    def test_range(self):
        node = parse("A1:B3")
        assert isinstance(node, RangeNode)

    def test_addition(self):
        node = parse("1+2")
        assert isinstance(node, BinOp) and node.op == "+"

    def test_precedence_mul_over_add(self):
        # 1 + 2 * 3  ->  BinOp(+, 1, BinOp(*, 2, 3))
        node = parse("1+2*3")
        assert isinstance(node, BinOp) and node.op == "+"
        assert isinstance(node.right, BinOp) and node.right.op == "*"

    def test_precedence_paren_overrides(self):
        node = parse("(1+2)*3")
        assert isinstance(node, BinOp) and node.op == "*"
        assert isinstance(node.left, BinOp) and node.left.op == "+"

    def test_right_associative_exponent(self):
        # 2^3^2 should parse as 2^(3^2)
        node = parse("2^3^2")
        assert isinstance(node, BinOp) and node.op == "^"
        assert isinstance(node.right, BinOp) and node.right.op == "^"

    def test_unary_minus(self):
        node = parse("-5")
        assert isinstance(node, UnaryOp) and node.op == "-"

    def test_function_call(self):
        node = parse("SUM(A1,2,3)")
        assert isinstance(node, FunctionCall)
        assert node.name == "SUM"
        assert len(node.args) == 3

    def test_function_call_empty_args(self):
        node = parse("TODAY()")
        assert isinstance(node, FunctionCall) and node.name == "TODAY"
        assert node.args == ()

    def test_function_with_range(self):
        node = parse("SUM(A1:B3)")
        assert isinstance(node, FunctionCall)
        assert isinstance(node.args[0], RangeNode)

    def test_concat_operator(self):
        node = parse('"hello" & " " & "world"')
        assert isinstance(node, BinOp) and node.op == "&"

    def test_comparison(self):
        node = parse("A1 >= 10")
        assert isinstance(node, BinOp) and node.op == ">="

    def test_trailing_garbage_rejected(self):
        with pytest.raises(ParseError):
            parse("1 2")

    def test_unclosed_paren_rejected(self):
        with pytest.raises(ParseError):
            parse("(1+2")
