from pathlib import Path

import typer

APP_NAME = "cogrion"


def app_dir() -> Path:
    path = Path(typer.get_app_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    return app_dir() / "config.json"
