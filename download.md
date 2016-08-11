---
layout: page
title: Download
permalink: /download/
---

## PyPI

Radicale is [available on PyPI](http://pypi.python.org/pypi/Radicale/). To
install, just type as superuser:

    pip install radicale

## Git Repository

If you want the development version of Radicale, take a look at the
[git repository on GitHub]({{ site.github.repository_url }}), or clone it
thanks to:

    git clone git://github.com/Kozea/Radicale.git

You can also download
[the Radicale package of the git repository](https://github.com/Kozea/Radicale/tarball/master).

## Source Packages

You can download the Radicale package for each release:

{% assign releases = site.github.releases | where:"draft",false | reverse %}
{% for release in releases %}
- [Radicale-{{ release.tag_name }}.tar.gz](http://pypi.python.org/packages/source/R/Radicale/Radicale-{{ release.tag_name }}.tar.gz){% endfor %}

## Linux Distribution Packages

Radicale has been packaged for:

- [ArchLinux (AUR)](https://aur.archlinux.org/packages/radicale/) by
  Guillaume Bouchard
- [Debian](http://packages.debian.org/radicale) by Jonas Smedegaard
- [Gentoo](https://packages.gentoo.org/packages/www-apps/radicale)
  by René Neumann, Maxim Koltsov and Manuel Rüger
- [Fedora](https://admin.fedoraproject.org/pkgdb/package/radicale/) by Jorti
- [Mageia](http://madb.mageia.org/package/show/application/0/name/radicale) by
  Jani Välimaa
- [OpenBSD](http://openports.se/productivity/radicale) by Sergey Bronnikov,
  Stuart Henderson and Ian Darwin
- [openSUSE](http://software.opensuse.org/package/Radicale?search_term=radicale)
  by Ákos Szőts and Rueckert
- [PyPM](http://code.activestate.com/pypm/radicale/)
- [Slackware](http://schoepfer.info/slackware.xhtml#packages-network) by
  Johannes Schöpfer
- [Trisquel](http://packages.trisquel.info/search?searchon=names&keywords=radicale)
- [Ubuntu](http://packages.ubuntu.com/radicale) by the MOTU and Jonas
  Smedegaard

Radicale is also
[available on Cloudron](https://cloudron.io/button.html?app=org.radicale.cloudronapp)
and has a Dockerfile.

If you are interested in creating packages for other Linux distributions, read
the ["Contribute" page]({{ site.baseurl }}/contribute/).
