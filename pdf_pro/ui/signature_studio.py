"""Draw / type / upload signature pad. Tablet pressure used when present."""

from __future__ import annotations

import base64
import io

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QTabletEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QSpinBox,
)

from pdf_pro.constants import VISUAL_SIGNATURE_NOTICE
from pdf_pro.fonts import HANDWRITING_FAMILY
from pdf_pro.signature_feedback import (
    MSG_SAVED,
    StudioState,
    validate_save_to_vault,
    validate_unlock,
    validate_use_on_page,
)
from pdf_pro.vault import SignatureAsset, SignatureVault, VaultError, WrongPassphrase


class DrawPad(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(420, 180)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor("white"))
        self.setPalette(pal)
        self.strokes: list[list[dict]] = []
        self._current: list[dict] = []
        self.setAttribute(Qt.WA_TabletTracking, True)

    def _norm(self, pos: QPointF, pressure: float) -> dict:
        w = max(1, self.width())
        h = max(1, self.height())
        return {"x": pos.x() / w, "y": pos.y() / h, "p": max(0.05, float(pressure))}

    def mousePressEvent(self, event) -> None:
        self._current = [self._norm(event.position(), 1.0)]
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._current:
            self._current.append(self._norm(event.position(), 1.0))
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._current:
            self.strokes.append(self._current)
            self._current = []
            self.update()

    def tabletEvent(self, event: QTabletEvent) -> None:
        pressure = event.pressure()
        if pressure <= 0:
            pressure = 1.0
        if event.type() == QTabletEvent.Type.TabletPress:
            self._current = [self._norm(event.position(), pressure)]
        elif event.type() == QTabletEvent.Type.TabletMove and self._current:
            self._current.append(self._norm(event.position(), pressure))
        elif event.type() == QTabletEvent.Type.TabletRelease and self._current:
            self.strokes.append(self._current)
            self._current = []
        self.update()
        event.accept()

    def clear(self) -> None:
        self.strokes = []
        self._current = []
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("white"))
        p.setRenderHint(QPainter.Antialiasing)
        for stroke in self.strokes + ([self._current] if self._current else []):
            if not stroke:
                continue
            for a, b in zip(stroke, stroke[1:]):
                width = 1.2 + 3.5 * ((a["p"] + b["p"]) / 2)
                p.setPen(QPen(QColor("black"), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawLine(
                    a["x"] * self.width(),
                    a["y"] * self.height(),
                    b["x"] * self.width(),
                    b["y"] * self.height(),
                )

    def to_png_b64(self) -> str:
        img = QImage(self.size() * 2, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        sx, sy = 2.0, 2.0
        for stroke in self.strokes:
            for a, b in zip(stroke, stroke[1:]):
                width = 2.4 + 7.0 * ((a["p"] + b["p"]) / 2)
                painter.setPen(QPen(QColor("black"), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.drawLine(
                    a["x"] * img.width(),
                    a["y"] * img.height(),
                    b["x"] * img.width(),
                    b["y"] * img.height(),
                )
        painter.end()
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")


class SignatureStudio(QDialog):
    def __init__(self, vault: SignatureVault, parent=None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.result_asset: SignatureAsset | None = None
        self.setWindowTitle("Signature — PDF_Pro")
        self.resize(560, 460)
        layout = QVBoxLayout(self)
        notice = QLabel(VISUAL_SIGNATURE_NOTICE)
        notice.setObjectName("legalNotice")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        self.tabs = QTabWidget()
        self.pad = DrawPad()
        draw_tab = QWidget()
        dl = QVBoxLayout(draw_tab)
        dl.addWidget(QLabel("Draw with mouse, trackpad, or stylus. Pressure is used when the tablet reports it."))
        dl.addWidget(self.pad)
        clr = QPushButton("Clear")
        clr.clicked.connect(self.pad.clear)
        dl.addWidget(clr)
        self.tabs.addTab(draw_tab, "Draw")

        type_tab = QWidget()
        tl = QFormLayout(type_tab)
        self.type_name = QLineEdit()
        self.type_size = QSpinBox()
        self.type_size.setRange(18, 96)
        self.type_size.setValue(48)
        self.type_preview = QLabel(" ")
        self.type_preview.setMinimumHeight(80)
        font = QFont(HANDWRITING_FAMILY)
        font.setPointSize(36)
        self.type_preview.setFont(font)
        self.type_name.textChanged.connect(lambda t: self.type_preview.setText(t))
        tl.addRow("Typed name", self.type_name)
        tl.addRow("Size", self.type_size)
        tl.addRow("Preview", self.type_preview)
        self.tabs.addTab(type_tab, "Type")

        up_tab = QWidget()
        ul = QVBoxLayout(up_tab)
        self.upload_path = QLabel("No image selected")
        pick = QPushButton("Upload PNG or JPEG…")
        pick.clicked.connect(self._pick_image)
        ul.addWidget(pick)
        ul.addWidget(self.upload_path)
        self._upload_b64 = ""
        self.tabs.addTab(up_tab, "Upload")

        vault_tab = QWidget()
        vl = QVBoxLayout(vault_tab)
        self.vault_status = QLabel()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        unlock_btn = QPushButton("Unlock / set passphrase")
        unlock_btn.clicked.connect(self._unlock)
        self.vault_list = QListWidget()
        vl.addWidget(self.vault_status)
        vl.addWidget(self.pass_edit)
        vl.addWidget(unlock_btn)
        vl.addWidget(self.vault_list)
        self.tabs.addTab(vault_tab, "Vault")
        self._refresh_vault_status()

        layout.addWidget(self.tabs)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Save as"))
        self.save_name = QLineEdit("Signature")
        name_row.addWidget(self.save_name)
        layout.addLayout(name_row)

        self.feedback = QLabel("")
        self.feedback.setObjectName("feedbackLabel")
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save to vault")
        save_btn.clicked.connect(self._save_vault)
        use_btn = QPushButton("Use on page")
        use_btn.setObjectName("primaryAction")
        use_btn.clicked.connect(self._use)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(use_btn)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _pick_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Signature image", "", "Images (*.png *.jpg *.jpeg)")
        if not path:
            return
        pix = QPixmap(path)
        if pix.isNull():
            self.upload_path.setText("Could not read image")
            return
        img = pix.toImage()
        buf = io.BytesIO()
        img.save(buf, "PNG")
        self._upload_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        self.upload_path.setText(path)

    def _refresh_vault_status(self) -> None:
        if self.vault.is_first_use():
            self.vault_status.setText("First use: enter a passphrase and click Unlock / set passphrase.")
        elif self.vault.unlocked:
            self.vault_status.setText("Vault unlocked for this session.")
            self._fill_list()
        else:
            self.vault_status.setText("Vault locked. Enter passphrase to unlock this session.")

    def _fill_list(self) -> None:
        self.vault_list.clear()
        if not self.vault.unlocked:
            return
        for a in self.vault.list_assets():
            item = QListWidgetItem(f"{a.name} ({a.kind})")
            item.setData(Qt.UserRole, a.id)
            self.vault_list.addItem(item)

    def _studio_state(self) -> StudioState:
        row = self.vault_list.currentItem()
        return StudioState(
            tab=self.tabs.currentIndex(),
            pad_has_strokes=bool(self.pad.strokes),
            typed_name=self.type_name.text(),
            image_present=bool(self._upload_b64),
            save_name=self.save_name.text(),
            vault_unlocked=bool(self.vault.unlocked),
            vault_selected=row is not None,
            passphrase=self.pass_edit.text(),
        )

    def _show_feedback(self, msg: str, vault: bool = False, ok: bool = False) -> None:
        self.feedback.setText(msg)
        self.feedback.setObjectName("feedbackOk" if ok else "feedbackLabel")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        if vault:
            self.tabs.setCurrentIndex(3)
            self.vault_status.setText(msg)

    def _unlock(self) -> None:
        err = validate_unlock(self._studio_state())
        if err:
            self._show_feedback(err, vault=True)
            return
        pw = self.pass_edit.text()
        try:
            if self.vault.is_first_use():
                self.vault.set_passphrase(pw)
            else:
                self.vault.unlock(pw)
        except WrongPassphrase as exc:
            self._show_feedback(str(exc), vault=True)
            return
        except VaultError as exc:
            self._show_feedback(str(exc), vault=True)
            return
        self.pass_edit.clear()
        self.feedback.setText("")
        self._refresh_vault_status()

    def _current_asset(self) -> SignatureAsset | None:
        tab = self.tabs.currentIndex()
        name = self.save_name.text().strip() or "Signature"
        if tab == 3:
            row = self.vault_list.currentItem()
            if not row or not self.vault.unlocked:
                return None
            return self.vault.get(row.data(Qt.UserRole))
        if tab == 0:
            if not self.pad.strokes:
                return None
            return SignatureAsset(
                id="",
                name=name,
                kind="draw",
                png_b64=self.pad.to_png_b64(),
                strokes=self.pad.strokes,
            )
        if tab == 1:
            text = self.type_name.text().strip()
            if not text:
                return None
            return SignatureAsset(
                id="",
                name=name,
                kind="type",
                text=text,
                font_family=HANDWRITING_FAMILY,
                png_b64=self._type_png(text),
            )
        if tab == 2:
            if not self._upload_b64:
                return None
            return SignatureAsset(id="", name=name, kind="image", png_b64=self._upload_b64)
        return None

    def _type_png(self, text: str) -> str:
        img = QImage(800, 200, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        font = QFont(HANDWRITING_FAMILY)
        font.setPointSize(72)
        p.setFont(font)
        p.setPen(QColor("black"))
        p.drawText(img.rect(), Qt.AlignCenter, text)
        p.end()
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def _save_vault(self) -> None:
        state = self._studio_state()
        err = validate_save_to_vault(state)
        if err:
            self._show_feedback(err, vault=not state.vault_unlocked)
            return
        asset = self._current_asset()
        if not asset:
            self._show_feedback("Nothing to save.")
            return
        try:
            self.vault.add(asset)
        except VaultError as exc:
            self._show_feedback(str(exc), vault=True)
            return
        self._fill_list()
        self._show_feedback(MSG_SAVED, ok=True)

    def _use(self) -> None:
        state = self._studio_state()
        err = validate_use_on_page(state)
        if err:
            self._show_feedback(err, vault=state.tab == 3)
            return
        asset = self._current_asset()
        if not asset:
            self._show_feedback("Nothing to place on the page.")
            return
        self.result_asset = asset
        self.accept()
