"""Validate the shared itinerary-card geometry and text hierarchy."""

from __future__ import annotations

from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QFont
from qgis.core import (
    QgsApplication,
    QgsLayoutItemLabel,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsUnitTypes,
)

import card_layout


def close(actual: float, expected: float, tolerance: float = 0.02) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{actual:.3f} != {expected:.3f}")


def main() -> int:
    app = QgsApplication([], False)
    app.initQgis()
    try:
        layout = QgsPrintLayout(QgsProject.instance())
        layout.initializeDefaults()
        layout.pageCollection().page(0).setPageSize(
            QgsLayoutSize(220.0, 180.0, QgsUnitTypes.LayoutMillimeters)
        )
        entries = (
            ("9.13", ("景点甲", "景点乙（未入）")),
            ("9.14", ("景点丙（别名）",)),
        )
        anchor = QPointF(165.0, 80.0)
        bounds = card_layout.add_itinerary_card(
            layout,
            "测试地点",
            entries,
            ("upper_left", -8.0, -5.0),
            anchor,
            (10.0, 10.0, 200.0, 150.0),
        )

        labels = [item for item in layout.items() if isinstance(item, QgsLayoutItemLabel)]
        by_text = {label.text(): label for label in labels}
        expected = {"测试地点", "9.13", "9.14", "景点甲", "景点乙", "（未入）", "景点丙", "（别名）"}
        if set(by_text) != expected:
            raise AssertionError(f"unexpected labels: {set(by_text) ^ expected}")
        if any("\n" in label.text() for label in labels):
            raise AssertionError("place labels must not contain newlines")

        for text in ("景点甲", "景点乙", "景点丙"):
            label = by_text[text]
            close(label.sizeWithUnits().height(), card_layout.BODY_ROW_HEIGHT)
            if label.textFormat().font().weight() != QFont.Medium:
                raise AssertionError(f"body label is not medium weight: {text}")

        if not by_text["测试地点"].textFormat().font().bold():
            raise AssertionError("title is not bold")
        for date in ("9.13", "9.14"):
            if not by_text[date].textFormat().font().bold():
                raise AssertionError(f"date is not bold: {date}")

        status = by_text["（未入）"].textFormat()
        close(status.size(), card_layout.PARENTHETICAL_SIZE)
        if status.color().name().upper() != card_layout.SECONDARY_COLOR:
            raise AssertionError("status note does not use the secondary color")

        measured_widths = [
            card_layout.measured_text_width_mm("测试地点", card_layout.TITLE_SIZE, bold=True),
            card_layout.measured_text_width_mm("9.13", card_layout.DATE_SIZE, bold=True, family="Arial"),
            card_layout.measured_text_width_mm("9.14", card_layout.DATE_SIZE, bold=True, family="Arial"),
            *(card_layout.place_width_mm(place) for _, places in entries for place in places),
        ]
        expected_inner_width = max(measured_widths)
        close(
            bounds.width - card_layout.HORIZONTAL_PADDING * 2.0,
            max(expected_inner_width, 14.0 - card_layout.HORIZONTAL_PADDING * 2.0),
        )
        status_x = by_text["（未入）"].positionWithUnits().x()
        expected_status_x = (
            bounds.x
            + card_layout.HORIZONTAL_PADDING
            + card_layout.measured_text_width_mm(
                "景点乙", card_layout.BODY_SIZE, weight=QFont.Medium
            )
        )
        close(status_x, expected_status_x)

        last_row = by_text["景点丙"]
        last_row_bottom = last_row.positionWithUnits().y() + last_row.sizeWithUnits().height()
        card_bottom = bounds.y + bounds.height
        close(card_bottom - last_row_bottom, card_layout.BOTTOM_PADDING)

        target = bounds.leader_target
        on_vertical_edge = close_edge(target.x(), bounds.x) or close_edge(
            target.x(), bounds.x + bounds.width
        )
        on_horizontal_edge = close_edge(target.y(), bounds.y) or close_edge(
            target.y(), bounds.y + bounds.height
        )
        if not (on_vertical_edge or on_horizontal_edge):
            raise AssertionError("leader does not terminate on a card edge")
        return 0
    finally:
        QgsProject.instance().clear()
        app.exitQgis()


def close_edge(actual: float, expected: float, tolerance: float = 0.02) -> bool:
    return abs(actual - expected) <= tolerance


if __name__ == "__main__":
    raise SystemExit(main())
