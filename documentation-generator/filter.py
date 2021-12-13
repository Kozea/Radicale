#!/usr/bin/env python3

"""
Filter program for transforming the Pandoc AST
"""

import json
import re
import sys

TITLE = "Documentation"


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

    delete_block_indices = []
    level1_heading = None
    # Use hierachical link fragments (e.g. #heading/subheading)
    headings = []
    for i, block in enumerate(data["blocks"]):
        if block["t"] != "Header":
            continue
        level, (attr_id, attr_class, attr_name), content = block["c"]
        if level == 1:
            if level1_heading is not None:
                print("ERROR: Mulitple level 1 headings found",
                      file=sys.stderr)
                exit(1)
            delete_block_indices.append(i)
            level1_heading = content
            continue
        shifted_level = level - 1  # Ignore level 1 heading
        title = text_content(content)
        headings = headings[:shifted_level - 1]
        while len(headings) < shifted_level - 1:
            headings.append("")
        headings.append(title)
        full_attr_id = convert_framgent(*headings)
        block["c"] = [level, [full_attr_id, attr_class, attr_name], content]
    if level1_heading != [{'t': 'Str', 'c': TITLE}]:
        print("ERROR: Level 1 heading must be %r" % TITLE, file=sys.stderr)
        exit(1)
    data["meta"]["title"] = {"t": "MetaInlines", "c": level1_heading}
    for i in reversed(delete_block_indices):
        del data["blocks"][i]

    json.dump(data, sys.stdout)


if __name__ == "__main__":
    main()
