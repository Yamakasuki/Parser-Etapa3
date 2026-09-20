# Projeto de Compiladores — Etapa 3: Parser LL(1) e AST

Este repositório é o ponto de partida da terceira etapa do compilador de
MicroC. O grupo implementará um parser por descida recursiva que consome os
tokens da etapa do lexer e constrói diretamente a AST fornecida.

Leia o [enunciado completo](ENUNCIADO.pdf) e a gramática
[`source_grammar.ebnf`](source_grammar.ebnf) antes de começar. A especificação da
linguagem MicroC continua sendo a referência normativa.

## O lexer

`Lexer.py` é a implementação do grupo entregue na primeira etapa, acompanhada de
`microc_automato.py` (autômato dirigido por tabela) e `microc_cursor.py`
(navegação com linha e coluna). Os nomes e números de `TokenKind` e os campos de
`Token` são exatamente os publicados.

O projeto de transformação de gramáticas é independente desta entrega. Não é
necessário copiar `grammar.py` nem gerar uma gramática durante a execução: a
gramática LL(1) que deve orientar o parser já está em `source_grammar.ebnf`.

## Estrutura do repositório

```text
.
├── .github/workflows/tests.yml  # testes públicos no GitHub Actions
├── tests/
│   ├── cases/valid/*.mc         # programas públicos que devem ser aceitos
│   ├── cases/invalid/*.mc       # programas públicos que devem ser rejeitados
│   └── test_parser.py           # testes e inspeções da AST
├── ENUNCIADO.pdf                # enunciado da etapa
├── Lexer.py                     # lexer do grupo (etapa 1)
├── microc_automato.py           # autômato dirigido por tabela do lexer
├── microc_cursor.py             # cursor com linha e coluna do lexer
├── ast_nodes.py                 # AST completa fornecida
├── ast_printer.py               # visualizações em árvore e Graphviz DOT
├── parser.py                    # parser por descida recursiva
├── runner.py                    # fonte MicroC para JSON, árvore ou DOT
├── source_grammar.ebnf          # gramática LL(1) fornecida
├── test.mc                      # programa para experimentação
├── pyproject.toml
└── requirements-dev.txt
```

`parse_program`, `parse_function`, `parse_type`, as operações sobre o fluxo de
tokens, os spans, os erros e toda a hierarquia da AST vieram prontos no starter.
Os demais métodos `parse_*` foram implementados pelo grupo, um por não terminal
da EBNF, sem alterar nomes, campos ou assinaturas públicas de `ast_nodes.py`,
`Parser`, `ParserError`, `Token` ou `TokenKind`.

## Preparação do ambiente

O ambiente de referência usa Python 3.12.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

No Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## Execução

Para visualizar a AST como uma árvore no terminal:

```sh
python runner.py --format tree test.mc
```

Use `--show-spans` para acrescentar as posições do código-fonte. Uma saída JSON
também está disponível com:

```sh
python runner.py --format json test.mc
```

Para criar um diagrama com Graphviz, gere primeiro um arquivo DOT e então o
converta para SVG ou PDF:

```sh
python runner.py --format dot test.mc > ast.dot
dot -Tsvg ast.dot -o ast.svg
dot -Tpdf ast.dot -o ast.pdf
```

Gerar o texto DOT não requer pacote Python nem a instalação do Graphviz; somente
os comandos `dot` de conversão precisam do programa externo. As visualizações
servem para inspeção. A interface entre as etapas do compilador é o objeto
`Program` retornado por:

```python
program = Parser(Lexer(source).scan()).parse()
```

Para executar os testes públicos:

```sh
python -m pytest -q
```

A suíte pública tem 18 testes e passa integralmente. A correção também usará
testes privados compatíveis com o enunciado.

Os arquivos em `tests/cases/` são parte da documentação executável. Cada caso
possui nome descritivo e pode ser executado isoladamente com o runner. Por
exemplo:

```sh
python runner.py tests/cases/valid/expressions.mc
python runner.py tests/cases/invalid/missing_semicolon.mc
```

O primeiro comando deve imprimir uma AST. O segundo deve produzir um diagnóstico
sintático. Para executar somente um grupo de testes, use, por exemplo:

```sh
python -m pytest -q tests/test_parser.py -k precedencia
```

## Antes de entregar

- confira que toda entrada termina com exatamente um token `EOF`;
- não implemente regras semânticas no parser;
- execute `python -m pytest -q`; e
- confira a aba **Actions** depois de cada `push`.
