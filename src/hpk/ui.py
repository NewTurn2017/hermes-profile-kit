"""Console output helpers. All hpk output flows through here for consistent formatting."""

from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme

THEME = Theme(
    {
        "step": "bold cyan",
        "ok": "bold green",
        "warn": "bold yellow",
        "err": "bold red",
        "muted": "dim",
    }
)

console = Console(theme=THEME)
console_err = Console(theme=THEME, stderr=True)


def step(msg: str) -> None:
    console.print(f"[step]▶[/] {msg}")


def ok(msg: str) -> None:
    console.print(f"  [ok]✓[/] {msg}")


def warn(msg: str) -> None:
    console.print(f"  [warn]⚠[/] {msg}")


def err(msg: str) -> None:
    console_err.print(f"  [err]✗[/] {msg}")


def header(title: str) -> None:
    console.print(Panel.fit(title, border_style="step"))
