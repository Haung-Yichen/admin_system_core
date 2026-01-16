"""
Splash Screen - Btop-style startup animation display.
Shows loading progress before main window appears.
"""
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, 
    QGraphicsDropShadowEffect, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor, QLinearGradient

from gui.theme import THEME, FONT_FAMILY_MONO


class StreamerProgressBar(QWidget):
    """A thin, glowing progress bar with a streamer effect."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self._progress = 0.0
        self._glow_pos = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate_glow)
        self._timer.start(30)
        
    def set_progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, value))
        self.update()

    def _animate_glow(self) -> None:
        self._glow_pos += 0.02
        if self._glow_pos > 1.4:
            self._glow_pos = -0.4
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # Background Track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(THEME["surface_0"]))
        painter.drawRoundedRect(0, 0, w, h, 2, 2)
        
        # Fill
        if self._progress > 0:
            fill_width = int(w * self._progress)
            
            # Gradient Fill - Cyan to Green (btop style)
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor(THEME["cpu"]))  # Cyan
            grad.setColorAt(1, QColor(THEME["success"]))  # Green
            
            painter.setBrush(grad)
            painter.drawRoundedRect(0, 0, fill_width, h, 2, 2)
            
            # Streamer/Shine Effect
            shine_x = int(w * self._glow_pos)
            shine_w = 40
            
            if shine_x + shine_w > 0 and shine_x < w:
                shine = QLinearGradient(shine_x, 0, shine_x + shine_w, 0)
                c_transparent = QColor(255, 255, 255, 0)
                c_white = QColor(255, 255, 255, 100)
                shine.setColorAt(0, c_transparent)
                shine.setColorAt(0.5, c_white)
                shine.setColorAt(1, c_transparent)
                
                painter.setBrush(shine)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
                painter.drawRoundedRect(0, 0, fill_width, h, 2, 2)


class AnimatedSplashScreen(QWidget):
    """Custom animated splash screen with btop-style progress indicator."""
    
    finished = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setFixedSize(640, 360)
        
        # Main Container
        self.bg = QFrame(self)
        self.bg.setGeometry(10, 10, 620, 340)
        self.bg.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME['bg_base']};
                border: 1px solid {THEME['surface_2']};
                border-radius: 4px;
            }}
        """)
        
        # Drop Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 8)
        self.bg.setGraphicsEffect(shadow)
        
        # Layout
        layout = QVBoxLayout(self.bg)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(8)
        
        # 1. Header Area
        title = QLabel("ADMIN_SYSTEM :: BOOT")
        title.setFont(QFont(FONT_FAMILY_MONO, 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {THEME['text_main']}; letter-spacing: 2px;")
        layout.addWidget(title)
        
        ver = QLabel("v1.0 | secure_boot=1 | modules_enabled")
        ver.setFont(QFont(FONT_FAMILY_MONO, 8))
        ver.setStyleSheet(f"color: {THEME['text_dim']};")
        layout.addWidget(ver)
        
        layout.addSpacing(15)
        
        # 2. ASCII Art / Centerpiece (Terminal style box)
        ascii_frame = QFrame()
        ascii_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME['bg_crust']};
                border: 1px solid {THEME['surface_2']};
                border-radius: 2px;
            }}
        """)
        ascii_layout = QVBoxLayout(ascii_frame)
        ascii_layout.setContentsMargins(10, 10, 10, 10)
        
        ascii_art = QLabel(
            "   █████╗ ██████╗ ███╗   ███╗██╗███╗   ██╗\n"
            "  ██╔══██╗██╔══██╗████╗ ████║██║████╗  ██║\n"
            "  ███████║██║  ██║██╔████╔██║██║██╔██╗ ██║\n"
            "  ██╔══██║██║  ██║██║╚██╔╝██║██║██║╚██╗██║\n"
            "  ██║  ██║██████╔╝██║ ╚═╝ ██║██║██║ ╚████║\n"
            "  ╚═╝  ╚═╝╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝"
        )
        ascii_art.setFont(QFont(FONT_FAMILY_MONO, 8))
        ascii_art.setStyleSheet(f"color: {THEME['cpu']}; border: none;")
        ascii_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ascii_layout.addWidget(ascii_art)
        layout.addWidget(ascii_frame)
        
        layout.addStretch()
        
        # 3. Dynamic Log Line
        self.lbl_log = QLabel("> Initializing system components...")
        self.lbl_log.setFont(QFont(FONT_FAMILY_MONO, 9))
        self.lbl_log.setStyleSheet(f"color: {THEME['success']};")
        layout.addWidget(self.lbl_log)
        
        # 4. Progress Bar
        self.progress = StreamerProgressBar()
        layout.addWidget(self.progress)
        
        # 5. Footer Status
        self.lbl_status = QLabel("WAITING")
        self.lbl_status.setFont(QFont(FONT_FAMILY_MONO, 8, QFont.Weight.Bold))
        self.lbl_status.setStyleSheet(f"color: {THEME['warning']};")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.lbl_status)

        self._center_on_screen()
    
    def set_progress(self, value: int, status: str = "") -> None:
        """Update the progress bar and status text."""
        self.progress.set_progress(value / 100.0)
        if status:
            self.lbl_log.setText(f"> {status}")
        
        # Change status color based on context
        if "error" in status.lower():
            self.lbl_status.setText("ERROR")
            self.lbl_status.setStyleSheet(f"color: {THEME['error']};")
        elif "success" in status.lower() or "ready" in status.lower() or "started" in status.lower():
            self.lbl_status.setText("OK")
            self.lbl_status.setStyleSheet(f"color: {THEME['success']};")
        else:
            self.lbl_status.setText("LOADING")
            self.lbl_status.setStyleSheet(f"color: {THEME['warning']};")
    
    def start_animation(self) -> None:
        """Start the loading animation (no-op, progress bar handles it)."""
        pass
    
    def stop_animation(self) -> None:
        """Stop the loading animation."""
        pass
    
    def show_loading_sequence(self, callback: callable) -> None:
        """Show animated loading sequence then call callback."""
        self.show()
        
        steps = [
            (0, "Initializing core"),
            (20, "Loading configuration"),
            (40, "Registering modules"),
            (60, "Starting API server"),
            (80, "Preparing GUI"),
            (100, "System ready - starting dashboard")
        ]
        
        delay = 0
        for progress, status in steps:
            QTimer.singleShot(delay, lambda p=progress, s=status: self.set_progress(p, s))
            delay += 400
        
        # Final callback
        QTimer.singleShot(delay + 500, lambda: self._finish_loading(callback))
    
    def _finish_loading(self, callback: callable) -> None:
        """Complete loading and transition to main window."""
        self.finished.emit()
        callback()
        self.close()
    
    def _center_on_screen(self) -> None:
        try:
            screen = QApplication.primaryScreen().availableGeometry()
            size = self.geometry()
            self.move(
                int((screen.width() - size.width()) / 2),
                int((screen.height() - size.height()) / 2)
            )
        except Exception:
            pass
