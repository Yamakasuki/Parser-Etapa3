from __future__ import annotations

from collections.abc import Sequence

from Lexer import Token, TokenKind
from ast_nodes import (
    BinaryExpr,
    BinaryOperator,
    Block,
    BoolLiteral,
    CallExpr,
    Expr,
    FunctionDecl,
    IdentifierExpr,
    IntLiteral,
    Node,
    Parameter,
    PrintItem,
    Program,
    SourceSpan,
    Stmt,
    StringLiteral,
    TypeName,
    UnaryExpr,
    UnaryOperator,
)


TYPE_START = {TokenKind.KW_INT, TokenKind.KW_BOOL, TokenKind.KW_VOID}
EXPRESSION_START = {
    TokenKind.IDENTIFIER,
    TokenKind.INT_LITERAL,
    TokenKind.KW_FALSE,
    TokenKind.KW_TRUE,
    TokenKind.LEFT_PAREN,
    TokenKind.LOGICAL_NOT,
    TokenKind.MINUS,
}
STATEMENT_START = TYPE_START | {
    TokenKind.IDENTIFIER,
    TokenKind.KW_IF,
    TokenKind.KW_WHILE,
    TokenKind.KW_RETURN,
    TokenKind.KW_PRINT,
    TokenKind.LEFT_BRACE,
}
# Subconjunto de EXPRESSION_START: exclui LOGICAL_NOT/MINUS, que pertencem a
# unary, não a primary. Mantém o conjunto "esperado" preciso nos erros de primary.
PRIMARY_START = {
    TokenKind.LEFT_PAREN,
    TokenKind.IDENTIFIER,
    TokenKind.INT_LITERAL,
    TokenKind.KW_TRUE,
    TokenKind.KW_FALSE,
}


TYPE_BY_TOKEN = {
    TokenKind.KW_INT: TypeName.INT,
    TokenKind.KW_BOOL: TypeName.BOOL,
    TokenKind.KW_VOID: TypeName.VOID,
}
UNARY_OPERATORS = {
    TokenKind.LOGICAL_NOT: UnaryOperator.NOT,
    TokenKind.MINUS: UnaryOperator.NEGATE,
}
ADDITIVE_OPERATORS = {
    TokenKind.PLUS: BinaryOperator.ADD,
    TokenKind.MINUS: BinaryOperator.SUBTRACT,
}
MULTIPLICATIVE_OPERATORS = {
    TokenKind.STAR: BinaryOperator.MULTIPLY,
    TokenKind.SLASH: BinaryOperator.DIVIDE,
    TokenKind.PERCENT: BinaryOperator.REMAINDER,
}


class ParserError(Exception):
    def __init__(self, token: Token, expected: set[TokenKind]):
        self.token = token
        self.expected = frozenset(expected)
        super().__init__()

    @property
    def line(self) -> int:
        return self.token.line

    @property
    def column(self) -> int:
        return self.token.column

    def __str__(self) -> str:
        names = ", ".join(kind.name for kind in sorted(
            self.expected,
            key=lambda kind: kind.value,
        ))
        return (
            f"erro sintático em {self.line}:{self.column}: esperado {{{names}}}, "
            f"encontrado {self.token.kind.name} ({self.token.lexeme!r})"
        )


class Parser:
    def __init__(self, tokens: Sequence[Token]):
        self.tokens = list(tokens)
        if not self.tokens:
            raise ValueError("a sequência de tokens deve terminar em EOF")
        if self.tokens[-1].kind is not TokenKind.EOF:
            raise ValueError("o último token deve ser EOF")
        if any(token.kind is TokenKind.EOF for token in self.tokens[:-1]):
            raise ValueError("EOF deve aparecer uma única vez, no final")
        self.current = 0

    def peek(self, offset: int = 0) -> Token:
        index = min(self.current + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def check(self, kind: TokenKind) -> bool:
        return self.peek().kind is kind

    def advance(self) -> Token:
        token = self.peek()
        if self.current < len(self.tokens) - 1:
            self.current += 1
        return token

    def match(self, *kinds: TokenKind) -> Token | None:
        if self.peek().kind in kinds:
            return self.advance()
        return None

    def expect(self, kinds: TokenKind | set[TokenKind]) -> Token:
        expected = kinds if isinstance(kinds, set) else {kinds}
        token = self.peek()
        if token.kind not in expected:
            raise ParserError(token, set(expected))
        return self.advance()

    @staticmethod
    def _token_span(token: Token) -> SourceSpan:
        return SourceSpan(
            token.line,
            token.column,
            token.line,
            token.column + len(token.lexeme),
        )

    @staticmethod
    def _start(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.start_line, value.span.start_column
        return value.line, value.column

    @staticmethod
    def _end(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.end_line, value.span.end_column
        return value.line, value.column + len(value.lexeme)

    @classmethod
    def _span(cls, first: Token | Node, last: Token | Node) -> SourceSpan:
        start_line, start_column = cls._start(first)
        end_line, end_column = cls._end(last)
        return SourceSpan(start_line, start_column, end_line, end_column)

    def parse(self) -> Program:
        return self.parse_program()

    # program ::= function* EOF
    def parse_program(self) -> Program:
        start = self.peek()
        functions: list[FunctionDecl] = []
        while self.peek().kind in TYPE_START:
            functions.append(self.parse_function())
        eof = self.expect(TokenKind.EOF)
        return Program(functions, span=self._span(start, eof))

    # function ::= type IDENTIFIER ... block
    def parse_function(self) -> FunctionDecl:
        start = self.peek()
        return_type = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)
        self.expect(TokenKind.LEFT_PAREN)
        parameters = (
            self.parse_parameter_list()
            if self.peek().kind in TYPE_START
            else []
        )
        self.expect(TokenKind.RIGHT_PAREN)
        body = self.parse_block()
        return FunctionDecl(
            return_type,
            name.lexeme,
            parameters,
            body,
            span=self._span(start, body),
        )

    # type ::= KW_INT | KW_BOOL | KW_VOID
    def parse_type(self) -> TypeName:
        token = self.expect(TYPE_START)
        return TYPE_BY_TOKEN[token.kind]

    def parse_parameter_list(self) -> list[Parameter]:
        parameters = [self.parse_parameter()]
        while self.match(TokenKind.COMMA) is not None:
            parameters.append(self.parse_parameter())
        return parameters

    def parse_parameter(self) -> Parameter:
        start = self.peek()
        type_ = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)
        return Parameter(type_, name.lexeme, span=self._span(start, name))

    def parse_block(self) -> Block:
        raise NotImplementedError("implemente block")

    def parse_statement(self) -> Stmt:
        raise NotImplementedError("implemente statement")

    def parse_id_or_call_statement(self) -> Stmt:
        raise NotImplementedError("implemente id_or_call_statement")

    def parse_declaration(self) -> Stmt:
        raise NotImplementedError("implemente declaration")

    def parse_if_statement(self) -> Stmt:
        raise NotImplementedError("implemente if_statement")

    def parse_while_statement(self) -> Stmt:
        raise NotImplementedError("implemente while_statement")

    def parse_return_statement(self) -> Stmt:
        raise NotImplementedError("implemente return_statement")

    def parse_print_statement(self) -> Stmt:
        raise NotImplementedError("implemente print_statement")

    def parse_print_item(self) -> PrintItem:
        raise NotImplementedError("implemente print_item")

    def parse_string_literals(self) -> StringLiteral:
        raise NotImplementedError("implemente string_literals")

    def parse_expression(self) -> Expr:
        raise NotImplementedError("implemente expression")

    def parse_logical_or(self) -> Expr:
        raise NotImplementedError("implemente logical_or")

    def parse_logical_and(self) -> Expr:
        raise NotImplementedError("implemente logical_and")

    def parse_equality(self) -> Expr:
        raise NotImplementedError("implemente equality")

    def parse_relational(self) -> Expr:
        raise NotImplementedError("implemente relational")

    def parse_additive(self) -> Expr:
        return self._parse_binary_level(self.parse_multiplicative, ADDITIVE_OPERATORS)

    def parse_multiplicative(self) -> Expr:
        return self._parse_binary_level(self.parse_unary, MULTIPLICATIVE_OPERATORS)

    # helper compartilhado por todos os niveis de expressao binaria
    def _parse_binary_level(self, operand, operators: dict[TokenKind, BinaryOperator]) -> Expr:
        left = operand()
        while True:
            token = self.match(*operators.keys())
            if token is None:
                return left
            right = operand()
            left = BinaryExpr(
                operators[token.kind],
                left,
                right,
                span=self._span(left, right),
            )

    def parse_unary(self) -> Expr:
        token = self.match(*UNARY_OPERATORS.keys())
        if token is not None:
            operand = self.parse_unary()
            return UnaryExpr(UNARY_OPERATORS[token.kind], operand, span=self._span(token, operand))
        return self.parse_primary()

    def parse_primary(self) -> Expr:
        left_paren = self.match(TokenKind.LEFT_PAREN)
        if left_paren is not None:
            expr = self.parse_expression()
            right_paren = self.expect(TokenKind.RIGHT_PAREN)
            expr.span = self._span(left_paren, right_paren)
            return expr

        identifier = self.match(TokenKind.IDENTIFIER)
        if identifier is not None:
            if self.match(TokenKind.LEFT_PAREN) is not None:
                arguments = self.parse_arguments()
                right_paren = self.expect(TokenKind.RIGHT_PAREN)
                return CallExpr(
                    identifier.lexeme,
                    arguments,
                    span=self._span(identifier, right_paren),
                )
            return IdentifierExpr(identifier.lexeme, span=self._token_span(identifier))

        integer = self.match(TokenKind.INT_LITERAL)
        if integer is not None:
            return IntLiteral(integer.value, span=self._token_span(integer))

        true_token = self.match(TokenKind.KW_TRUE)
        if true_token is not None:
            return BoolLiteral(True, span=self._token_span(true_token))

        false_token = self.match(TokenKind.KW_FALSE)
        if false_token is not None:
            return BoolLiteral(False, span=self._token_span(false_token))

        self.expect(PRIMARY_START)

    def parse_arguments(self) -> list[Expr]:
        if self.peek().kind not in EXPRESSION_START:
            return []
        arguments = [self.parse_expression()]
        while self.match(TokenKind.COMMA) is not None:
            arguments.append(self.parse_expression())
        return arguments
