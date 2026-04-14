"""
main.py — Entry point for AgentCompany.

Two modes:
  1. Dashboard mode (default): starts the FastAPI server + CEO dashboard
     python main.py
     Then open http://localhost:8000 in your browser.

  2. CLI mode: runs the company directly from the terminal
     python main.py run --industry "digital health"
"""
import sys
import os

# Force UTF-8 output on Windows so emojis render correctly
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import typer
import uvicorn

app = typer.Typer(help="AgentCompany — AI-powered autonomous company engine")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
):
    """
    Start the CEO Dashboard server.
    Open http://localhost:8000 in your browser to monitor the company.
    """
    typer.echo("🏢 AgentCompany — Starting CEO Dashboard...")
    typer.echo(f"   Open http://localhost:{port} in your browser")
    typer.echo("   Enter an industry and click ▶ Run Company to start.\n")
    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="warning",
    )


@app.command()
def run(
    industry: str = typer.Argument(..., help="Target industry (e.g. 'digital health')"),
    ad_budget: float = typer.Option(500.0, help="Smoke Test ad budget in USD"),
):
    """
    Run the company in CLI mode without the dashboard.
    Good for quick tests or running in headless environments.
    """
    from rich.console import Console
    console = Console()
    console.print(f"\n[bold gold1]🏢 AgentCompany CLI[/] — targeting: [cyan]{industry}[/]\n")

    from orchestrator import Orchestrator
    orch = Orchestrator(industry=industry, ad_budget_usd=ad_budget)
    result = orch.run()

    console.print(f"\n[bold]Final status:[/] {result['status']}")
    if result.get("product_name"):
        console.print(f"[bold]Product:[/] {result['product_name']}")
    if result.get("daily_report"):
        dr = result["daily_report"]
        console.print(f"[bold]Total spend:[/] ${dr.get('total_spend_usd', 0):.2f}")
    if result.get("daily_report", {}).get("action_items"):
        console.print("\n[bold gold1]CEO Action Items:[/]")
        for item in result["daily_report"]["action_items"]:
            console.print(f"  ⚡ {item}")


if __name__ == "__main__":
    # Default: serve the dashboard
    if len(sys.argv) == 1:
        serve()
    else:
        app()
