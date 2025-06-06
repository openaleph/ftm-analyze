from typing import Optional

import typer
from anystore.cli import ErrorHandler
from anystore.logging import configure_logging, get_logger
from rich.console import Console
from typing_extensions import Annotated

from ftm_analyze import __version__
from ftm_analyze.settings import Settings

settings = Settings()
cli = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)

log = get_logger(__name__)


class Opts:
    IN = typer.Option("-", "-i", help="Input entities uri (file, http, s3...)")
    OUT = typer.Option("-", "-o", help="Output entities uri (file, http, s3...)")


@cli.callback(invoke_without_command=True)
def cli_base(
    version: Annotated[Optional[bool], typer.Option(..., help="Show version")] = False,
):
    if version:
        print(__version__)
        raise typer.Exit()
    configure_logging()


@cli.command("settings")
def cli_settings():
    """Show current configuration"""
    with ErrorHandler():
        console.print(settings)
