"""Main window: viewer, overlays, signatures, export."""

from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import Qt, QSize, Slot
from PySide6.QtGui import QAction, QFontDatabase, QIcon, QKeySequence, QPixmap, QImage, QColor
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from pdf_pro.constants import (
    APP_NAME,
    COVER_NOT_REDACTION,
    DEFAULT_ZOOM,
    EXISTING_SIGNATURE_WARNING,
    MAX_ZOOM,
    MIN_ZOOM,
    VISUAL_SIGNATURE_NOTICE,
)
from pdf_pro.document import (
    CorruptPdf,
    NeedsPassword,
    OpenedPdf,
    PdfError,
    UnsupportedPdf,
    WrongPassword,
    file_sha256,
    open_pdf,
    verify_source_untouched,
)
from pdf_pro.export import ExportError, assert_export_destination, default_export_path, export_pdf
from pdf_pro.fonts import BUNDLED_FAMILIES, font_path
from pdf_pro.overlay import (
    OverlayDocument,
    make_cover_replace,
    make_image,
    make_text,
    make_whiteout,
)
from pdf_pro.paths import icon_path
from pdf_pro.render_kind import KIND_PAGE, KIND_THUMB, destination
from pdf_pro.signature_feedback import place_signature_on_page
from pdf_pro.undo import UndoStack
from pdf_pro.ui.canvas import PageCanvas
from pdf_pro.ui.preview import PreviewDialog
from pdf_pro.ui.render_thread import RenderEngine, RenderThread
from pdf_pro.ui.signature_studio import SignatureStudio
from pdf_pro.vault import SignatureVault


def load_bundled_fonts() -> None:
    for family in BUNDLED_FAMILIES:
        path = font_path(family)
        if path.is_file():
            QFontDatabase.addApplicationFont(path.as_posix())
    bold = font_path("DejaVu Sans", bold=True)
    if bold.is_file():
        QFontDatabase.addApplicationFont(bold.as_posix())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        ic = icon_path(256)
        if ic.is_file():
            self.setWindowIcon(QIcon(str(ic)))
        self.resize(1200, 800)
        load_bundled_fonts()

        self.opened: OpenedPdf | None = None
        self.overlay = OverlayDocument()
        self.history = UndoStack(self.overlay)
        self.vault = SignatureVault()
        self._pending_signature = None
        self._pending_image_b64 = None
        self.current_page = 0
        self.zoom = DEFAULT_ZOOM

        self.canvas = PageCanvas()
        self.canvas.rubber_finished.connect(self._rubber)
        self.canvas.overlay_changed.connect(self._after_change)
        self.canvas.edit_starting.connect(self._checkpoint)
        self.canvas.text_edit_requested.connect(self._edit_text)

        self.thumbs = QListWidget()
        self.thumbs.setMaximumWidth(160)
        self.thumbs.setIconSize(QSize(120, 160))
        self.thumbs.currentRowChanged.connect(self._thumb_changed)

        split = QSplitter()
        split.addWidget(self.thumbs)
        split.addWidget(self.canvas)
        split.setStretchFactor(1, 1)

        self.banner = QLabel("")
        self.banner.setObjectName("warningBanner")
        self.banner.setWordWrap(True)
        self.banner.hide()

        self.sig_notice = QLabel(VISUAL_SIGNATURE_NOTICE)
        self.sig_notice.setObjectName("legalNotice")
        self.sig_notice.setWordWrap(True)

        self.cover_notice = QLabel(COVER_NOT_REDACTION)
        self.cover_notice.setObjectName("legalNotice")
        self.cover_notice.setWordWrap(True)

        central = QWidget()
        v = QVBoxLayout(central)
        v.addWidget(self.banner)
        v.addWidget(split, 1)
        v.addWidget(self.cover_notice)
        v.addWidget(self.sig_notice)
        self.setCentralWidget(central)

        self._build_toolbar()
        self.setStatusBar(QStatusBar())
        self._status("Open a PDF to begin. The source file is never overwritten.")

        self.engine = RenderEngine()
        self.render_thread = RenderThread(self.engine)
        self.engine.page_ready.connect(self._page_ready)
        self.engine.failed.connect(lambda m: self._status(m))
        self.render_thread.start()

        self.setAcceptDrops(True)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(name, slot, shortcut=None):
            a = QAction(name, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            tb.addAction(a)
            return a

        act("Open", self.open_dialog, "Ctrl+O")
        tb.addSeparator()
        act("Select", lambda: self.canvas.set_tool("select"))
        act("Add text", lambda: self.canvas.set_tool("text"))
        act("White-out", lambda: self.canvas.set_tool("whiteout"))
        act("Cover and replace", lambda: self.canvas.set_tool("cover"))
        act("Insert image", self._insert_image)
        act("Signature", self._signature)
        tb.addSeparator()
        self.font_box = QComboBox()
        self.font_box.addItems(BUNDLED_FAMILIES)
        tb.addWidget(QLabel(" Font "))
        tb.addWidget(self.font_box)
        self.size_box = QSpinBox()
        self.size_box.setRange(6, 96)
        self.size_box.setValue(12)
        tb.addWidget(self.size_box)
        self.bold_box = QCheckBox("Bold")
        tb.addWidget(self.bold_box)
        self.color_btn = QPushButton("Colour")
        self._color = "#000000"
        self.color_btn.clicked.connect(self._pick_color)
        tb.addWidget(self.color_btn)
        tb.addSeparator()
        act("Undo", self.undo, "Ctrl+Z")
        act("Redo", self.redo, "Ctrl+Shift+Z")
        tb.addSeparator()
        act("Prev", lambda: self.goto_page(self.current_page - 1))
        act("Next", lambda: self.goto_page(self.current_page + 1))
        self.page_label = QLabel("—")
        tb.addWidget(self.page_label)
        tb.addSeparator()
        act("Zoom +", lambda: self.set_zoom(self.zoom * 1.25), "Ctrl+=")
        act("Zoom −", lambda: self.set_zoom(self.zoom / 1.25), "Ctrl+-")
        act("Fit width", self.fit_width)
        act("Fit page", self.fit_page)
        act("Rotate view", self.rotate_view)
        tb.addSeparator()
        self.export_btn = QPushButton("Preview / Export")
        self.export_btn.setObjectName("primaryAction")
        self.export_btn.setMinimumHeight(36)
        self.export_btn.clicked.connect(self.export_flow)
        tb.addWidget(self.export_btn)
        export_act = QAction("Preview / Export", self)
        export_act.setShortcut(QKeySequence("Ctrl+E"))
        export_act.triggered.connect(self.export_flow)
        self.addAction(export_act)
        del_act = QAction("Delete", self)
        del_act.setShortcut(QKeySequence.Delete)
        del_act.triggered.connect(self.delete_selected)
        self.addAction(del_act)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self)
        if c.isValid():
            self._color = c.name()

    def _status(self, msg: str) -> None:
        self.statusBar().showMessage(msg)

    def _style(self) -> dict:
        return {
            "font_family": self.font_box.currentText(),
            "font_size": self.size_box.value(),
            "color": self._color,
            "bold": self.bold_box.isChecked(),
        }

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self.open_path(Path(path))
                return

    def closeEvent(self, event) -> None:
        self._close_doc()
        self.render_thread.quit()
        self.render_thread.wait(2000)
        super().closeEvent(event)

    def _close_doc(self) -> None:
        if self.opened:
            path = self.opened.path
            sha = self.opened.sha256
            self.opened.close()
            if not verify_source_untouched(path, sha):
                QMessageBox.warning(
                    self,
                    APP_NAME,
                    "The source file checksum changed while it was open. PDF_Pro never writes the source; another process may have modified it.",
                )
        self.opened = None
        self.overlay = OverlayDocument()
        self.history.close_document()
        self.history.bind(self.overlay)
        self.thumbs.clear()
        self.banner.hide()

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF files (*.pdf)")
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path, password: str | None = None) -> None:
        self._close_doc()
        try:
            opened = open_pdf(path, password=password)
        except NeedsPassword:
            pw, ok = QInputDialog.getText(
                self, APP_NAME, "This PDF is password-protected. Enter the user password:", echo=QLineEditEcho()
            )
            if not ok:
                return
            return self.open_path(path, password=pw)
        except WrongPassword as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        except (CorruptPdf, UnsupportedPdf, PdfError) as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self.opened = opened
        self.overlay = OverlayDocument(
            source_path=str(opened.path),
            source_sha256=opened.sha256,
            page_count=opened.page_count,
        )
        self.history.bind(self.overlay)
        self.canvas.bind_overlay(self.overlay)
        self.engine.set_doc(opened)
        self.current_page = 0
        self._fill_thumbs()
        self.goto_page(0)
        if opened.has_digital_signature:
            self.banner.setText(EXISTING_SIGNATURE_WARNING)
            self.banner.show()
            QMessageBox.warning(self, APP_NAME, EXISTING_SIGNATURE_WARNING)
        self._status(f"Opened {opened.path.name} (read-only). {opened.page_count} pages.")

    def _fill_thumbs(self) -> None:
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        if not self.opened:
            self.thumbs.blockSignals(False)
            return
        for i in range(self.opened.page_count):
            item = QListWidgetItem(f"{i + 1}")
            self.thumbs.addItem(item)
            # progressive: request low-res later
        self.thumbs.blockSignals(False)
        # kick thumbnail renders
        for i in range(self.opened.page_count):
            self.engine.request.emit(i, 0.2, KIND_THUMB)

    def _thumb_changed(self, row: int) -> None:
        if row >= 0:
            self.goto_page(row)

    def goto_page(self, index: int) -> None:
        if not self.opened:
            return
        index = max(0, min(self.opened.page_count - 1, index))
        self.current_page = index
        self.canvas.page_index = index
        self.page_label.setText(f" {index + 1} / {self.opened.page_count} ")
        self.thumbs.blockSignals(True)
        self.thumbs.setCurrentRow(index)
        self.thumbs.blockSignals(False)
        self._request_page()

    def _request_page(self) -> None:
        if not self.opened:
            return
        self.engine.request.emit(self.current_page, self.zoom, KIND_PAGE)
        if self.current_page + 1 < self.opened.page_count:
            self.engine.request.emit(self.current_page + 1, self.zoom, KIND_PAGE)
        if self.current_page > 0:
            self.engine.request.emit(self.current_page - 1, self.zoom, KIND_PAGE)

    @Slot(int, float, QImage, float, float, str)
    def _page_ready(self, index: int, scale: float, image: QImage, w: float, h: float, kind: str = KIND_PAGE) -> None:
        if destination(kind, scale) == "thumbnail":
            # thumbnail
            if 0 <= index < self.thumbs.count():
                pix = QPixmap.fromImage(image).scaled(120, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumbs.item(index).setIcon(QIcon(pix))
            return
        if index == self.current_page and abs(scale - self.zoom) < 0.01:
            self.canvas.zoom = self.zoom
            self.canvas.set_page_image(image, w, h, scale)

    def set_zoom(self, z: float) -> None:
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, z))
        self.canvas.zoom = self.zoom
        self._request_page()

    def fit_width(self) -> None:
        if not self.opened:
            return
        w, _ = self.opened.page_size(self.current_page)
        vw = max(100, self.canvas.viewport().width() - 20)
        self.set_zoom(vw / w)

    def fit_page(self) -> None:
        if not self.opened:
            return
        w, h = self.opened.page_size(self.current_page)
        vw = max(100, self.canvas.viewport().width() - 20)
        vh = max(100, self.canvas.viewport().height() - 20)
        self.set_zoom(min(vw / w, vh / h))

    def rotate_view(self) -> None:
        self.canvas.view_rotation = (self.canvas.view_rotation + 90) % 360
        self.canvas.apply_view_rotation()

    def _rubber(self, x, y, w, h) -> None:
        if not self.opened:
            return
        tool = self.canvas._tool
        style = self._style()
        self.history.checkpoint()
        if tool == "text":
            self.overlay.add(
                make_text(self.current_page, x, y, w, h, text="Text", **style)
            )
        elif tool == "whiteout":
            self.overlay.add(make_whiteout(self.current_page, x, y, w, h))
        elif tool == "cover":
            self.overlay.add(make_cover_replace(self.current_page, x, y, w, h, text="", **style))
        self.canvas.bind_overlay(self.overlay)
        self.canvas.set_tool("select")
        self._after_change()

    def _insert_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Insert image", "", "Images (*.png *.jpg *.jpeg)")
        if not path or not self.opened:
            return
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, APP_NAME, "Could not read that image.")
            return
        img = pix.toImage()
        from io import BytesIO

        buf = BytesIO()
        img.save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        pw, ph = self.opened.page_size(self.current_page)
        width = min(200, pw * 0.4)
        height = width * (pix.height() / max(1, pix.width()))
        self.history.checkpoint()
        self.overlay.add(
            make_image(self.current_page, 72, 72, width, height, png_b64=b64, aspect_lock=True)
        )
        self.canvas.bind_overlay(self.overlay)
        self._after_change()

    def _signature(self) -> None:
        dlg = SignatureStudio(self.vault, self)
        if dlg.exec() != dlg.Accepted or not dlg.result_asset:
            return
        if not self.opened:
            QMessageBox.information(self, APP_NAME, "Open a PDF first, then place the signature.")
            return
        asset = dlg.result_asset
        pw, ph = self.opened.page_size(self.current_page)
        self.history.checkpoint()
        place_signature_on_page(self.overlay, asset, self.current_page, pw, ph)
        self.canvas.page_index = self.current_page
        self.canvas.bind_overlay(self.overlay)
        self.canvas.viewport().update()
        self._after_change()
        self._status("Signature placed on this page.")

    def delete_selected(self) -> None:
        item = self.canvas.selected_item()
        if not item:
            return
        self.history.checkpoint()
        self.overlay.remove(item.id)
        self.canvas.bind_overlay(self.overlay)
        self._after_change()

    def _checkpoint(self) -> None:
        self.history.checkpoint()

    def _edit_text(self, item_id: str) -> None:
        item = self.overlay.get(item_id)
        if not item or item.type not in ("text", "cover_replace"):
            return
        current = str((item.data or {}).get("text") or "")
        text, ok = QInputDialog.getMultiLineText(self, APP_NAME, "Replacement / text box:", current)
        if not ok:
            return
        self.history.checkpoint()
        item.data["text"] = text
        self.canvas.bind_overlay(self.overlay)
        self._after_change()

    def undo(self) -> None:
        if self.history.undo():
            self.canvas.bind_overlay(self.overlay)
            self._after_change()

    def redo(self) -> None:
        if self.history.redo():
            self.canvas.bind_overlay(self.overlay)
            self._after_change()

    def _after_change(self) -> None:
        n = len(self.overlay.items)
        extra = ""
        if self.overlay.has_cover_replace():
            extra = "  " + COVER_NOT_REDACTION
        self._status(f"{n} overlay(s). Source stays read-only.{extra}")

    def export_flow(self) -> None:
        if not self.opened:
            QMessageBox.information(self, APP_NAME, "Open a PDF first.")
            return
        try:
            preview = PreviewDialog(self.opened.path, self.overlay, self.opened.password, self)
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"Could not start preview.\nReason: {exc}")
            return
        if preview.exec() != preview.Accepted or not preview.ok:
            return
        dest_default = default_export_path(self.opened.path, self.overlay)
        dest_str, _ = QFileDialog.getSaveFileName(
            self, "Export flattened PDF", str(dest_default), "PDF files (*.pdf)"
        )
        if not dest_str:
            return
        dest = Path(dest_str)
        try:
            dest = assert_export_destination(self.opened.path, dest)
            export_pdf(self.opened.path, self.overlay, dest, password=self.opened.password)
        except ExportError as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(
                self, APP_NAME, f"Could not write export.\nReason: {exc}\nPath: {dest}"
            )
            return
        except Exception as exc:
            QMessageBox.critical(
                self, APP_NAME, f"Export failed.\nReason: {exc}\nPath: {dest}"
            )
            return
        if not verify_source_untouched(self.opened.path, self.opened.sha256):
            QMessageBox.critical(self, APP_NAME, "Source checksum changed — export may be unsafe.")
            return
        QMessageBox.information(self, APP_NAME, f"Exported to {dest}\nSource file is unchanged.")


def QLineEditEcho():
    from PySide6.QtWidgets import QLineEdit

    return QLineEdit.Password
