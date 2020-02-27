#!/usr/bin/env python3

"""
Documentation generator

Generates the documentation for every Git branch and commits it.
Gracefully handles conflicting commits.
"""

import contextlib
import glob
import os
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

REMOTE = "origin"
GIT_CONFIG = {"protocol.version": "2",
              "user.email": "<>",
              "user.name": "Github Actions"}
COMMIT_MESSAGE = "Generate documentation"
DOCUMENTATION_SRC = "DOCUMENTATION.md"
TARGET_DIR = "beta"
SHIFT_HEADING = 1
TOOLS_PATH = os.path.dirname(__file__)
TEMPLATE_PATH = os.path.join(TOOLS_PATH, "template.html")
FILTER_EXE = os.path.join(TOOLS_PATH, "filter.py")
POSTPROCESSOR_EXE = os.path.join(TOOLS_PATH, "postprocessor.py")
PANDOC_EXE = "pandoc"
PANDOC_DOWNLOAD = ("https://github.com/jgm/pandoc/releases/download/"
                   "2.9.2/pandoc-2.9.2-1-amd64.deb")


def convert_doc(src_path, to_path, branch, branches):
    subprocess.run([
        PANDOC_EXE,
        "--from=gfm",
        "--to=html5",
        os.path.abspath(src_path),
        "--toc",
        "--template=%s" % os.path.basename(TEMPLATE_PATH),
        "--output=%s" % os.path.abspath(to_path),
        "--section-divs",
        "--shift-heading-level-by=%d" % SHIFT_HEADING,
        "--toc-depth=4",
        "--filter=%s" % os.path.abspath(FILTER_EXE),
        "--variable=branch=%s" % branch,
        *["--variable=branches=%s" % b for b in branches]],
        check=True, cwd=os.path.dirname(TEMPLATE_PATH))
    with open(to_path, "rb+") as f:
        data = subprocess.run([POSTPROCESSOR_EXE], input=f.read(),
                              stdout=subprocess.PIPE, check=True).stdout
        f.seek(0)
        f.truncate()
        f.write(data)


def install_dependencies():
    subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4"],
                   check=True)
    with TemporaryDirectory() as temp:
        subprocess.run(["curl", "--location", "--output", "pandoc.deb",
                        PANDOC_DOWNLOAD], check=True, cwd=temp)
        subprocess.run(["sudo", "apt", "install", "--assume-yes",
                        "./pandoc.deb"], check=True, cwd=temp)


def natural_sort_key(s):
    # https://stackoverflow.com/a/16090640
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", s)]


def run_git(*args):
    config_args = []
    for key, value in GIT_CONFIG.items():
        config_args.extend(["-c", "%s=%s" % (key, value)])
    output = subprocess.run(["git", *config_args, *args],
                            stdout=subprocess.PIPE, check=True,
                            universal_newlines=True).stdout
    return tuple(filter(None, output.split("\n")))


def checkout(branch):
    run_git("checkout", "--progress", "--force", "-B", branch,
            "refs/remotes/%s/%s" % (REMOTE, branch))


def run_git_fetch_and_restart_if_changed(remote_commits, target_branch):
    run_git("fetch", "--no-tags", "--prune", "--progress",
            "--no-recurse-submodules", "--depth=1", REMOTE,
            "+refs/heads/*:refs/remotes/%s/*" % REMOTE)
    if remote_commits != run_git("rev-parse", "--remotes=%s" % REMOTE):
        checkout(target_branch)
        print("Remote changed, restarting", file=sys.stderr)
        os.execv(__file__, sys.argv)


def main():
    install_dependencies()
    target_branch, = run_git("rev-parse", "--abbrev-ref", "HEAD")
    remote_commits = run_git("rev-parse", "--remotes=%s" % REMOTE)
    run_git_fetch_and_restart_if_changed(remote_commits, target_branch)
    branches = [ref[len("refs/remotes/%s/" % REMOTE):] for ref in run_git(
        "rev-parse", "--symbolic-full-name", "--remotes=%s" % REMOTE)]
    branches.sort(key=natural_sort_key, reverse=True)
    os.makedirs(TARGET_DIR, exist_ok=True)
    for path in glob.iglob(os.path.join(TARGET_DIR, "*.html")):
        run_git("rm", "--", path)
    with TemporaryDirectory() as temp:
        branch_docs = {}
        for branch in branches:
            checkout(branch)
            if os.path.exists(DOCUMENTATION_SRC):
                branch_docs[branch] = os.path.join(temp, "%s.md" % branch)
                shutil.copy(DOCUMENTATION_SRC, branch_docs[branch])
        checkout(target_branch)
        for branch, src_path in branch_docs.items():
            to_path = os.path.join(TARGET_DIR, "%s.html" % branch)
            convert_doc(src_path, to_path, branch, branches)
            run_git("add", "--", to_path)
    with contextlib.suppress(subprocess.CalledProcessError):
        run_git("diff", "--cached", "--quiet")
        print("No changes", file=sys.stderr)
        return
    run_git("commit", "-m", COMMIT_MESSAGE)
    try:
        run_git("push", REMOTE, "HEAD:%s" % target_branch)
    except subprocess.CalledProcessError:
        run_git_fetch_and_restart_if_changed(remote_commits, target_branch)
        raise


if __name__ == "__main__":
    main()
