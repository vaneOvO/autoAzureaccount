"""Pure-OpenCV gap / puzzle-piece detection. No browser dependency.

Validated against the real ByteDance Turing slider captcha
(bdcaptcha.js): gap located exactly on production images.
"""
import cv2
import numpy as np


def detect_gap_x(img_bgr):
    """Find the left edge x of the puzzle gap in a BGR image.

    Returns:
        (x, method, bbox) where method is "contour" or "darkcol",
        bbox is (x, y, w, h) for contour or None for darkcol.
        Returns (None, None, None) when nothing found.

    Priority: white-border contour first (most reliable — real captchas
    outline the gap in white), dark-column widest-run as fallback.
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # Method 1 (preferred): white-border contour
    edges = cv2.Canny(gray, 80, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if x < w * 0.12:
            continue  # skip the puzzle piece on the left
        if x < 5 or y < 5 or x + cw > w - 5 or y + ch > h - 5:
            continue  # background outlines touch the image edge
        area = cw * ch
        if area < (w * h) * 0.004 or area > (w * h) * 0.12:
            continue
        if cw < 15 or ch < 15:
            continue
        aspect = cw / max(ch, 1)
        if aspect < 0.6 or aspect > 1.6:
            continue  # gaps are near-square; filter scenic streaks
        if best is None or area > best[4]:
            best = (x, y, cw, ch, area)
    if best:
        return best[0], "contour", best[:4]

    # Method 2 (fallback): widest dark-column run.
    # NOTE: take the widest run, NOT the first — scenic photos contain
    # shadows/objects that false-positive as narrow dark runs.
    dark = (gray < 55).astype(np.uint8)
    y0, y1 = int(h * 0.15), int(h * 0.85)  # middle band, skip decorations
    col_dark = dark[y0:y1, :].sum(axis=0)
    start = int(w * 0.12)
    peak = int(col_dark[start:].max())
    if peak >= 12:
        thresh = max(peak * 0.5, 12)
        best_run = None  # (width, start_x)
        rs, rl = None, 0
        for x in range(start, w + 1):
            if x < w and col_dark[x] >= thresh:
                if rs is None:
                    rs = x
                rl += 1
            else:
                if rl >= 8 and (best_run is None or rl > best_run[0]):
                    best_run = (rl, rs)
                rs, rl = None, 0
        if best_run and best_run[0] >= 20:
            return best_run[1], "darkcol", None
    return None, None, None


def detect_piece_left(img_bgr, y_band=None):
    """Find the left edge x of the puzzle piece in a BGR image.

    Args:
        y_band: (y0, y1) vertical band where the piece sits — normally the
            gap's bbox y-range (piece and gap are level). Enables the
            precise white-border scan.

    Returns:
        x in image pixels. 0 when not found (piece hugging the left edge
        is the common layout, so 0 is a safe default).
    """
    h, w = img_bgr.shape[:2]

    # Method 1: white-border column scan (piece has a white outline too)
    if y_band:
        y0 = max(0, y_band[0] - 8)
        y1 = min(h, y_band[1] + 8)
        band = img_bgr[y0:y1, :int(w * 0.30)]
        white = ((band[:, :, 0] > 235) & (band[:, :, 1] > 235)
                 & (band[:, :, 2] > 235)).astype(np.uint8)
        col_white = white.sum(axis=0)
        need = int((y1 - y0) * 0.35)
        for x in range(col_white.shape[0]):
            if col_white[x] >= need:
                return x

    # Method 2 (fallback): Canny edge column scan
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 180)
    strip = edges[:, :int(w * 0.30)]
    col_edge = (strip > 0).sum(axis=0)
    need = int(h * 0.10)
    for x in range(strip.shape[1]):
        if col_edge[x] >= need:
            return x
    return 0
