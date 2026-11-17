# About contributing to Radicale

Radicale is open source. Anyone can contribute.

## Issues

> [!NOTE]
> For larger updates, we highly recommend that you open an issue first, to give us the opportunity to review your proposal before you go ahead and raise a pull request.

[Issues](/en/issues/tracking-your-work-with-issues/learning-about-issues/about-issues) are used to track tasks that contributors can help with.

## Pull requests

A [pull request](/en/pull-requests/reference/pull-requests) is a way to suggest changes in our repository.
When we merge those changes, they're available as nightly (UTC) built [container](https://github.com/Kozea/Radicale/pkgs/container/radicale), see also 
[Wiki/Installing-on-Docker](https://github.com/Kozea/Radicale/wiki/Installing-on-Docker).

In case of bigger changes, please start a discussion first [Radicale/Discussions](https://github.com/Kozea/Radicale/discussions).

The source layout, data on disk, CI, and the release steps are in [docs/README.md](docs/README.md).
 
### Reviewing your own pull requests

You should always review and test your own pull request first, before marking it as ready for review by others.

For any changes, make sure that you:

* Don't break compatibility
  * with supported Python versions [Wiki/Main Page](https://github.com/Kozea/Radicale/wiki)
  * with supported Enterprise Linux versions [Wiki/Main Page](https://github.com/Kozea/Radicale/wiki)
* Overtake current or improved coding style.
* Confirm that the changes meet the requirements or successfully fixing an issue.
  * Extend test suite in case of fixing an issue which is currently not covered
* Code `diff` is easy to review.
* Review the change for technical accuracy.
* Local run of test suite passed successfully, see also [Wiki/Development Testing Release](https://github.com/Kozea/Radicale/wiki/05-%E2%80%90-Development-Testing-Release)
* If possible, include extension of [CHANGELOG.md](https://github.com/Kozea/Radicale/blob/master/CHANGELOG.md).
* If senseful, include adjustment/extension of [DOCUMENTATION.md](https://github.com/Kozea/Radicale/blob/master/DOCUMENTATION.md).
* On new or adjusted options do not forget to extend/update reference [config](https://github.com/Kozea/Radicale/blob/master/config),
* Extend copyright section of changed files if you feel your contribution is big enough.
* On new files, overtake license and copyright section from an existing file.
  
### AI support

It is accepted that your pull request is supported by AI under following conditions
* Reviewed by HI (Human Intelligence): you have read the whole diff, run the test suite locally, and can explain what each change and each added test is meant to guarantee.
* Coding style is aligned with current one.
* AI support is disclosed in the pull request description:
  * the **model** (e.g. `Claude Sonnet 5.5`, `Grok 4`, `GPT-5`),
  * ideally the **effort / reasoning level** and how it was used (e.g. autonomous agent, supervised, only drafted),
  * which parts were generated, and what you verified yourself.
* Preferably also disclose it in the commits, with a trailer such as `Co-Authored-By: <model> <noreply@...>` or `Assisted-by: <model>`, so that the information stays visible in `git log` after a squash.

Generated tests need particular care:
* A test must fail when the code it names is broken. Check this, e.g. by temporarily reverting the fix.
* Do not assert on current behavior you do not understand, only to increase coverage. If the behavior looks wrong, open an issue instead of pinning it in a test.
* Avoid assertions that cannot fail (`a or b` with a trivially true `b`, `status in (200, 400)`, membership of a single character).
* Prefer several small pull requests over one that is too big to be reviewed.

Maintainers may ask for a pull request to be split, reduced or reworked if it cannot be reviewed properly.

### Review pull request by maintainers

You can select which maintainer should review your pull request.
Don't worry if they return with questions.

### Merge pull request

Pull requests will only be merged if they pass the whole test suite without any issues.

> [!NOTE]
> New contributors have to wait until their pull request is approved before test suite is executed.

## Support

We are a small team working.
In case you need suppport, contact [Maintainers/Contributors](https://github.com/Kozea/Radicale/wiki/04-%E2%80%90-Maintainers-Contributors).

## Tasks

If you want to support improving the code in general, ongoing pending/open tasks are:
- code review regarding
  - style optimization
  - performance optimization
- extension of test cases to increase coverage
