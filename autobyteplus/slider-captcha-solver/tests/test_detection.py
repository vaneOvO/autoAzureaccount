"""Detection tests on synthetic captcha images. No browser needed."""
import cv2
import numpy as np
import pytest

from slider_captcha_solver import detect_gap_x, detect_piece_left
from slider_captcha_solver.trajectory import human_drag_trajectory


def make_image(with_white_border=True, seed=0, gap_x=210):
    rng = np.random.RandomState(seed)
    W, H = 340, 200
    bg = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        bg[y, :, 0] = 180 - y // 3
        bg[y, :, 1] = 200 - y // 4
        bg[y, :, 2] = 220 - y // 5
    bg = np.clip(bg.astype(np.int16) + rng.randint(-15, 15, (H, W, 3)),
                 0, 255).astype(np.uint8)
    # decoys: dark rectangle + circle (must not false-positive)
    cv2.rectangle(bg, (40, 120), (90, 170), (40, 50, 60), -1)
    cv2.circle(bg, (300, 40), 18, (50, 60, 70), -1)

    gx, gy, gw, gh = gap_x, 60, 52, 52
    cv2.rectangle(bg, (gx, gy), (gx + gw, gy + gh), (25, 25, 30), -1)
    if with_white_border:
        cv2.rectangle(bg, (gx, gy), (gx + gw, gy + gh), (255, 255, 255), 2)

    # piece at x=8 with white border
    px = 8
    cv2.rectangle(bg, (px, gy), (px + gw, gy + gh), (120, 150, 180), -1)
    if with_white_border:
        cv2.rectangle(bg, (px, gy), (px + gw, gy + gh), (255, 255, 255), 2)
    return bg, gx, px


@pytest.mark.parametrize("seed", range(5))
def test_gap_white_border(seed):
    img, gx, _ = make_image(with_white_border=True, seed=seed)
    x, method, bbox = detect_gap_x(img)
    assert x is not None, "gap not found"
    assert abs(x - gx) <= 4, f"gap x={x}, expected ~{gx}"
    assert method == "contour"


@pytest.mark.parametrize("seed", range(3))
def test_gap_no_border(seed):
    img, gx, _ = make_image(with_white_border=False, seed=seed)
    x, method, _ = detect_gap_x(img)
    assert x is not None, "gap not found"
    assert abs(x - gx) <= 6, f"gap x={x}, expected ~{gx}"


def test_piece_left():
    img, _, px = make_image(with_white_border=True)
    _, _, bbox = detect_gap_x(img)
    y_band = (bbox[1], bbox[1] + bbox[3]) if bbox else None
    pl = detect_piece_left(img, y_band)
    assert abs(pl - px) <= 6, f"piece x={pl}, expected ~{px}"


def test_trajectory_shape():
    traj = human_drag_trajectory(100, 200, 150, rng=__import__("random").Random(1))
    kinds = [s[0] for s in traj]
    assert kinds[0] == "move" and "down" in kinds and kinds[-1] == "up"
    moves = [s for s in traj if s[0] == "move"]
    # monotonic-ish progress with overshoot: max x exceeds target
    xs = [s[1] for s in moves[1:]]
    assert max(xs) > 100 + 150
    assert 45 <= len(traj) <= 90
