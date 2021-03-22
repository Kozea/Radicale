# Documentation

For the complete documentation, please visit [Radicale Documentation](https://radicale.org/).

## Generator

The HTML documentation is automatically generated from the markdown file
`DOCUMENTATION.md` in every git branch.

The documentation generator script is located in the `documentation-generator`
directory.
It is executed by the GitHub Actions workflow
`.github/workflows/generate-documentation.yml`.
Generated HTML files and `index.html` that redirects to the latest version are
committed to this branch.
