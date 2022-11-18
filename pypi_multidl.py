"""A tool to download Python packages for later offline installation on many platforms"""

from argparse import ArgumentParser
from collections import namedtuple
import hashlib
from pathlib import Path
import subprocess
import sys
from urllib.parse import urljoin

from packaging.requirements import Requirement
import packaging.utils as u
import requests


__version__ = "1.0.0"

DEFAULT_INDEX_URL = "https://pypi.org/simple/"


Download = namedtuple("Download", "filename, url, hash_algo, hash_digest")


def main():
    args = parse_args()
    requirements = collect_requirements(args)
    index_url = args.index_url or find_index_url()
    dest_dir = Path(args.dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    downloads = find_downloads(requirements, index_url, dest_dir)
    if args.dry_run:
        for download in downloads:
            print(download.filename)
    else:
        for download in downloads:
            download_file(download, dest_dir)


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("-V", "--version", action="store_true",
                        help="Display version and quit.")
    parser.add_argument("-r", "--requirement", metavar="<file>",
                        action="append", dest="reqfiles", default=[],
                        help="File with requirements (\"requirements.txt\")")
    parser.add_argument("requirements", metavar="<requirement>", nargs="*",
                        help="Dependency requirement (eg. foobar==1.2.3)")
    parser.add_argument("-d", "--dest-dir", default=".",
                        help="Which directory to download files to "
                        "(default: current directory)")
    parser.add_argument("-i", "--index-url",
                        help="Which package index to use. "
                        "Defaults \"pip config get global.index-url\" if set, "
                        "or PyPI otherwise.")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Don't download files, just list them.")
    args = parser.parse_args()
    if args.version:
        print(f"pypi-multidl {__version__}")
        sys.exit(0)
    return args


def collect_requirements(args):
    requirements = []
    for reqfile in args.reqfiles:
        with open(reqfile, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                requirements.append(Requirement(line))
    for req in args.requirements:
        requirements.append(Requirement(req))
    return requirements


def find_index_url():
    cmdline = [sys.executable, "-m", "pip",
               "config", "get", "global.index-url"]
    comp = subprocess.run(cmdline, capture_output=True, encoding="utf-8")
    if comp.returncode == 0:
        index_url = comp.stdout.strip()
    else:
        index_url = DEFAULT_INDEX_URL
    if not index_url.endswith("/"):
        index_url += "/"
    return index_url


def find_downloads(requirements, index_url, dest_dir):
    for req in requirements:
        yield from find_project_downloads(req.name, req.specifier,
                                          index_url, dest_dir)


def find_project_downloads(project_name, specifier_set, index_url, dest_dir):
    project_url = index_url + project_name + "/"
    headers = {"Accept": "application/vnd.pypi.simple.v1+json"}
    r = requests.get(project_url, headers=headers)
    project_json = r.json()
    for file_json in project_json["files"]:
        filename = file_json["filename"]
        if filename in [".", ".."] or "/" in filename:
            # Dangerous filenames that should never be used.
            continue
        if file_json.get("yanked", False):
            # We should only mirror yanked files if we also mirror the "yanked"
            # attribute. See: https://peps.python.org/pep-0592/#mirrors
            continue
        version = version_from_filename(filename)
        if not version:
            # Might be a Windows installer or some other lesser used format
            continue
        if version not in specifier_set:
            continue
        url = urljoin(project_url, file_json["url"])
        # Pick first hash we support (if there is any)
        for algo, digest in file_json["hashes"].items():
            algo = algo.lower()
            if algo in hashlib.algorithms_available:
                hash_algo = algo
                hash_digest = digest.lower()
                break
        else:
            hash_algo = None
            hash_digest = None
        yield Download(filename, url, hash_algo, hash_digest)


def version_from_filename(filename):
    try:
        return u.parse_wheel_filename(filename)[1]
    except u.InvalidWheelFilename:
        pass
    except Exception:
        return None
    try:
        return u.parse_sdist_filename(filename)[1]
    except u.InvalidSdistFilename:
        pass
    except Exception:
        # packaging.version.InvalidVersion will be raised if the sdist filename
        # has more than one hyphen (for example when the version does not follow
        # PEP 440)
        return None
    # Known extra cases: Windows installers
    # * foobar-1.2.3.win32.exe
    # * foobar-1.2.3.win32-pyX.Y.exe
    return None


def download_file(download, dest_dir):
    filename, url, hash_algo, hash_digest = download
    with (dest_dir / filename).open("wb") as f:
        print(filename)
        if hash_algo:
            h = hashlib.new(hash_algo)
        r = requests.get(url, stream=True)
        for chunk in r.iter_content(chunk_size=4096):
            f.write(chunk)
            if hash_algo:
                h.update(chunk)
        if hash_algo:
            if h.hexdigest() != hash_digest:
                msg = f"{hash_algo} hash for {filename} did not match!"
                raise Exception(msg)
