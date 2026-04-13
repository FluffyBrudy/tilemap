from __future__ import annotations

import argparse

from editor import Editor


def _parse_size(text: str) -> tuple[int, int]:
    parts = text.lower().split("x")
    if len(parts) == 1:
        n = int(parts[0])
        return n, n
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    raise ValueError("size must be WIDTHxHEIGHT")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run tilemap editor")
    parser.add_argument("--size", default="1500x900", help="Window size as WIDTHxHEIGHT")
    parser.add_argument("--fps", type=int, default=60, help="Editor FPS")
    args = parser.parse_args()

    size = _parse_size(args.size)
    editor = Editor(size=size, fps=max(1, args.fps))
    editor.run()


if __name__ == "__main__":
    main()
