"""Code for profiling a process."""
import os
import time
from os import PathLike
from typing import Optional, Sequence, TextIO, Union

import psutil

POSIX = os.name == "posix"
WINDOWS = os.name == "nt"

COLUMNS_DESCRIPT = (
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
            data = proc.as_dict(
                attrs=["cpu_times", "cpu_percent", "num_threads", "memory_info"]
            )
            if output_files_num:
                # test if on windows
                if POSIX:
                    data["num_files"] = proc.num_fds()
                elif WINDOWS:
                    data["num_files"] = proc.num_handles()
        except psutil.NoSuchProcess:
            break

        if data is None or data["cpu_percent"] is None:
            break

        results = {
            "elapsed_secs": elapsed_time,
            "cpu_time_user_secs": data["cpu_times"].user,
            "cpu_time_sys_secs": data["cpu_times"].system,
            "cpu_percent": data["cpu_percent"],
            "threads_num": data["num_threads"],
            "memory_rss_bytes": data["memory_info"].rss,
            "memory_vms_bytes": data["memory_info"].vms,
            "files_num": data.get("num_files", None),
        }

        if output_stream is not None:
            result = output_separator.join(str(results[name]) for name in col_headers)
            output_stream.write(result + "\n")
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


def plot_result(
    inpath: PathLike,
    outpath: PathLike,
    *,
    columns: Sequence[str] = ("memory_rss", "cpu_percent"),
    title: str = "",
    grid: bool = True,
) -> None:
    """Plot output stream CSV."""
    import pandas as pd

    convert = {
        "cpu_time_user": "cpu_time_user_secs",
        "cpu_time_sys": "cpu_time_sys_secs",
    }
    columns = [convert.get(col, col) for col in columns]

    df = pd.read_csv(inpath).set_index("elapsed_secs")
    df["memory_rss"] = df["memory_rss_bytes"] / (1024 * 1024)
    df["memory_vms"] = df["memory_vms_bytes"] / (1024 * 1024)
    axes = df.plot(y=list(columns), sharex=True, subplots=True, legend=False, grid=grid)
    axes[-1].set_xlabel("Elapsed Time (s)")
    for ax, column in zip(axes, columns):
        ax.set_ylabel(dict(PLOT_YLABELS)[column])
    fig = axes[0].get_figure()
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(outpath)
