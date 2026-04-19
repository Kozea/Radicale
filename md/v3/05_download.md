## Download

#### PyPI

Radicale is [available on PyPI](https://pypi.python.org/pypi/Radicale/). To
install, just type as superuser:

```bash
python3 -m pip install --upgrade radicale
```

#### Git Repository

If you want the development version of Radicale, take a look at the
[git repository on GitHub](https://github.com/Kozea/Radicale/), or install it
directly with:

```bash
python3 -m pip install --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz
```

You can also download the content of the repository as an
[archive](https://github.com/Kozea/Radicale/tarball/master).

#### Source Packages

You can find the source packages of all releases on
[GitHub](https://github.com/Kozea/Radicale/releases).

#### Docker

Radicale is available as a Docker image for platforms `linux/amd64` and `linux/arm64` on:

* [Docker Hub](https://hub.docker.com/r/kozea/radicale), and
* [GitHub's Container Registry](https://github.com/Kozea/Radicale/pkgs/container/radicale)

Here are the steps to install Radicale via Docker Compose:

1. Create required directories

    Create a directory to store the data, configuration and compose file.

    For example, assuming `./radicale`:

    ```bash
    $ mkdir radicale
    $ cd radicale
    ```
    Create directories to store data and configuration.

    For example, assuming data directory as `./data` and configuration directory as `./config`:

    ```bash
    $ mkdir config data
    ```

2. Download the compose file

    ```bash
    $ wget https://raw.githubusercontent.com/Kozea/Radicale/refs/heads/master/compose.yaml
    ```

    The compose file assumes `./config` and `./data` directories. Review the file and modify as needed.

3. Create Radicale configuration file as necessary

    Create a new configuration file or place an existing one in the `./config` directory.


    **Note**: This section demonstrates only basic steps to setup Radicale using `docker compose`. For details on configuring Radicale, including authentication, please refer to the documentation for [Basic Configuration](#basic-configuration) or detailed [Configuration](#configuration)


4. Start Radicale

    ```bash
    $ docker compose up -d
    ```

    This will start the Radicale container in detached mode.


    To view the logs of the running container, run:

    ```bash
    $ docker compose logs -f
    ```

    To stop the container, run this from the current directory:

    ```bash
    $ docker compose down
    ```

##### Available tags

* `stable`: Points to the latest stable release. This is recommended for most users.
* Major.Minor.Patch (e.g. `3.6.1`): Points to a specific release version.
* Major.Minor (e.g. `3.6`): Tracks the latest release for a minor version.
* Major (e.g. `3`): Tracks the latest release for a major version.
* nightly tags (e.g. `nightly-20260206`): Nightly builds.
* `latest`: Points to the most recent build. In most cases, this is nightly.

#### Linux Distribution Packages

Radicale has been packaged for:

* [ArchLinux](https://www.archlinux.org/packages/community/any/radicale/) by
  David Runge
* [Debian](https://packages.debian.org/radicale) by Jonas Smedegaard
* [Gentoo](https://packages.gentoo.org/packages/www-apps/radicale)
  by René Neumann, Maxim Koltsov and Manuel Rüger
* [Fedora/EnterpriseLinux](https://src.fedoraproject.org/rpms/radicale) by Jorti
  and Peter Bieringer
* [Mageia](http://madb.mageia.org/package/show/application/0/name/radicale)
  by Jani Välimaa
* [OpenBSD](http://openports.se/productivity/radicale) by Sergey Bronnikov,
  Stuart Henderson and Ian Darwin
* [openSUSE](http://software.opensuse.org/package/Radicale?search_term=radicale)
  by Ákos Szőts and Rueckert
* [PyPM](http://code.activestate.com/pypm/radicale/)
* [Slackware](http://schoepfer.info/slackware.xhtml#packages-network) by
  Johannes Schöpfer
* [Trisquel](http://packages.trisquel.info/search?searchon=names&keywords=radicale)
* [Ubuntu](http://packages.ubuntu.com/radicale) by the MOTU and Jonas
  Smedegaard

Radicale is also
[available on Cloudron](https://cloudron.io/button.html?app=org.radicale.cloudronapp2).

If you are interested in creating packages for other Linux distributions, read
the ["Contribute" section](#contribute).
