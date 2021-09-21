"""Code for profiling a process."""
import locale
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Callable, Optional, Pattern, TextIO, Union

ENCODING = locale.getdefaultlocale()[1]

PS_FIELDS = [
    "pid",
    "ppid",
    "etime",
    "%cpu",
    "%mem",
    "rss",
    "vsz",
]


def _call_command(command: str) -> str:
    """Call a command."""
    ps = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, text=True, encoding=ENCODING
    )
    stdout, _ = ps.communicate()
    return stdout


def profile_process(
    process: Union[int, Pattern],
    *,
    poll_interval: Union[int, float] = 1,
    quit_if_none: bool = True,
    quit_poll_func: Optional[Callable[[], bool]] = None,
    ssh_id: Optional[str] = None,
    debug_level: int = 0,
    debug_stream: TextIO = sys.stderr,
    output_stream: Optional[TextIO] = None,
    flush_output: bool = False,
    headers: bool = True,
    output_separator: str = ",",
    align_output=False,
    show_command: bool = False,
    caller: Callable[[str], str] = _call_command,
):
    """Poll process every `poll_interval` seconds and write system resource usage.

    :param process: either a PID or a regex for the process command

    :param poll_interval: Poll every n seconds
    :param quit_if_none: Quit polling if no records were found for the process
    :param quit_poll_func: Call after each poll loop and quit if returns ``True``
    :param ssh_id: Call ps over SSH ``ssh ssh_id ps ...``
    :param debug_level: Between 0 and 5
    :param debug_stream: Stream to debug outputs to

    output options:

    :param output_stream: Stream to write outputs to
    :param flush_output: Flush the output stream buffer after every write
    :param headers: Write field headers to output stream
    :param output_separator: Separator for fields
    :param align_output: align fields when writing to output stream
    :param show_command: record the command string

    """
    if align_output:
        ncolw = 5
        mcolw = 8
        wcolw = 11
        right_align_narrow = "%d" % ncolw
        right_align = "%d" % mcolw
        right_align_wide = "%d" % wcolw
    else:
        ncolw = 0
        mcolw = 0
        wcolw = 0
        right_align_narrow = ""
        right_align = ""
        right_align_wide = ""

    result_fields = [
        "%%(pid)%ss" % right_align,
        "%%(poll_date)%ss" % right_align_wide,
        "%%(poll_time)%ss" % right_align,
        "%%(etime)%ss" % right_align_wide,
        "%%(%%cpu)%ss" % right_align_narrow,
        "%%(%%mem)%ss" % right_align_narrow,
        "%%(rss)%ss" % right_align,
        "%%(vsz)%ss" % right_align,
        "%%(command)%ss" % right_align,
    ]

    if debug_level >= 1:
        result_fields.insert(0, "%%(ppid)%ss" % right_align)

    if show_command:
        result_fields.append("%(command)s")

    col_headers = [
        "PID".rjust(mcolw),
        "DATE".rjust(wcolw),
        "TIME".rjust(mcolw),
        "ELAPSED".rjust(wcolw),
        "CPU".rjust(ncolw),
        "MEM".rjust(ncolw),
        "RSS".rjust(mcolw),
        "VSIZE".rjust(mcolw),
        "CMD".rjust(mcolw),
    ]

    if debug_level >= 1:
        col_headers.insert(0, "PPID".rjust(mcolw))

    if show_command:
        col_headers.append("COMMAND")

    if headers and output_stream is not None:
        output_stream.write(output_separator.join(col_headers) + "\n")
        if flush_output:
            output_stream.flush()

    while True:
        pinfoset = poll_process(
            process=process,
            debug_stream=debug_stream,
            ssh_id=ssh_id,
            debug_level=debug_level,
            caller=caller,
        )

        if debug_level > 3:
            debug_stream.write(str(pinfoset) + "\n")
        if output_stream is not None:
            for pinfo in pinfoset:
                result = output_separator.join(result_fields) % pinfo
                output_stream.write(result + "\n")
                if flush_output:
                    output_stream.flush()

        # break conditions
        if quit_poll_func is not None and quit_poll_func():
            break
        if len(pinfoset) == 0 and quit_if_none:
            break

        time.sleep(poll_interval)


def poll_process(
    process: Union[int, Pattern],
    *,
    debug_stream: TextIO,
    ssh_id: Optional[str] = None,
    debug_level=0,
    caller: Callable[[str], str] = _call_command,
):
    """Calls ps, and extracts rows matching process."""
    if isinstance(process, int):
        should_record = lambda fields: int(fields[0]) == process
    elif isinstance(process, Pattern):
        should_record = lambda fields: process.search(fields[-1])
    else:
        raise TypeError(f"Process must be a PID or Command regex: {type(process)}")

    # count up all the fields so far
    # we are relying on all these fields NOT to contain
    # any space; we'll use this fact to parse out columns
    non_command_cols = len(PS_FIELDS)

    # add the command fields = command + args
    # this field will probably have spaces: we'll take this
    # into account
    ps_fields = PS_FIELDS + ["command"]

    ps_args = ['-o %s=""' % s for s in ps_fields]
    ps_invocation = "ps -A %s" % (" ".join(ps_args))

    if ssh_id is not None:
        ssh_val = f"ssh {ssh_id} "
        ps_invocation = ssh_val + ps_invocation

    if debug_level >= 2:
        debug_stream.write("\n" + ps_invocation + "\n")

    poll_time = datetime.now()
    stdout = caller(ps_invocation)
    stdout = stdout.strip()

    if debug_level >= 5:
        debug_stream.write(stdout + "\n")

    records = []
    for row in stdout.splitlines():
        if not row:
            continue
        fields = re.split(r"\s+", row.strip(), non_command_cols)
        if debug_level >= 4:
            debug_stream.write(str(fields) + "\n")
        if len(fields) != 8:
            debug_stream.write(
                "Skipping sample: found only %d columns: %s" % (len(fields), fields)
            )
            continue

        if should_record(fields):
            pinfo = {}
            for idx, field in enumerate(fields):
                pinfo[ps_fields[idx]] = field
            pinfo["poll_datetime"] = poll_time.isoformat(" ")
            pinfo["poll_date"] = poll_time.strftime("%Y-%m-%d")
            pinfo["poll_time"] = poll_time.strftime("%H:%M:%S")
            records.append(pinfo)
            if debug_level >= 3:
                debug_stream.write(str(pinfo) + "\n")
    return records
