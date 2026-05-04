"""Subtitle review/edit dialog.

Loads side-by-side source (English/etc) and Korean SRTs, lets the user
fix lines inline, then writes back the .ko.srt and re-muxes the .mkv
(stream-copy — no re-encoding, takes 1-3s on a 5-minute video).

Design priorities (per user feedback "최대한 수정 많이, 제한된 자원에서 효과적"):
- Zero LLM calls — everything is plain string editing
- Auto-highlight likely problems so the user finds them in seconds:
    * fallback (still in source language)        → red background
    * Korean+alphabet mojibake e.g. "Tyl러"       → yellow background
    * unedited line                              → default
    * user-edited line                           → bold
"""

from __future__ import annotations
import re
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QFrame, QCheckBox,
)
from lexisub.core import subtitle, muxer


_EN_START = re.compile(r"^[A-Za-z]")
_MIXED = re.compile(r"[가-힣][A-Za-z]|[A-Za-z][가-힣]")


def _classify(ko_text: str) -> str:
    """Return 'fallback' / 'mixed' / 'ok'.

    Order matters: a line like "Tyl러가 ..." has both an English start
    AND a Korean+Alphabet adjacency. We want it tagged as 'mixed' (the
    line WAS translated but the proper-noun romanisation broke), not as
    'fallback' (the line was kept verbatim in English). So mixed wins.
    """
    s = ko_text.strip()
    if not s:
        return "ok"
    if _MIXED.search(s):
        return "mixed"
    if _EN_START.match(s):
        return "fallback"
    return "ok"


class SubtitleEditDialog(QDialog):
    """Modal subtitle editor. Caller passes paths to the source SRT (the
    Whisper output, English/etc), the Korean SRT (the translated output),
    and the video so we can re-mux on save.
    """

    COLUMNS = ["#", "시간", "원문", "한국어 자막 (편집 가능)"]

    def __init__(
        self,
        video_path: Path,
        source_srt: Path,
        ko_srt: Path,
        mkv_out: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.video_path = video_path
        self.source_srt = source_srt
        self.ko_srt = ko_srt
        self.mkv_out = mkv_out

        self.setWindowTitle(f"자막 편집 — {video_path.name}")
        self.setMinimumSize(1100, 720)

        # Load both SRTs
        self.src_cues = subtitle.parse_srt(source_srt.read_text(encoding="utf-8"))
        self.ko_cues = subtitle.parse_srt(ko_srt.read_text(encoding="utf-8"))
        # Pair by index (length should match; if not, pad)
        n = max(len(self.src_cues), len(self.ko_cues))
        while len(self.src_cues) < n:
            self.src_cues.append(subtitle.Cue(len(self.src_cues) + 1, 0, 0, ""))
        while len(self.ko_cues) < n:
            self.ko_cues.append(subtitle.Cue(len(self.ko_cues) + 1, 0, 0, ""))

        # Header
        heading = QLabel("자막 편집")
        heading.setProperty("role", "heading")
        sub = QLabel(
            "한국어 자막 셀을 직접 편집하세요. "
            "<span style='color:#ff3b30'>빨강 배경</span> = 번역 누락(원문 그대로). "
            "<span style='color:#cc8800'>노랑 배경</span> = 한글·알파벳 혼용(음역 의심)."
        )
        sub.setProperty("role", "caption")
        sub.setWordWrap(True)
        sub.setTextFormat(Qt.TextFormat.RichText)

        # Stats label (updated on edit)
        self.stats = QLabel("")
        self.stats.setProperty("role", "caption")

        # Filter checkbox: show only suspicious lines
        self.only_susp = QCheckBox("의심 줄만 보기 (빨강/노랑)")
        self.only_susp.setObjectName("only_suspicious")
        self.only_susp.toggled.connect(self._apply_filter)

        # Table
        self.table = QTableWidget(n, len(self.COLUMNS))
        self.table.setObjectName("subtitle_edit_table")
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(True)
        self.table.itemChanged.connect(self._on_item_changed)

        self._populate()

        # Buttons
        self.save_btn = QPushButton("저장 + .mkv 재mux")
        self.save_btn.setObjectName("save_subtitle_button")
        self.save_btn.setToolTip(
            "수정한 한국어 자막을 .ko.srt에 덮어쓰고 .subbed.mkv를 다시 만듭니다. "
            "비디오 스트림은 복사라 1-3초면 끝납니다."
        )
        self.save_btn.clicked.connect(self._on_save)

        self.save_only_btn = QPushButton(".srt만 저장")
        self.save_only_btn.clicked.connect(self._on_save_srt_only)

        cancel_btn = QPushButton("닫기")
        cancel_btn.clicked.connect(self.reject)

        controls = QHBoxLayout()
        controls.addWidget(self.only_susp)
        controls.addWidget(self.stats)
        controls.addStretch()
        controls.addWidget(cancel_btn)
        controls.addWidget(self.save_only_btn)
        controls.addWidget(self.save_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(heading)
        layout.addWidget(sub)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(controls)

        self._dirty = False
        self._populating = False
        self._refresh_stats()

    # --- table population & styling ------------------------------------

    def _populate(self) -> None:
        self._populating = True
        for i, (src, ko) in enumerate(zip(self.src_cues, self.ko_cues)):
            self._set_row(i, src, ko)
        self._populating = False

    def _set_row(self, row: int, src, ko) -> None:
        idx_item = QTableWidgetItem(str(row + 1))
        idx_item.setFlags(idx_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        ts_text = f"{src.start_ms / 1000:.1f}s"
        ts_item = QTableWidgetItem(ts_text)
        ts_item.setFlags(ts_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        src_item = QTableWidgetItem(src.text)
        src_item.setFlags(src_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        src_item.setForeground(QBrush(QColor("#666")))

        ko_item = QTableWidgetItem(ko.text)
        # editable by default
        self._apply_class_style(ko_item, _classify(ko.text))

        self.table.setItem(row, 0, idx_item)
        self.table.setItem(row, 1, ts_item)
        self.table.setItem(row, 2, src_item)
        self.table.setItem(row, 3, ko_item)

    def _apply_class_style(self, item: QTableWidgetItem, klass: str, edited: bool = False) -> None:
        if klass == "fallback":
            item.setBackground(QBrush(QColor("#ffe4e1")))
        elif klass == "mixed":
            item.setBackground(QBrush(QColor("#fff4d6")))
        else:
            item.setBackground(QBrush(QColor(0, 0, 0, 0)))
        font: QFont = item.font()
        font.setBold(edited)
        item.setFont(font)

    def _refresh_stats(self) -> None:
        n = self.table.rowCount()
        fb = sum(
            1
            for r in range(n)
            if self.table.item(r, 3) and _classify(self.table.item(r, 3).text()) == "fallback"
        )
        mx = sum(
            1
            for r in range(n)
            if self.table.item(r, 3) and _classify(self.table.item(r, 3).text()) == "mixed"
        )
        self.stats.setText(
            f"총 {n}줄  ·  번역 누락 {fb}줄  ·  음역 의심 {mx}줄"
        )

    # --- filter --------------------------------------------------------

    def _apply_filter(self, only_susp: bool) -> None:
        for r in range(self.table.rowCount()):
            ko = self.table.item(r, 3).text() if self.table.item(r, 3) else ""
            klass = _classify(ko)
            self.table.setRowHidden(r, only_susp and klass == "ok")

    # --- edit tracking -------------------------------------------------

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._populating:
            return
        if item.column() != 3:
            return
        self._dirty = True
        klass = _classify(item.text())
        self._apply_class_style(item, klass, edited=True)
        # Filter may need to update
        if self.only_susp.isChecked():
            row = item.row()
            self.table.setRowHidden(row, klass == "ok")
        self._refresh_stats()

    # --- save / mux ----------------------------------------------------

    def _collect_cues(self):
        cues = []
        for r in range(self.table.rowCount()):
            src = self.src_cues[r]
            ko_item = self.table.item(r, 3)
            text = ko_item.text() if ko_item else ""
            cues.append(
                subtitle.Cue(
                    index=r + 1,
                    start_ms=src.start_ms,
                    end_ms=src.end_ms,
                    text=text,
                )
            )
        return cues

    def _on_save_srt_only(self) -> None:
        try:
            cues = self._collect_cues()
            self.ko_srt.write_text(subtitle.serialize_srt(cues), encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))
            return
        QMessageBox.information(
            self, "저장됨", f"{self.ko_srt.name} 저장 완료. .mkv는 갱신되지 않았습니다."
        )
        self._dirty = False

    def _on_save(self) -> None:
        try:
            cues = self._collect_cues()
            self.ko_srt.write_text(subtitle.serialize_srt(cues), encoding="utf-8")
            muxer.mux_subtitle(
                self.video_path,
                self.ko_srt,
                self.mkv_out,
                language="kor",
                title="Korean",
            )
        except Exception as e:
            QMessageBox.critical(self, "저장/mux 실패", str(e))
            return
        self._dirty = False
        QMessageBox.information(
            self,
            "완료",
            f".ko.srt 저장 + .mkv 재mux 완료\n\n"
            f"  • {self.ko_srt.name}\n"
            f"  • {self.mkv_out.name}",
        )
        self.accept()

    def reject(self) -> None:
        if self._dirty:
            ans = QMessageBox.question(
                self,
                "변경사항 버리기",
                "수정한 내용이 저장되지 않았습니다. 정말 닫을까요?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if ans != QMessageBox.StandardButton.Discard:
                return
        super().reject()
