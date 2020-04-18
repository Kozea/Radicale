#!/usr/bin/env python3

"""
Postprocessor program for the HTML output of Pandoc
"""

import sys

from bs4 import BeautifulSoup


def add_class(element, class_):
    element["class"] = element.get("class", []) + [class_]


def main():
    soup = BeautifulSoup(sys.stdin.buffer, "html.parser")

    # Mark the hierachical levels in the navigation
    nav = soup.select("main nav")[0]
    for section in soup.select("main section"):
        link = nav.find("a", href="#" + section["id"])
        if link is None:
            continue
        add_class(link.parent, section["class"][0])

    # Mark last section
    add_class(soup.select("main section")[-1], "last")

    # Wrap tables in a div container (for scrolling)
    for table in soup.select("main table"):
        container = soup.new_tag("div")
        add_class(container, "tableContainer")
        table.wrap(container)

    # Add a link with the fragment to every header
    for header in soup.select("main section > *:first-child"):
        section = header.parent
        link = soup.new_tag("a")
        add_class(link, "headerlink")
        link["href"] = "#" + section["id"]
        link.string = "¶"
        header.append(" ")
        header.append(link)

    sys.stdout.buffer.write(soup.encode(formatter="html5") + b"\n")


if __name__ == "__main__":
    main()
