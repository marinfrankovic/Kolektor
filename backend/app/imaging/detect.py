"""Subject detection. Every result is a proposal the user can accept, adjust or reject."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

MAX_WORK_PX = 1200


@dataclass
class Detection:
    method: str
    confidence: float
    shape: str  # circle | quad | box | none
    circle: tuple[float, float, float] | None = None
    quad: list[list[float]] | None = None
    box: tuple[float, float, float, float] | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "confidence": round(self.confidence, 3),
            "shape": self.shape,
            "circle": list(self.circle) if self.circle else None,
            "quad": self.quad,
            "box": list(self.box) if self.box else None,
            "notes": self.notes,
        }


def _work_copy(image: np.ndarray) -> tuple[np.ndarray, float]:
    h, w = image.shape[:2]
    scale = min(1.0, MAX_WORK_PX / max(h, w))
    if scale >= 1.0:
        return image, 1.0
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA), scale


def detect_coin(image: np.ndarray) -> Detection | None:
    work, scale = _work_copy(image)
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    h, w = gray.shape[:2]
    short = min(h, w)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=short // 2 or 1,
        param1=120,
        param2=60,
        minRadius=int(short * 0.18),
        maxRadius=int(short * 0.52),
    )
    if circles is None:
        return None

    found = np.round(circles[0]).astype(float)
    # Prefer the circle closest to the frame centre, tie-broken by radius.
    cx, cy = w / 2, h / 2
    best = min(found, key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cy) ** 2) ** 0.5 - c[2])
    x, y, r = (float(v) / scale for v in best)

    notes: list[str] = []
    if len(found) > 1:
        notes.append("multiple_circles")
    coverage = (2 * r) / (min(image.shape[:2]) or 1)
    confidence = 0.55 + min(0.35, coverage * 0.4) - (0.1 if len(found) > 1 else 0.0)
    if coverage > 0.98:
        notes.append("subject_fills_frame")

    return Detection("hough_circle", confidence, "circle", circle=(x, y, r), notes=notes)


def _order_quad(pts: np.ndarray) -> np.ndarray:
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32
    )


def detect_banknote(image: np.ndarray) -> Detection | None:
    work, scale = _work_copy(image)
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 60, 60)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    frame_area = float(work.shape[0] * work.shape[1])
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:6]
    notes: list[str] = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < frame_area * 0.08:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = _order_quad(approx.reshape(4, 2).astype(np.float32)) / scale
            confidence = 0.5 + min(0.4, area / frame_area * 0.5)
            return Detection(
                "contour_quad", confidence, "quad", quad=quad.tolist(), notes=notes
            )

    largest = contours[0]
    if cv2.contourArea(largest) < frame_area * 0.08:
        return None
    x, y, w, h = (float(v) / scale for v in cv2.boundingRect(largest))
    notes.append("fell_back_to_bounding_box")
    return Detection("contour_box", 0.35, "box", box=(x, y, w, h), notes=notes)


def detect_rembg(image: np.ndarray) -> Detection | None:
    """Alpha-matte fallback. Only available when the image was built with WITH_REMBG=true."""
    try:
        from rembg import remove  # noqa: PLC0415
    except ImportError:
        return None

    ok, buf = cv2.imencode(".png", image)
    if not ok:
        return None
    cut = remove(buf.tobytes())
    decoded = cv2.imdecode(np.frombuffer(cut, np.uint8), cv2.IMREAD_UNCHANGED)
    if decoded is None or decoded.shape[-1] != 4:
        return None

    alpha = decoded[:, :, 3]
    ys, xs = np.nonzero(alpha > 16)
    if ys.size == 0:
        return None
    x0, x1, y0, y1 = float(xs.min()), float(xs.max()), float(ys.min()), float(ys.max())
    return Detection(
        "rembg_alpha", 0.6, "box", box=(x0, y0, x1 - x0 + 1, y1 - y0 + 1), notes=["rembg"]
    )


def detect(image: np.ndarray, kind: str, allow_rembg: bool = False) -> Detection:
    candidate = detect_coin(image) if kind == "coin" else detect_banknote(image)
    if candidate is None and kind not in ("coin", "banknote"):
        candidate = detect_coin(image) or detect_banknote(image)
    if candidate is None and allow_rembg:
        candidate = detect_rembg(image)
    if candidate is None:
        return Detection("none", 0.0, "none", notes=["no_subject_found"])
    return candidate


def apply_detection(image: np.ndarray, detection: Detection, padding: float = 0.04) -> np.ndarray:
    h, w = image.shape[:2]

    if detection.shape == "circle" and detection.circle:
        x, y, r = detection.circle
        r = r * (1 + padding)
        x0, y0 = int(max(0, x - r)), int(max(0, y - r))
        x1, y1 = int(min(w, x + r)), int(min(h, y + r))
        return image[y0:y1, x0:x1].copy() if x1 > x0 and y1 > y0 else image

    if detection.shape == "quad" and detection.quad:
        src = np.array(detection.quad, dtype=np.float32)
        widths = [np.linalg.norm(src[0] - src[1]), np.linalg.norm(src[3] - src[2])]
        heights = [np.linalg.norm(src[0] - src[3]), np.linalg.norm(src[1] - src[2])]
        out_w, out_h = int(max(widths)), int(max(heights))
        if out_w < 16 or out_h < 16:
            return image
        dst = np.array(
            [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32
        )
        matrix = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(image, matrix, (out_w, out_h))

    if detection.shape == "box" and detection.box:
        bx, by, bw, bh = detection.box
        px, py = bw * padding, bh * padding
        x0, y0 = int(max(0, bx - px)), int(max(0, by - py))
        x1, y1 = int(min(w, bx + bw + px)), int(min(h, by + bh + py))
        return image[y0:y1, x0:x1].copy() if x1 > x0 and y1 > y0 else image

    return image
