from __future__ import annotations


APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #101418;
    color: #e8edf2;
    font-size: 13px;
}
QFrame#Sidebar {
    background: #151b22;
    border-right: 1px solid #26313c;
}
QPushButton {
    background: #26313c;
    border: 1px solid #354454;
    border-radius: 6px;
    padding: 8px 12px;
    color: #edf3f8;
}
QPushButton:hover {
    background: #31404f;
}
QPushButton:checked {
    background: #2d5f8a;
    border-color: #3f83ba;
}
QPushButton#NavButton {
    text-align: left;
    border: 0;
    background: transparent;
    padding: 10px 12px;
}
QPushButton#NavButton:hover {
    background: #202a34;
}
QPushButton#NavButton:checked {
    background: #2d5f8a;
}
QLabel#AppTitle {
    font-size: 18px;
    font-weight: 700;
}
QLabel#PageTitle {
    font-size: 22px;
    font-weight: 700;
}
QLabel#PageDescription, QLabel#MutedLabel, QLabel[objectName="MutedLabel"] {
    color: #a9b7c4;
}
QLabel#SectionTitle {
    font-size: 15px;
    font-weight: 700;
}
QFrame#MetricCard {
    background: #171e26;
    border: 1px solid #2a3541;
    border-radius: 8px;
}
QLabel#MetricCardTitle {
    color: #a9b7c4;
    font-size: 12px;
}
QLabel#MetricCardValue {
    font-size: 20px;
    font-weight: 700;
}
QLabel#MetricCardValue[negative="true"],
QLabel[negative="true"] {
    color: #ffb3a7;
}
QLabel#StatusBadge {
    border-radius: 8px;
    padding: 3px 8px;
    background: #2a3541;
}
QLabel#StatusBadge[tone="good"] {
    background: #1d4b35;
    color: #c9f7dd;
}
QLabel#StatusBadge[tone="warning"] {
    background: #5d4a1e;
    color: #ffe4a6;
}
QLabel#StatusBadge[tone="danger"] {
    background: #63302e;
    color: #ffd2cc;
}
QLineEdit, QTextEdit, QComboBox, QDateEdit {
    background: #0d1117;
    border: 1px solid #31404f;
    border-radius: 5px;
    padding: 6px;
    color: #edf3f8;
}
QGroupBox {
    border: 1px solid #2a3541;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QTableWidget {
    background: #0d1117;
    alternate-background-color: #111820;
    gridline-color: #26313c;
    selection-background-color: #2d5f8a;
    border: 1px solid #26313c;
    border-radius: 6px;
}
QHeaderView::section {
    background: #1c2630;
    color: #dce5ee;
    padding: 7px;
    border: 0;
    border-right: 1px solid #2a3541;
    font-weight: 700;
}
QScrollArea {
    border: 0;
}
"""
