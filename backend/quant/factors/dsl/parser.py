"""Parse the restricted factor expression language.

We use Python's parser only as a syntax front-end. The resulting AST is our
own whitelisted tree; no Python code is ever evaluated.
"""

from __future__ import annotations

import ast
from typing import Any

from quant.factors.dsl.ast import BinaryOp, Call, Expression, Field, Literal, UnaryOp
from quant.factors.operators.registry import (
    OPERATORS,
    DSLParseError,
    validate_operator_arguments,
)

_BIN_OPS: dict[type[ast.operator], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.Pow: "**",
    ast.Mod: "%",
}

_CMP_OPS: dict[type[ast.cmpop], str] = {
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Eq: "==",
    ast.NotEq: "!=",
}


def parse_expression(
    expression: str,
    *,
    fields: set[str],
    params: dict[str, Any] | None = None,
) -> Expression:
    """Parse and validate an expression.

    ``fields`` are the input columns available to the expression. ``params``
    are resolved scalar values (defaults plus any trial overrides); references
    to them become literals, so the AST is fully self-contained.
    """
    if not expression.strip():
        raise DSLParseError("expression must not be empty")
    if len(expression) > 5000:
        raise DSLParseError("expression is too long (max 5000 characters)")

    resolved_params = params or {}
    overlap = fields & set(resolved_params)
    if overlap:
        raise DSLParseError(f"parameter names collide with input fields: {sorted(overlap)}")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise DSLParseError(f"invalid expression syntax: {exc.msg}") from exc

    return _convert(tree.body, fields=fields, params=resolved_params)


def _convert(
    node: ast.AST,
    *,
    fields: set[str],
    params: dict[str, Any],
) -> Expression:
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None or isinstance(value, (bool, int, float, str)):
            return Literal(value)
        raise DSLParseError(f"unsupported literal type: {type(value).__name__}")

    if isinstance(node, ast.Name):
        if node.id in params:
            value = params[node.id]
            if value is not None and not isinstance(value, (bool, int, float, str)):
                raise DSLParseError(f"parameter '{node.id}' must be a scalar")
            return Literal(value)
        if node.id in fields:
            return Field(node.id)
        raise DSLParseError(f"unknown field or parameter: {node.id}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise DSLParseError("only direct calls to whitelisted operators are allowed")
        name = node.func.id
        if name not in OPERATORS:
            raise DSLParseError(f"operator is not whitelisted: {name}")
        args = tuple(_convert(arg, fields=fields, params=params) for arg in node.args)
        kwargs: list[tuple[str, Expression]] = []
        for keyword in node.keywords:
            if keyword.arg is None:
                raise DSLParseError("**kwargs is not allowed")
            kwargs.append(
                (keyword.arg, _convert(keyword.value, fields=fields, params=params))
            )
        call = Call(name=name, args=args, kwargs=tuple(kwargs))
        validate_operator_arguments(call)
        return call

    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise DSLParseError(f"operator '{type(node.op).__name__}' is not allowed")
        return BinaryOp(
            op=op,
            left=_convert(node.left, fields=fields, params=params),
            right=_convert(node.right, fields=fields, params=params),
        )

    if isinstance(node, ast.UnaryOp):
        operand = _convert(node.operand, fields=fields, params=params)
        if isinstance(node.op, ast.USub):
            if isinstance(operand, Literal) and isinstance(operand.value, (int, float)):
                return Literal(-operand.value)
            return UnaryOp(op="-", operand=operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.Not):
            return UnaryOp(op="not", operand=operand)
        raise DSLParseError(f"unary operator '{type(node.op).__name__}' is not allowed")

    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise DSLParseError("chained comparisons are not allowed; combine with 'and'")
        op = _CMP_OPS.get(type(node.ops[0]))
        if op is None:
            raise DSLParseError(f"comparison '{type(node.ops[0]).__name__}' is not allowed")
        return BinaryOp(
            op=op,
            left=_convert(node.left, fields=fields, params=params),
            right=_convert(node.comparators[0], fields=fields, params=params),
        )

    if isinstance(node, ast.BoolOp):
        op = "and" if isinstance(node.op, ast.And) else "or"
        values = [_convert(item, fields=fields, params=params) for item in node.values]
        result: Expression = values[0]
        for item in values[1:]:
            result = BinaryOp(op=op, left=result, right=item)
        return result

    raise DSLParseError(f"syntax '{type(node).__name__}' is not allowed")


def canonical_expression(expression: str, *, fields: set[str], params: dict[str, Any] | None = None) -> str:
    return parse_expression(expression, fields=fields, params=params).canonical()
