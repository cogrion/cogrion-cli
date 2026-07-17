import typer
from rich.console import Console

app = typer.Typer(help="Deploy apps to a linked cluster")
console = Console()


@app.command()
def run(
    env: str = typer.Option("prod", "--env", help="Target environment"),
) -> None:
    """Deploy the current app to a linked cluster."""
    console.print("[yellow]Not yet implemented.[/yellow]")
