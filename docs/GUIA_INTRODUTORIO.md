# Guia introdutório — Parser LL(1) e AST do MicroC (Etapa 3)

> Este documento assume que você nunca viu este projeto. Ele parte do zero: o
> que foi pedido, os conceitos necessários para ler o código, e depois
> `parser.py`, bloco a bloco, com o raciocínio por trás de cada decisão.
>
> Para o plano de implementação passo a passo que guiou esta branch (tasks,
> testes escritos antes do código, ordem de construção), veja
> [`superpowers/plans/2026-09-10-parser-microc.md`](superpowers/plans/2026-09-10-parser-microc.md).
> Este guia é mais longo e didático de propósito — é o ponto de entrada para
> quem está vendo o projeto pela primeira vez.

## Sumário

1. [Contexto: o que é este projeto](#1-contexto-o-que-é-este-projeto)
2. [O que foi pedido (o enunciado)](#2-o-que-foi-pedido-o-enunciado)
3. [O que veio pronto vs. o que foi implementado](#3-o-que-veio-pronto-vs-o-que-foi-implementado)
4. [Conceitos necessários antes do código](#4-conceitos-necessários-antes-do-código)
5. [Mapa da solução](#5-mapa-da-solução)
6. [`parser.py`, bloco a bloco](#6-parserpy-bloco-a-bloco)
7. [Exemplo ponta a ponta: `10 - 2 * 3 - 1` e `print` com strings adjacentes](#7-exemplo-ponta-a-ponta-10---2--3---1-e-print-com-strings-adjacentes)
8. [Como rodar e testar](#8-como-rodar-e-testar)
9. [Conformidade com o enunciado](#9-conformidade-com-o-enunciado)
10. [Decisões que valem atenção](#10-decisões-que-valem-atenção)

---

## 1. Contexto: o que é este projeto

Este é o **Projeto MicroC — Etapa 3**, da disciplina de Compiladores (PUC
Campinas, 2s/2026). É a continuação direta da Etapa 1 (lexer). O pipeline
completo do compilador, com esta etapa em destaque:

```
fonte MicroC → Lexer (Etapa 1) → tokens → Parser LL(1) (Etapa 3) → objeto Program (AST)
```

**O que um parser faz, em uma frase:** ele lê a sequência de tokens (não mais
o texto bruto — essa etapa já passou) e reconhece nela a estrutura
gramatical da linguagem, construindo ao mesmo tempo uma **árvore sintática
abstrata** (AST) — uma representação em memória do programa, feita de
objetos Python (`Program`, `FunctionDecl`, `IfStmt`, `BinaryExpr`, ...) em
vez de texto. É a mesma ideia de, depois de separar uma frase em palavras
(etapa do lexer), descobrir qual é o sujeito, o verbo e o objeto — só que
aqui a "gramática" é a do MicroC, e o resultado alimenta diretamente as
próximas etapas do compilador (análise semântica e geração de assembly
RISC-V 64), que nunca mais voltam a olhar para o texto-fonte ou para os
tokens brutos.

Por exemplo, os tokens de `return 10 - 2 * 3;` viram esta árvore (formato
`tree` do `runner.py`):

```
ReturnStmt
└── value: BinaryExpr
    ├── operator: -
    ├── left: IntLiteral
    │   └── value: 10
    └── right: BinaryExpr
        ├── operator: *
        ├── left: IntLiteral
        │   └── value: 2
        └── right: IntLiteral
            └── value: 3
```

Note que a árvore já reflete a **precedência** de `*` sobre `-` (a
multiplicação vira um nó filho dentro da subtração, não irmã dela) — isso
não é um passo separado, é uma consequência direta de como o parser é
estruturado (seção 6.5).

---

## 2. O que foi pedido (o enunciado)

O `ENUNCIADO.pdf` na raiz do repositório é o documento oficial. Resumo do
que ele exige, seção por seção.

### 2.1 A gramática é fixa e já vem pronta

`source_grammar.ebnf` contém a gramática LL(1) completa da MicroC — **não é
para ser alterada, nem lida em tempo de execução** (nada de escrever um
leitor de EBNF). Ela é só a especificação, para leitura humana; o código de
`parser.py` que *é* a implementação dela.

Cada não-terminal da gramática vira um método `parse_<nome>`. A notação
EBNF usada:

| Notação | Significado | Como vira código |
|---|---|---|
| `A B` (justapostos) | sequência | uma chamada depois da outra |
| `A \| B` | alternativa | `if`/`elif` decidido pelo token atual |
| `X?` | zero ou uma vez | um `if` opcional |
| `X*` | zero ou mais vezes | um `while` |
| `X+` | uma ou mais vezes | uma chamada seguida de um `while` |
| `( ... )` | agrupamento | não vira nada no código, só prioridade na leitura da regra |

### 2.2 O parser é por descida recursiva, LL(1), sem backtracking

- **Descida recursiva:** cada não-terminal é uma função; para reconhecer uma
  sequência, ela chama as funções dos não-terminais que a compõem, na ordem
  em que aparecem na regra.
- **LL(1):** a decisão de qual alternativa seguir é tomada olhando **só o
  token atual** (nenhum lookahead maior). É por isso que a gramática
  fornecida foi desenhada para ser LL(1) — cada alternativa de cada regra
  começa com um conjunto de tokens diferente do das outras.
- **Sem backtracking:** o parser nunca tenta uma alternativa, falha, e volta
  para tentar outra. Cada decisão, uma vez tomada, é definitiva.
- Nas expressões binárias, cada nível de precedência chama o nível
  imediatamente mais apertado e usa um **laço** para produzir associação à
  **esquerda** (`10 - 3 - 2` deve formar `(10 - 3) - 2`, nunca `10 - (3 -
  2)`). Operadores unários (`-`, `!`) usam **recursão** e associam à
  **direita** (`- - x` é `-(-(x))`).
- Um método nunca pode consumir o primeiro token da construção seguinte —
  cada `parse_*` para exatamente onde sua própria produção termina.

### 2.3 A AST é a interface pública para as próximas etapas

`ast_nodes.py` já vem pronto, com todos os nós, campos, enums e
serialização — e **não pode ser alterado**. Os campos concretos mais
importantes (todos com `span: SourceSpan` e `metadata: dict` herdados de
`Node`):

```
Program(functions)
FunctionDecl(return_type, name, parameters, body)
Parameter(type, name)
Block(statements)
VarDecl(type, name, initializer)          # initializer pode ser None
Assignment(target, value)                  # target é sempre um IdentifierExpr
CallStmt(call)                              # call é um CallExpr
IfStmt(condition, then_block, else_block)   # else_block pode ser None
WhileStmt(condition, body)
ReturnStmt(value)                           # value pode ser None
PrintStmt(items)                            # items: Expr ou StringLiteral
BinaryExpr(operator, left, right)
UnaryExpr(operator, operand)
CallExpr(name, arguments)
IdentifierExpr(name)
IntLiteral(value)
BoolLiteral(value)
StringLiteral(value)
```

Pontos que o enunciado destaca explicitamente:

- `TypeName`, `UnaryOperator` e `BinaryOperator` são **enums próprios da
  AST**, não os `TokenKind` do lexer — o parser traduz um pelo outro.
- **Parênteses não criam nó**: `(42)` produz o mesmo `IntLiteral` que `42`
  produziria, só que com o `span` ampliado para cobrir os parênteses
  também.
- Uma chamada usada como **comando** vira `CallStmt(call=CallExpr(...))`;
  usada como **valor** dentro de uma expressão, o `CallExpr` aparece
  direto, sem o `CallStmt` por cima.
- `string_literals ::= STRING_LITERAL+` deve **concatenar** os `value`
  decodificados de tokens de string adjacentes num único `StringLiteral`
  (seção 7 deste guia mostra um exemplo completo).
- `metadata` começa vazio em todo nó e é para uso de etapas **futuras**
  (semântica) — o parser nunca deve gravar nada nele.

### 2.4 Erros sintáticos

- Uma única exceção, `ParserError(token, expected)`, com propriedades
  públicas `token`, `expected`, `line`, `column` — já vem implementada no
  starter.
- O parser **para no primeiro erro**. Não há recuperação, sincronização nem
  acúmulo de múltiplos erros.
- O formato textual (também já implementado) é:

  ```
  erro sintático em 3:1: esperado {SEMICOLON}, encontrado RIGHT_BRACE ('}')
  ```

- São exemplos explícitos de **erro sintático** (não semântico): `print()`
  vazio, string fora de um `print`, uma expressão sozinha como comando
  (`1 + 2;`), comando vazio (`;` sozinho), atribuição encadeada (`x = y =
  1;`), declaração múltipla, `if`/`while` sem chaves.
- São **aceitos** pelo parser (o erro, se houver, é semântico, de uma etapa
  futura): arquivo vazio, funções duplicadas, programa sem `main`, e até
  algo como `int x = true;` — o parser só verifica a **forma**, nunca
  **tipos**, **nomes** ou **escopos** (seção 5 do enunciado, "limite entre
  sintaxe e semântica").

### 2.5 Restrições

Proibido: usar gerador de parser pronto (SLY, PLY, Lark, ANTLR, ...);
reconhecer o programa com expressões regulares; implementar backtracking;
rodar análise semântica durante o parsing; alterar a EBNF; ou substituir os
objetos da AST por dicionários / pelo JSON do `runner.py` (JSON, árvore de
texto e DOT são só *visualizações* — o resultado real da etapa é o objeto
`Program`).

---

## 3. O que veio pronto vs. o que foi implementado

O "starter" já trazia:

| Arquivo | O que já vinha pronto |
|---|---|
| `source_grammar.ebnf` | A gramática LL(1) completa — normativa, não é para alterar. |
| `ast_nodes.py` | Todos os nós, enums, `SourceSpan`, `metadata`, e `ast_to_dict` para serialização. **Não podia ser alterado.** |
| `ast_printer.py` | `format_ast` (árvore no terminal) e `ast_to_dot` (Graphviz). Genéricos — percorrem os campos do dataclass, não precisam conhecer cada tipo de nó. |
| `parser.py` | `TYPE_START`/`EXPRESSION_START`/`STATEMENT_START`, `ParserError`, a infraestrutura de `Parser` (`peek`/`check`/`advance`/`match`/`expect`, os quatro helpers de `span`), e três métodos completos: `parse`, `parse_program`, `parse_function`, `parse_type`. Os demais `parse_*`: `raise NotImplementedError`. |
| `Lexer.py` (deste repo) | Só a interface publicada na Etapa 1 — precisou ser **substituído** pela implementação real do grupo (ver `git log`, branch `etapa1-lexer` do repositório `Lexer`). |
| `runner.py`, `tests/test_parser.py`, `tests/cases/**` | Completos, não podiam ser alterados. |
| `README.md`, `requirements-dev.txt`, `pyproject.toml`, workflow do GitHub Actions | Configuração de ambiente e CI. |

O que foi **implementado** nesta etapa:

| Arquivo | Conteúdo |
|---|---|
| `Lexer.py`, `microc_automato.py`, `microc_cursor.py` | Copiados da implementação real da Etapa 1 do grupo (branch `etapa1-lexer` do repositório `Lexer`) — não escritos aqui, só trazidos para dentro deste repositório, como o enunciado pede. |
| `parser.py` | Todos os 20 métodos `parse_*` que restavam, mais um helper privado (`_parse_binary_level`) e quatro conjuntos/dicionários de apoio (`PRIMARY_START`, `UNARY_OPERATORS`, `EQUALITY_OPERATORS`, `RELATIONAL_OPERATORS`, `ADDITIVE_OPERATORS`, `MULTIPLICATIVE_OPERATORS`). `ParserError`, os campos e assinaturas públicas de `Parser` continuam exatamente como vieram. |
| `tests/test_parser_dev.py` | **Novo, não fazia parte do starter e não é a suíte avaliada** (essa é `tests/test_parser.py`, intocada). É uma suíte de desenvolvimento, escrita teste-antes-do-código por não-terminal, chamando os métodos `parse_*` diretamente (ex.: `Parser(tokens).parse_primary()`) em vez de sempre passar por `parse()` — útil porque, num parser recursivo descendente, testar um nível de precedência isoladamente não exige que o resto da gramática já exista. |

---

## 4. Conceitos necessários antes do código

### Descida recursiva (recursive descent)

A forma mais direta de implementar um parser à mão: um método por
não-terminal da gramática, que chama os métodos dos não-terminais que
aparecem do lado direito da sua produção, na mesma ordem. `function ::= type
IDENTIFIER LEFT_PAREN parameter_list? RIGHT_PAREN block` (já dado no
starter, `parse_function`) é o exemplo mais simples: chama `parse_type()`,
consome um `IDENTIFIER`, consome `(`, opcionalmente chama
`parse_parameter_list()`, consome `)`, chama `parse_block()` — na ordem
exata da regra.

### LL(1) e lookahead de um token

"LL(1)" quer dizer: lendo a entrada da **esquerda** para a direita (**L**),
construindo a derivação mais à **esquerda** (**L**), decidindo cada passo
olhando **1** token à frente. Isso só é possível porque a gramática
fornecida foi desenhada para isso — em nenhum ponto duas alternativas da
mesma regra começam com o mesmo token. Por exemplo, em `statement`, a
alternativa `declaration` começa com um token de `TYPE_START`
(`KW_INT`/`KW_BOOL`/`KW_VOID`), `id_or_call_statement` começa com
`IDENTIFIER`, `if_statement` com `KW_IF` — nunca há ambiguidade sobre qual
`parse_*` chamar só de olhar o token atual (`self.peek().kind`).

### Precedência e associatividade, sem tabela de precedência

Expressões aritméticas/lógicas/relacionais não usam uma tabela de
precedência genérica (como um parser LR faria) — a precedência é
**codificada na própria cadeia de chamadas** entre métodos, do operador de
**menor** precedência para o de **maior**:

```
expression → logical_or → logical_and → equality → relational → additive → multiplicative → unary → primary
```

Cada nível só "vê" os operadores do seu próprio nível; para obter os
operandos, ele sempre chama o próximo nível da cadeia (que já resolve tudo
que tem precedência maior). Isso é o que faz `2 + 3 * 4` virar `2 + (3 *
4)` automaticamente: `additive` (nível de `+`) pede seu operando esquerdo a
`multiplicative` (nível de `*`), que já devolve `3 * 4` como uma única
sub-árvore antes de `additive` sequer ver o `+`.

**Associatividade à esquerda** (a maioria dos operadores binários, como
`-`): depois de obter o primeiro operando, um **laço** (`while`) continua
consumindo `operador operando` enquanto o token atual for um dos operadores
daquele nível, e a cada volta o resultado acumulado vira o novo lado
esquerdo. **Associatividade à direita** (operadores unários `-x`, `!x`): em
vez de laço, **recursão** — `parse_unary` chama a si mesma para o operando,
então `- - x` naturalmente vira `NEGATE(NEGATE(x))` de dentro para fora.

### AST (árvore sintática abstrata) vs. árvore de derivação

Uma árvore de derivação (parse tree / árvore concreta) teria um nó para
*cada* símbolo da gramática, incluindo pontuação (`(`, `)`, `;`) e
não-terminais auxiliares só de agrupamento. Uma **AST** guarda só o que
importa semanticamente: por isso parênteses não geram nó (só afetam qual
sub-árvore vira filha de qual), `;` nunca aparece na árvore, e não-terminais
puramente "de gramática" (como `id_or_call_statement`, que é só uma forma
de agrupar duas alternativas de comando) não têm nó próprio — viram
diretamente `Assignment` ou `CallStmt`, dependendo de qual alternativa foi
reconhecida.

### `SourceSpan` e por que ele nunca é uma lista de posições

Cada nó guarda só **início** (linha/coluna inclusivas) e **fim**
(linha/coluna exclusivas) — não uma lista de spans dos tokens que o
formaram. Construir o span de um nó composto é sempre "do início do
primeiro pedaço até o fim do último pedaço" (é isso que o helper `_span`,
dado pelo starter, calcula). Um caso interessante disso é
`string_literals`: mesmo concatenando **múltiplos** tokens `STRING_LITERAL`
num único `StringLiteral`, o span final é só `_span(primeiro_token,
último_token)` — os tokens do meio (e os espaços/comentários entre eles)
somem da árvore, mas continuam implicitamente cobertos pelo intervalo.

---

## 5. Mapa da solução

```
                    ┌───────────────────────┐
                    │  source_grammar.ebnf   │   Especificação (não executa,
                    │  (starter, normativo)  │   só orienta a leitura humana)
                    └───────────┬────────────┘
                                │ cada não-terminal vira 1 método
                    ┌───────────▼────────────┐
                    │       parser.py         │   Parser: infra (starter) +
                    │                         │   20 métodos parse_* (esta etapa)
                    └───────────┬────────────┘
                                │ constrói e devolve
                    ┌───────────▼────────────┐
                    │      ast_nodes.py       │   Program, FunctionDecl, ...
                    │      (starter)          │   (dataclasses imutáveis na forma,
                    │                         │    mutáveis no armazenamento)
                    └───────────┬────────────┘
                                │ consumido por
              ┌─────────────────┼─────────────────┐
    ┌─────────▼─────────┐ ┌─────▼──────┐  ┌────────▼────────┐
    │   ast_printer.py    │ │ runner.py  │  │ tests/test_parser│
    │  (tree / dot, starter)│ │ (json/tree/dot,│  │  .py (starter,   │
    │                     │ │  starter)  │  │  suíte avaliada) │
    └─────────────────────┘ └────────────┘  └──────────────────┘
```

A entrada pública de toda a etapa é uma linha só:

```python
program: Program = Parser(tokens).parse()
```

`tokens` vem do `Lexer` da Etapa 1 (`Lexer(source).scan()`) — o parser nunca
olha para o texto-fonte, só para a lista de `Token`.

---

## 6. `parser.py`, bloco a bloco

### 6.1 O que já vinha pronto (infraestrutura)

```python
TYPE_START = {TokenKind.KW_INT, TokenKind.KW_BOOL, TokenKind.KW_VOID}
EXPRESSION_START = {
    TokenKind.IDENTIFIER, TokenKind.INT_LITERAL, TokenKind.KW_FALSE,
    TokenKind.KW_TRUE, TokenKind.LEFT_PAREN, TokenKind.LOGICAL_NOT, TokenKind.MINUS,
}
STATEMENT_START = TYPE_START | {
    TokenKind.IDENTIFIER, TokenKind.KW_IF, TokenKind.KW_WHILE,
    TokenKind.KW_RETURN, TokenKind.KW_PRINT, TokenKind.LEFT_BRACE,
}
```

Três conjuntos de tokens que respondem à pergunta "que token(s) podem
começar esta construção?" — a base de toda decisão LL(1) neste parser.
`EXPRESSION_START` inclui `LOGICAL_NOT`/`MINUS` porque uma expressão *pode*
começar com um operador unário (`!x`, `-5`); `STATEMENT_START` é a união de
tudo que pode começar um comando.

`ParserError`, e em `Parser`: `peek`/`check`/`advance`/`match`/`expect`
(consulta e consumo de tokens), `_token_span`/`_start`/`_end`/`_span`
(cálculo de `SourceSpan`), e três métodos já implementados —
`parse_program`, `parse_function`, `parse_type` — que servem de **exemplo**
do padrão a seguir: sequência é chamada direta atrás da outra; `?` é um
`if`; `*` é um `while`; o span do nó vai de `_span(primeiro_token_ou_nó,
último_token_ou_nó)`.

### 6.2 Parâmetros: o par mais simples

```ebnf
parameter_list ::= parameter (COMMA parameter)*
parameter ::= type IDENTIFIER
```

```python
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

O par "primeiro elemento obrigatório, depois um `while match(COMMA)`" é o
molde de **toda** lista separada por vírgula na gramática (reaparece em
`arguments` e no laço de `print_statement`) — `X (COMMA X)*` sempre vira
"chame uma vez, depois `while match(COMMA): chame de novo`", nunca um `for`
com contagem ou um `split`.

### 6.3 `primary` e `arguments`: a base de toda expressão

```ebnf
primary ::= LEFT_PAREN expression RIGHT_PAREN
          | IDENTIFIER (LEFT_PAREN arguments RIGHT_PAREN)?
          | INT_LITERAL | KW_TRUE | KW_FALSE
arguments ::= (expression (COMMA expression)*)?
```

```python
PRIMARY_START = {
    TokenKind.LEFT_PAREN, TokenKind.IDENTIFIER, TokenKind.INT_LITERAL,
    TokenKind.KW_TRUE, TokenKind.KW_FALSE,
}
```

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
            return CallExpr(identifier.lexeme, arguments, span=self._span(identifier, right_paren))
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
```

Cada `if` testa uma alternativa da regra, na mesma ordem em que ela aparece
na EBNF. Três decisões merecem destaque:

- **`PRIMARY_START` é um conjunto próprio, mais estreito que
  `EXPRESSION_START`.** `EXPRESSION_START` inclui `LOGICAL_NOT`/`MINUS`
  porque uma *expressão* pode começar com um unário — mas quando a execução
  chega ao fim de `parse_primary`, isso já não é mais possível: quem chama
  `parse_primary` é sempre `parse_unary`, e `parse_unary` já testou e
  descartou `LOGICAL_NOT`/`MINUS` antes de delegar para cá (seção 6.4). Se o
  último `self.expect(...)` daqui usasse `EXPRESSION_START`, a mensagem de
  erro diria "esperado {..., LOGICAL_NOT, MINUS}" para um token que, nesse
  ponto exato do parsing, **nunca** poderia mesmo ser aceito — informação
  falsa na exceção. `PRIMARY_START` existe só para manter o `expected` da
  `ParserError` **preciso**, como o enunciado exige (§6).
- **Parênteses não criam nó — a linha `expr.span = self._span(left_paren,
  right_paren)` é literalmente essa regra em código.** `parse_expression()`
  já devolveu um nó completo (`expr`) com seu próprio span, do tamanho só da
  expressão interna; a linha seguinte **substitui** esse span por um maior
  (cobrindo os parênteses também) no mesmo objeto, sem embrulhar `expr` em
  nada. Isso só é possível porque `Node` (base de todo nó da AST) é um
  `@dataclass(slots=True)` **sem** `frozen=True` — diferente do `Token` do
  lexer, que é imutável (`frozen=True`), um nó da AST pode ter campos
  reatribuídos depois de criado. `SourceSpan` em si é imutável
  (`frozen=True`); o que muda é *qual* `SourceSpan` o nó aponta.
- **A chamada é opcional só depois de já ter um `IDENTIFIER`.** `IDENTIFIER
  (LEFT_PAREN arguments RIGHT_PAREN)?` — por isso o `if
  self.match(TokenKind.LEFT_PAREN)` fica **aninhado dentro** do bloco que já
  consumiu o identificador, nunca antes.

```python
def parse_arguments(self) -> list[Expr]:
    if self.peek().kind not in EXPRESSION_START:
        return []
    arguments = [self.parse_expression()]
    while self.match(TokenKind.COMMA) is not None:
        arguments.append(self.parse_expression())
    return arguments
```

`(expression (COMMA expression)*)?` inteiro é opcional — por isso o método
começa checando se o token atual sequer poderia iniciar uma expressão
(`EXPRESSION_START`); se não, `()` foi encontrado e a lista é vazia, sem
consumir nada. Esse `if` de saída antecipada é o que faz `registrar()` (sem
argumentos) e `calcular(1, true)` (com argumentos) passarem pelo mesmo
método sem nenhum caso especial extra.

### 6.4 A cadeia de precedência e o helper `_parse_binary_level`

```ebnf
expression     ::= logical_or
logical_or     ::= logical_and (LOGICAL_OR logical_and)*
logical_and    ::= equality (LOGICAL_AND equality)*
equality       ::= relational ((EQUAL_EQUAL | NOT_EQUAL) relational)*
relational     ::= additive ((LESS | LESS_EQUAL | GREATER | GREATER_EQUAL) additive)*
additive       ::= multiplicative ((PLUS | MINUS) multiplicative)*
multiplicative ::= unary ((STAR | SLASH | PERCENT) unary)*
unary          ::= (LOGICAL_NOT | MINUS) unary | primary
```

As seis regras `logical_or` até `multiplicative` têm **exatamente a mesma
forma**: chame o nível mais apertado, depois `while` o token atual for um
dos operadores deste nível, consuma-o, chame o nível mais apertado de novo,
e monte um `BinaryExpr` com o resultado acumulado até agora como `left`.
Escrever essa lógica seis vezes seria repetição pura — por isso ela foi
extraída para um único helper privado, parametrizado por "qual é o próximo
nível" e "quais tokens contam como operador deste nível, e para qual
`BinaryOperator` cada um mapeia":

```python
def _parse_binary_level(self, operand, operators: dict[TokenKind, BinaryOperator]) -> Expr:
    left = operand()
    while True:
        token = self.match(*operators.keys())
        if token is None:
            return left
        right = operand()
        left = BinaryExpr(operators[token.kind], left, right, span=self._span(left, right))
```

`operand` é uma referência a método (`self.parse_multiplicative`, por
exemplo — passada sem `()`, para ser chamada dentro do helper), e
`operators` é um dicionário `TokenKind → BinaryOperator` (a tradução do
token do lexer para o enum da AST). Os quatro níveis com mais de um
operador têm seu dicionário definido uma vez, como constante de módulo:

```python
EQUALITY_OPERATORS = {TokenKind.EQUAL_EQUAL: BinaryOperator.EQUAL, TokenKind.NOT_EQUAL: BinaryOperator.NOT_EQUAL}
RELATIONAL_OPERATORS = {TokenKind.LESS: BinaryOperator.LESS, TokenKind.LESS_EQUAL: BinaryOperator.LESS_EQUAL,
                         TokenKind.GREATER: BinaryOperator.GREATER, TokenKind.GREATER_EQUAL: BinaryOperator.GREATER_EQUAL}
ADDITIVE_OPERATORS = {TokenKind.PLUS: BinaryOperator.ADD, TokenKind.MINUS: BinaryOperator.SUBTRACT}
MULTIPLICATIVE_OPERATORS = {TokenKind.STAR: BinaryOperator.MULTIPLY, TokenKind.SLASH: BinaryOperator.DIVIDE,
                             TokenKind.PERCENT: BinaryOperator.REMAINDER}
```

E cada `parse_*` da cadeia vira uma linha:

```python
def parse_expression(self) -> Expr:
    return self.parse_logical_or()

def parse_logical_or(self) -> Expr:
    return self._parse_binary_level(self.parse_logical_and, {TokenKind.LOGICAL_OR: BinaryOperator.LOGICAL_OR})

def parse_logical_and(self) -> Expr:
    return self._parse_binary_level(self.parse_equality, {TokenKind.LOGICAL_AND: BinaryOperator.LOGICAL_AND})

def parse_equality(self) -> Expr:
    return self._parse_binary_level(self.parse_relational, EQUALITY_OPERATORS)

def parse_relational(self) -> Expr:
    return self._parse_binary_level(self.parse_additive, RELATIONAL_OPERATORS)

def parse_additive(self) -> Expr:
    return self._parse_binary_level(self.parse_multiplicative, ADDITIVE_OPERATORS)

def parse_multiplicative(self) -> Expr:
    return self._parse_binary_level(self.parse_unary, MULTIPLICATIVE_OPERATORS)
```

`logical_or`/`logical_and` têm só **um** operador cada, então seu
dicionário é montado ali mesmo, inline, sem virar constante de módulo — não
há necessidade de reuso para um único par chave/valor. `expression` em si
não faz nada além de apontar para o topo da cadeia (`logical_or`, a menor
precedência) — é só o nome público que o resto da gramática usa
(`return_statement`, `arguments`, `print_item`, etc. todos chamam
`parse_expression()`, nunca `parse_logical_or()` diretamente).

`unary`, por outro lado, **não** usa o helper — ele é assimétrico dos
demais porque associa à **direita**, via recursão, não laço:

```python
UNARY_OPERATORS = {TokenKind.LOGICAL_NOT: UnaryOperator.NOT, TokenKind.MINUS: UnaryOperator.NEGATE}

def parse_unary(self) -> Expr:
    token = self.match(*UNARY_OPERATORS.keys())
    if token is not None:
        operand = self.parse_unary()  # recursão, não laço — associa à direita
        return UnaryExpr(UNARY_OPERATORS[token.kind], operand, span=self._span(token, operand))
    return self.parse_primary()
```

Se o token atual for `!` ou `-`, consome-o e chama **a si mesma de novo**
para o operando (permitindo `- - x`, `!!x`, ...); a base da recursão é
"quando não sobra mais unário, delega para `primary`".

### 6.5 `declaration` e `id_or_call_statement`

```ebnf
declaration ::= type IDENTIFIER (ASSIGN expression)? SEMICOLON
id_or_call_statement ::= IDENTIFIER (ASSIGN expression | LEFT_PAREN arguments RIGHT_PAREN) SEMICOLON
```

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
```

Tradução direta da regra: sequência vira chamadas em fila, `(ASSIGN
expression)?` vira um `if`. `initializer` começa `None` e só é preenchido
se o `if` disparar — exatamente o contrato de `VarDecl.initializer` descrito
no enunciado (pode ser `None`).

```python
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

Esta é a única regra da gramática em que, depois do primeiro token
(`IDENTIFIER`), existem **duas** continuações válidas (`ASSIGN` ou
`LEFT_PAREN`) — não uma opcional e uma obrigatória, mas uma escolha real. A
decisão de design aqui foi usar **um único** `self.expect({ASSIGN,
LEFT_PAREN})`, que consome o token **e** informa qual dos dois apareceu (via
`branch.kind`), em vez do padrão mais óbvio "`match(ASSIGN)`, senão
`expect(LEFT_PAREN)`". A diferença aparece só quando **nenhum dos dois**
aparece: com `expect({ASSIGN, LEFT_PAREN})`, a `ParserError` resultante tem
`expected == {ASSIGN, LEFT_PAREN}` — o conjunto *real* de continuações
válidas naquele ponto da gramática. Com o padrão "`match` depois `expect`
avulso", o erro reportaria só `expected == {LEFT_PAREN}`, escondendo que
`ASSIGN` também seria aceito ali — uma mensagem de diagnóstico
tecnicamente incompleta. Um `Assignment` sempre embrulha o alvo num
`IdentifierExpr` novo (o enunciado exige isso: "o alvo de `Assignment` é um
`IdentifierExpr`"), e uma chamada usada como comando sempre fica embrulhada
em `CallStmt` (diferente de uma chamada usada como valor, que devolve o
`CallExpr` puro — isso acontece em `parse_primary`, seção 6.3).

**Por que `x = y = 1;` é rejeitado:** a gramática nunca definiu "atribuição"
como uma forma de expressão — só `id_or_call_statement` (um **comando**)
tem `ASSIGN`. Ao processar `x = y = 1;`, o parser entra no ramo `ASSIGN`,
chama `parse_expression()` para o lado direito, que sobe e desce toda a
cadeia de precedência e para em `y` (um `IdentifierExpr`) — porque `=` não
é um operador de nenhum nível de expressão. De volta em
`parse_id_or_call_statement`, o próximo `self.expect(TokenKind.SEMICOLON)`
encontra `=` em vez de `;`, e o erro dispara sozinho, sem nenhum código
dedicado para "detectar encadeamento".

### 6.6 `print_item`, `string_literals`, `print_statement`

```ebnf
print_statement ::= KW_PRINT LEFT_PAREN print_item (COMMA print_item)* RIGHT_PAREN SEMICOLON
print_item ::= expression | string_literals
string_literals ::= STRING_LITERAL+
```

```python
def parse_print_statement(self) -> Stmt:
    start = self.expect(TokenKind.KW_PRINT)
    self.expect(TokenKind.LEFT_PAREN)
    items = [self.parse_print_item()]
    while self.match(TokenKind.COMMA) is not None:
        items.append(self.parse_print_item())
    self.expect(TokenKind.RIGHT_PAREN)
    semicolon = self.expect(TokenKind.SEMICOLON)
    return PrintStmt(items, span=self._span(start, semicolon))

def parse_print_item(self) -> PrintItem:
    if self.check(TokenKind.STRING_LITERAL):
        return self.parse_string_literals()
    return self.parse_expression()
```

`print_item` é a alternativa mais simples de decidir do parser inteiro:
`string_literals` só pode começar com `STRING_LITERAL`; toda outra
alternativa de `print_item` é `expression`. Um `self.check(...)` resolve.
Note que `print()` (vazio) é sintaticamente inválido porque a regra exige
**um** `print_item` antes de qualquer `(COMMA print_item)*` — não há `?` ao
redor do primeiro item — então, se o token logo após `(` já for `)`, nem
`parse_print_item` nem `parse_string_literals`/`parse_expression`
encontram nada que reconheçam, e o erro sobe de dentro de `parse_primary`
(seção 6.3).

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
```

`STRING_LITERAL+` (uma ou mais vezes) vira "consuma a primeira
obrigatoriamente, depois `while` ainda houver outra, consuma e concatene" —
o molde geral de `X+` sempre que `X` é ele mesmo o critério de parada (ao
contrário de `X (COMMA X)*`, aqui não há separador: a lista para assim que
o próximo token não for mais `STRING_LITERAL`). `value` acumula o **valor
decodificado** de cada token (`token.value`, já sem aspas nem escapes — foi
o lexer, na Etapa 1, quem fez essa decodificação); o `lexeme` original de
cada token individual é descartado, só a posição (`first`/`last`) e o valor
concatenado sobrevivem no `StringLiteral` final. Ver seção 7 para um
exemplo completo com dois literais adjacentes.

### 6.7 `block`, `statement` e o controle de fluxo

```ebnf
block ::= LEFT_BRACE statement* RIGHT_BRACE
statement ::= declaration | id_or_call_statement | if_statement
            | while_statement | return_statement | print_statement | block
```

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
```

`parse_statement` é o **dispatcher central** do parser: a decisão LL(1) por
excelência, sete alternativas, cada uma reconhecida por um único token de
`STATEMENT_START` diferente (é exatamente por isso que `STATEMENT_START`
existe como constante — o `if`/`elif` aqui é a enumeração explícita do
mesmo conjunto já usado em `parse_block` para decidir quando **parar** de
ler comandos). A última linha, `self.expect(STATEMENT_START)`, nunca
devolve nada num fluxo normal: se a execução chegou até ali, é porque
`kind` não bateu com **nenhuma** das sete verificações anteriores — e como
elas cobrem exatamente todos os elementos de `STATEMENT_START`, isso só
acontece quando `kind` **não está** em `STATEMENT_START`, o que é
precisamente a condição que faz `expect` lançar `ParserError`. É o mesmo
padrão do `self.expect(PRIMARY_START)` no fim de `parse_primary` (seção
6.3): uma chamada a `expect` usada como "gerador de erro com o conjunto
esperado certo", não como uma consulta cujo resultado será usado.

É assim, por exemplo, que `1 + 2;` (uma expressão solta como comando) é
rejeitado: `INT_LITERAL` não é membro de `STATEMENT_START`, então nenhum
`if` de `parse_statement` dispara, e o erro aponta exatamente para o `1`.

`if_statement` e `while_statement` seguem o mesmo molde de "sequência +
opcional", só que agora com `block` (não mais um token isolado) como parte
obrigatória da regra — e é isso que impõe **chaves obrigatórias**: como
`parse_if_statement`/`parse_while_statement` chamam `self.parse_block()`
diretamente (não algo mais flexível como "um `block` ou um `statement`
único"), `if (true) return 1;` sem chaves é rejeitado dentro de
`parse_block`, no primeiro `self.expect(TokenKind.LEFT_BRACE)`.

```python
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
```

A variável `last` existe só para o cálculo do `span` final: o nó `IfStmt`
termina no fim do `then_block` **ou**, se houver `else`, no fim do
`else_block` — qual dos dois depende de um `if` que só é decidido em tempo
de execução, então `last` guarda "o nó mais à direita até agora" e é
atualizada só quando o `else` de fato aparece.

```python
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

`return_statement ::= KW_RETURN expression? SEMICOLON` é o único outro
lugar (além de `arguments`) em que uma expressão inteira é opcional — o
mesmo truque de `parse_arguments` reaparece: `if self.peek().kind in
EXPRESSION_START` decide, sem consumir nada, se existe algo para
`parse_expression()` reconhecer antes do `;`.

---

## 7. Exemplo ponta a ponta: `10 - 2 * 3 - 1` e `print` com strings adjacentes

### 7.1 Precedência e associatividade

Para `return 10 - 2 * 3 - 1;` (arquivo `tests/cases/valid/expressions.mc`),
o caminho de chamadas até `additive` (nível de `-`), simplificado — cada
`additive()`/`multiplicative()` abaixo já é uma chamada recursiva:

| chamada | o que acontece |
|---|---|
| `parse_additive()` | chama `parse_multiplicative()` para o operando esquerdo |
| `parse_multiplicative()` | chama `parse_unary()` → ... → `parse_primary()`, devolve `IntLiteral(10)`; próximo token é `-`, que **não** está em `MULTIPLICATIVE_OPERATORS` → laço do helper para, devolve só `IntLiteral(10)` |
| de volta em `parse_additive` | `left = IntLiteral(10)`; token atual é `-` (em `ADDITIVE_OPERATORS`) → consome, chama `parse_multiplicative()` de novo |
| `parse_multiplicative()` (2ª vez) | `parse_unary()` devolve `IntLiteral(2)`; token atual é `*` (em `MULTIPLICATIVE_OPERATORS`) → consome, chama `parse_unary()` de novo, devolve `IntLiteral(3)`; monta `BinaryExpr(MULTIPLY, 2, 3)`; próximo token é `-` (fora do nível) → laço para, devolve `2 * 3` |
| de volta em `parse_additive` | monta `left = BinaryExpr(SUBTRACT, IntLiteral(10), BinaryExpr(MULTIPLY, 2, 3))`; token atual é `-` de novo → consome, chama `parse_multiplicative()` uma terceira vez, devolve `IntLiteral(1)`; monta `left = BinaryExpr(SUBTRACT, <tudo isso>, IntLiteral(1))`; próximo token é `;` (fora do nível) → laço final para |

Resultado — exatamente `(10 - (2 * 3)) - 1`, associando `-` à **esquerda**
e dando precedência maior para `*`:

```
BinaryExpr(-)
├── left: BinaryExpr(-)
│   ├── left: IntLiteral(10)
│   └── right: BinaryExpr(*)
│       ├── left: IntLiteral(2)
│       └── right: IntLiteral(3)
└── right: IntLiteral(1)
```

(Confirmado rodando `python runner.py --format tree --show-spans
tests/cases/valid/expressions.mc` — os spans aninham corretamente, nenhum
span de filho ultrapassa o do pai.)

### 7.2 Strings adjacentes em `print`

Para `print("resultado " "final = ", x);`:

1. `parse_print_statement` consome `KW_PRINT` e `(`, chama
   `parse_print_item()`.
2. O token atual é `STRING_LITERAL` → `parse_string_literals()`: consome o
   primeiro token (`value = "resultado "`), o **próximo** token também é
   `STRING_LITERAL` (`"final = "`) → consome e concatena
   (`value = "resultado final = "`), o token seguinte é `,` → laço para.
   Devolve **um único** `StringLiteral("resultado final = ")`, com span do
   início do primeiro literal ao fim do segundo.
3. De volta em `parse_print_statement`: `match(COMMA)` consome a vírgula,
   chama `parse_print_item()` de novo — agora o token é `IDENTIFIER`, então
   cai no ramo `parse_expression()`, devolvendo `IdentifierExpr("x")`.
4. `items = [StringLiteral("resultado final = "), IdentifierExpr("x")]` —
   exatamente os dois itens que o enunciado descreve para este exemplo
   (§4.2).

---

## 8. Como rodar e testar

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q                              # suíte avaliada + suíte de dev
python runner.py --format tree test.mc           # AST em árvore no terminal
python runner.py --format dot test.mc > ast.dot   # para Graphviz (dot -Tsvg ast.dot -o ast.svg)
python runner.py tests/cases/invalid/missing_semicolon.mc   # exit 1 + diagnóstico em stderr
```

No Windows, se caracteres acentuados/desenho de árvore (`├──`, `└──`)
saírem malformados no console, é só a code page do terminal (`cp1252`) — não
é um bug do parser; rode com `$env:PYTHONIOENCODING = "utf-8"` antes.

---

## 9. Conformidade com o enunciado

| Exigência | Status |
|---|---|
| Descida recursiva manual, 1 token de lookahead, sem gerador de parser | ✅ |
| Nenhum backtracking (nenhuma tentativa desfeita em nenhum `parse_*`) | ✅ |
| Cada não-terminal com seu próprio `parse_*`, consumindo só seus tokens | ✅ |
| Associatividade à esquerda (binários) e à direita (unários) corretas | ✅ (seção 7.1) |
| Parênteses não criam nó, só ampliam o span | ✅ (`parse_primary`, seção 6.3) |
| Strings adjacentes em `print` concatenadas num único `StringLiteral` | ✅ (seção 7.2) |
| `Assignment.target` sempre `IdentifierExpr`; chamada-comando sempre `CallStmt(CallExpr)` | ✅ |
| `ParserError` com `token`/`expected`/`line`/`column` e formato textual exato | ✅ (herdado do starter, `expected` mantido preciso — seções 6.3 e 6.5) |
| Formas semanticamente inválidas mas sintaticamente corretas são aceitas (`int x = true;`, função duplicada, sem `main`, arquivo vazio) | ✅ — nenhuma verificação de nome/tipo/escopo em `parser.py` |
| Formas sintaticamente inválidas rejeitadas (`print()`, string fora de `print`, expressão solta como comando, atribuição encadeada, `if`/`while` sem chaves, comando vazio) | ✅ (`tests/cases/invalid/*.mc`, todas cobertas por `tests/test_parser.py`) |
| Nenhuma regra semântica antecipada durante o parsing | ✅ |
| `ast_nodes.py`, `Lexer.py` (contrato), `Parser`/`ParserError` (nomes/campos/assinaturas públicas) intocados | ✅ |
| `tests/test_parser.py` (suíte avaliada) e `tests/cases/**` intocados | ✅ |
| 43/43 testes passando (18 da suíte avaliada + 25 da suíte de dev) | ✅ |

---

## 10. Decisões que valem atenção

- **Um helper privado (`_parse_binary_level`) em vez de seis corpos de
  método quase idênticos.** O enunciado permite explicitamente funções
  auxiliares (§1) — e as seis regras de `logical_or` a `multiplicative`
  diferem só em "qual o próximo nível" e "quais operadores". Extrair esse
  padrão evita que um bug de associatividade precise ser corrigido em seis
  lugares.
- **`PRIMARY_START` como conjunto próprio, mais estreito que
  `EXPRESSION_START`.** Detalhado na seção 6.3 — existe só para manter o
  `expected` de `ParserError` fiel ao que `primary` de fato aceita naquele
  ponto (sem `LOGICAL_NOT`/`MINUS`, que `unary` já teria consumido antes).
- **`expect({ASSIGN, LEFT_PAREN})` como escolha única, em vez de
  `match`+`expect` encadeados, em `parse_id_or_call_statement`.** Detalhado
  na seção 6.5 — mantém o conjunto esperado reportado em erro igual ao
  conjunto real de continuações válidas da gramática naquele ponto.
- **`self.expect(CONJUNTO)` usado só pelo efeito de lançar erro**, no fim de
  `parse_primary` e `parse_statement`. Não é uma consulta cujo retorno é
  usado — nos dois casos, a execução só chega ali quando **nenhuma**
  alternativa anterior bateu, e os dois conjuntos passados (`PRIMARY_START`,
  `STATEMENT_START`) são exatamente a união das alternativas já testadas —
  então a chamada é, por construção, sempre uma falha.
- **Reaproveitamento consistente do molde `X (COMMA X)*`** entre
  `parameter_list`, `arguments` e o laço de `print_statement` — os três
  são "primeiro elemento obrigatório, depois `while match(COMMA)`", nunca
  implementados de formas diferentes entre si.
- **Nenhuma verificação de nomes, tipos, ou de `main`.** O exemplo do
  próprio enunciado (§5) — `void y = true; if (1) { return 2 + false; }` —
  passa pelo parser sem erro, de propósito: tudo isso é forma sintática
  válida (declaração com tipo+nome+inicializador; `if` com uma expressão
  qualquer como condição; `return` com uma expressão qualquer). Validar que
  `1` "deveria" ser `bool`, ou que `2 + false` não faz sentido, é trabalho
  da próxima etapa (análise semântica) — antecipar isso aqui violaria a
  separação de responsabilidades que o enunciado pede explicitamente.
