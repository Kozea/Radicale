#!/usr/bin/env python3

"""
Documentation generator

Generates the documentation for every Git branch (excluding starting with "trial/" and commits it.
Gracefully handles conflicting commits.
"""

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile

from bs4 import BeautifulSoup

REMOTE = "origin"
GIT_CONFIG = {"protocol.version": "2",
              "user.email": "<>",
              "user.name": "Github Actions"}
COMMIT_MESSAGE = "Generate documentation"
DOCUMENTATION_SRC = "DOCUMENTATION.md"
TOC_DEPTH = 4
TOOLS_PATH = os.path.dirname(__file__)
TEMPLATE_PATH = os.path.join(TOOLS_PATH, "template.html")
PANDOC_EXE = "pandoc"
BRANCH_ORDERING = [  # Format: (REGEX, ORDER, DEFAULT)
    (r"v?\d+(?:\.\d+)*(?:\.x)*", 0, True),
    (r".*", 1, False)]
PROG = "documentation-generator"
RELEASE_BRANCH_PREFIXES = (f"{REMOTE}/master", f"{REMOTE}/v")
DOCS_MD_SOURCE_PATHSPEC = "docs/"
DOCS_MD_DIR_TEMPLATE = "md/{release}/"


class MDFile(Path):
    MATCHER = re.compile(r"^\d\d_(.+).md$").match

    def __init__(self, path, html_dir):
        super(MDFile, self).__init__(path)
        self.html_dir = html_dir

    def validate(self):
        match = self.MATCHER(self.name)
        if match:
            name = match[1]
            self.html_path = self.html_dir / f"{name}.html"
            return True
        return False

    @lru_cache
    def get_headings(self):
        md_lines = self.read_text().splitlines()
        headings = {line[3:].strip() for line in md_lines if line.startswith("## ")}  # remove "## "
        return headings

    @classmethod
    def validate_combined_files(cls, md_files):
        headings = defaultdict(list)
        for md_file in md_files:
            for heading in md_file.get_headings():
                headings[heading].append(md_file)
        failed = False
        for heading, files in headings.items():
            if len(files) > 1:
                print(f"""[ERROR] Top-level heading "## {heading}" is used more than once. Fix {[f.name for f in files]}.""")
                failed = True
        if failed:
            raise RuntimeError("[ERROR] validate_combined_files failed - please fix errors to process")


def run_pandoc(src_paths, template_path, metadata_file):
    cwd = os.path.dirname(template_path)
    args = [
        PANDOC_EXE,
        "--sandbox",
        "--from=gfm",
        "--to=html5",
        "--toc",
        "--template=%s" % os.path.basename(template_path),
        "--section-divs",
        "--toc-depth=%d" % TOC_DEPTH,
        "--metadata-file=%s" % os.path.abspath(metadata_file.name),
    ]
    args += src_paths
    return subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, check=True).stdout


def write_to_metadata_file(metadata_file, branch, branches):
    json.dump({
        "title": "Documentation",
        "document-css": False,
        "branch": branch,
        "branches": [{"name": b,
                      "href": f"{urllib.parse.quote_plus(b)}/index.html",
                      "default": b == branch}
                     for b in reversed(branches)]}, metadata_file)
    metadata_file.flush()


def install_dependencies():
    subprocess.run(["sudo", "apt", "install", "--assume-yes", "python3-pip"], check=True)
    subprocess.run(["sudo", "apt", "install", "--assume-yes", "python3-venv"], check=True)
    subprocess.run([sys.executable, "-m", "venv", "venv"], check=True),
    subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4"], check=True)
    subprocess.run(["sudo", "apt", "install", "--assume-yes", "pandoc"], check=True)


def natural_sort_key(s):
    # https://stackoverflow.com/a/16090640
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", s)]


def sort_branches(branches):
    branches = list(branches)
    order_least = min(order for _, order, _ in BRANCH_ORDERING) - 1
    for i, branch_dir in enumerate(branches):
        for regex, order, default in BRANCH_ORDERING:
            if re.fullmatch(regex, branch_dir.name):
                branches[i] = (order, natural_sort_key(branch_dir.name), default,
                               branch_dir)
                break
        else:
            branches[i] = (order_least, natural_sort_key(branch_dir.name), False,
                           branch_dir)
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


def postprocess_raw_soup(soup, md_files):
    # Build caches
    soup.all_ids = soup.select("*[id]")
    soup.internal_links = soup.select("a[href^=\\#]")
    links_by_id = defaultdict(list)
    for link in soup.internal_links:
        id_ = link["href"][1:]
        links_by_id[id_].append(link)
    soup.links_by_id = links_by_id
    soup.all_sections = soup.select("main section")
    soup.top_sections = soup.select("main section:not(section section)")

    checks_failed = False

    # Check for duplicate ids
    visited_ids = set()
    for element in soup.all_ids:
        if element["id"] in visited_ids:
            print("[ERROR] Duplicate id %r" % element["id"],
                  file=sys.stderr)
            checks_failed = True
        visited_ids.add(element["id"])

    # Check for dead internal links
    for link in soup.internal_links:
        if link["href"][1:] not in visited_ids:
            print("[ERROR] Dead internal link %r" % link["href"],
                  file=sys.stderr)
            checks_failed = True

    if checks_failed:
        raise RuntimeError("[ERROR] No failing checks allowed")

    # Copy the hierarchical levels of the sections and subsections to the corresponding navigation elements
    nav = soup.select("main nav")[0]
    for section in soup.all_sections:
        link = nav.find("a", href="#" + section["id"])
        if link is None:
            continue
        add_class(link.parent, section["class"][0])

    # Mark last section
    add_class(soup.all_sections[-1], "last")

    # Wrap tables in a div container (for scrolling)
    for table in soup.select("main table"):
        container = soup.new_tag("div")
        add_class(container, "tableContainer")
        table.wrap(container)

    # Instead of anchor only, link all hrefs to the correct HTML file AND the anchor
    # This is necessary to be able to remove sections at will
    html_path_by_heading = {h: f.html_path for f in md_files for h in f.get_headings()}
    for section in soup.top_sections:
        heading_in_soup = section.find().text.strip()
        html_path = html_path_by_heading[heading_in_soup]

        id_ = section["id"]
        for broken_href in soup.links_by_id[id_]:
            broken_href["href"] = f"./{html_path.name}"

        for element in section.select("*[id]"):
            id_ = element["id"]
            for broken_href in soup.links_by_id[id_]:
                broken_href["href"] = f"./{html_path.name}#{id_}"

    # Add a link with the fragment to every header
    for section in soup.all_sections:
        header = section.find()
        link = soup.new_tag("a")
        add_class(link, "headerlink")
        link["href"] = "#" + section["id"]
        link.string = "¶"
        header.append(" ")
        header.append(link)

    return soup


def add_class(element, class_):
    element["class"] = element.get("class", []) + [class_]


def extract_section_html(soup, curr_md_file):
    """
    Make sure to extract only the sections of the MD file.
    Important: hrefs should already point to the correct HTML file
    """
    print("Currently extracting:", curr_md_file.html_path)
    section_soup = deepcopy(soup)
    curr_headings = curr_md_file.get_headings()
    found_sections = False
    for section in section_soup.select("main section:not(section section)"):
        heading_in_soup = section.find("h2").text.removesuffix(" ¶")
        if heading_in_soup in curr_headings:
            found_sections = True
        else:
            section.extract()  # discard section not from the curr_md_file

    if not found_sections:
        raise RuntimeError(f"found no matching sections for {curr_headings}")
    return section_soup.encode(formatter="html5") + b"\n"


def ensure_clean_workspace(repo_dir):
    md_dir = repo_dir / "md"
    html_dir = repo_dir / "html"
    shutil.rmtree(md_dir, ignore_errors=True)
    shutil.rmtree(html_dir, ignore_errors=True)
    md_dir.mkdir(parents=False, exist_ok=False)
    html_dir.mkdir(parents=False, exist_ok=False)


def collect_docs_sources(repo_dir):
    """
    First, fetch remote branches - really necessary? fetch is done when pushing anyway, Github Actions has clean state
    Second, find all relevant branches - idea: switch to release sub-branches + strict checks instead of guessing
    Third, checkout the "docs/" pathspec for each remote branch and move it a common place
    """
    md_source_path = repo_dir / DOCS_MD_SOURCE_PATHSPEC
    run_git("fetch", "--no-tags", "--prune", "--progress", "--no-recurse-submodules", "--depth=1", REMOTE,
            "+refs/heads/*:refs/remotes/%s/*" % REMOTE)
    remote_revs = run_git("rev-parse", "--symbolic", "--remotes=%s" % REMOTE)
    release_branches = [rev[len(REMOTE) + 1:] for rev in remote_revs if rev.startswith(RELEASE_BRANCH_PREFIXES)]
    for branch in release_branches:
        try:
            run_git("restore", "--source", branch, "--", DOCS_MD_SOURCE_PATHSPEC)
        except subprocess.CalledProcessError:
            continue
        docs_md_dir = DOCS_MD_DIR_TEMPLATE.format(release=branch)
        shutil.move(md_source_path, docs_md_dir)  # TODO: use md_source_path.move once Python >= 3.14 is required


def build_docs_html(repo_dir):
    """
    Iterate over all release dirs by doing the following:
        - create result HTML dir
        - create a large complete HTML file
        - extract smaller HTML files from the large HTML file, one per MD file

    Extraction of smaller HTML files has proven to be more useful
    because all links can be cross-checked and repaired more easily.
    """
    md_dir = repo_dir / "md"
    html_dir = repo_dir / "html"
    release_dirs = list(md_dir.iterdir())
    release_dirs = sort_branches(release_dirs)[0]
    for release_dir in release_dirs:
        print(f"\nWorking on {release_dir}")
        html_dir_of_release = html_dir / release_dir.name
        html_dir_of_release.mkdir()

        md_files = [MDFile(file, html_dir_of_release) for file in release_dir.iterdir()]
        md_files = [md_file for md_file in md_files if md_file.validate()]
        if not md_files:
            print(f"no validated markdown files in {release_dir}")
            continue
        md_files = sorted(md_files)
        MDFile.validate_combined_files(md_files)

        with NamedTemporaryFile(mode="w", prefix="%s-" % PROG, suffix=".json") as metadata_file:
            write_to_metadata_file(metadata_file, release_dir.name, [dir.name for dir in release_dirs])
            raw_html = run_pandoc(md_files, TEMPLATE_PATH, metadata_file)
            soup = BeautifulSoup(raw_html, "html.parser")
            soup = postprocess_raw_soup(soup, md_files)

        for md_file in md_files:
            section_html = extract_section_html(soup, md_file)
            with open(md_file.html_path, "wb") as f:
                f.write(section_html)


def publish_html():
    run_git("add", "md")
    run_git("add", "html")
    with contextlib.suppress(subprocess.CalledProcessError):
        run_git("diff", "--cached", "--quiet")
        print("No changes", file=sys.stderr)
        return
    run_git("commit", "-m", COMMIT_MESSAGE)
    run_git("push")


def make_documentation(repo_dir):
    """
    Making a documentation is like cooking a recipe: clean the kitchen, collect ingredients and cook.
    """
    ensure_clean_workspace(repo_dir)
    collect_docs_sources(repo_dir)
    build_docs_html(repo_dir)


if __name__ == "__main__":
    run_as_github_action = bool(os.environ.get("GITHUB_ACTIONS", "") == "true")
    if run_as_github_action:
        install_dependencies()

    # git repository is mandatory; there's no way around it
    [repo_dir] = run_git("rev-parse", "--show-toplevel")
    os.chdir(repo_dir)
    make_documentation(Path(repo_dir))

    if run_as_github_action:
        publish_html()
