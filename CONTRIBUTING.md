# About contributing to Radicale

You can contribute to Radicale in several ways.

Radicale is open source. Anyone can contribute.

## Issues

> [!NOTE]
> For larger updates, we highly recommend that you open an issue first, to give us the opportunity to review your proposal before you go ahead and raise a pull request.

[Issues](/en/issues/tracking-your-work-with-issues/learning-about-issues/about-issues) are used to track tasks that contributors can help with.

## Pull requests

A [pull request](/en/pull-requests/reference/pull-requests) is a way to suggest changes in our repository.
When we merge those changes, they're available as nightly (UTC) built [container](https://github.com/Kozea/Radicale/pkgs/container/radicale), see also 
[Wiki/Installing-on-Docker](https://github.com/Kozea/Radicale/wiki/Installing-on-Docker).

In case of bigger changes, please start a discussion first [Radicale/Discussions](https://github.com/Kozea/Radicale/discussions)
 
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
* Local run of test suite passed successfully, see also [Wiki/Development Testing Release](https://github.com/Kozea/Radicale/wiki/Development-Testing-Release)
* If possible, include extension of [CHANGELOG.md](https://github.com/Kozea/Radicale/blob/master/CHANGELOG.md).
* If senseful, include adjustment/extension of [DOCUMENTATION.md](https://github.com/Kozea/Radicale/blob/master/DOCUMENTATION.md).
* On new or adjusted options do not forget to extend/update reference [config](https://github.com/Kozea/Radicale/blob/master/config),
* Extend copyright section of changed files if you feel your contribution is big enough.
* On new files, overtake license and copyright section from an existing file.
  
### AI support

It is accepted that your pull request is supported by AI under following conditions
* Reviewed by HI (Human Intelligence).
* Coding style is aligned with current one.
* AI support is mentioned in comment.

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
