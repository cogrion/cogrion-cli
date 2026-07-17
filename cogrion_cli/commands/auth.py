import typer
from rich.console import Console

app = typer.Typer(help="Authenticate the CLI with the Cogrion control plane")
console = Console()


@app.command()
def login() -> None:
    """Authenticate the CLI with your Cogrion control plane."""
    console.print("[yellow]Not yet implemented.[/yellow]")


@app.command()
def logout() -> None:
    """Clear the locally stored session."""
    console.print("[yellow]Not yet implemented.[/yellow]")
