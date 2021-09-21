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
from .profile import profile_process

PS_FIELD_HELP = (
    (
        "PID",
        "Process IDentifier -- a number used by the operating system"
        "kernel to uniquely identify a running program or process.",
    ),
    (
        "DATE",
        "The calender date, given as YEAR-MONTH-DAY, that the process was polled.",
    ),
    (
        "TIME",
        "The actual time, given as HOUR:MINUTE:SECONDS that the process was polled.",
    ),
    (
        "ELAPSED",
        "The total time that the process had been running up to the time it was polled.",
    ),
    (
        "CPU",
        "The CPU utilization of the process: CPU time used divided by the"
        "time the process has been running (cputime/realtime ratio),"
        "expressed as a percentage.",
    ),
    (
        "MEM",
        "The memory utilization of the process: ratio of the process's"
        "resident set size to the physical memory on the machine, expressed"
        "as a percentage.",
    ),
    (
        "RSS",
        "Resident Set Size -- the non-swapped physical memory (RAM) that a"
        "process is occupying (in kiloBytes). The rest of the process memory"
        "usage is in swap. If the computer has not used swap, this number"
        "will be equal to VSIZE.",
    ),
    (
        "VSIZE",
        "Virtual memory Size -- the total amount of memory the"
        "process is currently using (in kiloBytes). This includes the amount"
        "in RAM (the resident set size) as well as the amount in swap.",
    ),
    (
        "CMD",
        "Running process path and command line arguments.",
    ),
)


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
    click.echo(yaml.dump(dict(PS_FIELD_HELP), default_flow_style=False))
    ctx.exit()


@click.group()
@click.version_option(__version__)
@click.option(
    "--columns",
    is_eager=True,
    is_flag=True,
    expose_value=False,
    callback=columns_callback,
    help="Show the ps columns and exit",
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
@click.option("-i", "--interval", type=float, default=1, help="Interval in seconds")
@click.option(
    "-c",
    "--command-output",
    default="file",
    type=click.Choice(["hide", "screen", "file"]),
    show_default=True,
    help="Mode for stdout/stderr of command",
)
@click.option("-p", "--basepath", default="pplot_out", help="Basepath for output files")
@click.option(
    "-n", "--basename", help="Basename for output files (defaults to datetime)"
)
@click.option("-t", "--title", help="Plot title")
@click.option("-v", "--verbose", count=True, help="Increase verbosity")
@click.option("-q", "--quiet", is_flag=True, help="Quiet mode")
def cmd_exec(
    command, basepath, basename, interval, command_output, title, verbose, quiet
):
    """Execute a command and profile it."""

    basepath = Path(basepath)
    basename = basename or time.strftime("%Y%m%d%H%M%S", time.localtime())

    echo_info(
        f"Output files will be written to: {basepath.absolute()}, with basename: {basename}",
        quiet=quiet,
    )
    # if basepath.exists():
    #     click.confirm("Overwrite files in existing output folder?", abort=True)
    basepath.mkdir(parents=True, exist_ok=True)

    if command_output == "screen":
        stdout_context = nullcontext(sys.stdout)
        stderr_context = nullcontext(sys.stderr)
    elif command_output == "hide":
        stdout_context = open(os.devnull, "w")
        stderr_context = open(os.devnull, "w")
    elif command_output == "file":
        stdout_context = open(basepath / f"{basename}.out.log", "w")
        stderr_context = open(basepath / f"{basename}.err.log", "w")
    else:
        raise ValueError(f"Unknown command output mode: {command_output}")

    output_path = basepath / f"{basename}.csv"
    output_context = open(output_path, "w")

    echo_info("Running process", quiet=quiet)

    with stdout_context as stdout_stream:
        with stderr_context as stderr_stream:
            with output_context as output_stream:
                start_time = datetime.now()
                proc = subprocess.Popen(
                    shlex.split(command),
                    shell=False,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    env=os.environ,
                )
                profile_process(
                    proc.pid,
                    poll_interval=interval,
                    quit_if_none=True,
                    quit_poll_func=proc.poll,
                    output_stream=output_stream,
                    headers=True,
                    output_separator=",",
                    debug_level=verbose,
                )
                end_time = datetime.now()

    hours, mins, secs = str(end_time - start_time).split(":")
    echo_info(
        f"Total run time: {hours} hour(s), {mins} minute(s), {secs} second(s)",
        quiet=quiet,
    )
    echo_info("Plotting results", quiet=quiet)
    plot_result(output_path, basename, title)
    echo_success(quiet=quiet)


def plot_result(path: Path, basename: str, title: str = "", grid: bool = True):
    import pandas as pd

    df = pd.read_csv(path).set_index("ELAPSED")
    df["RSS"] = df["RSS"] / 1024
    ax1, ax2 = df.plot(
        y=["RSS", "CPU"], sharex=True, subplots=True, legend=False, grid=grid
    )
    ax1.set_ylabel("RSS Memory (MB)")
    ax2.set_ylabel("CPU Usage (%)")
    ax2.set_xlabel("Elapsed Time (s)")
    fig = ax1.get_figure()
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path.parent / f"{basename}.png")


if __name__ == "__main__":
    main()
