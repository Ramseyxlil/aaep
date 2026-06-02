"""
AAEP Conformance Suite — Command Line Interface.

Provides the `aaep-conformance` command with subcommands:

  producer   - Verify an AAEP producer at a given conformance level
  subscriber - Verify an AAEP subscriber at a given conformance level
  validate   - Validate a single AAEP event file against the schema
  version    - Print version information

Exit codes:
  0 - All tests passed (or validation succeeded)
  1 - Tests failed (or validation failed)
  2 - Configuration or invocation error
  3 - Internal suite error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from aaep_conformance import __version__, __aaep_spec_version__
from aaep_conformance.checks.envelope import validate_event
from aaep_conformance.runner import Runner, RunnerConfig
from aaep_conformance.reporter import Report, Severity, Verdict


console = Console()


# === Top-level CLI group ===

@click.group()
@click.version_option(version=__version__, prog_name="aaep-conformance")
def main() -> None:
    """
    AAEP Conformance Test Suite.

    Verify that your AAEP producer or subscriber implementation
    conforms to the Agent Accessibility Event Protocol specification.

    See https://aaep-protocol.org/conformance/ for documentation.
    """
    pass


# === Producer command ===

@main.command()
@click.option(
    "--endpoint",
    required=True,
    help="HTTP/HTTPS URL or transport identifier for the producer under test",
)
@click.option(
    "--level",
    type=click.Choice(["1", "2", "3"]),
    default="1",
    show_default=True,
    help="Conformance level to test against",
)
@click.option(
    "--report-json",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=Path("conformance-report.json"),
    show_default=True,
    help="Path to write JSON report",
)
@click.option(
    "--report-html",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=Path("conformance-report.html"),
    show_default=True,
    help="Path to write HTML report",
)
@click.option(
    "--timeout",
    type=int,
    default=300,
    show_default=True,
    help="Per-test timeout in seconds",
)
@click.option(
    "--fail-on-warning",
    is_flag=True,
    help="Exit with code 1 if any warnings occur (useful for strict CI)",
)
@click.option(
    "--profile",
    type=click.Choice([
        "default", "langchain-mode", "middleware-mode",
        "tool-mode", "bridge-mode", "manual-mode"
    ]),
    default="default",
    show_default=True,
    help="Test profile tailored to specific integration patterns",
)
@click.option(
    "--filter",
    "filter_pattern",
    help="Run only tests matching this pattern (substring match on test ID)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show per-test output during the run",
)
def producer(
    endpoint: str,
    level: str,
    report_json: Path,
    report_html: Path,
    timeout: int,
    fail_on_warning: bool,
    profile: str,
    filter_pattern: str | None,
    verbose: bool,
) -> None:
    """Test an AAEP producer endpoint at the given conformance level."""

    console.print(Panel.fit(
        f"[bold]AAEP Conformance Test — Producer Mode[/bold]\n"
        f"Endpoint:  {endpoint}\n"
        f"Level:     {level}\n"
        f"Profile:   {profile}\n"
        f"Suite:     {__version__}\n"
        f"Spec:      {__aaep_spec_version__}",
        border_style="cyan",
    ))

    config = RunnerConfig(
        target_kind="producer",
        endpoint=endpoint,
        level=int(level),
        timeout_seconds=timeout,
        profile=profile,
        filter_pattern=filter_pattern,
        verbose=verbose,
    )

    try:
        runner = Runner(config)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=not verbose,
        ) as progress:
            task = progress.add_task("Running conformance tests...", total=None)
            report = runner.run()
            progress.update(task, completed=1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(2)
    except Exception as exc:
        console.print(f"\n[red bold]Internal suite error:[/red bold] {exc}")
        sys.exit(3)

    _print_summary(report)
    report.save_json(report_json)
    report.save_html(report_html)
    console.print(f"\nReports written:\n  JSON: {report_json}\n  HTML: {report_html}")

    sys.exit(_exit_code_for(report, fail_on_warning))


# === Subscriber command ===

@main.command()
@click.option(
    "--connect",
    required=True,
    help="Connection string for the subscriber under test (e.g., tcp://host:port)",
)
@click.option(
    "--level",
    type=click.Choice(["1", "2", "3"]),
    default="1",
    show_default=True,
    help="Conformance level to test against",
)
@click.option(
    "--report-json",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=Path("conformance-report.json"),
    show_default=True,
)
@click.option(
    "--report-html",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=Path("conformance-report.html"),
    show_default=True,
)
@click.option("--timeout", type=int, default=300, show_default=True)
@click.option("--fail-on-warning", is_flag=True)
@click.option("--verbose", "-v", is_flag=True)
def subscriber(
    connect: str,
    level: str,
    report_json: Path,
    report_html: Path,
    timeout: int,
    fail_on_warning: bool,
    verbose: bool,
) -> None:
    """Test an AAEP subscriber by acting as a synthetic producer."""

    console.print(Panel.fit(
        f"[bold]AAEP Conformance Test — Subscriber Mode[/bold]\n"
        f"Connect:   {connect}\n"
        f"Level:     {level}\n"
        f"Suite:     {__version__}",
        border_style="cyan",
    ))

    config = RunnerConfig(
        target_kind="subscriber",
        endpoint=connect,
        level=int(level),
        timeout_seconds=timeout,
        verbose=verbose,
    )

    try:
        runner = Runner(config)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=not verbose,
        ) as progress:
            task = progress.add_task("Running subscriber tests...", total=None)
            report = runner.run()
            progress.update(task, completed=1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(2)
    except Exception as exc:
        console.print(f"\n[red bold]Internal suite error:[/red bold] {exc}")
        sys.exit(3)

    _print_summary(report)
    report.save_json(report_json)
    report.save_html(report_html)
    console.print(f"\nReports written:\n  JSON: {report_json}\n  HTML: {report_html}")

    sys.exit(_exit_code_for(report, fail_on_warning))


# === Validate command ===

@main.command()
@click.argument("event_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--strict",
    is_flag=True,
    help="Treat warnings as failures",
)
def validate(event_file: Path, strict: bool) -> None:
    """Validate a single AAEP event JSON file against the schema."""

    try:
        event = json.loads(event_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print(f"[red bold]Not valid JSON:[/red bold] {exc}")
        sys.exit(2)

    errors = validate_event(event)
    if not errors:
        console.print(f"[green]✓[/green] {event_file} is a valid AAEP event.")
        sys.exit(0)

    console.print(f"[red bold]Validation failed for {event_file}:[/red bold]")
    for err in errors:
        console.print(f"  [red]✗[/red] {err}")
    sys.exit(1)


# === Version command ===

@main.command()
def version() -> None:
    """Print version information and exit."""
    console.print(f"aaep-conformance {__version__}")
    console.print(f"AAEP specification version: {__aaep_spec_version__}")
    console.print(f"Python: {sys.version.split()[0]}")


# === Internal helpers ===

def _print_summary(report: Report) -> None:
    """Print a colored summary table of the report."""
    console.print()
    summary = Table(title="Conformance Test Summary", show_header=False, expand=False)
    summary.add_column("Field", style="bold")
    summary.add_column("Value")

    verdict_style = {
        Verdict.PASS: "[green]PASS[/green]",
        Verdict.FAIL: "[red]FAIL[/red]",
        Verdict.SKIPPED: "[yellow]SKIPPED[/yellow]",
    }
    summary.add_row("Verdict", verdict_style.get(report.verdict, str(report.verdict)))
    summary.add_row("Tests run", str(report.tests_run))
    summary.add_row("Passed", f"[green]{report.tests_passed}[/green]")
    summary.add_row("Failed", f"[red]{report.tests_failed}[/red]")
    summary.add_row("Skipped", f"[yellow]{report.tests_skipped}[/yellow]")
    summary.add_row("Pass rate", f"{report.pass_rate:.1%}")
    summary.add_row("Duration", f"{report.duration_seconds:.1f}s")
    console.print(summary)

    if report.failures:
        console.print()
        failures = Table(title=f"Failures ({len(report.failures)})", expand=True)
        failures.add_column("Test ID", style="cyan", no_wrap=True)
        failures.add_column("Severity", no_wrap=True)
        failures.add_column("Description")

        for fail in report.failures[:20]:
            sev_color = {
                Severity.ERROR: "red",
                Severity.WARNING: "yellow",
                Severity.INFO: "blue",
            }.get(fail.severity, "white")
            failures.add_row(
                fail.test_id,
                f"[{sev_color}]{fail.severity.value}[/{sev_color}]",
                fail.description[:80],
            )

        console.print(failures)
        if len(report.failures) > 20:
            console.print(f"[dim]... and {len(report.failures) - 20} more (see report files)[/dim]")


def _exit_code_for(report: Report, fail_on_warning: bool) -> int:
    """Translate a report into a process exit code."""
    has_errors = any(f.severity == Severity.ERROR for f in report.failures)
    has_warnings = any(f.severity == Severity.WARNING for f in report.failures)

    if has_errors:
        return 1
    if fail_on_warning and has_warnings:
        return 1
    return 0


if __name__ == "__main__":
    main()
