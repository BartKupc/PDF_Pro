"""Encode a QImage to PNG bytes using Qt's QBuffer (not Python BytesIO).

QImage.save() accepts a filename or a QIODevice. Passing io.BytesIO raises
TypeError in PySide6 and silently kills signature/image placement.
"""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage


class QtImageEncodeError(RuntimeError):
    """QImage could not be encoded to PNG."""


def qimage_to_png_bytes(img: QImage) -> bytes:
    """Return PNG bytes for *img*. Never returns empty bytes; raises on failure."""
    if img is None or img.isNull():
        raise QtImageEncodeError("Cannot encode a null QImage to PNG")
    ba = QByteArray()
    qbuf = QBuffer(ba)
    if not qbuf.open(QIODevice.OpenModeFlag.WriteOnly):
        raise QtImageEncodeError("Could not open QBuffer to encode QImage")
    try:
        ok = img.save(qbuf, "PNG")
    finally:
        qbuf.close()
    if not ok:
        raise QtImageEncodeError("QImage.save returned False; PNG encode failed")
    png_bytes = bytes(ba)
    if not png_bytes:
        raise QtImageEncodeError("QImage.save produced empty PNG bytes")
    return png_bytes
