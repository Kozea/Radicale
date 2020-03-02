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
SHIFT_HEADING = 1
TOOLS_PATH = os.path.dirname(__file__)
TEMPLATE_INDEX_PATH = os.path.join(TOOLS_PATH, "template-index.html")
TEMPLATE_PATH = os.path.join(TOOLS_PATH, "template.html")
FILTER_EXE = os.path.join(TOOLS_PATH, "filter.py")
POSTPROCESSOR_EXE = os.path.join(TOOLS_PATH, "postprocessor.py")
PANDOC_EXE = "pandoc"
PANDOC_DOWNLOAD = ("https://github.com/jgm/pandoc/releases/download/"
                   "2.9.2/pandoc-2.9.2-1-amd64.deb")
BRANCH_ORDERING = [  # Format: (REGEX, ORDER, DEFAULT)
    (r'v?\d+(?:\.\d+)*(?:\.x)*', 0, True),
    (r'.*', 1, False)]


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
        *("--variable=branches=%s" % b for b in branches)],
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


def sort_branches(branches):
    branches = list(branches)
    order_least = min(order for _, order, _ in BRANCH_ORDERING) - 1
    for i, branch in enumerate(branches):
        for regex, order, default in BRANCH_ORDERING:
            if re.fullmatch(regex, branch):
                branches[i] = (order, natural_sort_key(branch), default,
                               branch)
                break
        else:
            branches[i] = (order_least, natural_sort_key(branch), False,
                           branch)
    branches.sort()
    default_branch = [
        None, *(branch for _, _, _, branch in branches),
        *(branch for _, _, default, branch in branches if default)][-1]
    return [branch for _, _, _, branch in branches], default_branch


def pretty_branch_name(branch):
    while branch.endswith(".x"):
        branch = branch[:-len(".x")]
    return branch


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


def make_index_html(branch):
    with open(TEMPLATE_INDEX_PATH) as f:
        return f.read().format(branch=branch)


def main():
    if os.environ.get("GITHUB_ACTIONS", "") == "true":
        install_dependencies()
    target_branch, = run_git("rev-parse", "--abbrev-ref", "HEAD")
    remote_commits = run_git("rev-parse", "--remotes=%s" % REMOTE)
    run_git_fetch_and_restart_if_changed(remote_commits, target_branch)
    branches = [ref[len("refs/remotes/%s/" % REMOTE):] for ref in run_git(
        "rev-parse", "--symbolic-full-name", "--remotes=%s" % REMOTE)]
    with TemporaryDirectory() as temp:
        branch_docs = {}
        for branch in branches[:]:
            checkout(branch)
            if os.path.exists(DOCUMENTATION_SRC):
                branch_docs[branch] = os.path.join(temp, "%s.md" % branch)
                shutil.copy(DOCUMENTATION_SRC, branch_docs[branch])
            else:
                branches.remove(branch)
        checkout(target_branch)
        for path in glob.iglob("*.html"):
            run_git("rm", "--", path)
        branches, default_branch = sort_branches(branches)
        branches_pretty = [pretty_branch_name(b) for b in branches]
        default_branch_pretty = pretty_branch_name(default_branch)
        for branch, src_path in branch_docs.items():
            branch_pretty = pretty_branch_name(branch)
            to_path = "%s.html" % branch_pretty
            convert_doc(src_path, to_path, branch_pretty, branches_pretty)
            run_git("add", "--", to_path)
    if default_branch_pretty:
        index_path = "index.html"
        with open(index_path, "w") as f:
            f.write(make_index_html(default_branch_pretty))
        run_git("add", "--", index_path)
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
