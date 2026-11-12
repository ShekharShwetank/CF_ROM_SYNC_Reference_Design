#!/usr/bin/env python3
"""Read DO net capacitance from an OpenROAD rom-sta log.

report_net prints a single value or a rise-fall range such as
0.085758-0.089745. The minimum of that range is what has to clear
the ROM liberty min_capacitance of 0.111 pF.
"""

import re
import sys

MIN_PF = 0.111
TOTAL = re.compile(r"Total capacitance:\s+(\S+)")


def bounds(token):
    parts = token.split("-")
    if len(parts) == 2 and parts[0] and parts[1]:
        low = float(parts[0])
        high = float(parts[1])
        return min(low, high), max(low, high)
    value = float(token)
    return value, value


def main():
    corner = sys.argv[1]
    text = open(sys.argv[2]).read()
    rows = [bounds(token) for token in TOTAL.findall(text)]
    if len(rows) != 8:
        print(f"{corner}: expected 8 DO capacitances, found {len(rows)}", file=sys.stderr)
        return 1
    print(
        corner,
        "DO capacitance pF (low-high):",
        " ".join(f"{low:.4f}-{high:.4f}" for low, high in rows),
    )
    short = [low for low, _high in rows if low < MIN_PF]
    if short:
        print(
            f"{corner}: {len(short)} DO nets below {MIN_PF} pF "
            f"(lowest {min(short):.4f})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
