# process-plot

[![Build Status][ci-badge]][ci-link]
[![PyPI version][pypi-badge]][pypi-link]
<!-- [![codecov.io][cov-badge]][cov-link] -->

Create plots of memory and CPU usage for a process.

This is a wrapper around the [ps](https://man7.org/linux/man-pages/man1/ps.1.html) command,
which polls it at a set interval.

## Usage

Install the package with [pip](https://pip.pypa.io) or [pipx](https://github.com/pypa/pipx):

```console
$ pipx install process-plot
```

then run:

```console
$ pplot exec -i 0.1 "sleep 1"
PPLOT INFO: Output files will be written to: /user/pplot_out, with basename: 20210921024614
PPLOT INFO: Running process
PPLOT INFO: Total run time: 0 hour(s), 00 minute(s), 01.175246 second(s)
PPLOT INFO: Plotting results
PPLOT SUCCESS!
```

You will then find the output files in `/user/pplot_out`, with a plot for the process like:

![example plot](example.png)

Additional options are available:

```console
$ pplot exec --help
Usage: pplot exec [OPTIONS] COMMAND

  Execute a command and profile it.

Options:
  -i, --interval FLOAT            Interval in seconds
  -c, --command-output [hide|screen|file]
                                  Mode for stdout/stderr of command  [default:
                                  file]
  -p, --basepath TEXT             Basepath for output files
  -n, --basename TEXT             Basename for output files (defaults to
                                  datetime)
  -v, --verbose                   Increase verbosity  [x>=0]
  -q, --quiet                     Quiet mode
  --help                          Show this message and exit.
```

## Acknowledgements

Initially adapted from: <https://github.com/jeetsukumaran/Syrupy>

[ci-badge]: https://github.com/chrisjsewell/process-plot/workflows/CI/badge.svg?branch=main
[ci-link]: https://github.com/chrisjsewell/process-plot/actions?query=workflow%3ACI+branch%3Amain+event%3Apush
[cov-badge]: https://codecov.io/gh/chrisjsewell/process-plot/branch/main/graph/badge.svg
[cov-link]: https://codecov.io/gh/chrisjsewell/process-plot
[pypi-badge]: https://img.shields.io/pypi/v/process-plot.svg
[pypi-link]: https://pypi.org/project/process-plot
