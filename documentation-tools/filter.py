#!/usr/bin/env python3

"""
Filter program for transforming the Pandoc AST
"""

import json
import re
import sys

from build import SHIFT_HEADING


def text_content(content):
    text = ""
    for block in content:
        if block["t"] == "Space":
            text += " "
        elif block["t"] == "Str":
            text += block["c"]
    return text


def convert_framgent(*titles):
    titles = list(titles)
    for i, title in enumerate(titles):
        title = re.sub(r"\s", "-", title)
        title = re.sub(r"[^\w-]", "", title)
        titles[i] = title.lower()
    return "/".join(titles)


def main():
    data = json.load(sys.stdin)

    # Use hierachical link fragments (e.g. #heading/subheading)
    headings = []
    for block in data["blocks"]:
        if block["t"] != "Header":
            continue
        level, (attr_id, attr_class, attr_name), content = block["c"]
        shifted_level = level - SHIFT_HEADING
        title = text_content(content)
        headings = headings[:shifted_level - 1]
        while len(headings) < shifted_level - 1:
            headings.append("")
        headings.append(title)
        full_attr_id = convert_framgent(*headings)
        block["c"] = [level, [full_attr_id, attr_class, attr_name], content]

    json.dump(data, sys.stdout)


if __name__ == "__main__":
    main()
