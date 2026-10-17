"""Small, explicit AST for the factor expression language."""

from __future__ import annotations

from dataclasses import dataclass


class Node:
    def canonical(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class Literal(Node):
    value: int | float | str | bool | None

    def canonical(self) -> str:
        return repr(self.value)


@dataclass(frozen=True)
class Field(Node):
    name: str

    def canonical(self) -> str:
        return self.name


@dataclass(frozen=True)
class Call(Node):
    name: str
    args: tuple[Expression, ...]
    kwargs: tuple[tuple[str, Expression], ...] = ()

    def canonical(self) -> str:
        parts = [arg.canonical() for arg in self.args]
        parts.extend(f"{key}={value.canonical()}" for key, value in sorted(self.kwargs))
        return f"{self.name}({', '.join(parts)})"


@dataclass(frozen=True)
class UnaryOp(Node):
    op: str
    operand: Expression

    def canonical(self) -> str:
        return f"({self.op}{self.operand.canonical()})"


@dataclass(frozen=True)
class BinaryOp(Node):
    op: str
    left: Expression
    right: Expression

    def canonical(self) -> str:
        return f"({self.left.canonical()} {self.op} {self.right.canonical()})"


type Expression = Literal | Field | Call | UnaryOp | BinaryOp
