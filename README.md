# pypi-multidl

This tool was made to make it easier to download Python packages from one
computer and install them on other computers that are not connected to the
internet (and may run different OSes). This project is not officially endorsed
by anyone (for example, the maintainers of PyPI or `pip`).

Its input is a list of dependency specifications (package name and versions),
and the output is a destination directory populated with all the sdists and
wheels from PyPI that matches the specifications. This directory can then be
used offline with `pip` using the `-f/--find-links` option as a lightweight PyPI
mirror.

This tool does no dependency resolution. You are expected to use `pip-compile`
from the `pip-tools` package (or an equivalent tool) to find all the
dependencies of the dependencies, and pinning down all the exact version.
`pip-compile` can be used to process a `setup.py`/`setup.cfg`/`pyproject.toml`
file into a `requirements.txt` to be used by `pypi-multidl`.

## Example Usage: Download Dependencies for a Project

Assume you have a Python project you want to be able to install offline, and
that its dependencies aren't pinned to specific version. Then begin by compiling
the list of transitive pinned dependencies:

    cd some-project
	pip-compile setup.py # ...or setup.cfg, or pyproject.toml

Now you have a `requriements.txt` file. Continue to download all the
dependencies to the `deps/` directory:

    pypi-multidl -r requirements.txt -d deps/

The project can then be installed offline like this:

    pip install --no-index --find-links deps/ .

## Example Usage: List all Distribution Packages Available for a Project

The `pypi-multidl` tool can also be given dependency specifications directly on
the command line:

    pypi-multidl --dry-run 'appdirs' 'sphinx >=4.0.0, <5.0.0'

## Limitations

The approach used by pypi-multidl does not work in the general case. The
dependency resolution step `pip-compile` is actually platform-specific. A
package can have different dependencies on different platforms. For example,
Sphinx depends on `colorama`, but only on Windows. What you get from
`pip-compile` is the set of dependencies specific for the plaform that
`pip-compile` was run on. If no packages have platform-specific dependencies,
then everything should work. Currently, `pypi-multidl` does not make any attempt
to validate that the `requirements.txt` is platform-independent.

This tool currently only supports the PEP 691 JSON API via the simple endpoint.

Yanked files are never downloaded, not even when pinned using `==` (see PEP
592).

Requires-python and other metadata is not downloaded.

This tool only produces a flat directory of files, not a "simple" style
directory tree to be served by a web server.

## Comparison to other tools

The `pip download` command only supports downloading packages for one system at
a time. It also only downloads an sdist or a wheel, but never both.

The `pip-downloader` tool solves the same problem as `pypi-multi`, but is
implemented in a different way. It performs dependency resolution using `pip`
and uses its internal API. It needs to continually be updated whenever `pip`
changes in order not to break.

## Usage with a Local Cache

When experimenting with downloading from PyPI it is recommended to setup a local
PyPI cache. The `devpi` tool is easy to get started with:

    pip install devpi
	devpi-init
	devpi-server  # Runs an index on http://localhost:3141/root/pypi/+simple/

Leave that running in a terminal (or add it to your init system) and add this to
your pip config:

    [global]
    index-url = http://localhost:3141/root/pypi/+simple/

`pip`, `pip-compile` and `pypi-multidl` will then automatically use the cache.
Note that you also need to pass `--no-emit-options` to `pip-compile` so that it
doen't add an `--index-url` line to the `requirements.txt` (which `pypi-multidl`
doesn't understand).
