"""Small, safe filename-query language used by the file-selection tools."""

from __future__ import annotations

import fnmatch
import shlex
from collections.abc import Callable, Iterable


class FilterSyntaxError(ValueError):
    """Raised when a boolean filename expression is incomplete or malformed."""


def _tokens(expression: str) -> list[str]:
    lexer = shlex.shlex(expression, posix=True, punctuation_chars="()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        raw = list(lexer)
    except ValueError as exc:
        raise FilterSyntaxError(str(exc)) from exc

    normalized: list[str] = []
    for token in raw:
        upper = token.upper()
        normalized.append(upper if upper in {"AND", "OR", "NOT"} else token)

    # Adjacent search terms are an implicit AND: ``sample 0.1deg``.
    result: list[str] = []
    previous: str | None = None
    for token in normalized:
        previous_is_value = previous is not None and previous not in {"AND", "OR", "NOT", "("}
        current_starts_value = token not in {"AND", "OR", ")"}
        if previous_is_value and current_starts_value:
            result.append("AND")
        result.append(token)
        previous = token
    return result


def _to_rpn(tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    precedence = {"OR": 1, "AND": 2, "NOT": 3}
    output: list[str] = []
    operators: list[str] = []
    expecting_value = True

    for token in tokens:
        if token == "(":
            if not expecting_value:
                raise FilterSyntaxError("missing operator before '('")
            operators.append(token)
            expecting_value = True
        elif token == ")":
            if expecting_value:
                raise FilterSyntaxError("empty group or missing term before ')'")
            while operators and operators[-1] != "(":
                output.append(operators.pop())
            if not operators:
                raise FilterSyntaxError("unmatched ')'")
            operators.pop()
            expecting_value = False
        elif token in precedence:
            if token != "NOT" and expecting_value:
                raise FilterSyntaxError(f"'{token}' needs a term on its left")
            if token == "NOT" and not expecting_value:
                raise FilterSyntaxError("'NOT' needs an AND/OR before it")
            right_associative = token == "NOT"
            while (
                operators
                and operators[-1] in precedence
                and (
                    precedence[operators[-1]] > precedence[token]
                    or (precedence[operators[-1]] == precedence[token] and not right_associative)
                )
            ):
                output.append(operators.pop())
            operators.append(token)
            expecting_value = True
        else:
            if not expecting_value:
                raise FilterSyntaxError(f"missing operator before '{token}'")
            output.append(token)
            expecting_value = False

    if expecting_value:
        raise FilterSyntaxError("expression ends before the next search term")
    while operators:
        operator = operators.pop()
        if operator == "(":
            raise FilterSyntaxError("unmatched '('")
        output.append(operator)
    return output


def _term_matches(term: str, value: str) -> bool:
    term_folded = term.casefold()
    value_folded = value.casefold()
    if any(char in term for char in "*?["):
        return fnmatch.fnmatchcase(value_folded, term_folded)
    return term_folded in value_folded


def compile_filter(expression: str) -> Callable[[str], bool]:
    """Compile a boolean substring/wildcard expression into a predicate.

    Operators are case-insensitive. AND binds more tightly than OR; NOT is
    unary. Quoted phrases and parentheses are supported. Adjacent terms imply
    AND. Search terms containing shell wildcards use whole-name matching.
    """

    rpn = _to_rpn(_tokens(expression.strip()))
    if not rpn:
        return lambda _value: True

    def predicate(value: str) -> bool:
        stack: list[bool] = []
        for token in rpn:
            if token == "NOT":
                if not stack:
                    raise FilterSyntaxError("NOT has no search term")
                stack.append(not stack.pop())
            elif token in {"AND", "OR"}:
                if len(stack) < 2:
                    raise FilterSyntaxError(f"{token} is missing a search term")
                right = stack.pop()
                left = stack.pop()
                stack.append(left and right if token == "AND" else left or right)
            else:
                stack.append(_term_matches(token, value))
        if len(stack) != 1:
            raise FilterSyntaxError("invalid expression")
        return stack[0]

    return predicate


def parse_filename_list(text: str | Iterable[str]) -> list[str]:
    """Return non-empty filenames from pasted text, lines, or comma lists."""

    chunks = [text] if isinstance(text, str) else list(text)
    result: list[str] = []
    for chunk in chunks:
        for line in str(chunk).replace(",", "\n").splitlines():
            item = line.strip().strip('"').strip("'")
            if item and not item.startswith("#"):
                result.append(item)
    return list(dict.fromkeys(result))
