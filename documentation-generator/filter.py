#!/usr/bin/env python3

"""
Filter program for transforming the Pandoc AST
"""

import json
import sys

TITLE = "Documentation"


def main():
    data = json.load(sys.stdin)

    # Check and remove level 1 header
    level1_header = [
        (i, content) for i, (level, _, content)
        in ((i, b["c"]) for i, b in enumerate(data["blocks"])
            if b["t"] == "Header")
        if level == 1]
    if (len(level1_header) != 1
            or level1_header[0][1] != [{"t": "Str", "c": TITLE}]):
        print("ERROR: Document must contain single level 1 heading %r" % TITLE,
              file=sys.stderr)
        sys.exit(1)
    for i, _ in reversed(level1_header):
        del data["blocks"][i]
    # Use level 1 heading as title
    data["meta"]["title"] = {"t": "MetaInlines", "c": level1_header[0][1]}

    json.dump(data, sys.stdout)


if __name__ == "__main__":
    main()
