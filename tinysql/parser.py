"""Recursive-descent parser for SELECT and INSERT statements.

Grammar (keywords case-insensitive, optional trailing ';'):

    select  := SELECT ('*' | column (',' column)*) FROM IDENT
               [WHERE expr] [ORDER BY IDENT] [LIMIT NUMBER]
    insert  := INSERT INTO IDENT ['(' IDENT (',' IDENT)* ')']
               VALUES '(' literal (',' literal)* ')'
    expr    := and_expr (OR and_expr)*
    and_expr:= not_expr (AND not_expr)*
    not_expr:= NOT not_expr | comparison
    comparison := operand [('='|'<>'|'!='|'<'|'<='|'>'|'>=') operand]
    operand := IDENT | literal | '(' expr ')'
    literal := NUMBER | STRING | NULL
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Union

from .tokenizer import tokenize

COMPARISON_OPS = {"EQ": "=", "NE": "<>", "LT": "<", "LE": "<=", "GT": ">", "GE": ">="}


class ParseError(ValueError):
    """Raised when the token stream does not match the grammar."""


@dataclass(frozen=True)
class Column:
    name: str


@dataclass(frozen=True)
class Literal:
    value: object  # int, float, str or None (NULL)


@dataclass(frozen=True)
class Compare:
    op: str
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class And:
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class Or:
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class Not:
    operand: "Expr"


Expr = Union[Column, Literal, Compare, And, Or, Not]


@dataclass(frozen=True)
class Select:
    columns: Optional[Tuple[str, ...]]  # None means '*'
    table: str
    where: Optional[Expr] = None
    order_by: Optional[str] = None
    limit: Optional[int] = None


@dataclass(frozen=True)
class Insert:
    table: str
    columns: Optional[Tuple[str, ...]]  # None means all columns in table order
    values: Tuple[object, ...]


Statement = Union[Select, Insert]


def parse(text):
    """Parse one statement. Raises ParseError or TokenizeError."""
    return _Parser(tokenize(text)).statement()


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i]

    def advance(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def accept(self, kind):
        if self.peek().kind == kind:
            return self.advance()
        return None

    def expect(self, kind):
        tok = self.accept(kind)
        if tok is None:
            got = self.peek()
            raise ParseError(f"expected {kind} at {got.pos}, got {got.kind}")
        return tok

    def statement(self):
        if self.accept("SELECT"):
            stmt = self.select()
        elif self.accept("INSERT"):
            stmt = self.insert()
        else:
            got = self.peek()
            raise ParseError(f"expected SELECT or INSERT at {got.pos}, got {got.kind}")
        self.accept("SEMI")
        self.expect("EOF")
        return stmt

    def select(self):
        if self.accept("STAR"):
            columns = None
        else:
            columns = self.ident_list()
        self.expect("FROM")
        table = self.expect("IDENT").value
        where = self.expr() if self.accept("WHERE") else None
        order_by = None
        if self.accept("ORDER"):
            self.expect("BY")
            order_by = self.expect("IDENT").value
        limit = self.expect("NUMBER").value if self.accept("LIMIT") else None
        if limit is not None and not isinstance(limit, int):
            raise ParseError("LIMIT takes an integer")
        return Select(columns, table, where, order_by, limit)

    def insert(self):
        self.expect("INTO")
        table = self.expect("IDENT").value
        columns = None
        if self.accept("LPAREN"):
            columns = self.ident_list()
            self.expect("RPAREN")
        self.expect("VALUES")
        self.expect("LPAREN")
        values = [self.literal()]
        while self.accept("COMMA"):
            values.append(self.literal())
        self.expect("RPAREN")
        if columns is not None and len(columns) != len(values):
            raise ParseError(
                f"INSERT has {len(columns)} columns but {len(values)} values"
            )
        return Insert(table, columns, tuple(values))

    def ident_list(self):
        names = [self.expect("IDENT").value]
        while self.accept("COMMA"):
            names.append(self.expect("IDENT").value)
        return tuple(names)

    def literal(self):
        tok = self.peek()
        if tok.kind in ("NUMBER", "STRING"):
            self.advance()
            return tok.value
        if self.accept("NULL"):
            return None
        raise ParseError(f"expected literal at {tok.pos}, got {tok.kind}")

    def expr(self):
        node = self.and_expr()
        while self.accept("OR"):
            node = Or(node, self.and_expr())
        return node

    def and_expr(self):
        node = self.not_expr()
        while self.accept("AND"):
            node = And(node, self.not_expr())
        return node

    def not_expr(self):
        if self.accept("NOT"):
            return Not(self.not_expr())
        return self.comparison()

    def comparison(self):
        left = self.operand()
        for kind, op in COMPARISON_OPS.items():
            if self.accept(kind):
                return Compare(op, left, self.operand())
        return left

    def operand(self):
        if self.accept("LPAREN"):
            node = self.expr()
            self.expect("RPAREN")
            return node
        if self.peek().kind == "IDENT":
            return Column(self.advance().value)
        return Literal(self.literal())
