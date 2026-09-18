"""Main window: multi-doc tabs, ribbon, overlays, signatures, export."""

from __future__ import annotations

import base64
from datetime import date
from io import BytesIO
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, Slot, QEventLoop
from PySide6.QtGui import QAction, QFontDatabase, QIcon, QKeySequence, QPixmap, QImage, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
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
from pdf_pro.content_scan import scan_fitz_doc
from pdf_pro.document import (
    CorruptPdf,
    NeedsPassword,
    PdfError,
    UnsupportedPdf,
    WrongPassword,
    open_pdf,
    verify_source_untouched,
)
from pdf_pro.drafts import (
    MissingSource,
    clear_clean_exit,
    mark_clean_exit,
    open_draft,
    recover_unsaved,
    save_draft,
)
from pdf_pro.export import ExportError, default_export_path, export_pdf
from pdf_pro.export_session import complete_export, open_containing_folder
from pdf_pro.fonts import BUNDLED_FAMILIES, font_path
from pdf_pro.history import WIPE_NOTICE, load_history, record_export, wipe_local_data
from pdf_pro.overlay import (
    OverlayDocument,
    make_cover_replace,
    make_image,
    make_shape,
    make_text,
    make_whiteout,
)
from pdf_pro.overlay_ops import bring_to_front, duplicate_item, rotate_item, send_to_back
from pdf_pro.page_plan import PagePlan
from pdf_pro.paths import icon_path
from pdf_pro.render_kind import KIND_PAGE, KIND_THUMB, destination
from pdf_pro.ribbon_spec import ACTIONS, SHORTCUTS
from pdf_pro.search import copy_text_from_hits, search_fitz_doc
from pdf_pro.session import DocumentSession
from pdf_pro.signature_feedback import find_initials_asset, place_signature_on_page
from pdf_pro.ui.document_pane import DocumentPane
from pdf_pro.ui.file_dialogs import get_open_file_name, get_save_file_name
from pdf_pro.ui.preview import PreviewDialog
from pdf_pro.ui.render_thread import RenderEngine, RenderThread
from pdf_pro.ui.ribbon import RibbonBar
from pdf_pro.ui.signature_studio import SignatureStudio
from pdf_pro.ui.workers import ExportWorker
from pdf_pro.vault import SignatureVault


def load_bundled_fonts() -> None:
    for family in BUNDLED_FAMILIES:
        path = font_path(family)
        if path.is_file():
            QFontDatabase.addApplicationFont(path.as_posix())
    bold = font_path("DejaVu Sans", bold=True)
    if bold.is_file():
        QFontDatabase.addApplicationFont(bold.as_posix())


def QLineEditEcho():
    from PySide6.QtWidgets import QLineEdit as _LE

    return _LE.Password


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        ic = icon_path(256)
        if ic.is_file():
            self.setWindowIcon(QIcon(str(ic)))
        self.resize(1200, 800)
        load_bundled_fonts()

        self.vault = SignatureVault()
        self._color = "#000000"

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

        self.tabs = QTabWidget()
        self.tabs.setObjectName("docTabs")
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabCloseRequested.connect(self._close_tab)

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self._build_ribbon()
        v.addWidget(self.ribbon)
        v.addWidget(self.banner)
        v.addWidget(self.tabs, 1)
        v.addWidget(self.cover_notice)
        v.addWidget(self.sig_notice)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self._status("Open a PDF to begin. The source file is never overwritten.")

        self.engine = RenderEngine()
        self.render_thread = RenderThread(self.engine)
        self.engine.page_ready.connect(self._page_ready)
        self.engine.failed.connect(lambda m: self._status(m))
        self.render_thread.start()

        self.setAcceptDrops(True)
        self._autosave = QTimer(self)
        self._autosave.setInterval(30_000)
        self._autosave.timeout.connect(self._autosave_tick)
        self._autosave.start()
        QTimer.singleShot(400, self._offer_recovery)

    # --- active document ---
    def pane(self) -> DocumentPane | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, DocumentPane) else None

    @property
    def opened(self):
        p = self.pane()
        return None if p is None else p.session.opened

    @property
    def overlay(self):
        p = self.pane()
        return OverlayDocument() if p is None else p.session.overlay

    @property
    def history(self):
        p = self.pane()
        return None if p is None else p.session.undo

    @property
    def canvas(self):
        p = self.pane()
        return None if p is None else p.canvas

    @property
    def current_page(self) -> int:
        p = self.pane()
        return 0 if p is None else p.session.current_page

    @current_page.setter
    def current_page(self, value: int) -> None:
        p = self.pane()
        if p is not None:
            p.session.current_page = int(value)

    @property
    def zoom(self) -> float:
        p = self.pane()
        return DEFAULT_ZOOM if p is None else p.session.zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        p = self.pane()
        if p is not None:
            p.session.zoom = float(value)

    def _build_ribbon(self) -> None:
        self.page_label = QLabel("—")
        self.font_box = QComboBox()
        self.font_box.addItems(BUNDLED_FAMILIES)
        self.font_box.setMaximumWidth(120)
        self.size_box = QSpinBox()
        self.size_box.setRange(6, 96)
        self.size_box.setValue(12)
        self.size_box.setMaximumWidth(60)
        self.bold_box = QCheckBox("B")
        self.italic_box = QCheckBox("I")
        self.underline_box = QCheckBox("U")
        self.align_box = QComboBox()
        self.align_box.addItems(["left", "center", "right"])
        self.align_box.setMaximumWidth(80)
        self.color_btn = QPushButton("Colour")
        self.color_btn.clicked.connect(self._pick_color)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Find")
        self.search_box.setMaximumWidth(140)
        self.search_box.returnPressed.connect(self._find_next)
        self.sig_date = QLineEdit()
        self.sig_date.setPlaceholderText("Date")
        self.sig_date.setText(date.today().isoformat())
        self.sig_date.setMaximumWidth(100)
        self.sig_label = QLineEdit()
        self.sig_label.setPlaceholderText("Name")
        self.sig_label.setMaximumWidth(100)
        extras = {
            "page_label": self.page_label,
            "font": self.font_box,
            "size": self.size_box,
            "bold": self.bold_box,
            "italic": self.italic_box,
            "underline": self.underline_box,
            "align": self.align_box,
            "colour": self.color_btn,
            "search_box": self.search_box,
            "sig_date": self.sig_date,
            "sig_label": self.sig_label,
        }
        self.ribbon = RibbonBar()
        self.ribbon.populate(ACTIONS, extras)
        self._bind_ribbon()
        self._install_shortcuts()
        self.ribbon.currentChanged.connect(lambda *_: self._refresh_initials_button())
        self._refresh_initials_button()

    def _bind_ribbon(self) -> None:
        w = self.ribbon.widgets

        def on(aid, slot):
            w[aid].clicked.connect(lambda *_a, s=slot: s())

        on("open", self.open_dialog)
        on("drafts", self._show_drafts)
        on("history", self._show_history)
        on("wipe", self._wipe)
        on("find_prev", self._find_prev)
        on("find_next", self._find_next)
        on("copy_hit", self._copy_hit)
        on("select", lambda: self._set_tool("select"))
        on("add_text", lambda: self._set_tool("text"))
        on("whiteout", lambda: self._set_tool("whiteout"))
        on("cover_replace", lambda: self._set_tool("cover"))
        on("insert_image", self._insert_image)
        for kind, aid in (
            ("rect", "shape_rect"),
            ("line", "shape_line"),
            ("arrow", "shape_arrow"),
            ("ellipse", "shape_ellipse"),
            ("highlight", "shape_highlight"),
            ("underline", "shape_underline"),
            ("strike", "shape_strike"),
            ("pen", "shape_pen"),
        ):
            on(aid, lambda k=kind: self._set_tool(k))
        on("undo", self.undo)
        on("redo", self.redo)
        on("rotate_item", self._rotate_selected)
        on("duplicate_item", self._duplicate_selected)
        on("bring_front", self._bring_front)
        on("send_back", self._send_back)
        on("prev", lambda: self.goto_page(self.current_page - 1))
        on("next", lambda: self.goto_page(self.current_page + 1))
        on("zoom_in", lambda: self.set_zoom(self.zoom * 1.25))
        on("zoom_out", lambda: self.set_zoom(self.zoom / 1.25))
        on("fit_width", self.fit_width)
        on("fit_page", self.fit_page)
        on("rotate_view", self.rotate_view)
        on("page_rotate", self._page_rotate)
        on("page_delete", self._page_delete)
        on("page_duplicate", self._page_duplicate)
        on("page_up", lambda: self._page_move(-1))
        on("page_down", lambda: self._page_move(1))
        on("page_extract", self._page_extract)
        on("page_merge", self._page_merge)
        on("draw_signature", lambda: self._signature(0))
        on("type_signature", lambda: self._signature(1))
        on("upload_signature", lambda: self._signature(2))
        on("vault", lambda: self._signature(3))
        on("place_initials", self._place_initials)
        on("preview_export", self.export_flow)
        self.export_btn = w["preview_export"]

    def _install_shortcuts(self) -> None:
        slots = {
            "open": self.open_dialog,
            "undo": self.undo,
            "redo": self.redo,
            "zoom_in": lambda: self.set_zoom(self.zoom * 1.25),
            "zoom_out": lambda: self.set_zoom(self.zoom / 1.25),
            "preview_export": self.export_flow,
            "delete": self.delete_selected,
            "find": lambda: self.search_box.setFocus(),
        }
        for aid, slot in slots.items():
            seq = SHORTCUTS[aid]
            action = QAction(aid, self)
            if seq == "Delete":
                action.setShortcut(QKeySequence.Delete)
            else:
                action.setShortcut(QKeySequence(seq))
            action.triggered.connect(lambda *_a, s=slot: s())
            self.addAction(action)

    def _set_tool(self, tool: str) -> None:
        p = self.pane()
        if p:
            p.canvas.set_tool(tool)

    def _refresh_initials_button(self) -> None:
        btn = self.ribbon.widgets.get("place_initials")
        if btn is None:
            return
        present = find_initials_asset(self.vault) is not None
        btn.setVisible(present)
        btn.setEnabled(present)

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
            "italic": self.italic_box.isChecked(),
            "underline": self.underline_box.isChecked(),
            "align": self.align_box.currentText(),
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
        for i in range(self.tabs.count()):
            pane = self.tabs.widget(i)
            if isinstance(pane, DocumentPane) and pane.session.dirty:
                try:
                    save_draft(pane.session.overlay, pane.session.plan, dirty=True)
                except Exception:
                    pass
        mark_clean_exit()
        self.render_thread.quit()
        self.render_thread.wait(2000)
        super().closeEvent(event)

    def open_dialog(self) -> None:
        path, _ = get_open_file_name(self, "Open PDF", "", "PDF files (*.pdf)")
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path, password: str | None = None, *, plan=None, overlay=None) -> None:
        try:
            opened = open_pdf(path, password=password)
        except NeedsPassword:
            pw, ok = QInputDialog.getText(
                self, APP_NAME, "This PDF is password-protected. Enter the user password:", echo=QLineEditEcho()
            )
            if not ok:
                return
            return self.open_path(path, password=pw, plan=plan, overlay=overlay)
        except WrongPassword as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        except (CorruptPdf, UnsupportedPdf, PdfError) as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        sess = DocumentSession(
            source_path=str(opened.path),
            source_sha256=opened.sha256,
            page_count=opened.page_count,
            overlay=overlay,
            plan=plan or PagePlan.identity(str(opened.path), opened.page_count),
            opened=opened,
        )
        if overlay is None:
            sess.overlay.source_path = str(opened.path)
            sess.overlay.source_sha256 = opened.sha256
            sess.overlay.page_count = len(sess.plan)
        pane = DocumentPane(sess, self)
        pane.canvas.rubber_finished.connect(self._rubber)
        pane.canvas.freehand_finished.connect(self._freehand)
        pane.canvas.overlay_changed.connect(self._after_change)
        pane.canvas.edit_starting.connect(self._checkpoint)
        pane.canvas.text_edit_requested.connect(self._edit_text)
        pane.thumb_chosen.connect(self.goto_page)
        idx = self.tabs.addTab(pane, pane.title())
        self.tabs.setCurrentIndex(idx)
        self.engine.set_doc(opened)
        self._fill_thumbs()
        self.goto_page(0)
        self._apply_warnings(opened)
        if opened.has_digital_signature:
            self.banner.setText(EXISTING_SIGNATURE_WARNING)
            self.banner.show()
            QMessageBox.warning(self, APP_NAME, EXISTING_SIGNATURE_WARNING)
        else:
            self.banner.hide()
        self._status(f"Opened {opened.path.name} (read-only). {len(sess.plan)} pages.")
        clear_clean_exit()

    def _apply_warnings(self, opened) -> None:
        try:
            warns = scan_fitz_doc(opened.fitz_doc)
        except Exception:
            return
        scans = [w for w in warns if w.kind == "scan"]
        fonts = [w for w in warns if w.kind == "font"]
        bits = []
        if scans:
            bits.append(f"Scan-only page(s): {', '.join(str(w.page + 1) for w in scans)}.")
        if fonts:
            bits.append(fonts[0].message)
        if bits:
            self.banner.setText(" ".join(bits))
            self.banner.show()

    def _tab_changed(self, _index: int) -> None:
        p = self.pane()
        if p is None:
            self.engine.set_doc(None)
            return
        self.engine.set_doc(p.session.opened)
        self.goto_page(p.session.current_page)
        self._refresh_tab_titles()

    def _close_tab(self, index: int) -> None:
        pane = self.tabs.widget(index)
        if not isinstance(pane, DocumentPane):
            return
        sess = pane.session
        if sess.dirty:
            try:
                save_draft(sess.overlay, sess.plan, dirty=True)
            except Exception:
                pass
        if sess.opened:
            path = sess.opened.path
            sha = sess.opened.sha256
            sess.close()
            if not verify_source_untouched(path, sha):
                QMessageBox.warning(
                    self,
                    APP_NAME,
                    "The source file checksum changed while it was open. PDF_Pro never writes the source; another process may have modified it.",
                )
        self.tabs.removeTab(index)
        pane.deleteLater()

    def _fill_thumbs(self) -> None:
        p = self.pane()
        if not p or not p.session.opened:
            return
        n = len(p.session.plan)
        p.fill_thumbs(n)
        for i in range(n):
            self.engine.request.emit(i, 0.2, KIND_THUMB)

    def goto_page(self, index: int) -> None:
        p = self.pane()
        if not p or not p.session.opened:
            return
        n = max(1, len(p.session.plan))
        index = max(0, min(n - 1, index))
        p.session.current_page = index
        p.canvas.page_index = index
        self.page_label.setText(f" {index + 1} / {n} ")
        p.thumbs.blockSignals(True)
        p.thumbs.setCurrentRow(index)
        p.thumbs.blockSignals(False)
        self._request_page()
        self._apply_search_highlights()

    def _request_page(self) -> None:
        p = self.pane()
        if not p or not p.session.opened:
            return
        self.engine.set_doc(p.session.opened)
        # Render the source page of the logical plan entry.
        ref = p.session.plan.pages[p.session.current_page]
        self.engine.request.emit(ref.source_index, p.session.zoom, KIND_PAGE)

    @Slot(int, float, QImage, float, float, str)
    def _page_ready(self, index: int, scale: float, image: QImage, w: float, h: float, kind: str = KIND_PAGE) -> None:
        p = self.pane()
        if p is None:
            return
        if destination(kind, scale) == "thumbnail":
            # thumbs are logical pages; skip mismatched
            if 0 <= index < p.thumbs.count():
                pix = QPixmap.fromImage(image).scaled(120, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item = p.thumbs.item(index)
                if item:
                    item.setIcon(QIcon(pix))
            return
        ref = p.session.plan.pages[p.session.current_page] if p.session.plan.pages else None
        if ref and index == ref.source_index and abs(scale - p.session.zoom) < 0.01:
            p.canvas.zoom = p.session.zoom
            p.canvas.set_page_image(image, w, h, scale)

    def set_zoom(self, z: float) -> None:
        p = self.pane()
        if not p:
            return
        p.session.zoom = max(MIN_ZOOM, min(MAX_ZOOM, z))
        p.canvas.zoom = p.session.zoom
        self._request_page()

    def fit_width(self) -> None:
        p = self.pane()
        if not p or not p.session.opened:
            return
        ref = p.session.plan.pages[p.session.current_page]
        w, _ = p.session.opened.page_size(ref.source_index)
        vw = max(100, p.canvas.viewport().width() - 20)
        self.set_zoom(vw / w)

    def fit_page(self) -> None:
        p = self.pane()
        if not p or not p.session.opened:
            return
        ref = p.session.plan.pages[p.session.current_page]
        w, h = p.session.opened.page_size(ref.source_index)
        vw = max(100, p.canvas.viewport().width() - 20)
        vh = max(100, p.canvas.viewport().height() - 20)
        self.set_zoom(min(vw / w, vh / h))

    def rotate_view(self) -> None:
        p = self.pane()
        if not p:
            return
        p.canvas.view_rotation = (p.canvas.view_rotation + 90) % 360
        p.canvas.apply_view_rotation()

    def _rubber(self, x, y, w, h) -> None:
        p = self.pane()
        if not p or not p.session.opened:
            return
        tool = p.canvas._tool
        style = self._style()
        p.session.undo.checkpoint()
        page = p.session.current_page
        if tool == "text":
            p.session.overlay.add(make_text(page, x, y, w, h, text="Text", **style))
        elif tool == "whiteout":
            p.session.overlay.add(make_whiteout(page, x, y, w, h))
        elif tool == "cover":
            p.session.overlay.add(make_cover_replace(page, x, y, w, h, text="", **style))
        elif tool in ("rect", "line", "arrow", "ellipse", "highlight", "underline", "strike"):
            fill = "#000000" if tool == "rect" and self._color == "#000000" else ""
            if tool == "rect":
                fill = self._color if self._color else "#000000"
            if tool == "highlight":
                fill = "#FFFF00"
            p.session.overlay.add(make_shape(page, x, y, w, h, tool, stroke=self._color, fill=fill))
        p.canvas.bind_overlay(p.session.overlay)
        p.canvas.set_tool("select")
        self._after_change()

    def _freehand(self, pts: list) -> None:
        p = self.pane()
        if not p or len(pts) < 2:
            return
        xs = [float(t["x"]) for t in pts]
        ys = [float(t["y"]) for t in pts]
        x, y = min(xs), min(ys)
        w, h = max(1.0, max(xs) - x), max(1.0, max(ys) - y)
        local = [{"x": (float(t["x"]) - x) / w, "y": (float(t["y"]) - y) / h} for t in pts]
        p.session.undo.checkpoint()
        p.session.overlay.add(
            make_shape(p.session.current_page, x, y, w, h, "freehand", stroke=self._color, points=local)
        )
        p.canvas.bind_overlay(p.session.overlay)
        p.canvas.set_tool("select")
        self._after_change()

    def _insert_image(self) -> None:
        path, _ = get_open_file_name(self, "Insert image", "", "Images (*.png *.jpg *.jpeg)")
        p = self.pane()
        if not path or not p or not p.session.opened:
            return
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, APP_NAME, "Could not read that image.")
            return
        img = pix.toImage()
        buf = BytesIO()
        img.save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        pw, ph = p.session.opened.page_size(p.session.plan.pages[p.session.current_page].source_index)
        width = min(200, pw * 0.4)
        height = width * (pix.height() / max(1, pix.width()))
        p.session.undo.checkpoint()
        p.session.overlay.add(
            make_image(p.session.current_page, 72, 72, width, height, png_b64=b64, aspect_lock=True)
        )
        p.canvas.bind_overlay(p.session.overlay)
        self._after_change()

    def _signature(self, tab: int = 0) -> None:
        dlg = SignatureStudio(self.vault, self, initial_tab=tab)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result_asset:
            self._refresh_initials_button()
            return
        p = self.pane()
        if not p or not p.session.opened:
            QMessageBox.information(self, APP_NAME, "Open a PDF first, then place the signature.")
            self._refresh_initials_button()
            return
        asset = dlg.result_asset
        pw, ph = p.session.opened.page_size(p.session.plan.pages[p.session.current_page].source_index)
        p.session.undo.checkpoint()
        item = place_signature_on_page(p.session.overlay, asset, p.session.current_page, pw, ph)
        item.data["date"] = self.sig_date.text().strip()
        item.data["label"] = self.sig_label.text().strip()
        p.canvas.page_index = p.session.current_page
        p.canvas.bind_overlay(p.session.overlay)
        p.canvas.viewport().update()
        self._after_change()
        self._status("Signature placed on this page.")
        self._refresh_initials_button()

    def _place_initials(self) -> None:
        asset = find_initials_asset(self.vault)
        if not asset:
            QMessageBox.information(self, APP_NAME, "No initials in the vault. Unlock the vault and save initials first.")
            return
        p = self.pane()
        if not p or not p.session.opened:
            QMessageBox.information(self, APP_NAME, "Open a PDF first, then place initials.")
            return
        pw, ph = p.session.opened.page_size(p.session.plan.pages[p.session.current_page].source_index)
        p.session.undo.checkpoint()
        item = place_signature_on_page(p.session.overlay, asset, p.session.current_page, pw, ph)
        item.data["date"] = self.sig_date.text().strip()
        item.data["label"] = self.sig_label.text().strip()
        p.canvas.bind_overlay(p.session.overlay)
        self._after_change()

    def delete_selected(self) -> None:
        p = self.pane()
        if not p:
            return
        item = p.canvas.selected_item()
        if not item:
            return
        p.session.undo.checkpoint()
        p.session.overlay.remove(item.id)
        p.canvas.bind_overlay(p.session.overlay)
        self._after_change()

    def _rotate_selected(self) -> None:
        p = self.pane()
        if not p:
            return
        item = p.canvas.selected_item()
        if not item:
            return
        p.session.undo.checkpoint()
        rotate_item(item, 90)
        p.canvas.bind_overlay(p.session.overlay)
        self._after_change()

    def _duplicate_selected(self) -> None:
        p = self.pane()
        if not p:
            return
        item = p.canvas.selected_item()
        if not item:
            return
        p.session.undo.checkpoint()
        duplicate_item(p.session.overlay, item.id)
        p.canvas.bind_overlay(p.session.overlay)
        self._after_change()

    def _bring_front(self) -> None:
        p = self.pane()
        if not p:
            return
        item = p.canvas.selected_item()
        if not item:
            return
        p.session.undo.checkpoint()
        bring_to_front(p.session.overlay, item.id)
        p.canvas.bind_overlay(p.session.overlay)
        self._after_change()

    def _send_back(self) -> None:
        p = self.pane()
        if not p:
            return
        item = p.canvas.selected_item()
        if not item:
            return
        p.session.undo.checkpoint()
        send_to_back(p.session.overlay, item.id)
        p.canvas.bind_overlay(p.session.overlay)
        self._after_change()

    def _checkpoint(self) -> None:
        p = self.pane()
        if p:
            p.session.undo.checkpoint()

    def _edit_text(self, item_id: str) -> None:
        p = self.pane()
        if not p:
            return
        item = p.session.overlay.get(item_id)
        if not item or item.type not in ("text", "cover_replace"):
            return
        current = str((item.data or {}).get("text") or "")
        text, ok = QInputDialog.getMultiLineText(self, APP_NAME, "Replacement / text box:", current)
        if not ok:
            return
        p.session.undo.checkpoint()
        item.data["text"] = text
        p.canvas.bind_overlay(p.session.overlay)
        self._after_change()

    def undo(self) -> None:
        p = self.pane()
        if p and p.session.undo.undo():
            self._reload_thumbs_and_page()

    def redo(self) -> None:
        p = self.pane()
        if p and p.session.undo.redo():
            self._reload_thumbs_and_page()

    def _after_change(self) -> None:
        p = self.pane()
        if p and p.session.undo.discard_if_unchanged():
            return
        if p:
            p.session.mark_dirty()
            try:
                save_draft(p.session.overlay, p.session.plan, dirty=True)
            except Exception:
                pass
            self._refresh_tab_titles()
            n = len(p.session.overlay.items)
        else:
            n = 0
        extra = ""
        if self.overlay.has_cover_replace():
            extra = "  " + COVER_NOT_REDACTION
        self._status(f"{n} overlay(s). Source stays read-only.{extra}")

    def _refresh_tab_titles(self) -> None:
        for i in range(self.tabs.count()):
            pane = self.tabs.widget(i)
            if isinstance(pane, DocumentPane):
                self.tabs.setTabText(i, pane.title())

    def _autosave_tick(self) -> None:
        for i in range(self.tabs.count()):
            pane = self.tabs.widget(i)
            if isinstance(pane, DocumentPane) and pane.session.dirty:
                try:
                    save_draft(pane.session.overlay, pane.session.plan, dirty=True)
                except Exception:
                    pass

    def _offer_recovery(self) -> None:
        found = recover_unsaved()
        if not found:
            return
        rec = found[0]
        r = QMessageBox.question(
            self,
            APP_NAME,
            f"A draft was not saved cleanly:\n{rec.source_path}\nRestore it?",
        )
        if r != QMessageBox.Yes:
            return
        try:
            open_draft(rec)
        except MissingSource as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self.open_path(Path(rec.source_path), plan=rec.page_plan, overlay=rec.overlay)

    def _show_drafts(self) -> None:
        from pdf_pro.drafts import list_drafts

        drafts = list_drafts()
        if not drafts:
            QMessageBox.information(self, APP_NAME, "No drafts on this machine.")
            return
        names = [f"{d.source_path}  ({d.saved_at})" for d in drafts]
        item, ok = QInputDialog.getItem(self, APP_NAME, "Reopen draft:", names, 0, False)
        if not ok:
            return
        rec = drafts[names.index(item)]
        try:
            open_draft(rec)
        except MissingSource as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self.open_path(Path(rec.source_path), plan=rec.page_plan, overlay=rec.overlay)

    def _show_history(self) -> None:
        entries = load_history()
        if not entries:
            QMessageBox.information(self, APP_NAME, "No export history yet.")
            return
        lines = [
            f"{e.get('datetime','')}  {e.get('kind','')}  {e.get('original','')} → {e.get('export_path','')}"
            for e in entries
        ]
        QMessageBox.information(self, APP_NAME, "Local history (original / datetime / type / path):\n\n" + "\n".join(lines))

    def _wipe(self) -> None:
        r = QMessageBox.question(self, APP_NAME, WIPE_NOTICE + "\n\nContinue?")
        if r != QMessageBox.Yes:
            return
        result = wipe_local_data()
        QMessageBox.information(
            self,
            APP_NAME,
            "Wipe complete." if result.get("ok") else f"Wipe leftover: {result.get('leftover')}",
        )

    def _run_search(self) -> None:
        p = self.pane()
        if not p or not p.session.opened:
            return
        q = self.search_box.text()
        with p.session.opened._lock:
            hits = search_fitz_doc(p.session.opened.fitz_doc, q)
        p.session.search_hits = hits
        p.session.search_index = 0 if hits else -1
        self._apply_search_highlights()
        if hits:
            self.goto_page(hits[0].page)
            self._status(f"{len(hits)} match(es).")
        else:
            self._status("No matches.")

    def _apply_search_highlights(self) -> None:
        p = self.pane()
        if not p:
            return
        page = p.session.current_page
        rects = []
        for h in p.session.search_hits:
            if h.page == page:
                rects.append((h.x0, h.y0, h.x1 - h.x0, h.y1 - h.y0))
        p.canvas.search_rects = rects
        p.canvas.viewport().update()

    def _find_next(self) -> None:
        p = self.pane()
        if not p:
            return
        if not p.session.search_hits:
            self._run_search()
            if not p.session.search_hits:
                return
            return
        hits = p.session.search_hits
        p.session.search_index = (p.session.search_index + 1) % len(hits)
        self.goto_page(hits[p.session.search_index].page)

    def _find_prev(self) -> None:
        p = self.pane()
        if not p or not p.session.search_hits:
            self._run_search()
            return
        hits = p.session.search_hits
        p.session.search_index = (p.session.search_index - 1) % len(hits)
        self.goto_page(hits[p.session.search_index].page)

    def _copy_hit(self) -> None:
        p = self.pane()
        if not p or not p.session.search_hits:
            return
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(copy_text_from_hits(p.session.search_hits))
        self._status("Copied source text.")

    def _reload_thumbs_and_page(self) -> None:
        p = self.pane()
        if not p:
            return
        p.session.overlay.page_count = len(p.session.plan)
        self._fill_thumbs()
        self.goto_page(min(p.session.current_page, max(0, len(p.session.plan) - 1)))
        p.canvas.bind_overlay(p.session.overlay)
        self._after_change()

    def _page_rotate(self) -> None:
        p = self.pane()
        if not p:
            return
        p.session.undo.checkpoint()
        p.session.plan.rotate(p.session.current_page, 90)
        self._reload_thumbs_and_page()

    def _page_delete(self) -> None:
        p = self.pane()
        if not p:
            return
        try:
            p.session.undo.checkpoint()
            p.session.plan.delete_page(p.session.current_page, overlay=p.session.overlay)
        except (ValueError, IndexError) as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self._reload_thumbs_and_page()

    def _page_duplicate(self) -> None:
        p = self.pane()
        if not p:
            return
        p.session.undo.checkpoint()
        p.session.plan.duplicate_page(p.session.current_page, overlay=p.session.overlay)
        self._reload_thumbs_and_page()

    def _page_move(self, delta: int) -> None:
        p = self.pane()
        if not p:
            return
        src = p.session.current_page
        dst = src + delta
        if dst < 0 or dst >= len(p.session.plan):
            return
        p.session.undo.checkpoint()
        p.session.plan.move_page(src, dst, overlay=p.session.overlay)
        p.session.current_page = dst
        self._reload_thumbs_and_page()

    def _page_extract(self) -> None:
        p = self.pane()
        if not p or not p.session.opened:
            return
        dest_str, _ = get_save_file_name(self, "Extract pages", "", "PDF files (*.pdf)")
        if not dest_str:
            return
        from pdf_pro.compose import write_plan_pdf

        sub = p.session.plan.extract([p.session.current_page])
        passwords = {str(p.session.opened.path): p.session.opened.password or ""}

        def _do(progress):
            if progress:
                progress(10, "Extracting pages")
            dest = write_plan_pdf(sub, Path(dest_str), passwords=passwords)
            if progress:
                progress(100, "Done")
            return dest

        prog = QProgressDialog("Extracting…", "", 0, 100, self)
        prog.setCancelButton(None)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        worker = ExportWorker(_do, self)
        result_box = {"r": None, "err": None}

        def ok(res):
            result_box["r"] = res
            prog.close()

        def fail(msg):
            result_box["err"] = msg
            prog.close()

        worker.finished_ok.connect(ok)
        worker.failed.connect(fail)
        worker.progress.connect(lambda pct, msg: (prog.setValue(pct), prog.setLabelText(msg)))
        loop = QEventLoop(self)
        worker.finished.connect(loop.quit)
        worker.start()
        loop.exec()
        if result_box["err"]:
            QMessageBox.critical(self, APP_NAME, str(result_box["err"]))
            return
        self._status(f"Extracted page to {dest_str}")

    def _page_merge(self) -> None:
        p = self.pane()
        if not p:
            return
        path, _ = get_open_file_name(self, "Merge PDF", "", "PDF files (*.pdf)")
        if not path:
            return
        try:
            other = open_pdf(path)
            count = other.page_count
            other.close()
        except PdfError as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        p.session.undo.checkpoint()
        p.session.plan.merge_from(str(Path(path).resolve()), count)
        self._reload_thumbs_and_page()

    def export_flow(self) -> None:
        folder_to_open = None
        try:
            p = self.pane()
            if not p or not p.session.opened:
                QMessageBox.information(self, APP_NAME, "Open a PDF first.")
                return
            try:
                preview = PreviewDialog(
                    p.session.opened.path,
                    p.session.overlay,
                    p.session.opened.password,
                    self,
                    plan=p.session.plan,
                )
            except Exception as exc:
                QMessageBox.critical(self, APP_NAME, f"Could not start preview.\nReason: {exc}")
                return
            if preview.exec() != QDialog.DialogCode.Accepted or not preview.ok:
                return
            dest_default = default_export_path(p.session.opened.path, p.session.overlay)
            dest_str, _ = get_save_file_name(
                self, "Export flattened PDF", str(dest_default), "PDF files (*.pdf)"
            )
            dest = Path(dest_str) if dest_str else None

            def _do(progress):
                return complete_export(
                    p.session.opened.path,
                    p.session.overlay,
                    dest,
                    password=p.session.opened.password,
                    source_sha=p.session.opened.sha256,
                    export_fn=lambda src, ov, d, password=None: export_pdf(
                        src, ov, d, password=password, plan=p.session.plan, progress=progress
                    ),
                )

            prog = QProgressDialog("Exporting…", "", 0, 100, self)
            prog.setCancelButton(None)
            prog.setWindowModality(Qt.WindowModal)
            prog.setMinimumDuration(0)
            worker = ExportWorker(_do, self)
            result_box = {"r": None, "err": None}

            def ok(res):
                result_box["r"] = res
                prog.close()

            def fail(msg):
                result_box["err"] = msg
                prog.close()

            worker.finished_ok.connect(ok)
            worker.failed.connect(fail)
            worker.progress.connect(lambda pct, msg: (prog.setValue(pct), prog.setLabelText(msg)))
            loop = QEventLoop(self)
            worker.finished.connect(loop.quit)
            worker.start()
            loop.exec()
            if result_box["err"]:
                raise ExportError(result_box["err"])
            result = result_box["r"]
            if result is None or result.cancelled:
                return
            kind = "signed" if p.session.overlay.has_signature() else "amended"
            try:
                record_export(p.session.opened.path, result.path, kind=kind)
            except Exception:
                pass
            p.session.dirty = False
            save_draft(p.session.overlay, p.session.plan, dirty=False)
            self._refresh_tab_titles()
            box = QMessageBox(self)
            box.setWindowTitle(APP_NAME)
            box.setText(result.message)
            open_btn = box.addButton("Open containing folder", QMessageBox.ActionRole)
            box.addButton(QMessageBox.Ok)
            box.exec()
            if box.clickedButton() is open_btn and result.path is not None:
                folder_to_open = result.path
        except ExportError as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, APP_NAME, f"Could not write export.\nReason: {exc}")
            return
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"Export failed.\nReason: {exc}")
            return
        if folder_to_open is not None:
            try:
                open_containing_folder(folder_to_open)
            except OSError:
                pass
