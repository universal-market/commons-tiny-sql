import unittest

from tinysql.tokenizer import TokenizeError, tokenize


def kinds(text):
    return [t.kind for t in tokenize(text)]


class TokenizerTests(unittest.TestCase):
    def test_empty_input_is_only_eof(self):
        self.assertEqual(kinds(""), ["EOF"])

    def test_keywords_are_case_insensitive(self):
        self.assertEqual(kinds("select FROM wHere"), ["SELECT", "FROM", "WHERE", "EOF"])

    def test_identifier_keeps_case(self):
        toks = tokenize("UserName")
        self.assertEqual((toks[0].kind, toks[0].value), ("IDENT", "UserName"))

    def test_identifier_with_digits_and_underscore(self):
        toks = tokenize("col_2a")
        self.assertEqual(toks[0].value, "col_2a")

    def test_integer_and_float(self):
        toks = tokenize("42 3.5")
        self.assertEqual((toks[0].kind, toks[0].value), ("NUMBER", 42))
        self.assertEqual((toks[1].kind, toks[1].value), ("NUMBER", 3.5))

    def test_fraction_is_not_dropped(self):
        toks = tokenize("1.25")
        self.assertEqual(toks[0].value, 1.25)

    def test_string_with_escaped_quote(self):
        toks = tokenize("'it''s'")
        self.assertEqual((toks[0].kind, toks[0].value), ("STRING", "it's"))

    def test_unterminated_string_raises(self):
        with self.assertRaises(TokenizeError):
            tokenize("'abc")

    def test_two_char_operators(self):
        self.assertEqual(kinds("<= >= <> !="), ["LE", "GE", "NE", "NE", "EOF"])

    def test_single_char_symbols(self):
        self.assertEqual(
            kinds("(a, *) = t.b;"),
            ["LPAREN", "IDENT", "COMMA", "STAR", "RPAREN", "EQ",
             "IDENT", "DOT", "IDENT", "SEMI", "EOF"],
        )

    def test_line_comment_is_skipped(self):
        self.assertEqual(kinds("SELECT -- note\n1"), ["SELECT", "NUMBER", "EOF"])

    def test_positions_point_at_token_start(self):
        toks = tokenize("  SELECT x")
        self.assertEqual([t.pos for t in toks], [2, 9, 10])

    def test_unexpected_character_raises(self):
        with self.assertRaises(TokenizeError):
            tokenize("SELECT @")


if __name__ == "__main__":
    unittest.main()
