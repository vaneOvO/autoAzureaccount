"""Playwright integration: locate the widget, detect, drag, verify.

Usage:
    from playwright.sync_api import sync_playwright
    from slider_captcha_solver import try_solve_slider

    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_page()
        # ... trigger the captcha ...
        if try_solve_slider(page):
            print("solved")
"""
import os
import random
import re

import cv2
import numpy as np

from .detection import detect_gap_x, detect_piece_left
from .trajectory import human_drag_trajectory

DEBUG_PREFIX = "slider_debug"


def _log(msg):
    print(f"[slider-captcha-solver] {msg}", flush=True)


def _visible(el):
    try:
        return el.is_visible()
    except Exception:
        return False


def _find_modal(ctx):
    """Locate the captcha modal container, or None."""
    try:
        d = ctx.locator('[role="dialog"]').first
        if d.count() and _visible(d):
            return d
    except Exception:
        pass
    try:
        hint = ctx.get_by_text(
            re.compile(r"Drag the puzzle piece|Verify to continue", re.I)).first
        if hint.count():
            for xp in ("xpath=ancestor::*[@role='dialog'][1]",
                       "xpath=ancestor::div[6]",
                       "xpath=ancestor::div[5]",
                       "xpath=ancestor::div[4]"):
                try:
                    anc = hint.locator(xp).first
                    if anc.count() and _visible(anc):
                        return anc
                except Exception:
                    continue
    except Exception:
        pass
    return None


def _largest_img_canvas(scope):
    """Largest visible img/canvas (>=200x100) in scope, or None."""
    try:
        cands = scope.locator("img, canvas")
        best, best_area = None, 0
        for i in range(min(cands.count(), 80)):
            el = cands.nth(i)
            try:
                if not el.is_visible():
                    continue
                b = el.bounding_box()
                if not b or b["width"] < 200 or b["height"] < 100:
                    continue
                a = b["width"] * b["height"]
                if a > best_area:
                    best, best_area = el, a
            except Exception:
                continue
        return best
    except Exception:
        return None


def _bg_div_clip(scope):
    """Fallback: clip rect of the largest div with a background image."""
    try:
        return scope.evaluate("""(root) => {
          const els = root.querySelectorAll('div');
          let best = null, bestArea = 0;
          for (const el of els) {
            const r = el.getBoundingClientRect();
            if (r.width < 200 || r.height < 100 || r.width > 1200) continue;
            const cs = window.getComputedStyle(el);
            if (!cs.backgroundImage || cs.backgroundImage === 'none') continue;
            const area = r.width * r.height;
            if (area > bestArea) { best = el; bestArea = area; }
          }
          if (!best) return null;
          const r = best.getBoundingClientRect();
          return {x: r.x, y: r.y, width: r.width, height: r.height};
        }""")
    except Exception:
        return None


def _find_in_scope(ctx, scope):
    els = {"bg": None, "bg_clip": None, "track": None,
           "handle": None, "refresh": None}
    els["bg"] = _largest_img_canvas(scope)
    if not els["bg"]:
        els["bg_clip"] = _bg_div_clip(scope)
    try:
        t = scope.get_by_text(re.compile(r"Drag the puzzle piece", re.I)).first
        if t.count() and _visible(t):
            els["track"] = t
    except Exception:
        pass
    for sel in ("[role='slider']",
                "[class*='slider-button']",
                "[class*='move-block']",
                "[class*='slider-handle']",
                "[class*='drag-button']",
                "[class*='captcha-slider']"):
        try:
            h = scope.locator(sel).first
            if h.count() and _visible(h):
                b = h.bounding_box()
                if b and b["width"] < 140 and b["height"] < 140:
                    els["handle"] = h
                    break
        except Exception:
            continue
    try:
        r = scope.get_by_text("Refresh", exact=False).first
        if r.count() and _visible(r):
            els["refresh"] = r
    except Exception:
        pass
    return els


def _find_elements(page):
    """Search modal-first, then page-wide, then inside iframes."""
    try:
        frames = [page] + [f for f in page.frames if f != page.main_frame]
    except Exception:
        frames = [page]
    for ctx in frames:
        modal = _find_modal(ctx)
        if modal is not None:
            els = _find_in_scope(ctx, modal)
            if els["bg"] or els.get("bg_clip"):
                if ctx is not page:
                    _log("captcha is inside an iframe, switched context")
                return els, ctx
        els = _find_in_scope(ctx, ctx)
        if els["bg"] or els.get("bg_clip"):
            if ctx is not page:
                _log("captcha is inside an iframe, switched context")
            return els, ctx
    return _find_in_scope(page, page), page


def _is_solved(page):
    try:
        t = page.get_by_text(
            re.compile(r"Verify to continue|Drag the puzzle piece", re.I))
        if t.count() == 0:
            return True
        for i in range(t.count()):
            try:
                if t.nth(i).is_visible():
                    return False
            except Exception:
                continue
        return True
    except Exception:
        return False


def _click_refresh(ctx, els):
    try:
        r = els["refresh"]
        if r is not None:
            r.click(timeout=3000)
            _log("clicked Refresh for a new image")
            return True
    except Exception as e:
        _log(f"Refresh click failed: {e}")
    return False


def _save_debug(debug_dir, attempt, img_bgr, gap_x):
    try:
        dbg = img_bgr.copy()
        if gap_x is not None:
            cv2.line(dbg, (int(gap_x), 0),
                     (int(gap_x), dbg.shape[0]), (0, 0, 255), 2)
        path = os.path.join(debug_dir, f"{DEBUG_PREFIX}_attempt{attempt}.png")
        cv2.imwrite(path, dbg)
        _log(f"debug screenshot saved: {path}")
    except Exception:
        pass


def _run_trajectory(page, traj):
    for step in traj:
        if step[0] == "move":
            _, x, y, delay = step
            page.mouse.move(x, y)
            page.wait_for_timeout(int(delay))
        elif step[0] == "down":
            page.mouse.down()
            page.wait_for_timeout(int(step[1]))
        elif step[0] == "up":
            page.mouse.up()
            page.wait_for_timeout(int(step[1]))


def _attempt_once(page, attempt, debug_dir):
    els, ctx = _find_elements(page)
    if els["bg"]:
        box = els["bg"].bounding_box()
        png = els["bg"].screenshot()
        _log("background source: img/canvas element screenshot")
    elif els.get("bg_clip"):
        box = els["bg_clip"]
        png = page.screenshot(clip=box)
        _log("background source: div background-image region")
    else:
        _log("background image not found")
        return False
    if not box or box["width"] < 10:
        _log("invalid background region")
        return False
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        _log("failed to decode background screenshot")
        return False
    sh, sw = img.shape[:2]
    _log(f"background: {sw}x{sh}px screenshot, "
         f"{box['width']:.0f}x{box['height']:.0f}px on page")

    gap_x, method, bbox = detect_gap_x(img)
    if gap_x is None:
        _log("gap detection failed")
        _save_debug(debug_dir, attempt, img, None)
        return False
    y_band = (bbox[1], bbox[1] + bbox[3]) if bbox else None
    piece_left = detect_piece_left(img, y_band)
    _log(f"gap left x={gap_x}px (method={method}), "
         f"piece left x={piece_left}px")
    _save_debug(debug_dir, attempt, img, gap_x)

    # screenshot px -> css px -> track px
    scale = sw / box["width"]
    dist_img_css = (gap_x - piece_left) / scale
    track_box = els["track"].bounding_box() if els["track"] else None
    track_w = track_box["width"] if track_box else box["width"]
    if not els["track"]:
        _log("track element not found, estimating from image width")
    dist_track = dist_img_css * (track_w / box["width"])
    jitter = random.uniform(0.97, 1.03) if attempt > 1 else 1.0
    dist_track *= jitter
    _log(f"drag: {dist_img_css:.1f}px in image -> {dist_track:.1f}px on "
         f"track (jitter {jitter:.3f})")
    if dist_track < 20 or dist_track > track_w * 1.2:
        _log(f"unreasonable drag distance ({dist_track:.1f}px), skipping")
        return False

    if els["handle"]:
        hb = els["handle"].bounding_box()
        sx, sy = hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2
    elif track_box:
        sx, sy = track_box["x"] + 30, track_box["y"] + track_box["height"] / 2
    else:
        sx, sy = box["x"] + 30, box["y"] + box["height"] + 25
    _log(f"drag start ({sx:.0f}, {sy:.0f})")
    _run_trajectory(page, human_drag_trajectory(sx, sy, dist_track))

    page.wait_for_timeout(2500)
    if _is_solved(page):
        _log("verified!")
        return True
    _log("not solved this time")
    return False


def try_solve_slider(page, max_attempts=3, debug_dir=None):
    """Try to solve a slider captcha on a Playwright page.

    Args:
        page: sync Playwright Page with the captcha widget visible.
        max_attempts: max images to try (Refresh between attempts).
        debug_dir: where to save debug screenshots (default: cwd).

    Returns:
        True on success, False otherwise. Never raises for captcha
        failures — return False and let the caller fall back to manual.
    """
    if debug_dir is None:
        debug_dir = os.getcwd()
    for attempt in range(1, max_attempts + 1):
        _log(f"attempt {attempt}/{max_attempts}...")
        try:
            if _attempt_once(page, attempt, debug_dir):
                return True
        except Exception as e:
            _log(f"attempt raised: {str(e)[:150]}")
        if attempt < max_attempts:
            els, ctx = _find_elements(page)
            if not _click_refresh(ctx, els):
                _log("no Refresh button, stopping")
                break
            page.wait_for_timeout(2000)
    _log("auto-solve failed, hand back to caller")
    return False
