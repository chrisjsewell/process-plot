import os
from io import StringIO

from process_plot import profile_process


def test_profile_process():
    """Test running a single iteration against the current process"""
    quit_poll_func = lambda: True  # quit after the first iteration
    output_stream = StringIO()
    profile_process(
        os.getpid(), quit_poll_func=quit_poll_func, output_stream=output_stream
    )
    output_lines = output_stream.getvalue().rstrip().splitlines()
    assert len(output_lines) == 2
    assert output_lines[0] == "PID,DATE,TIME,ELAPSED,CPU,MEM,RSS,VSIZE,CMD"
    assert output_lines[1].startswith(str(os.getpid()))
