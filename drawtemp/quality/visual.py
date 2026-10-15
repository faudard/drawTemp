"""R14.5 visual regression primitives.

Explicit baselines only: a CI capture may be uploaded for review, but never
automatically accepted as its own golden. Qt is imported lazily for headless SDKs.
"""
from pathlib import Path


def compare_png(actual, baseline, *, max_channel_delta=12, max_changed_fraction=0.001,
                diff_path=None):
    """Compare RGBA pixels; ignore RGB on fully transparent pixels.

    Returns reproducible pixel statistics, independent of PNG encoder metadata.
    A missing/unreadable golden is an error, not a new approved baseline.
    """
    from PySide6.QtGui import QColor, QImage

    if not 0 <= max_channel_delta <= 255:
        raise ValueError("Channel tolerance must be in [0,255]")
    if not 0 <= max_changed_fraction <= 1:
        raise ValueError("Fraction tolerance must be in [0,1]")
    actual, baseline = Path(actual), Path(baseline)
    if not actual.is_file() or not baseline.is_file():
        raise FileNotFoundError("Missing actual image or approved golden")
    image_a, image_b = QImage(str(actual)), QImage(str(baseline))
    if image_a.isNull() or image_b.isNull():
        raise ValueError("Invalid PNG capture or golden")
    if image_a.size() != image_b.size():
        raise ValueError("Visual image dimensions differ")
    fmt = QImage.Format_RGBA8888
    image_a = image_a.convertToFormat(fmt)
    image_b = image_b.convertToFormat(fmt)
    width, height = image_a.width(), image_a.height()
    if width <= 0 or height <= 0:
        raise ValueError("Empty visual comparison")
    raw_a, raw_b = memoryview(image_a.constBits()), memoryview(image_b.constBits())
    stride_a, stride_b = image_a.bytesPerLine(), image_b.bytesPerLine()
    pixels = width * height
    changed = 0
    worst_delta = 0
    total_delta = 0
    heatmap = None
    if diff_path is not None:
        heatmap = QImage(width, height, QImage.Format_ARGB32)
        heatmap.fill(QColor("#101820"))
    for y in range(height):
        for x in range(width):
            off_a, off_b = y * stride_a + x * 4, y * stride_b + x * 4
            rgba_a = raw_a[off_a:off_a + 4]
            rgba_b = raw_b[off_b:off_b + 4]
            # Invisible texels are not perceptible: normalize RGB if alpha=0.
            if rgba_a[3] == rgba_b[3] == 0:
                delta = 0
            else:
                delta = max(abs(int(a) - int(b)) for a, b in zip(rgba_a, rgba_b))
            total_delta += delta
            worst_delta = max(worst_delta, delta)
            if delta > max_channel_delta:
                changed += 1
                if heatmap is not None:
                    heatmap.setPixelColor(x, y, QColor("#ff2852"))
    fraction = changed / pixels
    if heatmap is not None:
        destination = Path(diff_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not heatmap.save(str(destination), "PNG"):
            raise OSError("Unable to write pixel difference artifact")
    return {"width": width, "height": height, "pixels": pixels,
            "changed_pixels": changed, "changed_fraction": round(fraction, 8),
            "max_channel_delta": worst_delta,
            "mean_max_channel_delta": round(total_delta / pixels, 6),
            "tolerance": {"max_channel_delta": max_channel_delta,
                          "max_changed_fraction": max_changed_fraction},
            "passed": fraction <= max_changed_fraction}


def capture_widget(widget, destination):
    """Capture the real Qt Quick viewport; a null software frame is an error."""
    image = widget.grabFramebuffer()
    if image.isNull():
        raise RuntimeError("Qt viewport framebuffer capture was empty")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(destination), "PNG"):
        raise OSError("Unable to save Qt viewport capture")
    return {"path": str(destination), "width": image.width(),
            "height": image.height(), "device_pixel_ratio": image.devicePixelRatio()}
