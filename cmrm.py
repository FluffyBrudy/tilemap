#!/usr/bin/env python3
import os
import sys

EXCEPTIONS = {
    "#fmt: on",
    "#fmt: off",
    "#type: ignore",
}

def strip_comment(line):
    # Find the first '#' that is not inside quotes
    in_single = False
    in_double = False

    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            comment = line[i:].strip()
            if comment in EXCEPTIONS:
                return line.rstrip()
            return line[:i].rstrip()
    return line.rstrip()

def process_file(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = [strip_comment(line) + "\n" for line in lines]

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def main():
    root = sys.argv[1]
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".py"):
                process_file(os.path.join(dirpath, name))

if __name__ == "__main__":
    main()
