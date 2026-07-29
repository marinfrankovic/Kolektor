"""Conservative enhancement. Toning and true colour carry numismatic value, so every
step here is deliberately mild and the original file is never modified."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def measure_blur(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def estimate_skew(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    edges = cv2.Canny(gray, 60, 180)
    lines = cv2.HoughLines(edges, 1, np.pi / 360, threshold=max(80, min(gray.shape) // 4))
    if lines is None:
        return 0.0

    angles = []
    for rho_theta in lines[:60]:
        theta = float(rho_theta[0][1])
        deg = np.degrees(theta) - 90.0
        deg = (deg + 45) % 90 - 45
        if abs(deg) <= 12:
            angles.append(deg)
    return float(np.median(angles)) if angles else 0.0


def deskew(image: np.ndarray, angle: float) -> np.ndarray:
    if abs(angle) < 0.25:
        return image
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def white_balance(image: np.ndarray) -> np.ndarray:
    result = image.astype(np.float32)
    means = result.reshape(-1, 3).mean(axis=0)
    grey = float(means.mean())
    if grey <= 1e-6:
        return image
    for c in range(3):
        if means[c] > 1e-6:
            gain = np.clip(grey / means[c], 0.85, 1.18)
            result[:, :, c] *= gain
    return np.clip(result, 0, 255).astype(np.uint8)


def clahe_luminance(image: np.ndarray, clip: float = 1.4) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)
    lightness = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8)).apply(lightness)
    return cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2BGR)


def unsharp(image: np.ndarray, amount: float = 0.4, radius: int = 3) -> np.ndarray:
    blurred = cv2.GaussianBlur(image, (radius * 2 + 1, radius * 2 + 1), 0)
    return cv2.addWeighted(image, 1 + amount, blurred, -amount, 0)


def auto_enhance(image: np.ndarray, kind: str = "coin") -> tuple[np.ndarray, dict[str, Any]]:
    applied: dict[str, Any] = {}
    result = image

    if kind == "banknote":
        angle = estimate_skew(result)
        if abs(angle) >= 0.25:
            result = deskew(result, angle)
            applied["deskew_deg"] = round(angle, 2)

    balanced = white_balance(result)
    if not np.array_equal(balanced, result):
        applied["white_balance"] = "gray_world"
    result = balanced

    result = cv2.bilateralFilter(result, 5, 45, 45)
    applied["denoise"] = "bilateral"

    result = clahe_luminance(result, clip=1.4 if kind == "coin" else 1.8)
    applied["clahe"] = 1.4 if kind == "coin" else 1.8

    result = unsharp(result, amount=0.35 if kind == "coin" else 0.5)
    applied["unsharp"] = 0.35 if kind == "coin" else 0.5

    applied["blur_score"] = round(measure_blur(result), 1)
    return result, applied
