"""The commandline interface."""

from collections.abc import Sequence
from contextlib import nullcontext
from datetime import datetime
from enum import Enum
from io import TextIOWrapper
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Annotated, Optional, Union

try:
    from typing import TypeAlias
except ImportError:
    # added in python 3.10
    from typing_extensions import TypeAlias

from rich import print as echo
from rich.table import Table
import typer

from . import __version__
from .api import COLUMNS_DESCRIPT, PLOT_YLABELS, plot_result, profile_process

main = typer.Typer(
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",
)


def version_callback(value: bool) -> None:
    """Print the version and exit."""
    if value:
        echo(f"version: {__version__}")
        raise typer.Exit()


def columns_callback(value: bool) -> None:
    """Print the available columns and exit"""
    if value:
        table = Table(show_header=True)
        table.add_column("Name")
        table.add_column("Description")
        for name, desc in COLUMNS_DESCRIPT:
            table.add_row(name, desc)
        echo(table)
        raise typer.Exit()


@main.callback()
def main_app(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the application version and exit.",
    ),
    columns: Optional[bool] = typer.Option(
        None,
        "--columns",
        callback=columns_callback,
        is_eager=True,
        help="Show the available columns and exit.",
    ),
) -> None:
    """[underline]CLI to profile a process's memory/CPU usage and plot it[/underline]"""


def echo_info(string: str, quiet: bool = False) -> None:
    """Echo info to the user."""
    if not quiet:
        echo("[blue]PPLOT INFO: [/blue]" + string)


def echo_success(quiet: bool = False) -> None:
    """Echo success to the user."""
    if not quiet:
        echo("[bold green]PPLOT SUCCESS![/bold green]")


class CmdOutput(str, Enum):
    hide = "hide"
    screen = "screen"
    file = "file"


class PlotFormat(str, Enum):
    png = "png"
    pdf = "pdf"
    svg = "svg"


def parse_plot_columns(columns: Union[str, Sequence[str]]) -> list[str]:
    """Process the plot columns."""
    if isinstance(columns, str):
        cols = [c.strip() for c in columns.split(",")]
    else:
        cols = list(columns)
    if not set(cols).issubset({name for name, _ in PLOT_YLABELS}):
        raise typer.BadParameter(f"Unknown columns in {cols}")
    return cols


PlotColsT: TypeAlias = Annotated[
    Sequence[str],
    typer.Option(
        "-p",
        "--plot-cols",
        help="Columns to plot",
        metavar="COMMA-DELIMITED",
        rich_help_panel="Plot",
        parser=parse_plot_columns,
    ),
]
StackProcessesT: TypeAlias = Annotated[
    bool,
    typer.Option(help="Stack values per process in plot", rich_help_panel="Plot"),
]
TitleT: TypeAlias = Annotated[
    Optional[str],
    typer.Option(
        help="Plot title (defaults to command)",
        show_default=False,
        rich_help_panel="Plot",
    ),
]
GridT: TypeAlias = Annotated[
    bool,
    typer.Option("--grid/--no-grid", help="Add grid to plots", rich_help_panel="Plot"),
]
LegendT: TypeAlias = Annotated[
    bool,
    typer.Option(
        "--legend/--no-legend", help="Add legend to figure", rich_help_panel="Plot"
    ),
]
SizeWidthT: TypeAlias = Annotated[
    Optional[float],
    typer.Option(
        "-sw", "--size-width", help="Width of plot in cm", rich_help_panel="Plot"
    ),
]
SizeHeightT: TypeAlias = Annotated[
    Optional[float],
    typer.Option(
        "-sh", "--size-height", help="Height of plot in cm", rich_help_panel="Plot"
    ),
]
FormatT: TypeAlias = Annotated[
    PlotFormat,
    typer.Option("-f", "--format", help="Plot file format", rich_help_panel="Plot"),
]


@main.command(name="exec", no_args_is_help=True)
def cmd_exec(
    command: str,
    interval: Annotated[
        float, typer.Option("-i", "--interval", help="Polling interval (seconds)")
    ] = 1,
    timeout: Annotated[
        Optional[float],
        typer.Option(
            "-t", "--timeout", help="Timeout process (seconds)", show_default=False
        ),
    ] = None,
    child: Annotated[bool, typer.Option(help="Collect child process data")] = True,
    command_output: Annotated[
        CmdOutput,
        typer.Option(
            "-c",
            "--command-output",
            help="Mode for stdout/stderr of command",
            show_default=True,
        ),
    ] = CmdOutput.file,
    outfolder: Annotated[
        Path,
        typer.Option(
            "-o", "--outfolder", file_okay=False, help="Folder path for output files"
        ),
    ] = Path("pplot_out"),
    basename: Annotated[
        Optional[str],
        typer.Option(
            "-n",
            "--basename",
            help="Basename for output files (defaults to datetime)",
            show_default=False,
        ),
    ] = None,
    plot_cols: PlotColsT = ("memory_rss", "cpu_percent"),
    stack_processes: StackProcessesT = False,
    title: TitleT = None,
    grid: GridT = True,
    legend: LegendT = False,
    size_width: SizeWidthT = None,
    size_height: SizeHeightT = None,
    format: FormatT = PlotFormat.png,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Quiet mode")] = False,
) -> None:
    """Execute a command and profile it."""

    outfolder = Path(outfolder)
    basename = basename or time.strftime("%Y%m%d%H%M%S", time.localtime())

    echo_info(
        f"Output files will be written to: {outfolder.absolute()}, with basename: {basename}",
        quiet=quiet,
    )
    # if outfolder.exists():
    #     click.confirm("Overwrite files in existing output folder?", abort=True)
    outfolder.mkdir(parents=True, exist_ok=True)

    stdout_context: TextIOWrapper
    stderr_context: TextIOWrapper
    if command_output == CmdOutput.screen:
        stdout_context = nullcontext(sys.stdout)  # type: ignore[assignment]
        stderr_context = nullcontext(sys.stderr)  # type: ignore[assignment]
    elif command_output == CmdOutput.hide:
        stdout_context = open(os.devnull, "w")
        stderr_context = open(os.devnull, "w")
    elif command_output == CmdOutput.file:
        stdout_context = open(outfolder / f"{basename}.out.log", "w")
        stderr_context = open(outfolder / f"{basename}.err.log", "w")
    else:
        raise ValueError(f"Unknown command output mode: {command_output}")

    output_path = outfolder / f"{basename}.csv"
    output_context = open(output_path, "w")

    max_iterations = None
    if timeout:
        max_iterations = int(timeout / interval)

    command_list = shlex.split(command)
    echo_info(f"Staring command: {command_list}", quiet=quiet)

    with stdout_context as stdout_stream:
        with stderr_context as stderr_stream:
            with output_context as output_stream:
                start_time = datetime.now()
                proc = subprocess.Popen(
                    command_list,
                    shell=False,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    env=os.environ,
                )
                echo_info(f"Running process as PID: {proc.pid}", quiet=quiet)
                try:
                    profile_process(
                        proc.pid,
                        child_processes=child,
                        poll_interval=interval,
                        max_iterations=max_iterations,
                        output_stream=output_stream,
                        headers=True,
                        output_separator=",",
                        output_files_num="files_num" in plot_cols,
                    )
                except TimeoutError:
                    echo_info("Process reached timeout before terminating", quiet=quiet)
                proc.kill()
                end_time = datetime.now()

    hours, mins, secs = str(end_time - start_time).split(":")
    echo_info(
        f"Total run time: {hours} hour(s), {mins} minute(s), {secs} second(s)",
        quiet=quiet,
    )
    plot_path = output_path.parent / f"{basename}.{format.value}"
    echo_info(
        f"Plotting results to: [underline cyan]{plot_path}[/underline cyan]",
        quiet=quiet,
    )
    plotted = plot_result(
        output_path,
        plot_path,
        columns=plot_cols,
        title=(title or command),
        grid=grid,
        legend=legend,
        stack_processes=stack_processes,
        width_cm=size_width,
        height_cm=size_height,
    )
    if not plotted:
        echo_info("No data to plot", quiet=quiet)
    else:
        echo_success(quiet=quiet)


@main.command(name="plot", no_args_is_help=True)
def cmd_plot(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to the CSV file containing the process data",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    plot_cols: PlotColsT = ("memory_rss", "cpu_percent"),
    stack_processes: StackProcessesT = False,
    title: TitleT = None,
    grid: GridT = True,
    legend: LegendT = False,
    size_width: SizeWidthT = None,
    size_height: SizeHeightT = None,
    format: FormatT = PlotFormat.png,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Quiet mode")] = False,
) -> None:
    """Plot a previously profiled process."""
    # plot_path = output_path.parent / f"{basename}.{format.value}"
    plot_path = path.with_suffix(f".{format.value}")
    echo_info(
        f"Plotting results to: [underline cyan]{plot_path}[/underline cyan]",
        quiet=quiet,
    )
    plotted = plot_result(
        path,
        plot_path,
        columns=plot_cols,
        title=title or "",
        grid=grid,
        legend=legend,
        stack_processes=stack_processes,
        width_cm=size_width,
        height_cm=size_height,
    )
    if not plotted:
        echo_info("No data to plot", quiet=quiet)
    else:
        echo_success(quiet=quiet)


if __name__ == "__main__":
    main()
