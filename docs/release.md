# Releases

Maintainers ship a version. An agent does not tag, push tags, publish a GitHub Release, or run the PyPI or container workflows.

The steps below are the ones written on the wiki page [Development Testing Release](https://github.com/Kozea/Radicale/wiki/Development-Testing-Release) (the release section). The workflows that run after a published GitHub Release are in [ci.md](ci.md). If the wiki and this file disagree, the wiki is the process the maintainers follow. Update this file in the same change that updates the wiki.

## Before the version commit

* All last actions successfully executed.
* `CHANGELOG.md` lists the changes that will ship.
* No important issue is still open.
* The local checkout is up to date with upstream `master`.
* Every issue in the milestone is closed.

Then update the milestone date, close that milestone, and create the next one.

## Version commit and tag

Set `VERSION` to `x.y.z` and replace the `3.*.dev` version with `$VERSION` in:

* `CHANGELOG.md` (the `## x.y.z.dev` heading becomes `## $VERSION`)
* `pyproject.toml` (`version`)
* `setup.py.legacy`

Commit message: `Release $VERSION`.

Tag `v$VERSION`. Push the branch and the tags (`git push` and `git push --tags`).

Fedora and Enterprise Linux packages are built in [Koji](https://koji.fedoraproject.org/koji/packageinfo?packageID=16893). That build is outside this repository.

## GitHub Release

Draft the GitHub Release. The title is the version, depending on the changes. The body copies the changelog part for that version and sorts it by section. Publish it as a release, unless it should be a pre-release.

Publishing a release that is not a pre-release fires `released`. Publishing a pre-release directly fires `prereleased`. Publishing a draft as a pre-release fires `published`, not `prereleased` and not `released`. `pypi-publish.yml` listens only for `released`. `docker-publish.yml` listens for `released`, the daily schedule, and `workflow_dispatch`. A pre-release does not run either workflow. On `released`, [ci.md](ci.md) publishes the sdist and the wheel to PyPI and builds the container images. That container build includes `stable` and `latest`.

If the tag must be corrected, the wiki says to create `v$VERSION-SEQ` and point the GitHub Release at the new tag.

## Stable branch

The current stable branch is `v3`. After the tag exists, update it to that tag:

```
git checkout v3
git rebase v$VERSION
git push
git checkout master
```

## Return `master` to development

Set `VERSION_DEV` to the next `x.y.z`. Add a `## $VERSION_DEV.dev` section at the top of `CHANGELOG.md`. Set `version` in `pyproject.toml` and the version in `setup.py.legacy` to `$VERSION_DEV.dev`.

Commit message: `Development $VERSION_DEV`. Push `master`.

The comment at the top of `pyproject.toml` says a version change must add the changelog section. Do both in that same commit.

## What this repository does not automate

Nothing in `.github/workflows/` bumps the version, writes the tag, or opens the GitHub Release. Those are manual steps on a maintainer's machine. `pypi-publish.yml` and `docker-publish.yml` do not check the repository name. `pypi-publish.yml` runs only on `released`. `docker-publish.yml` runs on `released`, on the daily schedule, and on `workflow_dispatch`. The schedule is the run that is skipped when `DOCKERHUB_ORGNAME` is empty. A release or a manual run is not skipped for that reason.
