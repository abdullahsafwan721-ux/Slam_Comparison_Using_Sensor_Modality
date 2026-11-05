#!/usr/bin/env python3
"""Extract every printed file from eVTOL-SLAM-Complete-Project-Guide.pdf, exactly.

    python3 scripts/tools/guide_extract.py eVTOL-SLAM-Complete-Project-Guide.pdf <outdir> [first last]

Runs on the HOST (needs pdfminer.six). Writes <outdir>/<path> for every "File: <path>"
listing (a repeated path gets a .dupN suffix) and <outdir>/SNIPPETS.txt with every
"Host:" / "Container:" command block. Compare against the repo with diff; never copy
blindly -- the guide was never run by its author (its Appendix D).

Why not pdftotext: `-layout` estimates columns per text block, so indentation shifts
between blocks (fatal for Python), and it drops spaces inside code (it turned the
two-space sed pattern `^  message_generation$` into one space). This tool rebuilds code
from glyph positions instead:
  * code blocks are Menlo at 7.68 pt with a fixed 4.625 pt advance and column 0 at
    x = 59.53 pt on every page, so column = round((x - 59.53) / 4.625) is exact;
  * blank lines come from the constant 10.96 pt line pitch (within a page; a blank line
    that falls on a page break cannot be recovered);
  * wrapped lines (continuation starts with U+21AA) wrap at 98 columns: a first segment
    97 wide means the break swallowed a space, one 98 wide was broken mid-token.
Validated 2026-11-05: gen_configs.py extracted this way regenerates the 11 files the
guide prints (Sec. 2.3, Appendix A) byte-identically, apart from two PDF artefacts.
"""
import collections
import os
import re
import sys

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTChar

X0, CW, CODE_SIZE, PITCH, WRAP = 59.53, 4.625, 7.68, 10.96, 98
ARROW = "↪"


def walk(o):
    if isinstance(o, LTChar):
        yield o
    elif hasattr(o, "__iter__"):
        for c in o:
            yield from walk(c)


def is_code(c):
    return "Menlo" in c.fontname and abs(c.size - CODE_SIZE) < 0.05


def rows_of(pdf, first, last):
    """(kind, text, page, y) per printed line; kind is 'code' or 'prose'."""
    nums = list(range(first - 1, last))
    lp = LAParams(char_margin=1000, line_margin=0.0)
    for pno, page in zip(nums, extract_pages(pdf, page_numbers=nums, laparams=lp)):
        lines = collections.defaultdict(list)
        for c in walk(page):
            lines[round(c.y0, 0)].append(c)
        for y in sorted(lines, reverse=True):
            cs = sorted(lines[y], key=lambda c: c.x0)
            if all(is_code(c) or c.get_text() == ARROW for c in cs):
                buf = []
                for c in cs:
                    col = round((c.x0 - X0) / CW)
                    buf.extend(" " * max(0, col - len(buf)))
                    buf.append(c.get_text())
                yield "code", "".join(buf), pno + 1, y
            else:
                out, prev = [], None
                for c in cs:
                    if prev is not None and c.x0 - prev.x1 > 1.2:
                        out.append(" ")
                    out.append(c.get_text())
                    prev = c
                text = "".join(out).strip()
                if text.startswith("eVTOL SLAM: The Complete Project Guide") or text.isdigit():
                    continue                                   # page header / footer
                yield "prose", text, pno + 1, y


def logical_lines(rows):
    """Restore blank lines, then re-join wrapped lines."""
    out = []
    for kind, text, page, y in rows:
        if out and kind == "code" and out[-1][0] == "code" and out[-1][2] == page and out[-1][4] is not None:
            k = round((out[-1][4] - y) / PITCH)
            out.extend([("code", "", page, None, None)] * max(0, k - 1))
        if kind == "code" and text.lstrip().startswith(ARROW) and out and out[-1][0] == "code":
            rest = text[text.index(ARROW) + 1:]
            lead = len(rest) - len(rest.lstrip(" ")) - 1          # one column gap is normal
            # seg = the previous PHYSICAL row as printed (indent and arrow included):
            # its visible width tells whether the break swallowed a space
            k0, t0, p0, seg, _ = out[-1]
            sep = " " if len(seg.rstrip(" ")) == WRAP - 1 else ""
            body = " " * max(lead, 0) + rest.lstrip(" ")
            out[-1] = (k0, t0 + sep + body, p0, text, y)
        else:
            out.append((kind, text, page, text, y))
    return [(k, t) for k, t, _, _, _ in out]


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    pdf, outdir = sys.argv[1], sys.argv[2]
    first, last = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1, 10 ** 6)
    if last == 10 ** 6:
        from pdfminer.pdfpage import PDFPage
        with open(pdf, "rb") as f:
            last = sum(1 for _ in PDFPage.get_pages(f))
    files, snippets, cur, pending = [], [], None, None
    for kind, text in logical_lines(rows_of(pdf, first, last)):
        if kind == "prose":
            m = re.match(r"^File:\s*(\S+)$", text)
            if m:
                cur = [m.group(1), []]
                files.append(cur)
            elif text == "File:" and pending:
                cur = [pending, []]                        # path printed on the line above
                files.append(cur)
            elif text in ("Host:", "Container:", "Jetson host:"):
                cur = [text, []]
                snippets.append(cur)
            else:
                cur = None
            pending = text if re.match(r"^[\w./-]+(\.\w+|/[\w.-]+)$", text) else None
        elif cur is not None:
            cur[1].append(text)
    seen = collections.Counter()
    for path, body in files:
        while body and not body[-1].strip():
            body.pop()
        n = seen[path]
        seen[path] += 1
        dst = os.path.join(outdir, path + ("" if n == 0 else ".dup%d" % n))
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        with open(dst, "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")
        print("%5d lines  %s" % (len(body), dst))
    with open(os.path.join(outdir, "SNIPPETS.txt"), "w", encoding="utf-8") as f:
        for name, body in snippets:
            f.write("==== %s\n%s\n\n" % (name, "\n".join(body)))
    print("%d files, %d command snippets -> %s" % (len(files), len(snippets), outdir))


if __name__ == "__main__":
    main()
