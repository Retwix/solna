"""Behaviour: the watcher's photo-processing rules (the V0 'process' step)."""
import io

from PIL import Image


def _img_bytes(size, mode="RGB", fmt="JPEG"):
    img = Image.new(mode, size, color=(120, 90, 60) if mode == "RGB" else (120, 90, 60, 255))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_thumbnail_is_downscaled_and_jpeg():
    """A large photo is downscaled to the thumbnail bound and re-encoded JPEG."""
    import process

    out = process._make_thumbnail(_img_bytes((3000, 2000)))
    thumb = Image.open(io.BytesIO(out))
    assert thumb.format == "JPEG"
    assert max(thumb.size) <= process.THUMB_MAX


def test_thumbnail_flattens_transparency_to_rgb():
    """A PNG with alpha is converted to RGB so it can be saved as JPEG."""
    import process

    out = process._make_thumbnail(_img_bytes((1000, 1000), mode="RGBA", fmt="PNG"))
    assert Image.open(io.BytesIO(out)).mode == "RGB"


def test_photographer_id_is_parsed_from_intake_path():
    """raw/{photographer_id}/<file> resolves to the account; files outside don't."""
    import process

    inside = process.RAW_ROOT / "ph-123" / "photo.jpg"
    assert process._photographer_id_from_path(inside) == "ph-123"

    loose = process.RAW_ROOT / "stray.jpg"  # no account folder
    assert process._photographer_id_from_path(loose) is None


def test_only_image_files_are_processed():
    """Non-image files (e.g. a stray .txt) are ignored by the watcher."""
    import process
    from pathlib import Path

    assert process._is_image(Path("a.JPG"))
    assert process._is_image(Path("a.png"))
    assert not process._is_image(Path("notes.txt"))
