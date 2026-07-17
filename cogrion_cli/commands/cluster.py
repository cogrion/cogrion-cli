import typer
from rich.console import Console

app = typer.Typer(help="Manage your self-hosted cloud clusters")
console = Console()


@app.command("connect")
def connect(
    provider: str = typer.Option(..., "--provider", "-p", help="Cloud provider (aws/gcp/azure)"),
) -> None:
    """Link a cloud account to your self-hosted cluster."""
    console.print("[yellow]Not yet implemented.[/yellow]")


@app.command("list")
def list_clusters() -> None:
    """List clusters linked to your account."""
    console.print("[yellow]Not yet implemented.[/yellow]")
