"""Command-line entry point for the research kernel."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from quant.contracts.factor import FactorDocument
from quant.contracts.io import contract_hash, load_factor, load_profile, write_json_schema
from quant.contracts.profile import ValidationProfileDocument
from quant.data.adapters.binance import BinancePerpAdapter
from quant.data.panel import Panel
from quant.factors.runtime import compute_factor
from quant.validation.gates.g1_ic import run_g1_ic

_DURATION_RE = re.compile(r"^(\d+)([mhd])$")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "factor" and args.factor_command == "compute":
            return _cmd_factor_compute(args)
        if args.command == "validate":
            return _cmd_validate(args)
        if args.command == "schema" and args.schema_command == "export":
            return _cmd_schema_export(args)
    except Exception as exc:  # CLI boundary: print a concise error, no traceback by default
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quant", description="Factor research kernel")
    subparsers = parser.add_subparsers(dest="command", required=True)

    factor = subparsers.add_parser("factor", help="factor operations")
    factor_sub = factor.add_subparsers(dest="factor_command", required=True)
    compute = factor_sub.add_parser("compute", help="compute a FactorSpec")
    _add_data_args(compute)
    _add_spec_arg(compute)
    compute.add_argument("--params", action="append", default=[], help="parameter override key=value")
    compute.add_argument("--cache-dir", type=Path, default=Path("data/artifacts/factors"))
    compute.add_argument("--no-cache", action="store_true")
    compute.add_argument("--output", type=Path, required=True)
    compute.set_defaults(handler=_cmd_factor_compute)

    validate = subparsers.add_parser("validate", help="run validation gates")
    _add_data_args(validate)
    _add_spec_arg(validate)
    validate.add_argument("--profile", type=Path, required=True)
    validate.add_argument("--params", action="append", default=[], help="parameter override key=value")
    validate.add_argument("--gates", default="G1", help="comma-separated gate ids (currently G1)")
    validate.add_argument("--horizon-bars", type=int, default=None)
    validate.add_argument("--execution-lag-bars", type=int, default=1)
    validate.add_argument("--min-symbols", type=int, default=5)
    validate.add_argument("--cache-dir", type=Path, default=Path("data/artifacts/factors"))
    validate.add_argument("--output", type=Path, required=True)

    schema = subparsers.add_parser("schema", help="contract schema operations")
    schema_sub = schema.add_subparsers(dest="schema_command", required=True)
    export = schema_sub.add_parser("export", help="write JSON Schemas")
    export.add_argument("--output-dir", type=Path, default=Path("quant/contracts/schemas"))

    return parser


def _add_spec_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--spec", type=Path, required=True, help="FactorSpec YAML/JSON")


def _add_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", type=Path, default=Path("../../binance_data"))
    parser.add_argument("--frequency", default="30m")
    parser.add_argument("--symbols", default=None, help="comma-separated symbols; default all")
    parser.add_argument("--start", default=None, help="inclusive ISO date/datetime")
    parser.add_argument("--end", default=None, help="inclusive ISO date/datetime")


def _cmd_factor_compute(args: argparse.Namespace) -> int:
    document = load_factor(args.spec)
    panel = _load_panel(args, document)
    cache_dir = None if args.no_cache else args.cache_dir
    result = compute_factor(
        panel,
        document,
        params=_parse_params(args.params),
        cache_dir=cache_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.frame.write_parquet(args.output)
    metadata = {
        "cache_key": result.cache_key,
        "spec_hash": result.spec_hash,
        "expression": result.expression,
        "resolved_params": result.resolved_params,
        "rows": result.frame.height,
        "output": str(args.output),
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    gates = [gate.strip().upper() for gate in args.gates.split(",") if gate.strip()]
    if gates != ["G1"]:
        raise ValueError("only G1 is implemented in this slice; pass --gates G1")

    document = load_factor(args.spec)
    profile = load_profile(args.profile)
    panel = _load_panel(args, document, include_close=True)
    factor = compute_factor(
        panel,
        document,
        params=_parse_params(args.params),
        cache_dir=args.cache_dir,
    )
    horizon_bars = args.horizon_bars
    if horizon_bars is None:
        horizon_bars = horizon_to_bars(document.spec.frequency, document.spec.horizon)

    gate_result = run_g1_ic(
        factor.frame,
        panel,
        profile,
        horizon_bars=horizon_bars,
        execution_lag_bars=args.execution_lag_bars,
        min_symbols=args.min_symbols,
    )
    report: dict[str, Any] = {
        "factor": {
            "id": document.metadata.id,
            "name": document.metadata.name,
            "version": document.metadata.version,
            "spec_hash": contract_hash(document),
        },
        "profile": {
            "id": profile.metadata.id,
            "version": profile.metadata.version,
        },
        "gates": [gate_result.model_dump(mode="json")],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["gates"][0], ensure_ascii=False, indent=2))
    return 0


def _cmd_schema_export(args: argparse.Namespace) -> int:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_schema(FactorDocument, args.output_dir / "factor_spec.v1.json")
    write_json_schema(ValidationProfileDocument, args.output_dir / "validation_profile.v1.json")
    print(f"schemas written to {args.output_dir}")
    return 0


def _load_panel(
    args: argparse.Namespace,
    document: FactorDocument,
    *,
    include_close: bool = False,
) -> Panel:
    fields = sorted({field for item in document.spec.inputs for field in item.fields})
    if include_close and "close" not in fields:
        fields.append("close")
    symbols = [item.strip() for item in args.symbols.split(",")] if args.symbols else None
    adapter = BinancePerpAdapter(
        base_dir=args.data_dir,
        frequency=args.frequency,
        symbols=tuple(symbols) if symbols else None,
    )
    panel = adapter.load_panel(
        fields=fields,
        symbols=symbols,
        start=_parse_datetime(args.start),
        end=_parse_datetime(args.end),
    )
    return panel


def _parse_params(items: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"parameter override must be key=value: {item}")
        key, raw = item.split("=", 1)
        result[key.strip()] = _parse_scalar(raw.strip())
    return result


def _parse_scalar(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid datetime '{value}'; use ISO format") from exc
    return parsed


def horizon_to_bars(frequency: str, horizon: str) -> int:
    frequency_hours = _duration_hours(frequency)
    horizon_hours = _duration_hours(horizon)
    bars = horizon_hours / frequency_hours
    if bars < 1 or abs(bars - round(bars)) > 1e-9:
        raise ValueError(
            f"horizon {horizon} is not an integer number of {frequency} bars; "
            "pass --horizon-bars explicitly"
        )
    return int(round(bars))


def _duration_hours(value: str) -> float:
    match = _DURATION_RE.match(value.strip().lower())
    if match is None:
        raise ValueError(f"unsupported duration '{value}'; expected e.g. 30m, 1h, 1d")
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return amount / 60.0
    if unit == "h":
        return float(amount)
    return amount * 24.0


if __name__ == "__main__":
    raise SystemExit(main())
