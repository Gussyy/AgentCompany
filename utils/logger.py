"""
Rich console logger — gives the terminal a clean, readable output
showing which agent is running, gate decisions, and chamber progress.
"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich import print as rprint

console = Console()

# ── Agent colours ──────────────────────────────────────────────
AGENT_COLOURS = {
    "ARIA":   "cyan",
    "NOVA":   "bright_yellow",
    "QUANT":  "green",
    "GATE":   "red",
    "ARCH":   "blue",
    "CORE":   "bright_blue",
    "PIXEL":  "magenta",
    "VIGIL":  "bright_red",
    "APEX":   "bright_green",
    "HAVEN":  "bright_cyan",
    "SENTRY": "bright_magenta",
    "LEDGER": "yellow",
    "ORCA-1": "white",
}

CHAMBER_COLOURS = {
    1:   "cyan",
    1.5: "yellow",
    2:   "blue",
    2.5: "green",
    3:   "bright_green",
}


def chamber_banner(chamber_num: float, name: str) -> None:
    colour = CHAMBER_COLOURS.get(chamber_num, "white")
    label = f"Chamber {chamber_num}" if chamber_num != int(chamber_num) else f"Chamber {int(chamber_num)}"
    console.print(Rule(f"[bold {colour}]⚙  {label}: {name}[/]", style=colour))


def agent_start(agent_name: str, task: str) -> None:
    colour = AGENT_COLOURS.get(agent_name, "white")
    console.print(f"\n[bold {colour}]▶  {agent_name}[/] [dim]—[/] {task}")


def agent_output(agent_name: str, content: str) -> None:
    colour = AGENT_COLOURS.get(agent_name, "white")
    panel = Panel(
        content,
        title=f"[bold {colour}]{agent_name}[/]",
        border_style=colour,
        expand=False,
        padding=(0, 1),
    )
    console.print(panel)


def gate_decision(decision: str, reason: str) -> None:
    if decision == "GO":
        console.print(Panel(
            f"[bold green]✅  GO — {reason}[/]",
            title="[bold green]GATE DECISION[/]",
            border_style="green",
        ))
    elif decision == "KILL":
        console.print(Panel(
            f"[bold red]❌  KILL — {reason}[/]",
            title="[bold red]GATE DECISION[/]",
            border_style="red",
        ))
    else:
        console.print(Panel(
            f"[bold yellow]🔄  PIVOT — {reason}[/]",
            title="[bold yellow]GATE DECISION[/]",
            border_style="yellow",
        ))


def ceo_prompt(message: str) -> None:
    console.print(Panel(
        f"[bold gold1]{message}[/]",
        title="[bold gold1]👤 CEO — ACTION REQUIRED[/]",
        border_style="gold1",
    ))


def info(message: str) -> None:
    console.print(f"[dim]  ℹ  {message}[/]")


def success(message: str) -> None:
    console.print(f"[bold green]  ✓  {message}[/]")


def warning(message: str) -> None:
    console.print(f"[bold yellow]  ⚠  {message}[/]")


def error(message: str) -> None:
    console.print(f"[bold red]  ✗  {message}[/]")


def section(title: str) -> None:
    console.print(f"\n[bold white]{title}[/]")
    console.print("─" * len(title))
