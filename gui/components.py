"""
Industrial-style UI Components for Dashboard.
Includes gauges, LED indicators, cards, and metric displays.
"""
import math
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

from gui.theme import THEME, FONT_FAMILY_MONO, STYLES


class IndustrialGauge(QWidget):
    """Arc gauge with industrial styling - like a car speedometer."""
    
    def __init__(self, label: str, color: str, max_val: int = 100, parent=None):
        super().__init__(parent)
        self.label = label
        self.color = QColor(color)
        self.max_val = max_val
        self.value = 0
        self.setMinimumSize(120, 100)
        
    def set_value(self, val: float) -> None:
        self.value = max(0, min(self.max_val, val))
        self.update()
        
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2 + 10
        radius = min(w, h) // 2 - 15
        
        # Arc parameters (180 degree arc, starting from left)
        start_angle = 180 * 16  # Qt uses 1/16th degree
        span_angle = -180 * 16  # Negative = clockwise
        
        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        
        # Background arc (dark)
        pen = QPen(QColor(THEME['surface_2']), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, start_angle, span_angle)
        
        # Value arc (colored)
        if self.value > 0:
            pct = self.value / self.max_val
            value_span = int(span_angle * pct)
            
            # Gradient color based on value
            if pct < 0.5:
                arc_color = self.color
            elif pct < 0.8:
                arc_color = QColor(THEME['warning'])
            else:
                arc_color = QColor(THEME['error'])
            
            pen = QPen(arc_color, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, start_angle, value_span)
        
        # Tick marks
        painter.setPen(QPen(QColor(THEME['text_dim']), 1))
        for i in range(5):
            angle = math.radians(180 - i * 45)
            inner_r = radius - 12
            outer_r = radius - 5
            x1 = cx + int(inner_r * math.cos(angle))
            y1 = cy - int(inner_r * math.sin(angle))
            x2 = cx + int(outer_r * math.cos(angle))
            y2 = cy - int(outer_r * math.sin(angle))
            painter.drawLine(x1, y1, x2, y2)
        
        # Value text (center)
        painter.setPen(QColor(THEME['text_main']))
        painter.setFont(QFont(FONT_FAMILY_MONO, 16, QFont.Weight.Bold))
        val_text = f"{int(self.value)}%"
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(val_text)
        painter.drawText(cx - tw // 2, cy + 5, val_text)
        
        # Label (bottom)
        painter.setPen(QColor(THEME['text_dim']))
        painter.setFont(QFont(FONT_FAMILY_MONO, 9))
        lw = fm.horizontalAdvance(self.label)
        painter.drawText(cx - lw // 2, h - 5, self.label)


class LEDIndicator(QWidget):
    """LED-style status indicator with glow effect."""
    
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self._active = False
        self._color = QColor(THEME['surface_2'])
        self.setFixedSize(80, 55)
        
    def set_status(self, active: bool, status_text=None) -> None:
        self._active = active
        if active:
            self._color = QColor(THEME['success'])
        else:
            self._color = QColor(THEME['error'])
        self.update()
        
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cx = w // 2
        led_y = 16
        led_r = 10
        
        # Glow effect (if active)
        if self._active:
            for i in range(3, 0, -1):
                glow_color = QColor(self._color)
                glow_color.setAlpha(50 // i)
                painter.setBrush(glow_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(cx - led_r - i*3, led_y - led_r - i*3, 
                                   (led_r + i*3) * 2, (led_r + i*3) * 2)
        
        # LED bezel (dark ring)
        painter.setBrush(QColor(THEME['surface_1']))
        painter.setPen(QPen(QColor(THEME['surface_2']), 2))
        painter.drawEllipse(cx - led_r - 3, led_y - led_r - 3, 
                           (led_r + 3) * 2, (led_r + 3) * 2)
        
        # LED body
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx - led_r, led_y - led_r, led_r * 2, led_r * 2)
        
        # Highlight (specular)
        highlight = QColor(255, 255, 255, 80 if self._active else 30)
        painter.setBrush(highlight)
        painter.drawEllipse(cx - led_r + 3, led_y - led_r + 2, 5, 4)
        
        # Label
        painter.setPen(QColor(THEME['text_sub']))
        painter.setFont(QFont(FONT_FAMILY_MONO, 8))
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(self.label)
        painter.drawText(cx - tw // 2, h - 5, self.label)


class BtopCard(QFrame):
    """Card container with title and divider line."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLES["card"])
        self.setFrameShape(QFrame.Shape.StyledPanel)
        
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(10, 10, 10, 10)
        self.layout_main.setSpacing(6)
        
        # Header
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setFont(QFont(FONT_FAMILY_MONO, 10, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet(STYLES["card_title"])
        self.layout_main.addWidget(self.lbl_title)
        
        # Line Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet(f"background-color: {THEME['surface_2']}; border: none; max-height: 1px;")
        self.layout_main.addWidget(line)
        
        self.layout_main.addSpacing(4)
        
        # Content placeholder
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        self.layout_main.addWidget(self.content_widget)

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self.content_layout.addLayout(layout)


class MetricRow(QWidget):
    """Compact metric display: Label ............. Value"""
    
    def __init__(self, label: str, value: str = "--", color: str = None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("border: none; background: transparent;")
        self.color = color or THEME['text_main']
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        
        self.lbl_name = QLabel(label)
        self.lbl_name.setFont(QFont(FONT_FAMILY_MONO, 9))
        self.lbl_name.setStyleSheet(f"color: {THEME['text_sub']};")
        layout.addWidget(self.lbl_name)
        
        layout.addStretch()
        
        self.lbl_value = QLabel(str(value))
        self.lbl_value.setFont(QFont(FONT_FAMILY_MONO, 9, QFont.Weight.Bold))
        self.lbl_value.setStyleSheet(f"color: {self.color};")
        layout.addWidget(self.lbl_value)
    
    def set_value(self, value: str, color: str = None) -> None:
        self.lbl_value.setText(str(value))
        if color:
            self.color = color
            self.lbl_value.setStyleSheet(f"color: {self.color};")


class StatBox(QWidget):
    """Large stat display with value and label below."""
    
    def __init__(self, label: str, value: str = "0", color: str = None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("border: none; background: transparent;")
        self.color = color or THEME['cpu']
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_value = QLabel(str(value))
        self.lbl_value.setFont(QFont(FONT_FAMILY_MONO, 20, QFont.Weight.Bold))
        self.lbl_value.setStyleSheet(f"color: {self.color};")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_value)
        
        self.lbl_name = QLabel(label.upper())
        self.lbl_name.setFont(QFont(FONT_FAMILY_MONO, 8))
        self.lbl_name.setStyleSheet(f"color: {THEME['text_dim']};")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_name)
    
    def set_value(self, value: str, color: str = None) -> None:
        self.lbl_value.setText(str(value))
        if color:
            self.color = color
            self.lbl_value.setStyleSheet(f"color: {self.color};")


class LargeStatBox(QWidget):
    """Extra large stat display for prominent metrics."""
    
    def __init__(self, label: str, value: str = "0", color: str = None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            background-color: {THEME['surface_1']};
            border: 1px solid {THEME['surface_2']};
            border-radius: 6px;
        """)
        self.color = color or THEME['cpu']
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_value = QLabel(str(value))
        self.lbl_value.setFont(QFont(FONT_FAMILY_MONO, 28, QFont.Weight.Bold))
        self.lbl_value.setStyleSheet(f"color: {self.color}; background: transparent; border: none;")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_value)
        
        self.lbl_name = QLabel(label.upper())
        self.lbl_name.setFont(QFont(FONT_FAMILY_MONO, 10))
        self.lbl_name.setStyleSheet(f"color: {THEME['text_sub']}; background: transparent; border: none;")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_name)
    
    def set_value(self, value: str, color: str = None) -> None:
        self.lbl_value.setText(str(value))
        if color:
            self.color = color
            self.lbl_value.setStyleSheet(f"color: {self.color}; background: transparent; border: none;")

