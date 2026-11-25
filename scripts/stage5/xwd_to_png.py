#!/usr/bin/env python3
"""Convert X window dumps (xwd, ZPixmap, 24/32 bits per pixel) to PNG. Host, plain python3.

    python3 xwd_to_png.py <file.xwd>...        # writes <file>.png next to each, removes the .xwd

Used to keep pictures of the Gazebo window during a watched Stage 5 flight:
    xwd -display $DISPLAY -name Gazebo -silent > shot.xwd
(ImageMagick, the usual converter, is not installed on this workstation.)
"""
import os
import struct
import sys

import numpy as np
import matplotlib.image as mpimg


def convert(path):
    b = open(path, "rb").read()
    h = struct.unpack(">25I", b[:100])
    hsize, fmt, depth, w, ht = h[0], h[2], h[3], h[4], h[5]
    byte_order, bpp, bpl, ncolors = h[7], h[11], h[12], h[19]
    if fmt != 2 or bpp not in (24, 32):
        raise SystemExit("%s: unsupported xwd (format %d, %d bpp)" % (path, fmt, bpp))
    off = hsize + 12 * ncolors
    raw = np.frombuffer(b[off:off + bpl * ht], dtype=np.uint8).reshape(ht, bpl)
    px = raw[:, :w * (bpp // 8)].reshape(ht, w, bpp // 8)
    rgb = px[:, :, [2, 1, 0]] if byte_order == 0 else px[:, :, [1, 2, 3]] if bpp == 32 else px[:, :, [0, 1, 2]]
    out = os.path.splitext(path)[0] + ".png"
    mpimg.imsave(out, np.ascontiguousarray(rgb))
    os.remove(path)
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(convert(p))
