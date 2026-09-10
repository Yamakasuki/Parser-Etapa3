# Parser LL(1) MicroC (Etapa 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement every `parse_*` method left as `NotImplementedError` in `parser.py` so that `Parser(tokens).parse()` turns MicroC source into the `Program` AST defined in `ast_nodes.py`, exactly as specified by `source_grammar.ebnf` and `ENUNCIADO.pdf`.

**Architecture:** Hand-written recursive-descent, single-token lookahead, no backtracking. Each EBNF nonterminal gets one `parse_*` method that consumes exactly its own tokens and returns the AST node/list/value named in its signature. Binary expression levels (six of them) share one small helper to stay DRY, since they are structurally identical except for their operator set and the next-tighter level they call.

**Tech Stack:** Python 3.12, pytest (`requirements-dev.txt`), no parser-generator libraries (forbidden by the assignment).

**Spec:** `ENUNCIADO.pdf` (assignment) + `source_grammar.ebnf` (grammar) + `ast_nodes.py` (fixed AST contract) — all in this repo's root.

## Global Constraints

- Do not rename, remove, or change the signature of anything public in `ast_nodes.py`, `Lexer.py` (`Token`, `TokenKind`, `LexerError`), or `Parser`/`ParserError` in `parser.py`. Only add helper methods/constants.
- No parser generators (SLY/PLY/Lark/ANTLR), no regex-based parsing, no backtracking/try-multiple-alternatives, no semantic analysis inside the parser, no editing `source_grammar.ebnf`, no replacing AST nodes with dicts/JSON.
- A method must consume exactly the tokens of its nonterminal and must not consume the first token of whatever follows it.
- Binary expressions: each precedence level calls the next-tighter level and loops for left-associativity (`10 - 3 - 2` → `(10 - 3) - 2`). Unary operators recurse and are right-associative.
- Parentheses in `primary` do not create a node — they widen the inner expression's `span` and change precedence only.
- `print` string concatenation: `string_literals ::= STRING_LITERAL+` must merge the *decoded* `.value` of every adjacent `STRING_LITERAL` token into one `StringLiteral`.
- `ParserError` must carry the *exact* expected `TokenKind` set for the position where parsing failed (used verbatim in diagnostics and asserted by `tests/test_parser.py::test_erro_sintatico_informa_token_e_posicao`).
- Do not copy `grammar.py` from `LL-1-Grammar-Conversion` — that project is unrelated (grammar transformation tooling), the LL(1) grammar is already given in `source_grammar.ebnf`.
- Deadline: Sunday 2026-09-20, 23:59 (Brasília time) — the graded commit must be pushed to the group's GitHub Classroom repo by then.

---

## Task 0: Bring in the group's real lexer, confirm the baseline

The `Lexer.py` currently in this repo is only the Etapa 1 *interface skeleton* (`raise NotImplementedError`). The group's finished lexer lives in the separate `Lexer` repo, on branch `origin/etapa1-lexer` (not `master`, which is also just the skeleton) — commit `c222527 feat: implementa o analisador lexico do MicroC (Etapa 1)`. It's a mixed table-driven/manual design split across three files: `Lexer.py`, `microc_automato.py`, `microc_cursor.py`. All three must be copied together since `Lexer.py` imports the other two.

**Files:**
- Modify: `Lexer.py` (replace wholesale with the branch version)
- Create: `microc_automato.py`, `microc_cursor.py` (copied from the branch, new to this repo)
- Test: `tests/test_parser_dev.py` (new — a local scratch suite for this plan's TDD cycle; the graded suite is `tests/test_parser.py` and must not be touched)

**Interfaces:**
- Produces: `make_parser(source: str) -> Parser` fixture, reused by every later task to build a `Parser` straight from MicroC source text via the real lexer, so sub-parsers can be tested directly (`parser.parse_expression()`, `parser.parse_primary()`, ...) without needing the rest of the grammar to exist yet.

- [ ] **Step 1: Copy the three lexer files from the `Lexer` repo's `etapa1-lexer` branch**

```bash
cd "C:\Users\22003967\Documents\Lexer"
git show origin/etapa1-lexer:Lexer.py > "C:\Users\22003967\Documents\Parser-Etapa3\Lexer.py"
git show origin/etapa1-lexer:microc_automato.py > "C:\Users\22003967\Documents\Parser-Etapa3\microc_automato.py"
git show origin/etapa1-lexer:microc_cursor.py > "C:\Users\22003967\Documents\Parser-Etapa3\microc_cursor.py"
```

- [ ] **Step 2: Install dev dependencies and sanity-check the copy**

```bash
cd "C:\Users\22003967\Documents\Parser-Etapa3"
python -m pip install -r requirements-dev.txt
python -c "from Lexer import Lexer; print(Lexer('int main() {}').scan())"
```

Expected: a list of `Token` objects ending in one `EOF`, no `NotImplementedError`.

- [ ] **Step 3: Write the dev-suite fixture and one smoke test**

```python
# tests/test_parser_dev.py
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
```

- [ ] **Step 4: Run it**

```bash
python -m pytest -q tests/test_parser_dev.py
```

Expected: PASS (1 passed). If the lexer raises here, stop and fix the lexer copy before continuing — every later task depends on it.

- [ ] **Step 5: Run the full baseline to see current failure shape**

```bash
python -m pytest -q
```

Expected: `tests/test_parser.py` fails/errors on almost every test with `NotImplementedError: implemente ...` — this is the starting point the rest of the plan works down to zero.

- [ ] **Step 6: Commit**

```bash
git add Lexer.py microc_automato.py microc_cursor.py tests/test_parser_dev.py
git commit -m "chore: copia o lexer da etapa 1 e prepara suite de dev do parser"
```

---

## Task 1: Parameters

`parameter_list ::= parameter (COMMA parameter)*` and `parameter ::= type IDENTIFIER`. Both are already exercised end-to-end by `parse_function`, which is implemented — this task only fills in the two leaf methods it calls.

**Files:**
- Modify: `parser.py:174-178` (`parse_parameter_list`, `parse_parameter`)
- Test: `tests/test_parser_dev.py`

**Interfaces:**
- Consumes: `Parser.parse_type()` (given), `Parser.expect`, `Parser._span` (given, `parser.py:130`).
- Produces: `Parameter(type, name, span)` per node; `parse_parameter_list() -> list[Parameter]` in source order.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_parser_dev.py
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
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest -q tests/test_parser_dev.py -k parametro
```

Expected: FAIL with `NotImplementedError: implemente parameter_list`.

- [ ] **Step 3: Implement**

```python
# parser.py — replace the two NotImplementedError bodies
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
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest -q tests/test_parser_dev.py -k parametro
python -m pytest -q tests/test_parser.py -k parametros
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add parser.py tests/test_parser_dev.py
git commit -m "feat: implementa parameter e parameter_list"
```

---

## Task 2: Primary expressions and call arguments

`primary` (parenthesized expression / identifier / optional call / int literal / bool literals) and `arguments`. These are the base case every expression precedence level eventually bottoms out on, so they come before the precedence chain.

**Files:**
- Modify: `parser.py` — imports (add `BinaryExpr, BinaryOperator, UnaryExpr, UnaryOperator, CallExpr, IdentifierExpr, IntLiteral, BoolLiteral` to the `ast_nodes` import at the top), plus a new `PRIMARY_START` constant near `EXPRESSION_START`, plus `parse_primary` and `parse_arguments` bodies (`parser.py:234-238`).
- Test: `tests/test_parser_dev.py`

**Interfaces:**
- Consumes: `EXPRESSION_START` (given, module-level set), `Parser.expect/match/check/peek`.
- Produces: `parse_primary() -> Expr` (one of `IdentifierExpr`, `IntLiteral`, `BoolLiteral`, `CallExpr`, or a parenthesized sub-expression with widened span); `parse_arguments() -> list[Expr]`. Both are consumed by `parse_unary` in Task 3.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_parser_dev.py
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
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest -q tests/test_parser_dev.py -k "primary or arguments"
```

Expected: FAIL with `NotImplementedError: implemente primary` / `implemente arguments`.

- [ ] **Step 3: Implement**

First widen the import line at the top of `parser.py`:

```python
from ast_nodes import (
    Assignment,
    BinaryExpr,
    BinaryOperator,
    Block,
    BoolLiteral,
    CallExpr,
    CallStmt,
    Expr,
    FunctionDecl,
    IdentifierExpr,
    IfStmt,
    IntLiteral,
    Node,
    Parameter,
    PrintItem,
    PrintStmt,
    Program,
    ReturnStmt,
    SourceSpan,
    Stmt,
    StringLiteral,
    TypeName,
    UnaryExpr,
    UnaryOperator,
    VarDecl,
    WhileStmt,
)
```

Add near `EXPRESSION_START`:

```python
PRIMARY_START = {
    TokenKind.LEFT_PAREN,
    TokenKind.IDENTIFIER,
    TokenKind.INT_LITERAL,
    TokenKind.KW_TRUE,
    TokenKind.KW_FALSE,
}
```

(`PRIMARY_START` is narrower than `EXPRESSION_START` on purpose: `EXPRESSION_START` also includes `LOGICAL_NOT`/`MINUS`, which belong to `unary`, not `primary`. Reporting `PRIMARY_START` in `primary`'s own error keeps the diagnostic's expected-set accurate, per §6 of the assignment.)

```python
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
```

Note: `parse_primary` calls `self.parse_expression()`, which is implemented in Task 4. Until then this task's own tests that only exercise identifiers/literals/calls-with-literal-args will pass; leave that call as-is — Python only resolves it when actually invoked, so having the *body* reference a not-yet-passing method is fine, it just means the parenthesized-expression test stays red until Task 4 lands. Re-run it as part of Task 4's verification.

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest -q tests/test_parser_dev.py -k "primary or arguments"
```

Expected: `test_primary_identificador_inteiro_booleano`, `test_chamada_com_e_sem_argumentos`, `test_arguments_lista_vazia_quando_fecha_direto` PASS. `test_primary_parenteses_nao_criam_no_mas_ampliam_span` still FAILS here (needs `parse_expression`, done in Task 4) — expected at this point, do not chase it yet.

- [ ] **Step 5: Commit**

```bash
git add parser.py tests/test_parser_dev.py
git commit -m "feat: implementa primary e arguments"
```

---

## Task 3: Unary and the tight end of the precedence chain (multiplicative, additive)

Introduces the shared binary-level helper used by all six binary precedence levels (this task's two plus Task 4's four), and `unary`.

**Files:**
- Modify: `parser.py` — new `UNARY_OPERATORS`, `ADDITIVE_OPERATORS`, `MULTIPLICATIVE_OPERATORS` constants; new `_parse_binary_level` helper; `parse_unary`, `parse_additive`, `parse_multiplicative` bodies (`parser.py:225-232`).
- Test: `tests/test_parser_dev.py`

**Interfaces:**
- Consumes: `parse_primary` (Task 2).
- Produces: `_parse_binary_level(operand: Callable[[], Expr], operators: dict[TokenKind, BinaryOperator]) -> Expr` — reused verbatim by Task 4's four remaining levels, so its name and signature are load-bearing for that task. `parse_unary() -> Expr`, `parse_additive() -> Expr`, `parse_multiplicative() -> Expr`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_parser_dev.py
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
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest -q tests/test_parser_dev.py -k "unario or multiplicativa or aditiva"
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

```python
# constants, near TYPE_BY_TOKEN
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
```

```python
    # helper shared by every binary precedence level (this task + task 4)
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

    def parse_multiplicative(self) -> Expr:
        return self._parse_binary_level(self.parse_unary, MULTIPLICATIVE_OPERATORS)

    def parse_additive(self) -> Expr:
        return self._parse_binary_level(self.parse_multiplicative, ADDITIVE_OPERATORS)
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest -q tests/test_parser_dev.py -k "unario or multiplicativa or aditiva"
```

Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add parser.py tests/test_parser_dev.py
git commit -m "feat: implementa unary, multiplicative e additive"
```

---

## Task 4: Relational, equality, logical levels, and the expression entry point

Finishes the precedence chain using the same `_parse_binary_level` helper from Task 3, then wires `expression` to the top of it.

**Files:**
- Modify: `parser.py` — new `EQUALITY_OPERATORS`, `RELATIONAL_OPERATORS` constants; `parse_relational`, `parse_equality`, `parse_logical_and`, `parse_logical_or`, `parse_expression` bodies (`parser.py:210-223`).
- Test: `tests/test_parser_dev.py`

**Interfaces:**
- Consumes: `_parse_binary_level` (Task 3), `parse_additive` (Task 3).
- Produces: `parse_expression() -> Expr` — the method every statement-level parser in Tasks 5-7 calls for "parse one expression".

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_parser_dev.py


def test_relacional_e_igualdade():
    expr = make_parser("1 < 2 == true").parse_expression()
    assert expr.operator is BinaryOperator.EQUAL
    assert expr.left.operator is BinaryOperator.LESS


def test_logica_and_mais_apertada_que_or():
    expr = make_parser("true || false && true").parse_expression()
    assert expr.operator is BinaryOperator.LOGICAL_OR
    assert expr.right.operator is BinaryOperator.LOGICAL_AND


def test_parenteses_agora_fecham_o_ciclo_de_expressao():
    wrapped = make_parser("(42)").parse_primary()
    assert wrapped.value == 42
    assert wrapped.span.end_column == 5
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest -q tests/test_parser_dev.py -k "relacional or logica or ciclo_de_expressao"
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

```python
EQUALITY_OPERATORS = {
    TokenKind.EQUAL_EQUAL: BinaryOperator.EQUAL,
    TokenKind.NOT_EQUAL: BinaryOperator.NOT_EQUAL,
}
RELATIONAL_OPERATORS = {
    TokenKind.LESS: BinaryOperator.LESS,
    TokenKind.LESS_EQUAL: BinaryOperator.LESS_EQUAL,
    TokenKind.GREATER: BinaryOperator.GREATER,
    TokenKind.GREATER_EQUAL: BinaryOperator.GREATER_EQUAL,
}
```

```python
    def parse_expression(self) -> Expr:
        return self.parse_logical_or()

    def parse_logical_or(self) -> Expr:
        return self._parse_binary_level(
            self.parse_logical_and, {TokenKind.LOGICAL_OR: BinaryOperator.LOGICAL_OR}
        )

    def parse_logical_and(self) -> Expr:
        return self._parse_binary_level(
            self.parse_equality, {TokenKind.LOGICAL_AND: BinaryOperator.LOGICAL_AND}
        )

    def parse_equality(self) -> Expr:
        return self._parse_binary_level(self.parse_relational, EQUALITY_OPERATORS)

    def parse_relational(self) -> Expr:
        return self._parse_binary_level(self.parse_additive, RELATIONAL_OPERATORS)
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest -q tests/test_parser_dev.py
```

Expected: every test in the dev suite so far PASSES — the whole expression grammar is now done and self-consistent.

- [ ] **Step 5: Commit**

```bash
git add parser.py tests/test_parser_dev.py
git commit -m "feat: implementa relational, equality, logical_and, logical_or e expression"
```

---

## Task 5: Simple statements — declaration and id_or_call_statement

The first two statement forms. Both are leaves (they don't call `parse_block`/`parse_statement`), so they're testable in isolation before the mutually-recursive block/statement/control-flow group in Tasks 6-7.

**Files:**
- Modify: `parser.py:189-190` (`parse_declaration`), `parser.py:186-187` (`parse_id_or_call_statement`).
- Test: `tests/test_parser_dev.py`

**Interfaces:**
- Consumes: `parse_expression` (Task 4), `parse_arguments` (Task 2).
- Produces: `parse_declaration() -> Stmt` (a `VarDecl`), `parse_id_or_call_statement() -> Stmt` (an `Assignment` or `CallStmt`). Both feed `parse_statement` in Task 7.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_parser_dev.py
from ast_nodes import Assignment, CallStmt, VarDecl


def test_declaracao_com_e_sem_inicializador():
    sem_init = make_parser("int x;").parse_declaration()
    assert isinstance(sem_init, VarDecl) and sem_init.initializer is None
    com_init = make_parser("bool ativo = true;").parse_declaration()
    assert isinstance(com_init.initializer, BoolLiteral)


def test_atribuicao_constroi_identifierexpr_como_alvo():
    stmt = make_parser("x = 2;").parse_id_or_call_statement()
    assert isinstance(stmt, Assignment)
    assert isinstance(stmt.target, IdentifierExpr)
    assert stmt.target.name == "x"
    assert stmt.value.value == 2


def test_chamada_como_comando_forma_callstmt():
    stmt = make_parser("registrar();").parse_id_or_call_statement()
    assert isinstance(stmt, CallStmt)
    assert stmt.call.name == "registrar"


def test_atribuicao_encadeada_e_erro_sintatico():
    import pytest
    from parser import ParserError

    with pytest.raises(ParserError):
        make_parser("x = y = 1;").parse_id_or_call_statement()
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest -q tests/test_parser_dev.py -k "declaracao or atribuicao or chamada_como_comando"
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

```python
    def parse_declaration(self) -> Stmt:
        start = self.peek()
        type_ = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)
        initializer: Expr | None = None
        if self.match(TokenKind.ASSIGN) is not None:
            initializer = self.parse_expression()
        semicolon = self.expect(TokenKind.SEMICOLON)
        return VarDecl(type_, name.lexeme, initializer, span=self._span(start, semicolon))

    def parse_id_or_call_statement(self) -> Stmt:
        name = self.expect(TokenKind.IDENTIFIER)
        branch = self.expect({TokenKind.ASSIGN, TokenKind.LEFT_PAREN})
        if branch.kind is TokenKind.ASSIGN:
            value = self.parse_expression()
            semicolon = self.expect(TokenKind.SEMICOLON)
            target = IdentifierExpr(name.lexeme, span=self._token_span(name))
            return Assignment(target, value, span=self._span(name, semicolon))

        arguments = self.parse_arguments()
        right_paren = self.expect(TokenKind.RIGHT_PAREN)
        call = CallExpr(name.lexeme, arguments, span=self._span(name, right_paren))
        semicolon = self.expect(TokenKind.SEMICOLON)
        return CallStmt(call, span=self._span(name, semicolon))
```

`parse_id_or_call_statement` deliberately uses one `self.expect({ASSIGN, LEFT_PAREN})` rather than `match(ASSIGN)` then falling through to `expect(LEFT_PAREN)`: that keeps the reported `expected` set accurate (both alternatives) if neither token appears, per the assignment's diagnostic requirement.

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest -q tests/test_parser_dev.py -k "declaracao or atribuicao or chamada_como_comando"
```

Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add parser.py tests/test_parser_dev.py
git commit -m "feat: implementa declaration e id_or_call_statement"
```

---

## Task 6: print — items, adjacent string concatenation, and the statement

`print_item`, `string_literals` (the adjacent-string-merge rule from §4.2 of the assignment), and `print_statement`.

**Files:**
- Modify: `parser.py:201-208` (`parse_print_statement`, `parse_print_item`, `parse_string_literals`).
- Test: `tests/test_parser_dev.py`

**Interfaces:**
- Consumes: `parse_expression` (Task 4).
- Produces: `parse_print_statement() -> Stmt` (a `PrintStmt`), used by `parse_statement` in Task 7.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_parser_dev.py
from ast_nodes import PrintStmt, StringLiteral


def test_strings_adjacentes_viram_um_unico_stringliteral():
    literal = make_parser('"resultado " "final = "').parse_string_literals()
    assert isinstance(literal, StringLiteral)
    assert literal.value == "resultado final = "


def test_print_mistura_strings_e_expressoes():
    stmt = make_parser('print("resultado " "final = ", x);').parse_print_statement()
    assert isinstance(stmt, PrintStmt)
    assert len(stmt.items) == 2
    assert isinstance(stmt.items[0], StringLiteral)
    assert stmt.items[0].value == "resultado final = "
    assert isinstance(stmt.items[1], IdentifierExpr)


def test_print_vazio_e_erro_sintatico():
    import pytest
    from parser import ParserError

    with pytest.raises(ParserError):
        make_parser("print();").parse_print_statement()
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest -q tests/test_parser_dev.py -k "strings_adjacentes or print"
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

```python
    def parse_string_literals(self) -> StringLiteral:
        first = self.expect(TokenKind.STRING_LITERAL)
        value = str(first.value)
        last = first
        while self.check(TokenKind.STRING_LITERAL):
            token = self.advance()
            value += str(token.value)
            last = token
        return StringLiteral(value, span=self._span(first, last))

    def parse_print_item(self) -> PrintItem:
        if self.check(TokenKind.STRING_LITERAL):
            return self.parse_string_literals()
        return self.parse_expression()

    def parse_print_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_PRINT)
        self.expect(TokenKind.LEFT_PAREN)
        items = [self.parse_print_item()]
        while self.match(TokenKind.COMMA) is not None:
            items.append(self.parse_print_item())
        self.expect(TokenKind.RIGHT_PAREN)
        semicolon = self.expect(TokenKind.SEMICOLON)
        return PrintStmt(items, span=self._span(start, semicolon))
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest -q tests/test_parser_dev.py -k "strings_adjacentes or print"
```

Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add parser.py tests/test_parser_dev.py
git commit -m "feat: implementa print_item, string_literals e print_statement"
```

---

## Task 7: Control flow and blocks — the piece that wires everything together

`block`, `statement` (the dispatcher), `if_statement`, `while_statement`, `return_statement`. These are mutually recursive with each other and with everything from Tasks 5-6, so they land together. Once this task lands, `parse_function` → `parse_block` → `parse_statement` → (any statement form) is a complete path, and the *graded* suite (`tests/test_parser.py`) becomes runnable for the first time.

**Files:**
- Modify: `parser.py:180-199` (`parse_block`, `parse_statement`, `parse_if_statement`, `parse_while_statement`, `parse_return_statement`).
- Test: `tests/test_parser_dev.py`, then the full graded suite.

**Interfaces:**
- Consumes: everything from Tasks 1-6 (`parse_declaration`, `parse_id_or_call_statement`, `parse_print_statement`, `parse_expression`), plus `STATEMENT_START`/`TYPE_START` (given, module-level).
- Produces: `parse_block() -> Block`, `parse_statement() -> Stmt` — the two methods `parse_function` (already implemented) and `parse_if_statement`/`parse_while_statement` depend on.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_parser_dev.py
from ast_nodes import Block, IfStmt, ReturnStmt, WhileStmt


def test_bloco_vazio_e_bloco_aninhado():
    block = make_parser("{ { } }").parse_block()
    assert isinstance(block, Block)
    assert isinstance(block.statements[0], Block)
    assert block.statements[0].statements == []


def test_if_com_e_sem_else():
    sem_else = make_parser("if (true) { }").parse_if_statement()
    assert isinstance(sem_else, IfStmt) and sem_else.else_block is None
    com_else = make_parser("if (true) { } else { }").parse_if_statement()
    assert com_else.else_block is not None


def test_while_exige_chaves():
    stmt = make_parser("while (false) { }").parse_while_statement()
    assert isinstance(stmt, WhileStmt)

    import pytest
    from parser import ParserError

    with pytest.raises(ParserError):
        make_parser("while (false) return 1;").parse_while_statement()


def test_return_com_e_sem_valor():
    vazio = make_parser("return;").parse_return_statement()
    assert isinstance(vazio, ReturnStmt) and vazio.value is None
    com_valor = make_parser("return 2 + 3;").parse_return_statement()
    assert com_valor.value is not None


def test_comando_vazio_e_erro_sintatico():
    import pytest
    from parser import ParserError

    with pytest.raises(ParserError):
        make_parser(";").parse_statement()
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest -q tests/test_parser_dev.py -k "bloco or if_com or while_exige or return_com or comando_vazio"
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

```python
    def parse_block(self) -> Block:
        start = self.expect(TokenKind.LEFT_BRACE)
        statements: list[Stmt] = []
        while self.peek().kind in STATEMENT_START:
            statements.append(self.parse_statement())
        end = self.expect(TokenKind.RIGHT_BRACE)
        return Block(statements, span=self._span(start, end))

    def parse_statement(self) -> Stmt:
        kind = self.peek().kind
        if kind in TYPE_START:
            return self.parse_declaration()
        if kind is TokenKind.IDENTIFIER:
            return self.parse_id_or_call_statement()
        if kind is TokenKind.KW_IF:
            return self.parse_if_statement()
        if kind is TokenKind.KW_WHILE:
            return self.parse_while_statement()
        if kind is TokenKind.KW_RETURN:
            return self.parse_return_statement()
        if kind is TokenKind.KW_PRINT:
            return self.parse_print_statement()
        if kind is TokenKind.LEFT_BRACE:
            return self.parse_block()
        self.expect(STATEMENT_START)

    def parse_if_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_IF)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        then_block = self.parse_block()
        else_block: Block | None = None
        last: Token | Node = then_block
        if self.match(TokenKind.KW_ELSE) is not None:
            else_block = self.parse_block()
            last = else_block
        return IfStmt(condition, then_block, else_block, span=self._span(start, last))

    def parse_while_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_WHILE)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        body = self.parse_block()
        return WhileStmt(condition, body, span=self._span(start, body))

    def parse_return_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_RETURN)
        value: Expr | None = None
        if self.peek().kind in EXPRESSION_START:
            value = self.parse_expression()
        semicolon = self.expect(TokenKind.SEMICOLON)
        return ReturnStmt(value, span=self._span(start, semicolon))
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest -q tests/test_parser_dev.py
python -m pytest -q tests/test_parser.py
```

Expected: the entire dev suite passes, and `tests/test_parser.py` — the graded public suite, untouched since Task 0 — now passes end to end (it was failing on `NotImplementedError` for every test until this task).

- [ ] **Step 5: Commit**

```bash
git add parser.py tests/test_parser_dev.py
git commit -m "feat: implementa block, statement, if/while/return_statement"
```

---

## Task 8: Full verification pass

Nothing left to implement — `parser.py` has zero `NotImplementedError` left. This task is the checklist from §9 of `ENUNCIADO.pdf`, run for real.

**Files:** none modified; this task only runs and inspects.

- [ ] **Step 1: Full test suite, both public and dev**

```bash
python -m pytest -q
```

Expected: 0 failures. If anything fails, it's a real bug — go back to the task that owns the failing construct, not around it.

- [ ] **Step 2: Manual run against the provided fixtures**

```bash
python runner.py --format tree test.mc
python runner.py --format tree tests/cases/valid/integrated.mc
python runner.py tests/cases/invalid/missing_semicolon.mc
```

Expected: first two print a tree AST with exit code 0; the third prints `erro sintático em 3:1: esperado {SEMICOLON}, encontrado RIGHT_BRACE ('}')`-shaped output on stderr and exits with status 1 (check with `echo $?` / `$LASTEXITCODE`).

- [ ] **Step 3: Spot-check spans**

```bash
python runner.py --format tree --show-spans tests/cases/valid/expressions.mc
```

Expected: the `10 - 2 * 3 - 1` expression's outer `BinaryExpr` span starts at the `1` in `return` line's first non-space column and ends right after the final `1`; nested spans nest correctly (no span extending past its parent's).

- [ ] **Step 4: DOT output round-trip (optional, needs Graphviz installed)**

```bash
python runner.py --format dot test.mc > ast.dot
dot -Tsvg ast.dot -o ast.svg
```

Skip if `dot` isn't installed locally — this isn't graded by pytest, only mentioned as a nice-to-have visualization in §8.

- [ ] **Step 5: Checklist from §9 of ENUNCIADO.pdf**

- [ ] `Lexer.py` (+ `microc_automato.py`, `microc_cursor.py`) is the group's real Etapa 1 implementation, not the skeleton.
- [ ] Every `parse_*` method is implemented (`grep -n "NotImplementedError" parser.py` returns nothing).
- [ ] Each construct consumes only its own tokens; lists preserve source order (covered by the tests above).
- [ ] Associativity, adjacent-string concatenation, and spans follow the assignment (Tasks 3, 4, 6, and this task's Step 3).
- [ ] No semantic rules were implemented in the parser (no name resolution, no type checks, no `main` check — confirm by re-reading `parser.py` top to bottom once).
- [ ] `python -m pytest -q` passes.
- [ ] The latest commit is pushed to the correct GitHub Classroom repo and GitHub Actions is green.

- [ ] **Step 6: Push and confirm CI**

```bash
git push
```

Then check the **Actions** tab on GitHub for a green run, per the assignment's own final checklist item.
