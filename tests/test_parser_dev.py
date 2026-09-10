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


from ast_nodes import BoolLiteral, CallExpr, IdentifierExpr, IntLiteral


def test_primary_identificador_inteiro_booleano():
    assert isinstance(make_parser("x").parse_primary(), IdentifierExpr)
    literal = make_parser("42").parse_primary()
    assert isinstance(literal, IntLiteral) and literal.value == 42
    assert make_parser("true").parse_primary().value is True
    assert make_parser("false").parse_primary().value is False


def test_primary_parenteses_nao_criam_no_mas_ampliam_span():
    inner = make_parser("42").parse_primary()
    wrapped = make_parser("(42)").parse_primary()
    assert type(wrapped) is type(inner)
    assert wrapped.span.start_column == 1
    assert wrapped.span.end_column == 5  # cobre "(42)"


def test_chamada_com_e_sem_argumentos():
    sem_args = make_parser("registrar()").parse_primary()
    assert isinstance(sem_args, CallExpr) and sem_args.arguments == []
    com_args = make_parser("calcular(1, true)").parse_primary()
    assert isinstance(com_args, CallExpr)
    assert com_args.name == "calcular"
    assert [type(a) for a in com_args.arguments] == [IntLiteral, BoolLiteral]


def test_arguments_lista_vazia_quando_fecha_direto():
    parser = make_parser(")")
    assert parser.parse_arguments() == []


from ast_nodes import BinaryOperator, UnaryOperator


def test_unario_associa_a_direita():
    expr = make_parser("- - x").parse_unary()
    assert expr.operator is UnaryOperator.NEGATE
    assert expr.operand.operator is UnaryOperator.NEGATE
    assert expr.operand.operand.name == "x"

    expr = make_parser("!true").parse_unary()
    assert expr.operator is UnaryOperator.NOT
    assert expr.operand.value is True


def test_multiplicativa_associa_a_esquerda():
    expr = make_parser("2 * 3 / 4").parse_multiplicative()
    assert expr.operator is BinaryOperator.DIVIDE
    assert expr.left.operator is BinaryOperator.MULTIPLY
    assert expr.left.left.value == 2
    assert expr.left.right.value == 3
    assert expr.right.value == 4


def test_aditiva_chama_multiplicativa_primeiro():
    expr = make_parser("10 - 3 - 2").parse_additive()
    assert expr.operator is BinaryOperator.SUBTRACT
    assert expr.left.operator is BinaryOperator.SUBTRACT
    assert expr.left.left.value == 10
    assert expr.left.right.value == 3
    assert expr.right.value == 2
