import io

import numpy as np
import pytest
from PIL import Image

from sandbox import model

SAMPLE = "samples/normal_pa.jpg"


def png(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_center_crop_is_square_and_centred():
    gray = np.zeros((100, 60), dtype=np.uint8)
    gray[20:80, :] = 255
    out = model.center_crop(gray)
    assert out.shape == (60, 60)
    assert out.min() == 255


def test_read_grayscale_rejects_non_images():
    with pytest.raises(ValueError):
        model.read_grayscale(b"not an image")


def test_read_grayscale_rejects_huge_images():
    with pytest.raises(ValueError):
        model.read_grayscale(png(np.zeros((10, model.MAX_SIDE + 1), dtype=np.uint8)))


def test_analyse_returns_ranked_findings_and_overlay():
    result = model.analyse(open(SAMPLE, "rb").read())
    scores = [f.score for f in result.findings]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert result.cam_label == result.findings[0].label
    assert result.overlay_png.startswith(b"\x89PNG")


def test_analyse_honours_requested_cam_label():
    result = model.analyse(open(SAMPLE, "rb").read(), cam_label="Effusion")
    assert result.cam_label == "Effusion"


def test_model_has_no_tube_position_label():
    labels = " ".join(model.all_labels()).lower()
    assert "tube" not in labels and "catheter" not in labels
