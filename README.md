# Documentation for Radical Documentation Generation

For the complete documentation, please visit [Radicale Documentation](https://radicale.org/).


## Generator

### Location and Requirements
The HTML documentation is automatically generated from the markdown files
in docs/ in every git branch.
The documentation generator script is located at the `documentation-generator/run.py`.
Make sure that all MD files added, have `## ...` sections as their top-level
headings.
Python 3.9 and Pandoc installable from apt is required.

### Tool Structure
The script comprise the top-level script `run.py`, a Pandoc filter
file `filter.py` and an HTML template file `template.html`.

### Functional Principle
For each git release branch, we restore the complete `docs/` folder of
the last release commit and move it to `md/{release_name}/`.
We do so, by using the `git restore` command in order to avoid messing
with the working copy.

HINT: make sure that all MD files are sorted by prefix `00_`, `01_`, `02_`, ...
Otherwise, we don't know what content to put first, second, etc.

Then, again for each git release branch, we convert all respective MD files into
a single large HTML file and postprocess it to ensure integrity.
We also augment links by their respective future HTML file.

The last step is to extract smaller HTML files per MD file provided.
As the hrefs have already been fixed in the previous step, links will
still work.

For Github Actions, we make sure to install all dependencies first and
add, commit + push all changes into the current branch.

### Static assets

Static assets live in `assets/`.


## Usage

### locally
Set your working directory somewhere inside the repository so git finds it.
Python 3.9 is required.
Install all dependencies listed in the Python function `install_dependencies`.

### by Github Actions
`documentation-generator/run.py` is executed by the GitHub Actions workflow `.github/workflows/generate-documentation.yml`.

Generated HTML files and `index.html` that redirects to the latest version are
committed to branch gh-pages.
