"""Compile a validated factor AST into a staged Polars plan.

Polars does not reliably allow a window expression to be nested inside a
window expression with a *different* grouping key. The canonical factor
``cs_rank(ts_return(close, 20))`` is exactly that shape, so we materialize
each grouped operation into a temporary column and evaluate the plan in
dependency order. Pure math and conditionals stay inline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal as TypingLiteral
from typing import cast

import polars as pl

from quant.factors.dsl.ast import BinaryOp, Call, Expression, Field, Literal, UnaryOp
from quant.factors.operators.registry import (
    DSLParseError,
    UnsupportedOperatorError,
    bind_call,
    literal_int,
    literal_number,
    validate_operator_arguments,
)

_RANK_METHODS = {"average", "min", "max", "dense", "ordinal"}
_RankMethod = TypingLiteral["average", "min", "max", "dense", "ordinal"]


@dataclass(frozen=True)
class CompileContext:
    symbol_col: str = "symbol"
    time_col: str = "timestamp"
    reserved_columns: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CompiledPlan:
    steps: tuple[pl.Expr, ...]
    output_column: str
    temp_columns: tuple[str, ...]


def compile_plan(expression: Expression, context: CompileContext | None = None) -> CompiledPlan:
    ctx = context or CompileContext()
    builder = _PlanBuilder(ctx)
    final = builder.build(expression)
    output_column = builder.add_step(final)
    return CompiledPlan(
        steps=tuple(builder.steps),
        output_column=output_column,
        temp_columns=tuple(builder.temp_columns),
    )


class _PlanBuilder:
    def __init__(self, context: CompileContext) -> None:
        self.context = context
        self.steps: list[pl.Expr] = []
        self.temp_columns: list[str] = []
        self._counter = 0

    def _new_name(self) -> str:
        while True:
            name = f"__factor_tmp_{self._counter}"
            self._counter += 1
            if name not in self.context.reserved_columns and name not in self.temp_columns:
                return name

    def add_step(self, expr: pl.Expr) -> str:
        name = self._new_name()
        self.steps.append(expr.alias(name))
        self.temp_columns.append(name)
        return name

    def materialize(self, expr: pl.Expr) -> pl.Expr:
        return pl.col(self.add_step(expr))

    def build(self, node: Expression) -> pl.Expr:
        if isinstance(node, Literal):
            return pl.lit(node.value)
        if isinstance(node, Field):
            return pl.col(node.name)
        if isinstance(node, UnaryOp):
            operand = self.build(node.operand)
            if node.op == "-":
                return -operand
            if node.op == "not":
                return ~operand
            raise DSLParseError(f"unsupported unary operator: {node.op}")
        if isinstance(node, BinaryOp):
            return self._build_binary(node)
        if isinstance(node, Call):
            return self._build_call(node)
        raise DSLParseError(f"unsupported AST node: {type(node).__name__}")

    def _build_binary(self, node: BinaryOp) -> pl.Expr:
        left = self.build(node.left)
        right = self.build(node.right)
        if node.op == "+":
            return left + right
        if node.op == "-":
            return left - right
        if node.op == "*":
            return left * right
        if node.op == "/":
            return left / right
        if node.op == "**":
            return left**right
        if node.op == "%":
            return left % right
        if node.op == ">":
            return left > right
        if node.op == ">=":
            return left >= right
        if node.op == "<":
            return left < right
        if node.op == "<=":
            return left <= right
        if node.op == "==":
            return left == right
        if node.op == "!=":
            return left != right
        if node.op == "and":
            return left & right
        if node.op == "or":
            return left | right
        raise DSLParseError(f"unsupported binary operator: {node.op}")

    def _build_call(self, node: Call) -> pl.Expr:
        validate_operator_arguments(node)
        bound = bind_call(node)
        name = node.name

        def arg(key: str) -> pl.Expr:
            return self.build(bound[key])

        def window() -> int:
            return literal_int(bound["window"], name="window")

        def min_periods(win: int) -> int:
            if "min_periods" in bound:
                return literal_int(bound["min_periods"], name="min_periods")
            return win

        if name in {"ts_mean", "ts_sum", "ts_min", "ts_max"}:
            win = window()
            rolling_op = {
                "ts_mean": "rolling_mean",
                "ts_sum": "rolling_sum",
                "ts_min": "rolling_min",
                "ts_max": "rolling_max",
            }[name]
            expr = getattr(arg("x"), rolling_op)(win, min_samples=min_periods(win))
            return self.materialize(expr.over(self.context.symbol_col))

        if name == "ts_std":
            win = window()
            expr = arg("x").rolling_std(win, min_samples=min_periods(win))
            return self.materialize(expr.over(self.context.symbol_col))

        if name == "ts_rank":
            win = window()
            expr = arg("x").rolling_rank(win, min_samples=min_periods(win))
            return self.materialize(expr.over(self.context.symbol_col))

        if name == "ts_zscore":
            win = window()
            x = arg("x")
            mean = x.rolling_mean(win, min_samples=min_periods(win))
            std = x.rolling_std(win, min_samples=min_periods(win))
            return self.materialize(((x - mean) / std).over(self.context.symbol_col))

        if name in {"ts_return", "ts_delta"}:
            win = window()
            x = arg("x")
            shifted = x.shift(win)
            result = (x / shifted - 1.0) if name == "ts_return" else (x - shifted)
            return self.materialize(result.over(self.context.symbol_col))

        if name == "ts_shift":
            n = literal_int(bound["n"], name="n")
            return self.materialize(
                arg("x").shift(n).over(self.context.symbol_col)
            )

        if name in {"ts_corr", "ts_cov"}:
            win = window()
            fn = pl.rolling_corr if name == "ts_corr" else pl.rolling_cov
            expr = fn(
                arg("x"),
                arg("y"),
                window_size=win,
                min_samples=min_periods(win),
            )
            return self.materialize(expr.over(self.context.symbol_col))

        if name == "ts_ema":
            span = literal_int(bound["span"], name="span")
            expr = arg("x").ewm_mean(span=span, adjust=False)
            return self.materialize(expr.over(self.context.symbol_col))

        if name == "ts_decay_linear":
            win = window()
            weights = [float(i) for i in range(1, win + 1)]
            expr = arg("x").rolling_mean(
                win,
                weights=weights,
                min_samples=min_periods(win),
            )
            return self.materialize(expr.over(self.context.symbol_col))

        if name == "cs_rank":
            method: _RankMethod = "average"
            if "method" in bound:
                method_node = bound["method"]
                if not isinstance(method_node, Literal) or not isinstance(method_node.value, str):
                    raise DSLParseError("cs_rank method must be a string literal")
                method = cast(_RankMethod, method_node.value)
                if method not in _RANK_METHODS:
                    raise DSLParseError(
                        f"cs_rank method must be one of {sorted(_RANK_METHODS)}, got {method!r}"
                    )
            return self.materialize(
                arg("x").rank(method=method).over(self.context.time_col)
            )

        if name == "cs_zscore":
            x = arg("x")
            mean = x.mean().over(self.context.time_col)
            std = x.std().over(self.context.time_col)
            return self.materialize((x - mean) / std)

        if name == "cs_demean":
            x = arg("x")
            return self.materialize(x - x.mean().over(self.context.time_col))

        if name == "cs_winsorize":
            x = arg("x")
            lower = literal_number(bound.get("lower", Literal(0.01)), name="lower")
            upper = literal_number(bound.get("upper", Literal(0.99)), name="upper")
            lower_expr = x.quantile(lower).over(self.context.time_col)
            upper_expr = x.quantile(upper).over(self.context.time_col)
            return self.materialize(
                pl.min_horizontal(pl.max_horizontal(x, lower_expr), upper_expr)
            )

        if name in {"abs", "log", "sign", "sqrt"}:
            return getattr(arg("x"), name)()

        if name == "clip":
            x = arg("x")
            lower = literal_number(bound["lower"], name="lower")
            upper = literal_number(bound["upper"], name="upper")
            if lower > upper:
                raise DSLParseError("clip lower must be <= upper")
            return pl.min_horizontal(pl.max_horizontal(x, pl.lit(lower)), pl.lit(upper))

        if name == "where":
            return pl.when(arg("cond")).then(arg("x")).otherwise(arg("y"))

        if name == "add":
            return arg("x") + arg("y")
        if name == "sub":
            return arg("x") - arg("y")
        if name == "mul":
            return arg("x") * arg("y")
        if name == "div":
            return arg("x") / arg("y")
        if name == "pow":
            return arg("x") ** arg("y")

        raise UnsupportedOperatorError(f"{name} is whitelisted but not implemented by the runtime")
