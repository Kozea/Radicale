# Developer documentation

These pages describe how the Radicale source tree is put together. They are for people and agents changing the code.

Operator setup, options, and client notes stay in the files that already exist. Do not copy them here.

| Topic | Where |
| --- | --- |
| Architecture and request path | [architecture.md](architecture.md) |
| Stored data | [data-model.md](data-model.md) |
| Packages and plugins | [components.md](components.md) |
| GitHub Actions | [ci.md](ci.md) |
| How a maintainer ships a version | [release.md](release.md) |
| Install, options, and clients | [DOCUMENTATION.md](../DOCUMENTATION.md) at the repository root. The site https://radicale.org/master.html is generated from that file. |
| Telugu translation of the operator manual | [translations/DOCUMENTATION.te.md](translations/DOCUMENTATION.te.md) |
| Sharing behavior and the management API | [SHARING.md](../SHARING.md) |
| Defaults for every option | [config](../config) |
| Rights file example | [rights](../rights) |
| How to contribute | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Agent commit and review rules | [AGENTS.md](../AGENTS.md) |
| Security contact and supported major version | [SECURITY.md](../SECURITY.md) |
| Changelog | [CHANGELOG.md](../CHANGELOG.md) |
| Requirements, tested Python versions, and install notes | [project wiki](https://github.com/Kozea/Radicale/wiki) |
| Local test commands beyond CI | [Development Testing Release](https://github.com/Kozea/Radicale/wiki/05-%E2%80%90-Development-Testing-Release) |
| Web UI type check | [radicale/web/README.md](../radicale/web/README.md) |
| Browser integration tests | [integ_tests/README.md](../integ_tests/README.md) |
| CalDAV client compatibility tests | [caldav_compat_tests/README.md](../caldav_compat_tests/README.md) |
| Reverse-proxy examples | [contrib/](../contrib/) |

`docs/**` and `**.md` are ignored by the Test workflow. A pull request that only changes these pages does not run the test jobs. See [ci.md](ci.md).
