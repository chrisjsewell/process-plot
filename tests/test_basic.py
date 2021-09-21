import os
from io import StringIO

from click.testing import CliRunner

from process_plot import profile_process
from process_plot.cli import cmd_exec


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


def test_cli_help():
    """Test the help output"""
    runner = CliRunner()
    result = runner.invoke(cmd_exec, ["--help"])
    assert result.exit_code == 0


def test_cli_exec(tmp_path):
    """Test the command line interface"""
    runner = CliRunner()
    result = runner.invoke(
        cmd_exec, ["--basepath", str(tmp_path), "--basename", "output", "echo hi"]
    )
    assert result.exit_code == 0
    assert os.path.exists(os.path.join(str(tmp_path), "output.csv"))
    assert os.path.exists(os.path.join(str(tmp_path), "output.png"))
