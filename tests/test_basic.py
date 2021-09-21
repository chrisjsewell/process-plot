import os
from io import StringIO

import pytest
from click.testing import CliRunner

from process_plot.api import COLUMNS_DESCRIPT, PLOT_YLABELS, profile_process
from process_plot.cli import cmd_exec


def test_profile_process():
    """Test running a single iteration against the current process"""
    output_stream = StringIO()
    with pytest.raises(TimeoutError):
        profile_process(
            os.getpid(),
            max_iterations=2,
            output_separator=",",
            output_stream=output_stream,
            output_files_num=True,
        )
    output_lines = output_stream.getvalue().rstrip().splitlines()
    assert len(output_lines) == 3
    assert output_lines[0] == ",".join(dict(COLUMNS_DESCRIPT))


def test_cli_help():
    """Test the help output"""
    runner = CliRunner()
    result = runner.invoke(cmd_exec, ["--help"])
    assert result.exit_code == 0


def test_cli_exec(tmp_path):
    """Test the command line interface"""
    runner = CliRunner()
    result = runner.invoke(
        cmd_exec,
        [
            "--outfolder",
            str(tmp_path),
            "--basename",
            "output",
            "--plot-cols",
            ",".join(dict(PLOT_YLABELS)),
            "-sw",
            "10",
            "-sh",
            "50",
            "echo hi",
        ],
    )
    print(result.output)
    print(result.exception)
    assert result.exit_code == 0
    assert os.path.exists(os.path.join(str(tmp_path), "output.csv"))
    assert os.path.exists(os.path.join(str(tmp_path), "output.png"))
