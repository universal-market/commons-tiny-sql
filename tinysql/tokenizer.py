"""Tokenizer for a small SQL dialect.

Produces a list of Token objects ending with an EOF token. Keywords are
case-insensitive and stored upper-cased; identifiers keep their case.
"""

from dataclasses import dataclass

KEYWORDS = frozenset({
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "AND", "OR", "NOT",
    "NULL", "ORDER", "BY", "LIMIT", "CREATE", "TABLE", "PRIMARY", "KEY", "DELETE",
})

SYMBOLS = {
    "(": "LPAREN", ")": "RPAREN", ",": "COMMA", "*": "STAR", ";": "SEMI",
    "=": "EQ", "<": "LT", ">": "GT", ".": "DOT",
}
TWO_CHAR_SYMBOLS = {"<=": "LE", ">=": "GE", "<>": "NE", "!=": "NE"}


class TokenizeError(ValueError):
    """Raised on input that cannot be tokenized."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    pos: int


def tokenize(text):
    """Split SQL text into tokens. Raises TokenizeError on bad input."""
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == "-" and text.startswith("--", i):
            end = text.find("\n", i)
            i = n if end == -1 else end + 1
        elif c == "'":
            i = _read_string(text, i, tokens)
        elif c.isdigit():
            i = _read_number(text, i, tokens)
        elif c.isalpha() or c == "_":
            i = _read_word(text, i, tokens)
        elif text[i:i + 2] in TWO_CHAR_SYMBOLS:
            tokens.append(Token(TWO_CHAR_SYMBOLS[text[i:i + 2]], text[i:i + 2], i))
            i += 2
        elif c in SYMBOLS:
            tokens.append(Token(SYMBOLS[c], c, i))
            i += 1
        else:
            raise TokenizeError(f"unexpected character {c!r} at {i}")
    tokens.append(Token("EOF", None, n))
    return tokens


def _read_string(text, start, tokens):
    # A quote inside a string is doubled: 'it''s' -> it's
    chars = []
    i = start + 1
    while i < len(text):
        if text[i] == "'":
            if text[i + 1:i + 2] == "'":
                chars.append("'")
                i += 2
                continue
            tokens.append(Token("STRING", "".join(chars), start))
            return i + 1
        chars.append(text[i])
        i += 1
    raise TokenizeError(f"unterminated string at {start}")


def _read_number(text, start, tokens):
    i = start
    while i < len(text) and text[i].isdigit():
        i += 1
    if i < len(text) and text[i] == "." and text[i + 1:i + 2].isdigit():
        i += 1
        while i < len(text) and text[i].isdigit():
            i += 1
        tokens.append(Token("NUMBER", float(text[start:i]), start))
    else:
        tokens.append(Token("NUMBER", int(text[start:i]), start))
    return i


def _read_word(text, start, tokens):
    i = start
    while i < len(text) and (text[i].isalnum() or text[i] == "_"):
        i += 1
    word = text[start:i]
    if word.upper() in KEYWORDS:
        tokens.append(Token(word.upper(), word.upper(), start))
    else:
        tokens.append(Token("IDENT", word, start))
    return i
