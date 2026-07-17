import sys

import typer

from cogrion_cli.commands import auth, cluster, deploy
from cogrion_cli.state import State

app = typer.Typer(help="Cogrion BYOC control plane CLI", no_args_is_help=True)
app.add_typer(auth.app, name="auth")
app.add_typer(cluster.app, name="cluster")
app.add_typer(deploy.app, name="deploy")

state = State()


@app.callback()
def main_callback(
    json_output: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of formatted output"
    ),
) -> None:
    state.json_output = json_output


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\nCancelled.", err=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
