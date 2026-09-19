from app.services import imaging
from scripts.synth import PAPER, WARM_BULB, photo

TILE = (200, 120, 90)
# What the tile should measure once the paper is normalised to 240 grey.
TRUE_LAB = imaging.rgb_to_lab([c * 240 / p for c, p in zip(TILE, PAPER)])


def analyze(data, shot="color_reference"):
    return imaging.analyze(imaging.open_image(data), shot)


def test_white_sheet_cancels_warm_dim_lighting():
    data = photo(TILE, tint=WARM_BULB, exposure=0.75)
    corrected = analyze(data, "color_reference")
    raw = analyze(data, "surface_closeup")
    assert corrected["white_balanced"] and corrected["quality_ok"]
    assert imaging.delta_e(corrected["color_lab"], TRUE_LAB) < 3
    assert imaging.delta_e(raw["color_lab"], TRUE_LAB) > 10


def test_same_item_under_different_lights_matches():
    a = analyze(photo(TILE, tint=WARM_BULB, exposure=0.8, seed=1))
    b = analyze(photo(TILE, tint=(0.85, 0.93, 1.05), exposure=0.95, seed=2))
    assert imaging.delta_e(a["color_lab"], b["color_lab"]) < 3


def test_overexposed_white_sheet_asks_for_retake():
    r = analyze(photo(TILE, tint=(0.85, 0.93, 1.05), exposure=1.1))
    assert "white_clipped" in r["issues"] and not r["white_balanced"]


def test_quality_issues_are_flagged():
    assert "blurry" in analyze(photo(TILE, blur=True))["issues"]
    assert "too_small" in analyze(photo(TILE, size=(240, 180)))["issues"]
    assert "too_small" not in analyze(photo(TILE, size=(640, 480)))["issues"]   # typical web image is fine
    assert "too_dark" in analyze(photo(TILE, exposure=0.15))["issues"]
    assert "no_white_reference" in analyze(photo(TILE, paper=False))["issues"]


def test_white_item_is_not_called_overexposed():
    assert analyze(photo((238, 236, 232)), "surface_closeup")["quality_ok"]
