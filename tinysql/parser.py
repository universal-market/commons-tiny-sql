"""Recursive-descent parser for SELECT and INSERT statements.

Grammar (keywords case-insensitive, optional trailing ';'):

    select  := SELECT ('*' | column (',' column)*) FROM IDENT
               [WHERE expr] [ORDER BY IDENT [DESC]] [LIMIT NUMBER [OFFSET NUMBER]]
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
class IsNull:
    operand: "Expr"


@dataclass(frozen=True)
class InList:
    operand: "Expr"
    items: tuple


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


Expr = Union[Column, Literal, Compare, IsNull, InList, And, Or, Not]


@dataclass(frozen=True)
class Select:
    columns: Optional[Tuple[str, ...]]  # None means '*'
    table: str
    where: Optional[Expr] = None
    order_by: Optional[str] = None
    order_desc: bool = False
    limit: Optional[int] = None
    offset: int = 0
    distinct: bool = False


@dataclass(frozen=True)
class Insert:
    table: str
    columns: Optional[Tuple[str, ...]]  # None means all columns in table order
    rows: Tuple[Tuple[object, ...], ...]


@dataclass(frozen=True)
class Delete:
    table: str
    where: "Expr"  # required: DELETE without WHERE is rejected


@dataclass(frozen=True)
class Update:
    table: str
    column: str
    value: "Expr"
    where: "Expr"  # required: UPDATE without WHERE is rejected


@dataclass(frozen=True)
class ColumnDef:
    name: str
    type_name: str  # INT, FLOAT, TEXT or BOOL
    nullable: bool


@dataclass(frozen=True)
class DropTable:
    table: str


@dataclass(frozen=True)
class CreateTable:
    table: str
    columns: Tuple[ColumnDef, ...]
    primary_key: str


Statement = Union[Select, Insert, CreateTable, DropTable, Delete, Update]

COLUMN_TYPES = frozenset({"INT", "FLOAT", "TEXT", "BOOL"})


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
        elif self.accept("CREATE"):
            stmt = self.create_table()
        elif self.accept("DROP"):
            self.expect("TABLE")
            stmt = DropTable(self.expect("IDENT").value)
        elif self.accept("DELETE"):
            stmt = self.delete()
        elif self.accept("UPDATE"):
            stmt = self.update()
        else:
            got = self.peek()
            raise ParseError(f"expected SELECT, INSERT, CREATE or DELETE at {got.pos}, got {got.kind}")
        self.accept("SEMI")
        self.expect("EOF")
        return stmt

    def select(self):
        distinct = bool(self.accept("DISTINCT"))
        if self.accept("STAR"):
            columns = None
        elif self.accept("COUNT"):
            self.expect("LPAREN")
            self.expect("STAR")
            self.expect("RPAREN")
            columns = ("COUNT(*)",)  # same as executor.COUNT_STAR
        else:
            columns = self.ident_list()
        self.expect("FROM")
        table = self.expect("IDENT").value
        where = self.expr() if self.accept("WHERE") else None
        order_by = None
        order_desc = False
        if self.accept("ORDER"):
            self.expect("BY")
            order_by = self.expect("IDENT").value
            order_desc = bool(self.accept("DESC"))
        limit = self.expect("NUMBER").value if self.accept("LIMIT") else None
        if limit is not None and not isinstance(limit, int):
            raise ParseError("LIMIT takes an integer")
        offset = 0
        if self.accept("OFFSET"):
            offset = self.expect("NUMBER").value
            if not isinstance(offset, int):
                raise ParseError("OFFSET takes an integer")
        return Select(columns, table, where, order_by, order_desc, limit, offset, distinct)

    def update(self):
        table = self.expect("IDENT").value
        self.expect("SET")
        column = self.expect("IDENT").value
        self.expect("EQ")
        value = self.expr()
        self.expect("WHERE")
        return Update(table, column, value, self.expr())

    def delete(self):
        self.expect("FROM")
        table = self.expect("IDENT").value
        self.expect("WHERE")
        return Delete(table, self.expr())

    def insert(self):
        self.expect("INTO")
        table = self.expect("IDENT").value
        columns = None
        if self.accept("LPAREN"):
            columns = self.ident_list()
            self.expect("RPAREN")
        self.expect("VALUES")
        rows = [self.value_row()]
        while self.accept("COMMA"):
            rows.append(self.value_row())
        for values in rows:
            if columns is not None and len(columns) != len(values):
                raise ParseError(
                    f"INSERT has {len(columns)} columns but {len(values)} values"
                )
        return Insert(table, columns, tuple(rows))

    def value_row(self):
        self.expect("LPAREN")
        values = [self.literal()]
        while self.accept("COMMA"):
            values.append(self.literal())
        self.expect("RPAREN")
        return tuple(values)

    def create_table(self):
        self.expect("TABLE")
        table = self.expect("IDENT").value
        self.expect("LPAREN")
        columns = [self.column_def()]
        while self.accept("COMMA") and self.peek().kind != "PRIMARY":
            columns.append(self.column_def())
        self.expect("PRIMARY")
        self.expect("KEY")
        self.expect("LPAREN")
        primary_key = self.expect("IDENT").value
        self.expect("RPAREN")
        self.expect("RPAREN")
        names = [c.name for c in columns]
        if len(set(names)) != len(names):
            raise ParseError("duplicate column name in CREATE TABLE")
        if primary_key not in names:
            raise ParseError(f"PRIMARY KEY names unknown column {primary_key!r}")
        return CreateTable(table, tuple(columns), primary_key)

    def column_def(self):
        name = self.expect("IDENT").value
        type_tok = self.expect("IDENT")
        type_name = type_tok.value.upper()
        if type_name not in COLUMN_TYPES:
            raise ParseError(f"unknown column type {type_tok.value!r}")
        nullable = bool(self.accept("NULL"))
        return ColumnDef(name, type_name, nullable)

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
        if self.accept("IS"):
            negated = bool(self.accept("NOT"))
            self.expect("NULL")
            return Not(IsNull(left)) if negated else IsNull(left)
        if self.accept("BETWEEN"):
            low = self.operand()
            self.expect("AND")
            high = self.operand()
            return And(Compare(">=", left, low), Compare("<=", left, high))
        if self.accept("IN"):
            self.expect("LPAREN")
            items = [self.operand()]
            while self.accept("COMMA"):
                items.append(self.operand())
            self.expect("RPAREN")
            return InList(left, tuple(items))
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
