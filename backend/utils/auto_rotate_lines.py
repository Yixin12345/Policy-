

"""

auto_rotate_lines.py — Detect whether a document/table image is sideways using ONLY line/edge structure

(no OCR, no admin-required installs).

Strategy (per rotation 0/90/180/270):

- Binarize & enhance line structures.

- Measure horizontal vs vertical "ink" via morphology (opening with long rect kernels).

- Measure horizontal vs vertical edge energy via gradient orientations.

- If structure scores are inconclusive, fall back to projection-profile variability (text baselines).

- Combine signals to choose the rotation that maximizes horizontal dominance.

- Optionally do a small deskew (±3°) around the best rotation.

Dependencies (pip, no admin needed):

    pip install --user opencv-python numpy

CLI examples:

    python auto_rotate_lines.py --in page.png --out corrected.png

    python auto_rotate_lines.py --in page.png --out corrected.png --headless --deskew 0

Programmatic:

    from auto_rotate_lines import choose_best_rotation

    angle, rotated, debug = choose_best_rotation(img_bgr)

"""

from __future__ import annotations

import argparse

import math

import os

from typing import Dict, Tuple, Any

import cv2

import numpy as np


# When gross-structure scores are nearly tied, use projection-profile fallback.
PROJECTION_UNCERTAINTY_MARGIN = 5e-4
PROJECTION_SELECTION_MARGIN = 1e-4

# Guardrails to avoid rotating when confidence is weak.
STRUCTURE_MIN_SCORE_DELTA = 1e-1
STRUCTURE_MIN_ABS_SCORE = 5e-2


def _ensure_bgr(img: np.ndarray) -> np.ndarray:

    if img is None:

        raise ValueError("Input image is None")

    if img.dtype != np.uint8:

        img = cv2.convertScaleAbs(img)

    if img.ndim == 2:

        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    if img.shape[2] == 4:

        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    return img


def _adaptive_block(h: int, w: int) -> int:

    # Choose an odd block size proportional to the smaller dimension

    b = max(15, (min(h, w) // 24) | 1)  # ensure odd

    if b % 2 == 0:

        b += 1

    return b


def _preprocess(gray: np.ndarray) -> np.ndarray:

    # Light denoise and adaptive threshold to highlight strokes/lines

    gray = cv2.bilateralFilter(gray, 7, 50, 50)

    block = _adaptive_block(*gray.shape)

    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,

                               cv2.THRESH_BINARY_INV, block, 10)

    return bw


def _line_ink_scores(bw: np.ndarray, min_len_ratio: float = 0.06) -> Tuple[float, float, Dict[str, Any]]:

    """

    Extract horizontal/vertical line ink using morphology (opening with long kernels).

    Returns (horiz_ink, vert_ink, debug).

    """

    h, w = bw.shape[:2]

    kx = max(10, int(min_len_ratio * w))

    ky = max(10, int(min_len_ratio * h))

    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kx, 1))

    vert_kernel  = cv2.getStructuringElement(cv2.MORPH_RECT, (1, ky))

    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horiz_kernel)

    vert  = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vert_kernel)

    horiz_ink = float(horiz.sum()) / 255.0

    vert_ink  = float(vert.sum()) / 255.0

    dbg = {

        "kx": kx, "ky": ky,

        "horiz_ink": horiz_ink,

        "vert_ink": vert_ink,

    }

    return horiz_ink, vert_ink, dbg


def _edge_orientation_scores(gray: np.ndarray) -> Tuple[float, float, Dict[str, Any]]:

    """

    Use Sobel gradients to estimate horizontal vs vertical edge energy.

    Horizontal lines produce gradients pointing vertically (~90°),

    Vertical lines produce gradients pointing horizontally (~0°).

    """

    gray_f = gray.astype(np.float32) / 255.0

    gx = cv2.Sobel(gray_f, cv2.CV_32F, 1, 0, ksize=3)

    gy = cv2.Sobel(gray_f, cv2.CV_32F, 0, 1, ksize=3)

    mag = np.sqrt(gx * gx + gy * gy) + 1e-6

    ang = (np.degrees(np.arctan2(gy, gx)) + 180.0) % 180.0  # 0..180

    # Weight by gradient magnitude; use broad bins around 0° (vertical lines) and 90° (horizontal lines)

    horiz_mask = (ang > 65) & (ang < 115)      # ~horizontal lines

    vert_mask  = (ang < 25) | (ang > 155)      # ~vertical lines

    horiz_energy = float(mag[horiz_mask].sum())

    vert_energy  = float(mag[vert_mask].sum())

    dbg = {

        "horiz_energy": horiz_energy,

        "vert_energy": vert_energy,

        "pixels_considered": int(mag.size),

    }

    return horiz_energy, vert_energy, dbg


def _projection_profile_scores(bw: np.ndarray) -> Tuple[float, float, Dict[str, Any]]:
    """Estimate orientation from projection profile variability.

    Horizontal text lines yield higher variance across row sums than column sums.
    """

    # Sum ink per row/column; normalise to [0, 1] by image area.
    row_profile = bw.sum(axis=1).astype(np.float32)
    col_profile = bw.sum(axis=0).astype(np.float32)

    row_norm = bw.shape[1] * 255.0 + 1e-6
    col_norm = bw.shape[0] * 255.0 + 1e-6

    row_profile /= row_norm
    col_profile /= col_norm

    # Measure variation (std deviation scaled to [0, 1]).
    row_std = float(np.std(row_profile))
    col_std = float(np.std(col_profile))

    total = row_std - col_std

    dbg = {
        "row_std": row_std,
        "col_std": col_std,
        "total": total,
    }

    return row_std, col_std, dbg


def _score_rotation(img_bgr: np.ndarray) -> Tuple[float, Dict[str, Any]]:

    """

    Score a single orientation: positive means more horizontally-structured content (good),

    negative means vertically-dominated (likely sideways).

    """

    img_bgr = _ensure_bgr(img_bgr)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    bw = _preprocess(gray)

    h_ink, v_ink, dbg_ink = _line_ink_scores(bw)

    h_eng, v_eng, dbg_eng = _edge_orientation_scores(gray)

    proj_h, proj_v, dbg_proj = _projection_profile_scores(bw)

    # Normalize by image area so results are comparable across sizes

    area = float(gray.shape[0] * gray.shape[1])

    h_ink_n = h_ink / area

    v_ink_n = v_ink / area

    h_eng_n = h_eng / area

    v_eng_n = v_eng / area

    # Combine cues (weights tuned to similar dynamic ranges)

    horiz_score = h_ink_n * 1.0 + h_eng_n * 0.6

    vert_score  = v_ink_n * 1.0 + v_eng_n * 0.6

    total = horiz_score - vert_score

    projection_total = proj_h - proj_v

    debug = {

        "area": area,

        "horiz_score": horiz_score,

        "vert_score": vert_score,

        "total": total,

        "ink": dbg_ink,

        "edge": dbg_eng,

        "projection": {

            **dbg_proj,

            "total": projection_total,

        },

    }

    return total, debug


def _rotate90(img_bgr: np.ndarray, angle: int) -> np.ndarray:

    angle %= 360

    if angle == 0:

        return img_bgr

    if angle == 90:

        return cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)

    if angle == 180:

        return cv2.rotate(img_bgr, cv2.ROTATE_180)

    if angle == 270:

        return cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)

    raise ValueError("Angle must be in {0,90,180,270}")


def _deskew_small(img_bgr: np.ndarray, max_deg: float = 3.0) -> Tuple[np.ndarray, float]:

    """

    Optional: small deskew after gross rotation using Hough lines.

    """

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    bw = _preprocess(gray)

    edges = cv2.Canny(bw, 80, 160)

    lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=max(100, int(min(img_bgr.shape[:2]) * 0.5)))

    if lines is None or len(lines) == 0:

        return img_bgr, 0.0

    # Convert to degrees around 0

    angles = []

    for rho_theta in lines[:256]:

        rho, theta = rho_theta[0]

        deg = (theta * 180.0 / np.pi) - 90.0  # make 0 ~ horizontal

        # Wrap to [-90, 90]

        if deg > 90: deg -= 180

        if deg < -90: deg += 180

        if abs(deg) <= max_deg:

            angles.append(deg)

    if not angles:

        return img_bgr, 0.0

    skew = float(np.median(angles))

    if abs(skew) < 0.1:

        return img_bgr, 0.0

    # Rotate by small angle (skimage not used; do it with OpenCV)

    h, w = gray.shape[:2]

    M = cv2.getRotationMatrix2D((w/2, h/2), skew, 1.0)

    rotated = cv2.warpAffine(img_bgr, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    return rotated, skew


def choose_best_rotation(

    img_bgr: np.ndarray,

    try_angles=(0, 90, 180, 270),

    do_deskew: bool = True,

    max_deskew_deg: float = 2.0,

) -> Tuple[int, np.ndarray, Dict[int, float], Dict[int, Dict[str, Any]]]:

    """

    Evaluate candidate rotations using structural cues with a projection-profile fallback.

    Returns:

        best_angle, best_img, score_by_angle, debug_by_angle

    """

    img_bgr = _ensure_bgr(img_bgr)

    score_by_angle: Dict[int, float] = {}

    debug_by_angle: Dict[int, Dict[str, Any]] = {}

    image_by_angle: Dict[int, np.ndarray] = {}

    best_angle = 0

    best_score = -1e9

    best_img = img_bgr

    for a in try_angles:

        rotated = _rotate90(img_bgr, a)

        image_by_angle[a] = rotated

        score, debug = _score_rotation(rotated)

        score_by_angle[a] = score

        debug_by_angle[a] = debug

        # Prefer upright (0/180) over sideways (90/270) on ties

        tie_bias = 0.0001 if a in (0, 180) else 0.0

        if (score + tie_bias) > best_score:

            best_score = score + tie_bias

            best_angle = a

            best_img = rotated

    sorted_scores = sorted(score_by_angle.items(), key=lambda item: item[1], reverse=True)

    fallback_used = False

    structure_margin = None

    projection_margin = None

    initial_best_angle = best_angle

    confidence_reason = None

    if len(sorted_scores) >= 2:

        structure_margin = sorted_scores[0][1] - sorted_scores[1][1]

        if structure_margin < PROJECTION_UNCERTAINTY_MARGIN:

            projection_scores = {

                angle: debug_by_angle[angle].get("projection", {}).get("total", 0.0)

                for angle in score_by_angle.keys()

            }

            if projection_scores:

                sorted_projection = sorted(projection_scores.items(), key=lambda item: item[1], reverse=True)

                projection_margin = sorted_projection[0][1] - (sorted_projection[1][1] if len(sorted_projection) > 1 else 0.0)

                if projection_margin > PROJECTION_SELECTION_MARGIN:

                    candidate_angle = sorted_projection[0][0]

                    if candidate_angle != best_angle:

                        best_angle = candidate_angle

                        best_img = image_by_angle[best_angle]

                        best_score = score_by_angle[best_angle]

                        fallback_used = True

    base_score = score_by_angle.get(0)

    if best_angle not in (0, 180) and base_score is not None:

        score_delta = best_score - base_score

        if best_score < STRUCTURE_MIN_ABS_SCORE:

            best_angle = 0

            best_img = image_by_angle[0]

            best_score = base_score

            confidence_reason = "low_absolute_score"

        elif score_delta < STRUCTURE_MIN_SCORE_DELTA:

            best_angle = 0

            best_img = image_by_angle[0]

            best_score = base_score

            confidence_reason = "insufficient_delta"

    if do_deskew:

        best_img, skew = _deskew_small(best_img, max_deg=max_deskew_deg)

        debug_by_angle[best_angle]["deskew_deg"] = skew

    selection_method = "projection" if fallback_used else "structure"

    raw_best_angle = best_angle

    # Normalize 180 to 0, 270 to -90 (optional)

    if best_angle == 180:

        best_angle = 0  # tables look the same; keep upright

    if best_angle == 270:

        best_angle = 90  # prefer clockwise for consistency

    debug_by_angle[-1] = {

        "selection_method": selection_method,

        "structure_margin": structure_margin,

        "projection_margin": projection_margin,

        "fallback_used": fallback_used,

        "structure_best_angle": initial_best_angle,

        "raw_best_angle": raw_best_angle,

        "normalized_best_angle": best_angle,

        "confidence_reason": confidence_reason,

    }

    return best_angle, best_img, score_by_angle, debug_by_angle


def _read_image(path: str) -> np.ndarray:

    img = cv2.imread(path, cv2.IMREAD_COLOR)

    if img is None:

        raise FileNotFoundError(f"Could not read image at: {path}")

    return img


def _write_image(path: str, img_bgr: np.ndarray) -> None:

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    ok = cv2.imwrite(path, img_bgr)

    if not ok:

        raise IOError(f"Failed to save image to: {path}")


def main():

    ap = argparse.ArgumentParser(description="Auto-rotate document/table image using line/edge analysis (no OCR).")

    ap.add_argument("--in", dest="inp", required=True, help="Input image path")

    ap.add_argument("--out", dest="out", required=True, help="Output corrected image path")

    ap.add_argument("--angles", default="0,90,180,270", help="Angles to try, e.g. '0,90,180,270'")

    ap.add_argument("--deskew", type=float, default=2.0, help="Max small deskew in degrees (set 0 to disable)")

    ap.add_argument("--headless", action="store_true", help="Use opencv-python-headless compatible flags (no effect, kept for convenience)")

    args = ap.parse_args()

    try_angles = tuple(int(x.strip()) for x in args.angles.split(",") if x.strip())

    img = _read_image(args.inp)

    do_deskew = args.deskew > 0.0

    best_angle, best_img, score_map, debug_map = choose_best_rotation(

        img, try_angles=try_angles, do_deskew=do_deskew, max_deskew_deg=float(args.deskew)

    )

    print(f"[INFO] Tried angles: {sorted(score_map.keys())}")

    for a in sorted(score_map.keys()):

        dbg = debug_map[a]

        ink = dbg["ink"]; edge = dbg["edge"]

        proj = dbg.get("projection", {})

        ds = dbg.get("deskew_deg", 0.0)

        print(f"  angle={a:>3}°  total={dbg['total']:+.4f}  "

              f"hInk={ink['horiz_ink']:.1f} vInk={ink['vert_ink']:.1f}  "

              f"hEng={edge['horiz_energy']:.1f} vEng={edge['vert_energy']:.1f}  "

              f"proj={proj.get('total', 0.0):+0.4f}  "

              f"deskew={ds:+.2f}°")

    meta = debug_map.get(-1, {})

    method = meta.get("selection_method", "structure")

    if method == "projection":

        print(

            f"[RESULT] Best gross rotation: {best_angle}° (projection fallback, "

            f"margin={meta.get('projection_margin', 0.0):+.4e})"

        )

    else:

        print(

            f"[RESULT] Best gross rotation: {best_angle}° "

            f"(structure margin={meta.get('structure_margin', 0.0):+.4e})"

        )

    if meta.get("confidence_reason"):

        print(f"[NOTE] Rotation suppressed due to {meta['confidence_reason']}")

    _write_image(args.out, best_img)

    print(f"[SAVED] -> {args.out}")


if __name__ == "__main__":

    main()
 