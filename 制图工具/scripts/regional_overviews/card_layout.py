"""Shared itinerary-card layout for the Gansu and regional maps."""

from __future__ import annotations

import re
from dataclasses import dataclass

from qgis.PyQt.QtCore import QPointF, Qt
from qgis.PyQt.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPolygonF
from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsLayoutItemLabel,
    QgsLayoutItemPolyline,
    QgsLayoutItemShape,
    QgsLayoutMeasurement,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsLineSymbol,
    QgsPrintLayout,
    QgsTextFormat,
    QgsUnitTypes,
)


FONT_FAMILY = "思源黑体 CN"
TITLE_SIZE = 9.2
DATE_SIZE = 7.8
BODY_SIZE = 8.4
PARENTHETICAL_SIZE = 7.2

HORIZONTAL_PADDING = 2.6
TITLE_TOP = 0.6
TITLE_HEIGHT = 5.7
TITLE_RULE_Y = 6.8
CONTENT_TOP = 7.4
DATE_HEIGHT = 3.8
DATE_RULE_GAP = 0.2
AFTER_DATE_RULE = 0.7
BODY_ROW_HEIGHT = 4.7
ENTRY_GAP = 0.8
BOTTOM_PADDING = 1.8
CORNER_RADIUS = 2.0
DASH_PATTERN = (0.8, 1.0)

MAIN_TEXT_COLOR = "#202020"
BODY_COLOR = MAIN_TEXT_COLOR
PARENTHETICAL_COLOR = "#555555"
SECONDARY_COLOR = PARENTHETICAL_COLOR
SECONDARY_MARKERS = (
    "未入",
    "未进",
    "未去",
    "未开放",
    "闭馆",
    "关闭",
    "外观",
    "路过",
    "途经",
)

PARENTHETICAL_RE = re.compile(r"^(.*?)([\uff08(].*[\uff09)])$")


@dataclass(frozen=True)
class CardBounds:
    x: float
    y: float
    width: float
    height: float
    leader_target: QPointF


def split_parenthetical(text: str) -> tuple[str, str]:
    match = PARENTHETICAL_RE.match(text)
    if not match:
        return text, ""
    return match.group(1), match.group(2)


def measured_text_width_mm(
    text: str,
    point_size: float,
    bold: bool = False,
    family: str = FONT_FAMILY,
    weight: int | None = None,
) -> float:
    font = QFont(family)
    font.setPointSizeF(point_size)
    if weight is None:
        font.setBold(bold)
    else:
        font.setWeight(weight)
    screen = QGuiApplication.primaryScreen()
    dpi = screen.logicalDotsPerInchX() if screen else 96.0
    return QFontMetricsF(font).horizontalAdvance(text) * 25.4 / dpi


def place_width_mm(place: str) -> float:
    main, parenthetical = split_parenthetical(place)
    width = measured_text_width_mm(main, BODY_SIZE, weight=QFont.Medium)
    if parenthetical:
        width += measured_text_width_mm(parenthetical, PARENTHETICAL_SIZE)
    return width


def card_size(
    title: str,
    entries: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[float, float]:
    widths = [measured_text_width_mm(title, TITLE_SIZE, bold=True)]
    cursor = CONTENT_TOP
    for entry_index, (date, places) in enumerate(entries):
        widths.append(measured_text_width_mm(date, DATE_SIZE, bold=True, family="Arial"))
        widths.extend(place_width_mm(place) for place in places)
        cursor += DATE_HEIGHT + DATE_RULE_GAP + AFTER_DATE_RULE
        cursor += len(places) * BODY_ROW_HEIGHT
        if entry_index < len(entries) - 1:
            cursor += ENTRY_GAP

    width = max(14.0, max(widths) + HORIZONTAL_PADDING * 2.0)
    if entries:
        height = cursor + BOTTOM_PADDING
    else:
        height = TITLE_RULE_Y + BOTTOM_PADDING
    return width, height


def _text_format(
    size: float,
    color: str,
    family: str = FONT_FAMILY,
    bold: bool = False,
    weight: int | None = None,
) -> QgsTextFormat:
    text_format = QgsTextFormat()
    font = QFont(family)
    font.setPointSizeF(size)
    if weight is None:
        font.setBold(bold)
    else:
        font.setWeight(weight)
    text_format.setFont(font)
    text_format.setSize(size)
    text_format.setColor(QColor(color))
    return text_format


def _add_label(
    layout: QgsPrintLayout,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    size: float,
    color: str,
    family: str = FONT_FAMILY,
    bold: bool = False,
    weight: int | None = None,
) -> QgsLayoutItemLabel:
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    item.setTextFormat(_text_format(size, color, family, bold, weight))
    item.setHAlign(Qt.AlignLeft)
    item.setVAlign(Qt.AlignVCenter)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    item.attemptResize(QgsLayoutSize(width, height, QgsUnitTypes.LayoutMillimeters))
    return item


def _add_line(
    layout: QgsPrintLayout,
    points: list[QPointF],
    color: str,
    width: float,
    dashed: bool = False,
) -> QgsLayoutItemPolyline:
    item = QgsLayoutItemPolyline(QPolygonF(points), layout)
    symbol = QgsLineSymbol.createSimple(
        {
            "line_color": color,
            "line_width": str(width),
            "line_width_unit": "MM",
            "line_style": "dash" if dashed else "solid",
        }
    )
    if dashed:
        line_layer = symbol.symbolLayer(0)
        line_layer.setUseCustomDashPattern(True)
        line_layer.setCustomDashVector(list(DASH_PATTERN))
        line_layer.setCustomDashPatternUnit(Qgis.RenderUnit.Millimeters)
    item.setSymbol(symbol)
    layout.addLayoutItem(item)
    return item


def _placed_origin(
    anchor: QPointF,
    width: float,
    height: float,
    placement: tuple[str, float, float],
) -> tuple[float, float]:
    side, x_offset, y_offset = placement
    if side == "above":
        return anchor.x() - width / 2.0 + x_offset, anchor.y() - height + y_offset
    if side == "below":
        return anchor.x() - width / 2.0 + x_offset, anchor.y() + y_offset
    if side == "left":
        return anchor.x() - width + x_offset, anchor.y() - height / 2.0 + y_offset
    if side == "right":
        return anchor.x() + x_offset, anchor.y() - height / 2.0 + y_offset
    if side == "upper_right":
        return anchor.x() + x_offset, anchor.y() - height + y_offset
    if side == "upper_left":
        return anchor.x() - width + x_offset, anchor.y() - height + y_offset
    if side == "lower_left":
        return anchor.x() - width + x_offset, anchor.y() + y_offset
    if side == "lower_right":
        return anchor.x() + x_offset, anchor.y() + y_offset
    raise ValueError(f"Unknown card placement: {side}")


def nearest_edge_point(
    anchor: QPointF,
    x: float,
    y: float,
    width: float,
    height: float,
) -> QPointF:
    clamped_x = min(max(anchor.x(), x), x + width)
    clamped_y = min(max(anchor.y(), y), y + height)
    candidates = (
        QPointF(clamped_x, y),
        QPointF(clamped_x, y + height),
        QPointF(x, clamped_y),
        QPointF(x + width, clamped_y),
    )
    return min(
        candidates,
        key=lambda point: (point.x() - anchor.x()) ** 2 + (point.y() - anchor.y()) ** 2,
    )


def add_itinerary_card(
    layout: QgsPrintLayout,
    title: str,
    entries: tuple[tuple[str, tuple[str, ...]], ...],
    placement: tuple[str, float, float],
    anchor: QPointF,
    frame: tuple[float, float, float, float],
    frame_inset: float = 2.0,
) -> CardBounds:
    width, height = card_size(title, entries)
    x, y = _placed_origin(anchor, width, height, placement)
    x = min(max(frame[0] + frame_inset, x), frame[0] + frame[2] - width - frame_inset)
    y = min(max(frame[1] + frame_inset, y), frame[1] + frame[3] - height - frame_inset)

    leader_target = nearest_edge_point(anchor, x, y, width, height)
    _add_line(layout, [anchor, leader_target], "#748984", 0.16)

    shape = QgsLayoutItemShape(layout)
    shape.setShapeType(QgsLayoutItemShape.Rectangle)
    shape.setCornerRadius(QgsLayoutMeasurement(CORNER_RADIUS, QgsUnitTypes.LayoutMillimeters))
    shape.setSymbol(
        QgsFillSymbol.createSimple(
            {
                "color": "#FFF9EE" if entries else "#FBFCFB",
                "outline_color": "#56766C" if entries else "#8C9A96",
                "outline_width": "0.26" if entries else "0.22",
                "outline_width_unit": "MM",
            }
        )
    )
    layout.addLayoutItem(shape)
    shape.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    shape.attemptResize(QgsLayoutSize(width, height, QgsUnitTypes.LayoutMillimeters))

    title_label = _add_label(
        layout,
        title,
        x + HORIZONTAL_PADDING,
        y + TITLE_TOP,
        width - HORIZONTAL_PADDING * 2.0,
        TITLE_HEIGHT,
        TITLE_SIZE,
        MAIN_TEXT_COLOR,
        bold=True,
    )
    title_label.setHAlign(Qt.AlignHCenter)
    _add_line(
        layout,
        [QPointF(x + 2.0, y + TITLE_RULE_Y), QPointF(x + width - 2.0, y + TITLE_RULE_Y)],
        "#9EAAA7",
        0.14,
    )

    cursor = y + CONTENT_TOP
    for entry_index, (date, places) in enumerate(entries):
        _add_label(
            layout,
            date,
            x + HORIZONTAL_PADDING,
            cursor,
            width - HORIZONTAL_PADDING * 2.0,
            DATE_HEIGHT,
            DATE_SIZE,
            MAIN_TEXT_COLOR,
            family="Arial",
            bold=True,
        )
        cursor += DATE_HEIGHT
        rule_y = cursor + DATE_RULE_GAP
        _add_line(
            layout,
            [QPointF(x + HORIZONTAL_PADDING, rule_y), QPointF(x + width - HORIZONTAL_PADDING, rule_y)],
            "#AAB4B1",
            0.10,
            dashed=True,
        )
        cursor += DATE_RULE_GAP + AFTER_DATE_RULE

        for place in places:
            main, parenthetical = split_parenthetical(place)
            available_width = width - HORIZONTAL_PADDING * 2.0
            _add_label(
                layout,
                main,
                x + HORIZONTAL_PADDING,
                cursor,
                available_width,
                BODY_ROW_HEIGHT,
                BODY_SIZE,
                BODY_COLOR,
                weight=QFont.Medium,
            )
            if parenthetical:
                main_width = measured_text_width_mm(
                    main, BODY_SIZE, weight=QFont.Medium
                )
                parenthetical_color = (
                    SECONDARY_COLOR
                    if any(marker in parenthetical for marker in SECONDARY_MARKERS)
                    else PARENTHETICAL_COLOR
                )
                _add_label(
                    layout,
                    parenthetical,
                    x + HORIZONTAL_PADDING + main_width,
                    cursor,
                    max(1.0, available_width - main_width),
                    BODY_ROW_HEIGHT,
                    PARENTHETICAL_SIZE,
                    parenthetical_color,
                )
            cursor += BODY_ROW_HEIGHT
        if entry_index < len(entries) - 1:
            cursor += ENTRY_GAP

    return CardBounds(x, y, width, height, leader_target)
