# Releases

An agent does not tag, push tags, publish a GitHub Release, or run the PyPI or container workflows.

The wiki page [Development Testing Release](https://github.com/Kozea/Radicale/wiki/05-%E2%80%90-Development-Testing-Release) points its release section here. What the workflows do after a release is published is in [ci.md](ci.md).

Run this first, so the later commands are not applied on a stale checkout:

```bash
git pull
```

## Verifications

* All last actions successfully executed.
* `CHANGELOG.md` is up to date.
* No important issues are still pending.
* The local repository is up to date: `git pull`.
* All issues assigned to the related milestone are closed.

## Preparation

### Milestones

* Update the date of the current milestone.
* Close the current milestone.
* Create the new milestone.

### Files

Pull the latest changes from upstream:

```bash
git pull
```

Define the version:

```bash
VERSION="x.y.z"
```

| File | Action |
| --- | --- |
| `CHANGELOG.md` | replace `3.*.dev` with `$VERSION` |
| `setup.py.legacy` | replace `3.*.dev` with `$VERSION` |
| `pyproject.toml` | replace `3.*.dev` with `$VERSION` |

Commit the changes:

```bash
git commit -a -m "Release $VERSION"
```

Create the release tag:

```bash
git tag v$VERSION
```

Push:

```bash
git push
git push --tags
```

### Build RPMs for Fedora/EL

Build RPMs for Fedora/EL: https://koji.fedoraproject.org/koji/packageinfo?packageID=16893

## Release

### Draft the new release

* Release title: the version, depending on the changes.
* Description: copy the part from `CHANGELOG.md` and sort it by section.
* Set it as a release, unless it should be a pre-release.

If something needs to be corrected, create a new tag `v$VERSION-SEQ` and change the tag of the release.

### Rebase the major version

The commands rebase the current major-version branch (`v3`) onto the tag `v$VERSION`.

```bash
git checkout v3
git rebase v$VERSION
git push
git checkout master
```

## Turn `master` back to development

Define the version:

```bash
VERSION_DEV="x.y.z"
```

| File | Action |
| --- | --- |
| `CHANGELOG.md` | add a new section with `$VERSION_DEV.dev` |
| `setup.py.legacy` | replace `$VERSION` with `$VERSION_DEV.dev` |
| `pyproject.toml` | replace `$VERSION` with `$VERSION_DEV.dev` |

Commit the changes:

```bash
git commit -a -m "Development $VERSION_DEV"
```

Push:

```bash
git push
```
