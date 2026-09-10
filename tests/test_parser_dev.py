from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from Lexer import Lexer  # noqa: E402
from parser import Parser  # noqa: E402


def make_parser(source: str) -> Parser:
    return Parser(Lexer(source).scan())


def test_lexer_esta_completo_o_bastante_para_tokenizar():
    tokens = Lexer("int x = 1;").scan()
    assert tokens[-1].kind.name == "EOF"
