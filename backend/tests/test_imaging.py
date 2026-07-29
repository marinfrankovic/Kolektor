"""Detection, enhancement and hashing. No network, no tesseract binary required."""

from __future__ import annotations

import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.imaging.detect import apply_detection, detect, detect_banknote, detect_coin
from app.imaging.enhance import auto_enhance, deskew, estimate_skew, measure_blur, white_balance
from app.imaging.pipeline import hamming, load_oriented_bgr, phash, process_image
from tests.conftest import banknote_photo, coin_photo, encode_jpeg


class TestDetection:
    def test_coin_is_found_as_a_circle(self):
        detection = detect_coin(coin_photo())
        assert detection.shape == "circle"
        assert detection.circle is not None
        assert detection.confidence > 0.3

    def test_coin_circle_is_roughly_centred(self):
        detection = detect_coin(coin_photo(700))
        x, y, r = detection.circle
        assert 300 < x < 400
        assert 300 < y < 400
        assert 180 < r < 280

    def test_banknote_is_found_as_a_quad_or_box(self):
        detection = detect_banknote(banknote_photo())
        assert detection.shape in {"quad", "box"}
        assert detection.confidence > 0.3

    def test_blank_canvas_yields_no_detection(self):
        blank = np.full((400, 400, 3), 128, dtype=np.uint8)
        assert detect(blank, "coin", allow_rembg=False).shape == "none"

    def test_detection_serialises_to_a_dict(self):
        payload = detect(coin_photo(), "coin", allow_rembg=False).to_dict()
        assert payload["shape"] == "circle"
        assert isinstance(payload["confidence"], float)

    def test_apply_detection_crops_the_image(self):
        image = coin_photo(700)
        cropped = apply_detection(image, detect(image, "coin", allow_rembg=False))
        assert cropped.shape[0] < image.shape[0]
        assert cropped.shape[1] < image.shape[1]

    def test_apply_detection_keeps_a_margin_around_the_subject(self):
        image = coin_photo(700)
        detection = detect(image, "coin", allow_rembg=False)
        assert detection.circle is not None
        diameter = detection.circle[2] * 2
        cropped = apply_detection(image, detection)
        assert cropped.shape[1] > diameter * 1.1

    def test_apply_detection_is_a_no_op_without_a_detection(self):
        blank = np.full((300, 300, 3), 128, dtype=np.uint8)
        result = apply_detection(blank, detect(blank, "coin", allow_rembg=False))
        assert result.shape == blank.shape

    def test_banknote_warp_produces_a_landscape_crop(self):
        image = banknote_photo()
        cropped = apply_detection(image, detect(image, "banknote", allow_rembg=False))
        assert cropped.shape[1] > cropped.shape[0]


class TestEnhancement:
    def test_auto_enhance_preserves_shape_and_dtype(self):
        image = coin_photo()
        result, applied = auto_enhance(image, "coin")
        assert result.shape == image.shape
        assert result.dtype == np.uint8
        assert "blur_score" in applied

    def test_enhancement_is_recorded_for_reproducibility(self):
        _, applied = auto_enhance(banknote_photo(), "banknote")
        assert {"denoise", "clahe", "unsharp", "blur_score"} <= set(applied)

    def test_coins_are_not_deskewed(self):
        _, applied = auto_enhance(coin_photo(), "coin")
        assert "deskew_deg" not in applied

    def test_blur_score_drops_when_the_image_is_blurred(self):
        sharp = coin_photo()
        blurred = cv2.GaussianBlur(sharp, (15, 15), 0)
        assert measure_blur(blurred) < measure_blur(sharp)

    def test_skew_is_estimated_on_a_rotated_note(self):
        image = banknote_photo()
        matrix = cv2.getRotationMatrix2D((450, 300), 5.0, 1.0)
        rotated = cv2.warpAffine(image, matrix, (900, 600), borderValue=(30, 30, 30))
        assert abs(estimate_skew(rotated)) > 1.0

    def test_deskew_reduces_the_remaining_angle(self):
        image = banknote_photo()
        matrix = cv2.getRotationMatrix2D((450, 300), 6.0, 1.0)
        rotated = cv2.warpAffine(image, matrix, (900, 600), borderValue=(30, 30, 30))
        angle = estimate_skew(rotated)
        assert abs(angle) > 1.0
        straightened = deskew(rotated, angle)
        assert abs(estimate_skew(straightened)) < abs(angle)

    def test_white_balance_gains_are_clamped(self):
        # A heavy colour cast must not be "corrected" into a different metal tone.
        image = coin_photo()
        tinted = image.copy()
        tinted[:, :, 0] = np.clip(tinted[:, :, 0].astype(int) + 60, 0, 255)
        balanced = white_balance(tinted)
        assert abs(int(balanced.mean()) - int(tinted.mean())) < 40


class TestHashing:
    def test_identical_images_hash_identically(self):
        assert phash(coin_photo()) == phash(coin_photo())

    def test_hash_is_16_hex_characters(self):
        value = phash(coin_photo())
        assert len(value) == 16
        int(value, 16)

    def test_recompression_barely_changes_the_hash(self):
        original = coin_photo()
        recompressed = cv2.imdecode(
            np.frombuffer(encode_jpeg(original), np.uint8), cv2.IMREAD_COLOR
        )
        assert hamming(phash(original), phash(recompressed)) <= 6

    def test_different_subjects_hash_far_apart(self):
        assert hamming(phash(coin_photo()), phash(banknote_photo())) > 10


class TestLoading:
    def test_exif_orientation_is_applied(self, tmp_path):
        image = banknote_photo()
        path = tmp_path / "rotated.jpg"
        exif = Image.Exif()
        exif[0x0112] = 6  # rotate 90 CW
        Image.fromarray(image[:, :, ::-1]).save(path, format="JPEG", exif=exif)

        loaded = load_oriented_bgr(path)
        assert loaded.shape[0] > loaded.shape[1]

    def test_oversized_images_are_refused(self, tmp_path):
        path = tmp_path / "big.jpg"
        Image.fromarray(np.zeros((1200, 1200, 3), dtype=np.uint8)).save(path)
        with pytest.raises(ValueError, match="pixel budget"):
            load_oriented_bgr(path, max_megapixels=1)


class TestPipeline:
    def test_process_image_writes_all_derivatives(self, tmp_path):
        source = tmp_path / "coin.jpg"
        source.write_bytes(encode_jpeg(coin_photo()))

        result = process_image(
            source, tmp_path, "abc", "coin", autocrop=True, autoenhance=True, run_ocr=False
        )

        for key in ("display_path", "preview_path", "thumb_path"):
            assert result[key].exists()
        assert result["phash"]
        assert result["detection"]["shape"] == "circle"

    def test_thumb_is_smaller_than_the_preview(self, tmp_path):
        source = tmp_path / "coin.jpg"
        source.write_bytes(encode_jpeg(coin_photo()))
        result = process_image(
            source, tmp_path, "abc", "coin", autocrop=True, autoenhance=True, run_ocr=False
        )

        def side(path) -> int:
            with Image.open(path) as img:
                return max(img.size)

        assert side(result["thumb_path"]) < side(result["preview_path"])

    def test_original_is_never_modified(self, tmp_path):
        source = tmp_path / "coin.jpg"
        payload = encode_jpeg(coin_photo())
        source.write_bytes(payload)
        process_image(source, tmp_path, "abc", "coin", autocrop=True, autoenhance=True, run_ocr=False)
        assert source.read_bytes() == payload

    def test_autocrop_can_be_switched_off(self, tmp_path):
        source = tmp_path / "coin.jpg"
        source.write_bytes(encode_jpeg(coin_photo(700)))
        result = process_image(
            source, tmp_path, "abc", "coin", autocrop=False, autoenhance=False, run_ocr=False
        )
        assert "crop" not in result["transform"]
        assert result["width"] == 700

    def test_manual_transform_overrides_the_detection(self, tmp_path):
        source = tmp_path / "coin.jpg"
        source.write_bytes(encode_jpeg(coin_photo(700)))
        manual = {"detection": {"shape": "box", "box": [100, 100, 200, 200], "confidence": 1.0}}
        result = process_image(
            source,
            tmp_path,
            "abc",
            "coin",
            autocrop=True,
            autoenhance=False,
            run_ocr=False,
            manual_transform=manual,
        )
        assert result["width"] <= 270
        assert result["height"] <= 270

    def test_derivatives_carry_no_exif(self, tmp_path):
        source = tmp_path / "coin.jpg"
        exif = Image.Exif()
        exif[0x8825] = {1: "N"}
        Image.fromarray(coin_photo()[:, :, ::-1]).save(source, format="JPEG", exif=exif)

        result = process_image(
            source, tmp_path, "abc", "coin", autocrop=True, autoenhance=True, run_ocr=False
        )
        with Image.open(result["preview_path"]) as img:
            assert not img.getexif().get_ifd(0x8825)

    def test_corrupt_file_raises_a_clear_error(self, tmp_path):
        source = tmp_path / "broken.jpg"
        source.write_bytes(b"\xff\xd8\xff\xe0 not really a jpeg")
        with pytest.raises((ValueError, OSError)):
            process_image(
                source, tmp_path, "abc", "coin", autocrop=True, autoenhance=True, run_ocr=False
            )

    def test_png_with_alpha_is_handled(self, tmp_path):
        source = tmp_path / "coin.png"
        rgba = np.dstack([coin_photo(400), np.full((400, 400), 255, dtype=np.uint8)])
        buffer = io.BytesIO()
        Image.fromarray(rgba[:, :, [2, 1, 0, 3]], mode="RGBA").save(buffer, format="PNG")
        source.write_bytes(buffer.getvalue())
        result = process_image(
            source, tmp_path, "abc", "coin", autocrop=False, autoenhance=False, run_ocr=False
        )
        assert result["width"] > 0
