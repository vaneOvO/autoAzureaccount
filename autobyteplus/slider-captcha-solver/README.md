# slider-captcha-solver

Solve jigsaw **slider captchas** in browser automation: detect the gap, measure the puzzle piece position, and drag with a human-like trajectory that passes behavior-analysis scoring.

Validated end-to-end against the real **ByteDance Turing** slider captcha (`bdcaptcha.js`, used by BytePlus): the solver's drag was accepted by the live risk engine, closing the widget and letting the login proceed.

## How it works

```
screenshot bg element → detect gap x → detect piece left x
→ distance = gap − piece → human-like drag → verify → retry with Refresh
```

1. **Locate the widget** — searches inside the visible modal first, then iframes. Background image found via `img`/`canvas` element or CSS `background-image` div fallback.
2. **Detect the gap** — white-border contour first (Canny → largest near-square contour). Real captchas outline the gap in white; this is the most reliable signal. Falls back to widest dark-column run (never the first run — scenic photos false-positive on shadows).
3. **Detect the piece** — white-pixel column scan at the gap's height; **measured, never assumed at x=0**.
4. **Human drag** — sine acceleration/deceleration (fast middle, slow ends), ±2px jitter, 4–9px overshoot with pull-back, 45–75 steps. Monotonic ease-out drags get flagged as bots.
5. **Verify & retry** — up to 3 images via Refresh, then returns `False` for the caller to fall back to manual handling. Never infinite-loops.

## Install

```bash
pip install slider-captcha-solver[playwright]
playwright install chromium
```

For servers without a display, `opencv-python-headless` is used by default (no GUI libs needed).

## Quickstart

```python
from playwright.sync_api import sync_playwright
from slider_captcha_solver import try_solve_slider

with sync_playwright() as p:
    page = p.chromium.launch(headless=True).new_page()
    page.goto("https://example.com/login")
    # ... submit credentials until the captcha widget appears ...

    if try_solve_slider(page, max_attempts=3):
        print("solved!")
    else:
        print("needs manual handling")
```

Low-level API (framework-agnostic):

```python
from slider_captcha_solver import detect_gap_x, detect_piece_left, human_drag_trajectory
import cv2

img = cv2.imread("captcha_bg.png")
gap_x, method, bbox = detect_gap_x(img)          # ("contour"|"darkcol")
y_band = (bbox[1], bbox[1] + bbox[3]) if bbox else None
piece_x = detect_piece_left(img, y_band)
distance = gap_x - piece_x

for step in human_drag_trajectory(start_x, start_y, distance):
    # ("move", x, y, delay_ms) | ("down", delay_ms) | ("up", delay_ms)
    ...
```

## API

| Function | Description |
|---|---|
| `try_solve_slider(page, max_attempts=3, debug_dir=None)` | Full Playwright flow. Returns `True`/`False`, never raises on captcha failures. |
| `detect_gap_x(img_bgr)` | `(x, method, bbox)` — pure OpenCV, no browser needed. |
| `detect_piece_left(img_bgr, y_band=None)` | Piece left edge x in image pixels. |
| `human_drag_trajectory(sx, sy, dist, rng=None)` | Waypoint list for any automation framework. |

Debug screenshots (`slider_debug_attempt{N}.png`, red line = detected gap) are saved per attempt.

## Test results

- Synthetic captchas: gap detection ≤4px error across randomized images; decoy dark regions correctly ignored.
- Real ByteDance Turing images: gap located exactly (x=339 on 552px image).
- Live widget: drag accepted by the risk engine on the 2nd attempt (first attempt mis-detected the piece, Refresh + retry recovered — the designed resilience path).
- `pytest tests/` — no browser required.

## Notes

- Test trajectory scoring with **fake credentials**: captchas are validated before the password, so a fake login proves the drag passes with zero account risk.
- If the drag distance looks right but keeps failing, check `slider_debug_attempt*.png` first — 9 times out of 10 it's detection, not the trajectory.

## License

MIT
