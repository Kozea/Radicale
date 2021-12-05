#!/usr/bin/env python3

"""
Documentation generator

Generates the documentation for every Git branch and commits it.
Gracefully handles conflicting commits.
"""

import contextlib
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from tempfile import TemporaryDirectory

REMOTE = "origin"
GIT_CONFIG = {"protocol.version": "2",
              "user.email": "<>",
              "user.name": "Github Actions"}
COMMIT_MESSAGE = "Generate documentation"
DOCUMENTATION_SRC = "DOCUMENTATION.md"
REDIRECT_CONFIG_PATH = "redirect.json"
SHIFT_HEADING = 1
TOC_DEPTH = 3
TOOLS_PATH = os.path.dirname(__file__)
REDIRECT_TEMPLATE_PATH = os.path.join(TOOLS_PATH, "template-redirect.html")
TEMPLATE_PATH = os.path.join(TOOLS_PATH, "template.html")
FILTER_EXE = os.path.join(TOOLS_PATH, "filter.py")
POSTPROCESSOR_EXE = os.path.join(TOOLS_PATH, "postprocessor.py")
PANDOC_EXE = "pandoc"
PANDOC_DOWNLOAD = ("https://github.com/jgm/pandoc/releases/download/"
                   "2.16.2/pandoc-2.16.2-1-amd64.deb")
PANDOC_SHA256 = ("2001d93463c003f8fee6c36b1bfeccd5"
                 "51ab6e35370b24f74f457e3f6dffb8b7")
BRANCH_ORDERING = [  # Format: (REGEX, ORDER, DEFAULT)
    (r"v?\d+(?:\.\d+)*(?:\.x)*", 0, True),
    (r".*", 1, False)]


def escape_js(s):
    return s.translate(str.maketrans({
        "\t": "\\t",
        "\v": "\\v",
        "\0": "\\0",
        "\b": "\\b",
        "\f": "\\f",
        "\n": "\\n",
        "\r": "\\r",
        "\'": "\\'",
        "\"": "\\\"",
        "\\": "\\\\"}))


def convert_doc(src_path, to_path, branch, branches):
    raw_html = subprocess.run([
        PANDOC_EXE,
        "--sandbox",
        "--from=gfm",
        "--to=html5",
        os.path.abspath(src_path),
        "--toc",
        "--template=%s" % os.path.basename(TEMPLATE_PATH),
        "--metadata=document-css=false",
        "--section-divs",
        "--shift-heading-level-by=%d" % SHIFT_HEADING,
        "--toc-depth=%d" % (TOC_DEPTH+SHIFT_HEADING),
        "--filter=%s" % os.path.abspath(FILTER_EXE),
        "--variable=branch_html=%s" % html.escape(branch),
        "--variable=branch_js=%s" % escape_js(branch),
        *("--variable=branches_js=%s" % escape_js(b) for b in branches)],
        cwd=os.path.dirname(TEMPLATE_PATH),
        stdout=subprocess.PIPE, check=True).stdout
    raw_html = subprocess.run([POSTPROCESSOR_EXE], input=raw_html,
                              stdout=subprocess.PIPE, check=True).stdout
    with open(to_path, "wb") as f:
        f.write(raw_html)


def install_dependencies():
    subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4"],
                   check=True)
    with TemporaryDirectory() as temp:
        subprocess.run(["curl", "--location", "--output", "pandoc.deb",
                        PANDOC_DOWNLOAD], check=True, cwd=temp)
        subprocess.run(["sha256sum", "--check", "--strict", "--quiet"],
                       input="%s *pandoc.deb" % PANDOC_SHA256, text=True,
                       check=True, cwd=temp)
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
        for branch, src_path in branch_docs.items():
            to_path = "%s.html" % branch
            convert_doc(src_path, to_path, branch, branches)
            run_git("add", "--", to_path)
    try:
        with open(REDIRECT_CONFIG_PATH) as f:
            redirect_config = json.load(f)
    except FileNotFoundError:
        redirect_config = {}
    with open(REDIRECT_TEMPLATE_PATH) as f:
        redirect_template = f.read()
    for source, target in redirect_config.items():
        if target == ":DEFAULT_BRANCH:":
            if default_branch is None:
                raise RuntimeError("no default branch")
            target = default_branch
        source_path = "%s.html" % str(source)
        target_url = urllib.parse.quote_plus("%s.html" % str(target))
        with open(source_path, "w") as f:
            f.write(redirect_template.format(target=target_url))
        run_git("add", "--", source_path)
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
