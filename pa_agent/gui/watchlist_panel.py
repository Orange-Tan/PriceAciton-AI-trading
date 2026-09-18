"""Grouped watchlist panel with quote and daily-decision columns."""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pa_agent.config.watchlist_store import (
    DEFAULT_GROUP,
    normalize_watchlist_groups,
    serialize_watchlist_groups,
)
from pa_agent.data.ashare_common import normalize_ashare_symbol
from pa_agent.gui.theme import tokens as T

_ADD_PROMPT = "输入股票代码 / 指数 / 品种名：\n· A股 6 位代码，如 600519、000001\n· 指数 000300 或 sh000300\n· 其他（TradingView）可输入 XAUUSD 等"
_NAME_MAP = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "000001": "平安银行",
    "000300": "沪深300",
    "399006": "创业板指",
    "600000": "浦发银行",
    "600510": "黑牡丹",
    "600519": "贵州茅台",
    "600520": "文一科技",
    "601318": "中国平安",
    "601398": "工商银行",
    "601988": "中国银行",
    "301526": "国际复材",
}


class _NameLookupSignals(QObject):
    resolved = pyqtSignal(str, str)


class _NameLookupTask(QRunnable):
    """Resolve one A-share name without blocking the watchlist UI thread."""

    def __init__(self, symbol: str, signals: _NameLookupSignals) -> None:
        super().__init__()
        self._symbol = symbol
        self._signals = signals

    def run(self) -> None:
        def _emit(name: str) -> None:
            try:
                self._signals.resolved.emit(self._symbol, name)
            except RuntimeError:
                # Receiver QObject may have been deleted while worker was running.
                return

        try:
            from pa_agent.data.eastmoney_client import fetch_stock_quote

            quote = fetch_stock_quote(self._symbol)
            name = str((quote or {}).get("name") or "").strip()
            _emit(name if name != self._symbol else "")
        except Exception:
            _emit("")
            return


class WatchlistPanel(QWidget):
    """Two-column group selector and quote table."""

    symbol_selected = pyqtSignal(str)
    list_changed = pyqtSignal()
    groups_changed = pyqtSignal()
    group_selected = pyqtSignal(str)
    scan_requested = pyqtSignal(str, int)
    _HEADERS = ["代码", "名称", "现价", "今日涨幅", "今日决策"]

    def __init__(
        self, symbols: list[str] | dict[str, list[str]] | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._groups = normalize_watchlist_groups(
            {DEFAULT_GROUP: symbols} if isinstance(symbols, list) else symbols
        )
        self._current_group = DEFAULT_GROUP
        self._quotes: dict[str, dict[str, Any]] = {}
        self._name_lookup_pending: set[str] = set()
        self._name_lookup_failures: dict[str, float] = {}
        self._name_lookup_backoff_s = 30.0
        self._name_lookup_pool = QThreadPool.globalInstance()
        self._name_lookup_signals = _NameLookupSignals(self)
        self._name_lookup_signals.resolved.connect(self._on_name_resolved)
        self._build_ui()
        self.set_groups(self._groups)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(6)

        self._group_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._group_splitter.setChildrenCollapsible(False)
        self._group_splitter.setHandleWidth(1)
        self._group_list = QListWidget()
        self._group_list.setObjectName("watchlistGroups")
        self._group_list.setMinimumWidth(0)
        self._group_list.setMaximumWidth(180)
        self._group_list.setFrameShape(QFrame.Shape.NoFrame)
        self._group_list.setStyleSheet(
            "QListWidget#watchlistGroups { border: none; background: transparent; padding: 0; }"
        )
        self._group_list.setToolTip("点击板块名称切换板块内的自选股")

        self._group_column = QWidget()
        self._group_column.setMaximumWidth(180)
        self._group_column.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        group_col_layout = QVBoxLayout(self._group_column)
        group_col_layout.setContentsMargins(0, 0, 0, 0)
        group_col_layout.setSpacing(2)
        group_header_row = QHBoxLayout()
        group_header_row.setContentsMargins(0, 0, 0, 0)
        group_header_row.setSpacing(0)
        self._group_header = QLabel("板块")
        self._group_header.setStyleSheet(
            f"color: {T.FG_2}; font-size: 11px; font-weight: 600; padding: 0 4px;"
        )
        group_header_row.addWidget(self._group_header)
        group_header_row.addStretch(1)
        self._add_group_btn = QPushButton("+")
        self._add_group_btn.setFixedSize(28, 28)
        self._add_group_btn.setStyleSheet(
            f"QPushButton {{ min-width: 26px; max-width: 26px; min-height: 26px; "
            f"max-height: 26px; border: 1px solid transparent; background: transparent; "
            f"color: {T.ACCENT_PRIMARY}; font-size: 20px; font-weight: 600; padding: 0; }} "
            "QPushButton:hover { background: rgba(127, 127, 127, 0.12); "
            f"border-color: {T.ACCENT_PRIMARY}; }}"
        )
        self._add_group_btn.setToolTip("新增板块")
        group_header_row.addWidget(self._add_group_btn)
        group_col_layout.addLayout(group_header_row)
        group_col_layout.addWidget(self._group_list)
        group_col_layout.addStretch(1)
        self._group_splitter.addWidget(self._group_column)

        self._stock_column = QWidget()
        self._stock_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(self._stock_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        stock_header_row = QHBoxLayout()
        stock_header_row.setContentsMargins(0, 0, 0, 0)
        stock_header_row.setSpacing(0)
        self._stock_header = QLabel("自选股")
        self._stock_header.setStyleSheet(
            f"color: {T.FG_2}; font-size: 11px; font-weight: 600; padding: 0 2px;"
        )
        stock_header_row.addWidget(self._stock_header)
        stock_header_row.addStretch(1)
        self._table = QTableWidget(0, len(self._HEADERS))
        self._table.setHorizontalHeaderLabels(self._HEADERS)
        self._table.setObjectName("watchlistTable")
        self._table.setFrameShape(QFrame.Shape.NoFrame)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(
            "QTableWidget#watchlistTable { border: none; background: transparent; }"
            " QTableWidget#watchlistTable::item { padding: 2px 4px; }"
            " QHeaderView::section { padding: 3px 4px; }"
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        for column, width in enumerate((62, 76, 62, 68)):
            self._table.setColumnWidth(column, width)
        self._add_symbol_btn = QPushButton("+")
        self._add_symbol_btn.setFixedSize(28, 28)
        self._add_symbol_btn.setStyleSheet(
            f"QPushButton {{ min-width: 26px; max-width: 26px; min-height: 26px; "
            f"max-height: 26px; border: 1px solid transparent; background: transparent; "
            f"color: {T.ACCENT_PRIMARY}; font-size: 20px; font-weight: 600; padding: 0; }} "
            "QPushButton:hover { background: rgba(127, 127, 127, 0.12); "
            f"border-color: {T.ACCENT_PRIMARY}; }}"
        )
        self._add_symbol_btn.setToolTip("添加自选股")
        stock_header_row.addWidget(self._add_symbol_btn)
        right_layout.addLayout(stock_header_row)
        right_layout.addWidget(self._table, stretch=1)
        self._group_splitter.addWidget(self._stock_column)
        self._group_splitter.setStretchFactor(0, 0)
        self._group_splitter.setStretchFactor(1, 1)
        layout.addWidget(self._group_splitter, stretch=1)

        # Compatibility list for callers of the former panel API.
        self._list = QListWidget(self)
        self._list.hide()
        self._add_group_btn.clicked.connect(self._on_add_group_clicked)
        self._add_symbol_btn.clicked.connect(self._on_add_clicked)
        self._group_list.currentTextChanged.connect(self._on_group_selected)
        self._table.itemClicked.connect(self._on_table_item_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
        self._group_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._group_list.customContextMenuRequested.connect(self._on_group_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)

    def groups(self) -> dict[str, list[str]]:
        return serialize_watchlist_groups(self._groups)

    def set_groups(self, groups: dict[str, list[str]] | None) -> None:
        self._groups = normalize_watchlist_groups(groups)
        if self._current_group not in self._groups:
            self._current_group = DEFAULT_GROUP
        names = list(self._groups)
        self._group_list.blockSignals(True)
        self._group_list.clear()
        self._group_list.addItems(names)
        self._group_list.setCurrentRow(names.index(self._current_group))
        self._group_list.blockSignals(False)
        self._resize_group_list()
        self._resize_group_column()
        self._refresh_table()

    def current_group(self) -> str:
        return self._current_group

    def add_group(self, name: str) -> bool:
        clean = (name or "").strip()
        if not clean or clean in self._groups:
            return False
        self._groups[clean] = []
        self._current_group = clean
        self.set_groups(self._groups)
        self._emit_groups_changed()
        return True

    def rename_group(self, old_name: str, new_name: str) -> bool:
        old, new = (old_name or "").strip(), (new_name or "").strip()
        if old == DEFAULT_GROUP or old not in self._groups or not new or new in self._groups:
            return False
        self._groups[new] = self._groups.pop(old)
        self._current_group = new
        self.set_groups(self._groups)
        self._emit_groups_changed()
        return True

    def remove_current_group(self) -> bool:
        if self._current_group == DEFAULT_GROUP:
            return False
        del self._groups[self._current_group]
        self._current_group = DEFAULT_GROUP
        self.set_groups(self._groups)
        self._emit_groups_changed()
        return True

    def symbols(self, group: str | None = None) -> list[str]:
        return list(self._groups.get(group or self._current_group, []))

    def set_symbols(self, symbols: list[str] | None) -> None:
        self.set_groups({DEFAULT_GROUP: symbols or []})

    def add_symbol(self, symbol: str, group: str | None = None) -> bool:
        target = (group or self._current_group).strip() or DEFAULT_GROUP
        display = self._normalize_symbol(symbol)
        if target not in self._groups or not display or display in self._groups[target]:
            return False
        self._groups[target].append(display)
        self._current_group = target
        self.set_groups(self._groups)
        self._emit_groups_changed()
        return True

    def remove_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            row = self._list.currentRow()
        current = self.symbols()
        if row < 0 or row >= len(current):
            return
        del self._groups[self._current_group][row]
        self.set_groups(self._groups)
        if self.symbols():
            self._list.setCurrentRow(min(row, len(self.symbols()) - 1))
        self._emit_groups_changed()

    def update_quote(
        self, symbol: str, *, name: str | None = None, price: object = "", change: object = ""
    ) -> None:
        key = self._normalize_symbol(symbol)
        if not key:
            return
        data = self._quotes.setdefault(key, {})
        data.update(
            {
                "name": name or self._name_for_symbol(key),
                "price": self._format_price(price),
                "change": self._format_change(change),
            }
        )
        self._refresh_table()

    def update_decision(
        self, symbol: str, text: str, decision_date: date | str | None = None
    ) -> None:
        key = self._normalize_symbol(symbol)
        if not key:
            return
        raw_date = decision_date or date.today()
        day = raw_date.isoformat() if isinstance(raw_date, date) else str(raw_date)
        self._quotes.setdefault(key, {}).update(
            {"decision": (text or "").strip(), "decision_date": day}
        )
        self._refresh_table()

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        value = (symbol or "").strip()
        if not value:
            return ""
        normalized = normalize_ashare_symbol(value)
        return (
            normalized
            if normalized and (normalized.isdigit() or normalized.startswith(("sh", "sz")))
            else value
        )

    @staticmethod
    def _name_for_symbol(symbol: str) -> str:
        return _NAME_MAP.get(symbol, symbol)

    def _request_name_lookup(self, symbol: str) -> None:
        if symbol in self._name_lookup_pending or not symbol.isdigit() or len(symbol) != 6:
            return
        failed_at = self._name_lookup_failures.get(symbol)
        if failed_at is not None and time.monotonic() - failed_at < self._name_lookup_backoff_s:
            return
        self._name_lookup_pending.add(symbol)
        self._name_lookup_pool.start(_NameLookupTask(symbol, self._name_lookup_signals))

    def _on_name_resolved(self, symbol: str, name: str) -> None:
        self._name_lookup_pending.discard(symbol)
        if name:
            self._name_lookup_failures.pop(symbol, None)
            self._quotes.setdefault(symbol, {})["name"] = name
            self._refresh_table()
        else:
            self._name_lookup_failures[symbol] = time.monotonic()

    @staticmethod
    def _format_price(value: object) -> str:
        if value in (None, ""):
            return ""
        try:
            return f"{float(value):.6g}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _format_change(value: object) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, str):
            text = value.strip()
            if text.endswith("%"):
                return text
            try:
                value = float(text)
            except ValueError:
                return text
        try:
            return f"{float(value):+.2f}%"
        except (TypeError, ValueError):
            return str(value)

    def _emit_groups_changed(self) -> None:
        self.groups_changed.emit()
        self.list_changed.emit()

    def _sync_compat_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        self._list.addItems(self.symbols())
        self._list.blockSignals(False)
        self._sync_remove_button()

    def _resize_group_list(self) -> None:
        """Keep the add-group action adjacent to the visible group entries."""
        row_height = self._group_list.sizeHintForRow(0)
        if row_height <= 0:
            row_height = 32
        content_height = max(1, self._group_list.count()) * row_height + 10
        self._group_list.setMinimumHeight(min(max(content_height, 36), 280))
        self._group_list.setMaximumHeight(280)

    def _group_column_width_for(self, names: list[str]) -> int:
        """Return a compact initial width that fits the longest group name."""
        widest = max(
            (self.fontMetrics().horizontalAdvance(name) for name in names),
            default=0,
        )
        return min(max(widest + 22, 56), 180)

    def _resize_group_column(self) -> None:
        """Set the initial group-column width without disabling user resizing."""
        width = self._group_column_width_for(list(self._groups))
        total = max(self._group_splitter.width(), width + 160)
        self._group_splitter.setSizes([width, max(total - width, 160)])

    def _resize_table(self) -> None:
        """Keep the add-symbol action below rows while retaining a scroll cap."""
        header_height = self._table.horizontalHeader().sizeHint().height()
        row_height = sum(self._table.rowHeight(row) for row in range(self._table.rowCount()))
        content_height = header_height + row_height + 4
        self._table.setMinimumHeight(min(max(content_height, 36), 360))

    def _refresh_table(self) -> None:
        symbols = self.symbols()
        self._table.setRowCount(len(symbols))
        today = date.today().isoformat()
        for row, symbol in enumerate(symbols):
            data = self._quotes.get(symbol, {})
            name = data.get("name") or self._name_for_symbol(symbol)
            if not data.get("name") and name == symbol:
                self._request_name_lookup(symbol)
            values = [
                symbol,
                name,
                data.get("price", ""),
                data.get("change", ""),
                data.get("decision", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.ItemDataRole.UserRole, symbol)
                self._table.setItem(row, col, item)
            decision = str(data.get("decision", "") or "")
            decision_day = str(data.get("decision_date", "") or "")
            color = T.FG_2
            if decision_day == today and "买入" in decision:
                color = "#f85149"
            elif decision_day == today and "卖出" in decision:
                color = "#3fb950"
            self._table.item(row, 4).setForeground(QColor(color if decision else T.FG_2))
        self._resize_table()
        self._sync_compat_list()

    def _on_group_selected(self, name: str) -> None:
        if name not in self._groups:
            return
        self._current_group = name
        self._refresh_table()
        self.group_selected.emit(name)

    def _on_table_item_clicked(self, item: QTableWidgetItem) -> None:
        symbol = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if symbol:
            self.symbol_selected.emit(symbol)

    def _sync_remove_button(self) -> None:
        return None

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        text = (item.text() or "").strip()
        if text:
            self.symbol_selected.emit(text)

    def _on_add_group_clicked(self) -> None:
        text, ok = QInputDialog.getText(self, "新增板块", "板块名称：")
        if ok and text and not self.add_group(text):
            QMessageBox.information(self, "新增板块", f"「{text.strip()}」已存在。")

    def _on_rename_group_clicked(self) -> None:
        if self._current_group == DEFAULT_GROUP:
            QMessageBox.information(self, "重命名板块", "“全部”板块不能重命名。")
            return
        text, ok = QInputDialog.getText(self, "重命名板块", "新名称：", text=self._current_group)
        if ok and text and not self.rename_group(self._current_group, text):
            QMessageBox.information(self, "重命名板块", "名称为空或已存在。")

    def _on_remove_group_clicked(self) -> None:
        if self._current_group == DEFAULT_GROUP:
            QMessageBox.information(self, "删除板块", "“全部”板块不能删除。")
            return
        if (
            QMessageBox.question(self, "删除板块", f"确定删除「{self._current_group}」？")
            == QMessageBox.StandardButton.Yes
        ):
            self.remove_current_group()

    def _on_add_clicked(self) -> None:
        text, ok = QInputDialog.getText(self, "添加自选股", _ADD_PROMPT)
        if ok and text and not self.add_symbol(text):
            QMessageBox.information(self, "添加自选股", f"「{text.strip()}」已在当前板块中。")

    def _on_remove_clicked(self) -> None:
        self.remove_selected()

    def _on_table_context_menu(self, pos) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        self._table.selectRow(row)
        menu = QMenu(self)
        remove_action = menu.addAction("删除自选股")
        if menu.exec(self._table.viewport().mapToGlobal(pos)) == remove_action:
            self.remove_selected()

    def _on_group_context_menu(self, pos) -> None:
        item = self._group_list.itemAt(pos)
        if item is None:
            return
        self._group_list.setCurrentItem(item)
        menu = QMenu(self)
        rename_action = menu.addAction("重命名板块")
        remove_action = menu.addAction("删除板块")
        chosen = menu.exec(self._group_list.viewport().mapToGlobal(pos))
        if chosen == rename_action:
            self._on_rename_group_clicked()
        elif chosen == remove_action:
            self._on_remove_group_clicked()

    def _on_scan_clicked(self) -> None:
        count = len(self.symbols())
        if count == 0:
            QMessageBox.information(self, "分析当前板块", "当前板块没有自选股。")
            return
        answer = QMessageBox.question(
            self,
            "分析当前板块",
            f"将分析当前板块的 {count} 只个股"
            + ("，将消耗较多 token" if count > 5 else "")
            + "，是否继续？",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.scan_requested.emit(self._current_group, count)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self.remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)
