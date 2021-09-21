"""The commandline interface."""
import os
import shlex
import subprocess
import sys
import time
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

import click
import yaml

from . import __version__
from .api import COLUMNS_DESCRIPT, PLOT_YLABELS, plot_result, profile_process


def echo_info(string: str, quiet=False) -> None:
    """Echo info to the user."""
    if not quiet:
        click.echo(click.style("PPLOT INFO: ", fg="blue") + string)


def echo_success(quiet=False):
    """Echo success to the user."""
    if not quiet:
        click.echo(click.style("PPLOT SUCCESS!", fg="green"))


def columns_callback(ctx, param, value: bool) -> None:
    """Plot the ps columns and exit"""
    if not value or ctx.resilient_parsing:
        return
    click.echo(yaml.dump(dict(COLUMNS_DESCRIPT), default_flow_style=False))
    ctx.exit()


@click.group()
@click.version_option(__version__)
@click.option(
    "--columns",
    is_eager=True,
    is_flag=True,
    expose_value=False,
    callback=columns_callback,
    help="Show output column descriptions and exit",
)
def main(
    context_settings={  # noqa: B006
        "help_option_names": (
            "-h",
            "--help",
        )
    }
):
    """CLI to profile a process's memory/CPU usage and plot it."""


@main.command("exec")
@click.argument("command")
@click.option(
    "-i", "--interval", type=float, default=1, help="Polling interval (seconds)"
)
@click.option("-t", "--timeout", type=float, help="Timeout process (seconds)")
@click.option(
    "-c",
    "--command-output",
    default="file",
    type=click.Choice(["hide", "screen", "file"]),
    show_default=True,
    help="Mode for stdout/stderr of command",
)
@click.option(
    "-o",
    "--outfolder",
    default="pplot_out",
    type=click.Path(file_okay=False),
    help="Folder path for output files",
)
@click.option(
    "-n", "--basename", help="Basename for output files (defaults to datetime)"
)
@click.option(
    "-p",
    "--plot-cols",
    metavar=f"[{'|'.join(dict(PLOT_YLABELS))}]",
    default="memory_rss,cpu_percent",
    show_default=True,
    help="Columns to plot (comma-delimited)",
)
@click.option("--title", help="Plot title (defaults to command)")
@click.option(
    "--grid/--no-grid",
    is_flag=True,
    default=True,
    show_default=True,
    help="Add grid to plots",
)
@click.option(
    "-f",
    "--format",
    default="png",
    type=click.Choice(["png", "pdf", "svg"]),
    help="Plot file format",
)
@click.option("-v", "--verbose", count=True, help="Increase verbosity")
@click.option("-q", "--quiet", is_flag=True, help="Quiet mode")
def cmd_exec(
    command,
    outfolder,
    basename,
    interval,
    timeout,
    command_output,
    plot_cols,
    format,
    title,
    grid,
    verbose,
    quiet,
):
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

    if command_output == "screen":
        stdout_context = nullcontext(sys.stdout)
        stderr_context = nullcontext(sys.stderr)
    elif command_output == "hide":
        stdout_context = open(os.devnull, "w")
        stderr_context = open(os.devnull, "w")
    elif command_output == "file":
        stdout_context = open(outfolder / f"{basename}.out.log", "w")
        stderr_context = open(outfolder / f"{basename}.err.log", "w")
    else:
        raise ValueError(f"Unknown command output mode: {command_output}")

    output_path = outfolder / f"{basename}.csv"
    output_context = open(output_path, "w")

    max_iterations = None
    if timeout:
        max_iterations = int(timeout / interval)

    columns = plot_cols.split(",")
    if not set(columns).issubset(dict(PLOT_YLABELS)):
        raise click.BadOptionUsage(
            "plot_cols",
            f"Invalid value for '-p' / '--plot-cols': Unknown columns in {columns}",
        )

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
                        poll_interval=interval,
                        max_iterations=max_iterations,
                        output_stream=output_stream,
                        headers=True,
                        output_separator=",",
                        output_files_num="files_num" in columns,
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
    plot_path = output_path.parent / f"{basename}.{format}"
    echo_info(f"Plotting results to: {plot_path}", quiet=quiet)
    plot_result(
        output_path, plot_path, columns=columns, title=(title or command), grid=grid
    )
    echo_success(quiet=quiet)


if __name__ == "__main__":
    main()
