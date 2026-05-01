"""Modal dialog for editing a single glossary term.

Editable fields: ko_term, category, status, definition.
Read-only: source_lang, source_term (changing them would break the
UNIQUE(source_lang, source_term, ko_term) constraint and the existing
term_sources rows). To rename them, delete the term and add a new one.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QTextEdit, QLabel,
    QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFrame,
)


class TermEditDialog(QDialog):
    CATEGORIES = ["", "기술", "해부학", "의학", "개념", "장비", "포지션", "인명", "기타"]
    STATUSES = [("approved", "승인"), ("pending", "보류"), ("rejected", "거부")]

    def __init__(self, term_row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("용어 편집")
        self.setMinimumWidth(560)
        self._term = term_row

        # Read-only header
        header = QLabel(
            f"<h3 style='margin:0'>{term_row['source_term']}"
            f" <span style='color:#888;font-weight:normal'>"
            f"({term_row['source_lang']})</span></h3>"
        )

        sub = QLabel(
            "원어 표기와 언어는 잠금 상태입니다. 변경하려면 삭제 후 새로 추가하세요."
        )
        sub.setStyleSheet("color:#888; font-size:12px;")

        # Form
        self.ko_edit = QLineEdit(term_row["ko_term"] or "")
        self.ko_edit.setObjectName("ko_term_edit")

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        for c in self.CATEGORIES:
            self.category_combo.addItem(c)
        cur_cat = term_row["category"] or ""
        if cur_cat and cur_cat not in self.CATEGORIES:
            self.category_combo.addItem(cur_cat)
        self.category_combo.setCurrentText(cur_cat)

        self.status_combo = QComboBox()
        for code, label in self.STATUSES:
            self.status_combo.addItem(label, code)
        cur_status = term_row["status"]
        for i, (code, _) in enumerate(self.STATUSES):
            if code == cur_status:
                self.status_combo.setCurrentIndex(i)
                break

        self.definition_edit = QTextEdit()
        cur_def = term_row["definition"] if "definition" in term_row.keys() else ""
        self.definition_edit.setPlainText(cur_def or "")
        self.definition_edit.setMinimumHeight(120)
        self.definition_edit.setPlaceholderText(
            "이 용어의 한국어 정의를 1~2 문장으로 작성하세요. "
            "비워두면 정의 없음으로 저장됩니다."
        )

        # Evidence (read-only display)
        ev = (
            term_row["evidence_level"]
            if "evidence_level" in term_row.keys()
            else None
        )
        ev_label = QLabel(self._evidence_html(ev))
        ev_label.setTextFormat(0)  # PlainText off — render as RichText
        ev_label.setOpenExternalLinks(False)
        ev_label.setWordWrap(True)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(0)
        form.addRow("한국어 번역", self.ko_edit)
        form.addRow("분류", self.category_combo)
        form.addRow("상태", self.status_combo)
        form.addRow("정의", self.definition_edit)

        # Layout
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #ddd;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addSpacing(8)
        layout.addLayout(form)
        layout.addSpacing(4)
        layout.addWidget(sep)
        layout.addWidget(ev_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("저장")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(buttons)
        layout.addLayout(btn_row)

    @staticmethod
    def _evidence_html(level: str | None) -> str:
        labels = {
            "from_text": ("✓ 본문 근거", "PDF 본문에 외국어와 한국어가 함께 등장.", "#34c759"),
            "inferred": ("⚠ 모델 추론", "본문에는 한국어 번역이 없음. 모델이 자체 지식으로 추론. 검토 권장.", "#ff9500"),
            "user_edit": ("✓ 사용자 수정", "사용자가 직접 검토·편집한 항목 — 가장 신뢰도 높음.", "#34c759"),
            "csv_import": ("CSV 가져오기", "외부 CSV 파일에서 임포트.", "#007aff"),
        }
        if level in labels:
            text, expl, color = labels[level]
            return f'<p style="color:{color};margin:0"><b>근거:</b> {text}</p><p style="color:#666;margin:0;font-size:11px">{expl}</p>'
        return '<p style="color:#888;margin:0;font-size:11px">근거 정보 없음 (구버전 데이터 또는 미분류).</p>'

    def values(self) -> dict:
        """Return the edited values. Caller passes them to repository.update_term
        and must add ``evidence_level='user_edit'`` to mark the edit.
        """
        return {
            "ko_term": self.ko_edit.text().strip(),
            "category": self.category_combo.currentText().strip() or None,
            "status": self.status_combo.currentData(),
            "definition": self.definition_edit.toPlainText().strip(),
        }
