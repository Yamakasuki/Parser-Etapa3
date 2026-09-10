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


from ast_nodes import Parameter, TypeName


def test_parametro_unico():
    parser = make_parser("int x")
    parameters = parser.parse_parameter_list()
    assert parameters == [Parameter(TypeName.INT, "x", span=parameters[0].span)]


def test_lista_de_parametros_preserva_ordem():
    parser = make_parser("int x, bool ativo, void y")
    parameters = parser.parse_parameter_list()
    assert [(p.type, p.name) for p in parameters] == [
        (TypeName.INT, "x"),
        (TypeName.BOOL, "ativo"),
        (TypeName.VOID, "y"),
    ]
