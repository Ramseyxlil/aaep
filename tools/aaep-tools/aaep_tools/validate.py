"""
aaep-validate — validate AAEP events against the JSON Schemas.

Usage:
    aaep-validate < event.json              # validate single event from stdin
    aaep-validate event.json                # validate one or more files
    aaep-validate --file stream.jsonl       # validate a JSONL event stream
    aaep-validate --quiet stream.jsonl      # exit code only, no output
    aaep-validate --json stream.jsonl       # JSON-formatted error report

Exit codes:
    0 - all events valid
    1 - at least one event invalid
    2 - usage error or I/O failure
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterator, TextIO

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
except ImportError as e:
    print(f"jsonschema is required: pip install jsonschema (got: {e})", file=sys.stderr)
    sys.exit(2)


# === Schema loading ===

# AAEP event type -> schema filename
_SCHEMA_MAP = {
    "aaep:agent.session.started": "session-started.json",
    "aaep:agent.session.completed": "session-completed.json",
    "aaep:agent.session.errored": "session-errored.json",
    "aaep:agent.session.cancelled": "session-cancelled.json",
    "aaep:agent.state.changed": "state-changed.json",
    "aaep:agent.progress.updated": "progress-updated.json",
    "aaep:agent.tool.invoked": "tool-invoked.json",
    "aaep:agent.tool.completed": "tool-completed.json",
    "aaep:agent.output.streaming": "output-streaming.json",
    "aaep:agent.awaiting.confirmation": "awaiting-confirmation.json",
    "aaep:agent.awaiting.clarification": "awaiting-clarification.json",
    "aaep:agent.handoff.requested": "handoff-requested.json",
}

_VALIDATORS_CACHE: dict[str, Draft202012Validator] = {}


def _find_schema_dir() -> Path:
    """Locate the bundled schemas directory."""
    # 1) Bundled inside the installed package
    here = Path(__file__).parent
    bundled = here / "schemas"
    if bundled.is_dir():
        return bundled

    # 2) Development mode: look at the repo schemas/ directory
    repo_schemas = here.parent.parent.parent / "schemas"
    if repo_schemas.is_dir():
        return repo_schemas

    raise FileNotFoundError(
        f"Could not find AAEP schemas. Looked at {bundled} and {repo_schemas}."
    )


def _get_validator(event_type: str) -> Draft202012Validator:
    """Return a cached validator for the given event type."""
    if event_type in _VALIDATORS_CACHE:
        return _VALIDATORS_CACHE[event_type]

    schema_filename = _SCHEMA_MAP.get(event_type)
    if schema_filename is None:
        raise ValueError(f"Unknown AAEP event type: {event_type!r}")

    schema_path = _find_schema_dir() / schema_filename
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    validator = Draft202012Validator(schema)
    _VALIDATORS_CACHE[event_type] = validator
    return validator


# === Validation API ===

class ValidationResult:
    """Outcome of validating a single event."""

    __slots__ = ("valid", "event_type", "errors", "location")

    def __init__(
        self,
        *,
        valid: bool,
        event_type: str | None,
        errors: list[str],
        location: str,
    ):
        self.valid = valid
        self.event_type = event_type
        self.errors = errors
        self.location = location

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "event_type": self.event_type,
            "errors": self.errors,
            "location": self.location,
        }


def validate_event(event: Any, *, location: str = "<input>") -> ValidationResult:
    """Validate a single event dict against the appropriate schema."""
    if not isinstance(event, dict):
        return ValidationResult(
            valid=False,
            event_type=None,
            errors=[f"Expected JSON object, got {type(event).__name__}"],
            location=location,
        )

    event_type = event.get("type")
    if not isinstance(event_type, str):
        return ValidationResult(
            valid=False,
            event_type=None,
            errors=["Missing or invalid 'type' field"],
            location=location,
        )

    if event_type not in _SCHEMA_MAP:
        return ValidationResult(
            valid=False,
            event_type=event_type,
            errors=[f"Unknown AAEP event type: {event_type!r}"],
            location=location,
        )

    validator = _get_validator(event_type)
    errors = list(validator.iter_errors(event))

    if not errors:
        return ValidationResult(
            valid=True,
            event_type=event_type,
            errors=[],
            location=location,
        )

    formatted: list[str] = []
    for err in errors:
        pointer = "/".join(str(p) for p in err.absolute_path) or "<root>"
        formatted.append(f"{pointer}: {err.message}")

    return ValidationResult(
        valid=False,
        event_type=event_type,
        errors=formatted,
        location=location,
    )


def validate_stream(
    source: TextIO,
    *,
    source_name: str = "<stdin>",
) -> Iterator[ValidationResult]:
    """Validate a JSONL stream (one event per line) yielding results."""
    line_no = 0
    for raw_line in source:
        line_no += 1
        stripped = raw_line.strip()
        if not stripped:
            continue
        location = f"{source_name}:line {line_no}"
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError as e:
            yield ValidationResult(
                valid=False,
                event_type=None,
                errors=[f"Invalid JSON: {e.msg} (column {e.colno})"],
                location=location,
            )
            continue
        yield validate_event(event, location=location)


# === Output formatters ===

def _format_result_human(result: ValidationResult) -> str:
    if result.valid:
        return f"OK  {result.location}  {result.event_type}"
    lines = [f"FAIL {result.location}  {result.event_type or '<no type>'}"]
    for err in result.errors:
        lines.append(f"     {err}")
    return "\n".join(lines)


# === CLI ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-validate",
        description="Validate AAEP events against the JSON Schemas",
        epilog=(
            "Examples:\n"
            "  aaep-validate < event.json           # validate stdin\n"
            "  aaep-validate event.json             # validate one file\n"
            "  aaep-validate --file stream.jsonl    # validate a JSONL stream\n"
            "  aaep-validate --quiet *.jsonl        # exit code only\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="JSON or JSONL files to validate (uses stdin if none given)",
    )
    parser.add_argument(
        "--file", "-f",
        action="append",
        default=[],
        dest="extra_files",
        help="Additional JSONL files to validate (repeatable)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="No output, only exit code (0 = all valid, 1 = any invalid)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON-formatted validation reports (one per result)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="aaep-validate 1.0.0 (AAEP spec 1.0.0)",
    )

    args = parser.parse_args(argv)

    all_paths = list(args.paths) + list(args.extra_files)

    total = 0
    failed = 0

    try:
        if not all_paths:
            # Read from stdin
            content = sys.stdin.read()
            results = _validate_input(content, source_name="<stdin>")
            for result in results:
                total += 1
                if not result.valid:
                    failed += 1
                _emit_result(result, args)
        else:
            for path_str in all_paths:
                path = Path(path_str)
                if not path.is_file():
                    print(f"aaep-validate: {path_str}: file not found", file=sys.stderr)
                    return 2
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                results = _validate_input(content, source_name=str(path))
                for result in results:
                    total += 1
                    if not result.valid:
                        failed += 1
                    _emit_result(result, args)
    except OSError as e:
        print(f"aaep-validate: {e}", file=sys.stderr)
        return 2

    if not args.quiet:
        if failed:
            print(f"\n{failed} of {total} event(s) failed validation.", file=sys.stderr)
        else:
            print(f"\nAll {total} event(s) valid.", file=sys.stderr)

    return 0 if failed == 0 else 1


def _validate_input(content: str, source_name: str) -> list[ValidationResult]:
    """Decide whether the input is a single event (JSON) or a stream (JSONL)."""
    stripped = content.strip()
    if not stripped:
        return []

    # Heuristic: if it parses as a single JSON object, treat as one event.
    # Otherwise treat as JSONL.
    try:
        event = json.loads(stripped)
        if isinstance(event, dict):
            return [validate_event(event, location=source_name)]
        if isinstance(event, list):
            # JSON array of events
            return [
                validate_event(e, location=f"{source_name}[{i}]")
                for i, e in enumerate(event)
            ]
    except json.JSONDecodeError:
        pass

    # Treat as JSONL
    import io
    return list(validate_stream(io.StringIO(content), source_name=source_name))


def _emit_result(result: ValidationResult, args: argparse.Namespace) -> None:
    if args.quiet:
        return
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(_format_result_human(result))


if __name__ == "__main__":
    sys.exit(main())
