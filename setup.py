# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2009-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Radicale.  If not, see <http://www.gnu.org/licenses/>.

from setuptools import find_packages, setup

# When the version is updated, a new section in the CHANGELOG.md file must be
# added too.
VERSION = "3.dev"

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()
web_files = ["web/internal_data/css/icon.png",
             "web/internal_data/css/loading.svg",
             "web/internal_data/css/logo.svg",
             "web/internal_data/css/main.css",
             "web/internal_data/css/icons/delete.svg",
             "web/internal_data/css/icons/download.svg",
             "web/internal_data/css/icons/edit.svg",
             "web/internal_data/css/icons/new.svg",
             "web/internal_data/css/icons/upload.svg",
             "web/internal_data/fn.js",
             "web/internal_data/index.html"]

install_requires = ["defusedxml", "passlib", "vobject>=0.9.6",
                    "python-dateutil>=2.7.3",
                    "pika>=1.1.0",
                    "setuptools; python_version<'3.9'"]
bcrypt_requires = ["bcrypt"]
test_requires = ["pytest>=7", "typeguard<4.3", "waitress", *bcrypt_requires]

setup(
    name="Radicale",
    version=VERSION,
    description="CalDAV and CardDAV Server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Guillaume Ayoub",
    author_email="guillaume.ayoub@kozea.fr",
    url="https://radicale.org/",
    license="GNU GPL v3",
    platforms="Any",
    packages=find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    package_data={"radicale": [*web_files, "py.typed"]},
    entry_points={"console_scripts": ["radicale = radicale.__main__:run"]},
    install_requires=install_requires,
    extras_require={"test": test_requires, "bcrypt": bcrypt_requires},
    keywords=["calendar", "addressbook", "CalDAV", "CardDAV"],
    python_requires=">=3.8.0",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Office/Business :: Groupware"])
