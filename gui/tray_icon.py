"""
System Tray Icon - Windows system tray integration.
"""
from typing import Optional
from pathlib import Path
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PyQt6.QtCore import pyqtSignal, QObject


# Path to resources directory
RESOURCES_DIR = Path(__file__).parent.parent / "resources"


class SystemTrayManager(QObject):
    """Manages the system tray icon and its context menu."""
    
    show_window_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._tray_icon = QSystemTrayIcon(self)
        self._menu = QMenu()
        self._tray_icon.setIcon(self._load_icon())
        self._setup_menu()
        self._tray_icon.setContextMenu(self._menu)
        self._tray_icon.setToolTip("Admin System Core")
        self._tray_icon.activated.connect(self._on_tray_activated)
    
    def _load_icon(self) -> QIcon:
        """Load icon from resources directory, fallback to generated icon."""
        ico_path = RESOURCES_DIR / "icon.ico"
        png_path = RESOURCES_DIR / "icon.png"
        
        if ico_path.exists():
            return QIcon(str(ico_path))
        elif png_path.exists():
            return QIcon(str(png_path))
        else:
            return self._create_default_icon()
    
    def _create_default_icon(self) -> QIcon:
        """Create a fallback icon programmatically."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#1e1e2e"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Consolas", 36, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#89b4fa"))
        painter.drawText(0, 0, 64, 64, 0x0084, "A")
        painter.setPen(QColor("#cba6f7"))
        painter.drawEllipse(4, 4, 56, 56)
        painter.end()
        return QIcon(pixmap)
    
    def _setup_menu(self) -> None:
        self._show_action = QAction("Show Dashboard", self)
        self._show_action.triggered.connect(lambda: self.show_window_requested.emit())
        self._menu.addAction(self._show_action)
        self._menu.addSeparator()
        self._status_action = QAction("● Server: Running", self)
        self._status_action.setEnabled(False)
        self._menu.addAction(self._status_action)
        self._menu.addSeparator()
        self._exit_action = QAction("Exit", self)
        self._exit_action.triggered.connect(lambda: self.exit_requested.emit())
        self._menu.addAction(self._exit_action)
    
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window_requested.emit()
    
    def show(self) -> None:
        self._tray_icon.show()
    
    def hide(self) -> None:
        self._tray_icon.hide()
    
    def update_server_status(self, running: bool, port: int = 8000) -> None:
        if running:
            self._status_action.setText(f"● Server: Running (:{port})")
        else:
            self._status_action.setText("○ Server: Stopped")
    
    def show_notification(self, title: str, message: str) -> None:
        self._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
