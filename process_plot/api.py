"""Code for profiling a process."""

from collections.abc import Sequence
import os
from os import PathLike
import time
from typing import Optional, TextIO, Union

import matplotlib.pyplot as plt
import pandas as pd
import psutil

POSIX = os.name == "posix"
WINDOWS = os.name == "nt"

COLUMNS_DESCRIPT = (
    ("type", "main or child"),
    ("pid", "Process ID"),
    ("elapsed_secs", "Cumulative time since the process was created."),
    ("cpu_time_user_secs", "Time spent executing in user mode"),
    ("cpu_time_sys_secs", "Time spent executing in kernel mode"),
    (
        "cpu_percent",
        "Percentage of process times to system CPU times elapsed since last call",
    ),
    ("threads_num", "Number of threads currently used"),
    ("memory_rss_bytes", "Resident Set Size; the non-swapped physical memory used"),
    ("memory_vms_bytes", "Virtual Memory Size: the virtual memory used"),
    ("files_num", "Number of file descriptors (POSIX) or handles (Windows) used"),
)


def profile_process(
    pid: int,
    *,
    poll_interval: Union[int, float] = 1,
    max_iterations: Optional[int] = None,
    output_stream: Optional[TextIO] = None,
    flush_output: bool = False,
    headers: bool = True,
    output_separator: str = ",",
    output_files_num: bool = False,
    child_processes: bool = True,
) -> None:
    """Poll process every `poll_interval` seconds and write system resource usage.

    :param process: either a PID or a regex for the process command
    :param poll_interval: Poll every n seconds
    :param max_intervals: If not None, stop after this many intervals
    :param output_stream: Stream to write outputs to
    :param flush_output: Flush the output stream buffer after every write
    :param headers: Write field headers to output stream
    :param output_separator: Separator for fields
    :param output_files_num:
        Output number of file descriptors (unix) or handles (windows) used by process.
        Note, this is a more expensive operation than others.

    """
    col_headers = [name for name, _ in COLUMNS_DESCRIPT]
    if output_files_num:
        assert POSIX or WINDOWS, "output_files_num only supported on posix and windows"
    else:
        col_headers.remove("files_num")

    if headers and output_stream is not None:
        output_stream.write(output_separator.join(col_headers) + "\n")
        if flush_output:
            output_stream.flush()

    iteration = 0
    proc = psutil.Process(pid)
    while True:
        iteration += 1

        elapsed_time = time.time() - proc.create_time()
        try:
            if not proc.is_running() or proc.status() == "zombie":
                raise psutil.NoSuchProcess(proc.pid)
            attrs = ["pid", "cpu_times", "cpu_percent", "num_threads", "memory_info"]
            data = proc.as_dict(attrs=attrs)
            data["is_main"] = True
            if child_processes:
                child_data = [
                    p.as_dict(attrs=attrs) for p in proc.children(recursive=True)
                ]
            else:
                child_data = []
        except psutil.NoSuchProcess:
            break
        if output_files_num:
            try:
                if POSIX:
                    data["num_files"] = proc.num_fds()
                elif WINDOWS:
                    data["num_files"] = proc.num_handles()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # this was happening on linux with num_fds call
                pass

        if data is None or data["cpu_percent"] is None:
            break

        if output_stream is not None:
            for item in [data, *child_data]:
                results = {
                    "pid": item["pid"],
                    "type": "main" if item.get("is_main") else "child",
                    "elapsed_secs": elapsed_time,
                    "cpu_time_user_secs": item["cpu_times"].user,
                    "cpu_time_sys_secs": item["cpu_times"].system,
                    "cpu_percent": item["cpu_percent"],
                    "threads_num": item["num_threads"],
                    "memory_rss_bytes": item["memory_info"].rss,
                    "memory_vms_bytes": item["memory_info"].vms,
                    "files_num": item.get("num_files", "-"),
                }
                output_stream.write(
                    output_separator.join(str(results[name]) for name in col_headers)
                    + "\n"
                )
            if flush_output:
                output_stream.flush()

        if max_iterations is not None and iteration >= max_iterations:
            raise TimeoutError("Max iterations reached")

        time.sleep(poll_interval)


PLOT_YLABELS = (
    ("memory_rss", "RSS Memory (MB)"),
    ("memory_vms", "VMS Memory (MB)"),
    ("cpu_percent", "CPU Usage (%)"),
    ("cpu_time_user", "CPU Time, user (s)"),
    ("cpu_time_sys", "CPU Time, system (s)"),
    ("threads_num", "# threads"),
    ("files_num", "# files"),
)

_convert_column_names = {
    "cpu_time_user_secs": "cpu_time_user",
    "cpu_time_sys_secs": "cpu_time_sys",
}


def plot_result(
    inpath: PathLike,
    outpath: PathLike,
    *,
    columns: Sequence[str] = ("memory_rss", "cpu_percent"),
    stack_processes: bool = False,
    title: str = "",
    grid: bool = True,
    width_cm: Optional[float] = None,
    height_cm: Optional[float] = None,
) -> bool:
    """Plot output stream CSV.

    :returns: True if successful, False if no data to plot
    """
    df = pd.read_csv(inpath, na_values="-").set_index("elapsed_secs")
    if not df.shape[0]:
        return False

    df["memory_rss"] = df["memory_rss_bytes"] / (1024 * 1024)
    df["memory_vms"] = df["memory_vms_bytes"] / (1024 * 1024)
    df["Process"] = df.apply(
        lambda row: f"{row['type'].capitalize()} ({row['pid']})", axis=1
    )
    # TODO sort so main process is always on top
    df.rename(_convert_column_names, axis=1, inplace=True)

    fig, axes = plt.subplots(nrows=len(columns), sharex=True)

    for i, column in enumerate(columns):
        data = df.pivot(columns="Process", values=column)
        if stack_processes:
            data.sort_values(by=data.index[-1], axis=1, ascending=False).plot.area(
                ax=axes[i], grid=grid, stacked=True, legend=False
            )
        else:
            data.sum(axis=1).plot(ax=axes[i], grid=grid, legend=False)
        axes[i].set_ylabel(dict(PLOT_YLABELS)[column])

    axes[-1].set_xlabel("Elapsed Time (s)")

    if stack_processes:
        lines, labels = axes[0].get_legend_handles_labels()
        fig.legend(
            lines, labels, loc="center left", bbox_to_anchor=(1, 0.5), title="Process"
        )

    if title:
        fig.suptitle(title)
    if width_cm:
        fig.set_figwidth(width_cm * 0.393701)
    if height_cm:
        fig.set_figheight(height_cm * 0.393701)
    fig.align_ylabels()
    fig.tight_layout()
    fig.savefig(outpath, bbox_inches="tight")
    return True
