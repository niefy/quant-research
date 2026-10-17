"""Whitelisted factor operators and their argument contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal as TypingLiteral

from quant.factors.dsl.ast import Call, Expression, Literal, Node


class DSLParseError(ValueError):
    """Raised when an expression is syntactically invalid or not whitelisted."""


class UnsupportedOperatorError(ValueError):
    """Raised when a valid operator is not implemented by this runtime yet."""


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    params: tuple[str, ...]
    required: int
    kind: TypingLiteral["ts", "cs", "math", "cond"]
    int_params: frozenset[str] = frozenset()
    positive_int_params: frozenset[str] = frozenset()
    non_negative_int_params: frozenset[str] = frozenset()
    numeric_params: frozenset[str] = frozenset()


def _spec(
    name: str,
    params: tuple[str, ...],
    required: int,
    kind: TypingLiteral["ts", "cs", "math", "cond"],
    *,
    int_params: tuple[str, ...] = (),
    positive_int_params: tuple[str, ...] = (),
    non_negative_int_params: tuple[str, ...] = (),
    numeric_params: tuple[str, ...] = (),
) -> OperatorSpec:
    return OperatorSpec(
        name=name,
        params=params,
        required=required,
        kind=kind,
        int_params=frozenset(int_params),
        positive_int_params=frozenset(positive_int_params),
        non_negative_int_params=frozenset(non_negative_int_params),
        numeric_params=frozenset(numeric_params),
    )


OPERATORS: dict[str, OperatorSpec] = {
    # Time-series operators always look backwards within each symbol.
    "ts_mean": _spec(
        "ts_mean",
        ("x", "window", "min_periods"),
        2,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    "ts_std": _spec(
        "ts_std",
        ("x", "window", "min_periods"),
        2,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    "ts_sum": _spec(
        "ts_sum",
        ("x", "window", "min_periods"),
        2,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    "ts_min": _spec(
        "ts_min",
        ("x", "window", "min_periods"),
        2,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    "ts_max": _spec(
        "ts_max",
        ("x", "window", "min_periods"),
        2,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    "ts_rank": _spec(
        "ts_rank",
        ("x", "window", "min_periods"),
        2,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    "ts_zscore": _spec(
        "ts_zscore",
        ("x", "window", "min_periods"),
        2,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    "ts_return": _spec(
        "ts_return",
        ("x", "window"),
        2,
        "ts",
        positive_int_params=("window",),
    ),
    "ts_delta": _spec(
        "ts_delta",
        ("x", "window"),
        2,
        "ts",
        positive_int_params=("window",),
    ),
    "ts_shift": _spec(
        "ts_shift",
        ("x", "n"),
        2,
        "ts",
        non_negative_int_params=("n",),
    ),
    "ts_corr": _spec(
        "ts_corr",
        ("x", "y", "window", "min_periods"),
        3,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    "ts_cov": _spec(
        "ts_cov",
        ("x", "y", "window", "min_periods"),
        3,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    "ts_ema": _spec(
        "ts_ema",
        ("x", "span"),
        2,
        "ts",
        positive_int_params=("span",),
    ),
    "ts_decay_linear": _spec(
        "ts_decay_linear",
        ("x", "window", "min_periods"),
        2,
        "ts",
        positive_int_params=("window", "min_periods"),
    ),
    # Cross-sectional operators are evaluated independently per timestamp.
    "cs_rank": _spec("cs_rank", ("x", "method"), 1, "cs"),
    "cs_zscore": _spec("cs_zscore", ("x",), 1, "cs"),
    "cs_demean": _spec("cs_demean", ("x",), 1, "cs"),
    "cs_winsorize": _spec(
        "cs_winsorize",
        ("x", "lower", "upper"),
        1,
        "cs",
        numeric_params=("lower", "upper"),
    ),
    # Pure math.
    "abs": _spec("abs", ("x",), 1, "math"),
    "log": _spec("log", ("x",), 1, "math"),
    "sign": _spec("sign", ("x",), 1, "math"),
    "sqrt": _spec("sqrt", ("x",), 1, "math"),
    "clip": _spec("clip", ("x", "lower", "upper"), 3, "math", numeric_params=("lower", "upper")),
    "where": _spec("where", ("cond", "x", "y"), 3, "cond"),
    "add": _spec("add", ("x", "y"), 2, "math"),
    "sub": _spec("sub", ("x", "y"), 2, "math"),
    "mul": _spec("mul", ("x", "y"), 2, "math"),
    "div": _spec("div", ("x", "y"), 2, "math"),
    "pow": _spec("pow", ("x", "y"), 2, "math"),
}


def bind_call(call: Call) -> dict[str, Expression]:
    spec = OPERATORS.get(call.name)
    if spec is None:
        raise DSLParseError(f"operator is not whitelisted: {call.name}")
    if len(call.args) > len(spec.params):
        raise DSLParseError(
            f"{call.name} accepts at most {len(spec.params)} positional arguments, "
            f"got {len(call.args)}"
        )
    if len(call.args) < spec.required:
        raise DSLParseError(
            f"{call.name} requires at least {spec.required} arguments, got {len(call.args)}"
        )
    bound: dict[str, Expression] = dict(zip(spec.params, call.args, strict=False))
    for key, value in call.kwargs:
        if key not in spec.params:
            raise DSLParseError(f"{call.name} does not accept keyword argument '{key}'")
        if key in bound:
            raise DSLParseError(f"{call.name} received argument '{key}' twice")
        bound[key] = value
    missing = [name for name in spec.params[: spec.required] if name not in bound]
    if missing:
        raise DSLParseError(f"{call.name} is missing required arguments: {missing}")
    return bound


def literal_int(value: Node, *, name: str) -> int:
    if not isinstance(value, Literal) or isinstance(value.value, bool) or not isinstance(value.value, int):
        raise DSLParseError(f"{name} must be an integer literal")
    return value.value


def literal_number(value: Node, *, name: str) -> float:
    if not isinstance(value, Literal) or isinstance(value.value, bool) or not isinstance(
        value.value, (int, float)
    ):
        raise DSLParseError(f"{name} must be a numeric literal")
    return float(value.value)


def validate_operator_arguments(call: Call) -> dict[str, Expression]:
    spec = OPERATORS.get(call.name)
    if spec is None:
        raise DSLParseError(f"operator is not whitelisted: {call.name}")
    bound = bind_call(call)

    for name in spec.int_params | spec.positive_int_params | spec.non_negative_int_params:
        if name in bound:
            literal_int(bound[name], name=name)

    for name in spec.positive_int_params:
        if name in bound and literal_int(bound[name], name=name) < 1:
            raise DSLParseError(f"{name} must be >= 1")

    for name in spec.non_negative_int_params:
        if name in bound and literal_int(bound[name], name=name) < 0:
            raise DSLParseError(f"{name} must be >= 0 (negative values imply future data)")

    for name in spec.numeric_params:
        if name in bound:
            literal_number(bound[name], name=name)

    if call.name == "ts_shift":
        n = literal_int(bound["n"], name="n")
        if n < 0:
            raise DSLParseError("ts_shift n must be >= 0; negative n is a future function")

    if "window" in bound:
        window = literal_int(bound["window"], name="window")
        if window < 1:
            raise DSLParseError("window must be >= 1")
        if "min_periods" in bound:
            min_periods = literal_int(bound["min_periods"], name="min_periods")
            if min_periods > window:
                raise DSLParseError("min_periods must be <= window")

    if call.name == "cs_winsorize":
        lower = literal_number(bound.get("lower", Literal(0.01)), name="lower")
        upper = literal_number(bound.get("upper", Literal(0.99)), name="upper")
        if not 0.0 <= lower < upper <= 1.0:
            raise DSLParseError("cs_winsorize requires 0 <= lower < upper <= 1")

    return bound
