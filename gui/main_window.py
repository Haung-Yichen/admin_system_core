"""
Main Window - btop-style Dashboard UI.
Industrial-themed monitoring dashboard with gauges, LEDs, and metrics.
"""
import datetime
from typing import Optional, TYPE_CHECKING
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QFrame, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QCloseEvent, QIcon
import psutil

from gui.theme import THEME, FONT_FAMILY_MONO, STYLES
from gui.components import (
    IndustrialGauge, LEDIndicator, BtopCard, MetricRow, StatBox
)

if TYPE_CHECKING:
    from core.app_context import AppContext
    from core.registry import ModuleRegistry


# Path to resources directory
RESOURCES_DIR = Path(__file__).parent.parent / "resources"


class DashboardWidget(QWidget):
    """Main dashboard content widget with industrial-style layout."""
    
    def __init__(
        self, 
        context: "AppContext", 
        registry: "ModuleRegistry",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._registry = registry
        self.start_time = datetime.datetime.now()
        self._setup_ui()
        self._start_updates()
    
    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # ========================================
        # TOP SECTION: 3 Columns
        # Column 1: System Gauges & Service Status
        # Column 2: Module/Chatbot Monitor
        # Column 3: Quick Stats & Server Metrics
        # ========================================
        top_section = QWidget()
        top_layout = QHBoxLayout(top_section)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)
        
        # -- COLUMN 1: System Health --
        col1 = QVBoxLayout()
        col1.setSpacing(10)
        
        # Gauges
        self.card_gauges = BtopCard("SYSTEM LOAD")
        gauge_grid = QGridLayout()
        gauge_grid.setSpacing(5)
        self.gauge_cpu = IndustrialGauge("CPU", THEME['cpu'])
        self.gauge_mem = IndustrialGauge("RAM", THEME['mem'])
        self.gauge_disk = IndustrialGauge("DISK", THEME['net'])
        self.gauge_net = IndustrialGauge("NET", THEME['proc'])
        gauge_grid.addWidget(self.gauge_cpu, 0, 0)
        gauge_grid.addWidget(self.gauge_mem, 0, 1)
        gauge_grid.addWidget(self.gauge_disk, 1, 0)
        gauge_grid.addWidget(self.gauge_net, 1, 1)
        self.card_gauges.add_layout(gauge_grid)
        col1.addWidget(self.card_gauges, 2)  # Stretch factor 2 (larger)
        
        # Service Status
        self.card_status = BtopCard("SERVICE STATUS")
        led_grid = QGridLayout()
        led_grid.setSpacing(5)
        self.led_server = LEDIndicator("SERVER")
        self.led_api = LEDIndicator("API")
        self.led_db = LEDIndicator("DB")
        self.led_modules = LEDIndicator("MOD")
        led_grid.addWidget(self.led_server, 0, 0)
        led_grid.addWidget(self.led_api, 0, 1)
        led_grid.addWidget(self.led_db, 0, 2)
        led_grid.addWidget(self.led_modules, 0, 3)
        self.card_status.add_layout(led_grid)
        col1.addWidget(self.card_status, 1)  # Stretch factor 1
        
        top_layout.addLayout(col1, 1)
        
        # -- COLUMN 2: Chatbot / Module Monitor --
        col2 = QVBoxLayout()
        col2.setSpacing(10)
        
        self.card_chatbot = BtopCard("CHATBOT STATUS")
        
        # Row 1: Quick Stats (StatBox)
        cb_stats = QHBoxLayout()
        cb_stats.setSpacing(5)
        self.box_sop = StatBox("SOP Docs", "0", THEME['cpu'])
        self.box_users = StatBox("Users", "0", THEME['mem'])
        cb_stats.addWidget(self.box_sop)
        cb_stats.addWidget(self.box_users)
        self.card_chatbot.add_layout(cb_stats)
        
        # Row 2: Details (MetricRow)
        self.stat_vector_model = MetricRow("Model", "Loading...", THEME['net'])
        self.stat_model_status = MetricRow("Status", "Init...", THEME['warning'])
        self.stat_device = MetricRow("Device", "Checking...", THEME['cpu'])
        
        self.card_chatbot.add_widget(self.stat_vector_model)
        self.card_chatbot.add_widget(self.stat_model_status)
        self.card_chatbot.add_widget(self.stat_device)
        
        col2.addWidget(self.card_chatbot, 1)  # Stretch factor 1 (fills full height)
        top_layout.addLayout(col2, 1)
        
        # -- COLUMN 3: General Stats --
        col3 = QVBoxLayout()
        col3.setSpacing(10)
        
        # Quick Stats
        self.card_stats = BtopCard("QUICK STATS")
        self.stat_modules = StatBox("Modules", "0", THEME['cpu'])
        self.stat_uptime = StatBox("Uptime", "0s", THEME['mem'])
        self.stat_events = StatBox("Events", "0", THEME['net'])
        
        stats_row = QHBoxLayout()
        stats_row.setSpacing(5)
        stats_row.addWidget(self.stat_modules)
        stats_row.addWidget(self.stat_uptime)
        stats_row.addWidget(self.stat_events)
        self.card_stats.add_layout(stats_row)
        col3.addWidget(self.card_stats, 1)  # Stretch factor 1
        
        # Server Metrics
        self.card_api = BtopCard("SERVER METRICS")
        
        # Row 1: StatBoxes
        srv_stats = QHBoxLayout()
        srv_stats.setSpacing(5)
        self.box_port = StatBox("Port", "8000", THEME['cpu'])
        self.box_cpu = StatBox("Proc CPU", "0%", THEME['mem'])
        srv_stats.addWidget(self.box_port)
        srv_stats.addWidget(self.box_cpu)
        self.card_api.add_layout(srv_stats)
        
        # Row 2: Status
        self.metric_status = MetricRow("Server Status", "Running", THEME['success'])
        self.card_api.add_widget(self.metric_status)

        col3.addWidget(self.card_api, 1)  # Stretch factor 1
        
        top_layout.addLayout(col3, 1)
        
        main_layout.addWidget(top_section)
        
        # ========================================
        # BOTTOM SECTION: Log Console
        # ========================================
        self.card_log = BtopCard("EVENT LOG")
        
        # Log Toolbar
        log_tools = QHBoxLayout()
        log_tools.setContentsMargins(0, 0, 0, 5)
        
        lbl_info = QLabel(" INFO ")
        lbl_info.setFont(QFont(FONT_FAMILY_MONO, 8))
        lbl_info.setStyleSheet(f"background:{THEME['cpu']}; color:{THEME['bg_base']}; border-radius:3px; padding:2px;")
        lbl_warn = QLabel(" WARN ")
        lbl_warn.setFont(QFont(FONT_FAMILY_MONO, 8))
        lbl_warn.setStyleSheet(f"background:{THEME['warning']}; color:{THEME['bg_base']}; border-radius:3px; padding:2px;")
        lbl_err = QLabel(" ERROR ")
        lbl_err.setFont(QFont(FONT_FAMILY_MONO, 8))
        lbl_err.setStyleSheet(f"background:{THEME['error']}; color:{THEME['bg_base']}; border-radius:3px; padding:2px;")
        
        log_tools.addWidget(lbl_info)
        log_tools.addWidget(lbl_warn)
        log_tools.addWidget(lbl_err)
        log_tools.addStretch()
        
        self.btn_clear = QPushButton("CLEAR")
        self.btn_clear.setStyleSheet(STYLES["btn"])
        self.btn_clear.clicked.connect(self._clear_logs)
        log_tools.addWidget(self.btn_clear)
        self.card_log.add_layout(log_tools)
        
        # Text Edit
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(STYLES["log"])
        self.card_log.add_widget(self.console)
        
        main_layout.addWidget(self.card_log, 1)  # Stretch to fill remaining space
    
    def _clear_logs(self) -> None:
        self.console.clear()
        self._event_count = 0
        self.stat_events.set_value("0")
    
    def _start_updates(self) -> None:
        self._event_count = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_stats)
        self._timer.start(1000)
    
    def _update_stats(self) -> None:
        # Update CPU/Memory gauges
        try:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage('C:').percent if hasattr(psutil, 'disk_usage') else 0
            
            self.gauge_cpu.set_value(cpu)
            self.gauge_mem.set_value(mem)
            self.gauge_disk.set_value(disk)
            
            # Update metrics
            self.box_cpu.set_value(f"{cpu:.1f}%")
        except Exception:
            pass
        
        # Update server status
        running, port = self._context.get_server_status()
        self.led_server.set_status(running)
        self.led_api.set_status(running)
        self.led_db.set_status(True)  # Assume DB is up if server is running
        
        if running:
            self.metric_status.set_value("Running", THEME['success'])
            self.box_port.set_value(str(port))
        else:
            self.metric_status.set_value("Stopped", THEME['error'])
        
        # Update modules
        modules = self._registry.get_module_names()
        module_count = len(modules)
        self.stat_modules.set_value(str(module_count))
        self.led_modules.set_status(module_count > 0)
        
        # --- Update Chatbot Specific Stats ---
        # Try to find chatbot module and get its status
        chatbot_module = self._registry.get_module("chatbot")
        if chatbot_module and hasattr(chatbot_module, "get_status"):
            status = chatbot_module.get_status()
            details = status.get("details", {})
            
            self.box_sop.set_value(details.get("SOP Documents", "0"))
            self.box_users.set_value(details.get("LINE Users", "0"))
            
            # Update Model Info (MetricRow)
            # Update Model Info (MetricRow)
            self.stat_vector_model.set_value(details.get("Embedding Model", "N/A"))
            self.stat_device.set_value(details.get("Device", "Unknown"))
            
            model_status = details.get("Model Status", "Unknown")
            status_color = THEME['success'] if model_status == "Ready" else THEME['warning']
            self.stat_model_status.set_value(model_status, status_color)
        else:
            self.box_sop.set_value("-")
            self.box_users.set_value("-")
            self.stat_model_status.set_value("Not Loaded", THEME['error'])
            self.stat_device.set_value("N/A", THEME['error'])

        # Update uptime
        delta = datetime.datetime.now() - self.start_time
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            uptime_str = f"{total_seconds}s"
        elif total_seconds < 3600:
            uptime_str = f"{total_seconds // 60}m"
        else:
            uptime_str = f"{total_seconds // 3600}h"
        self.stat_uptime.set_value(uptime_str)
        
        # Update logs from context
        logs = self._context.get_event_log()
        if logs and len(logs) > self._event_count:
            new_logs = logs[self._event_count:]
            for log_entry in new_logs:
                self._append_log(log_entry)
            self._event_count = len(logs)
            self.stat_events.set_value(str(self._event_count))
    
    def _append_log(self, text: str) -> None:
        """Append a log entry with color coding."""
        color = THEME['text_main']
        if "ERROR" in text.upper():
            color = THEME['error']
        elif "WARNING" in text.upper() or "WARN" in text.upper():
            color = THEME['warning']
        elif "INFO" in text.upper():
            color = THEME['cpu']
        
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:{THEME["text_dim"]}">[{ts}]</span> <span style="color:{color}">{text}</span>'
        
        self.console.append(html)
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())


class MainWindow(QMainWindow):
    """Main application window with btop-style dashboard."""
    
    close_to_tray = pyqtSignal()
    
    def __init__(
        self,
        context: "AppContext",
        registry: "ModuleRegistry",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._registry = registry
        self._setup_window()
        self._setup_ui()
    
    def _setup_window(self) -> None:
        self.setWindowTitle("Admin System Core - Dashboard")
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)
        
        # Set window icon
        ico_path = RESOURCES_DIR / "icon.ico"
        png_path = RESOURCES_DIR / "icon.png"
        if ico_path.exists():
            self.setWindowIcon(QIcon(str(ico_path)))
        elif png_path.exists():
            self.setWindowIcon(QIcon(str(png_path)))
        
        # Dark theme
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {THEME['bg_base']};
            }}
            QWidget {{
                font-family: {FONT_FAMILY_MONO}, monospace;
            }}
        """)
    
    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header Bar
        header_bar = QFrame()
        header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME['surface_0']};
                border-bottom: 1px solid {THEME['surface_2']};
            }}
        """)
        header_bar.setFixedHeight(50)
        
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(15, 5, 15, 5)
        
        title = QLabel("ADMIN SYSTEM CORE")
        title.setFont(QFont(FONT_FAMILY_MONO, 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {THEME['cpu']}; border: none;")
        hb_layout.addWidget(title)
        
        hb_layout.addStretch()
        
        version_label = QLabel("v1.0 | PyQt6 + FastAPI")
        version_label.setFont(QFont(FONT_FAMILY_MONO, 9))
        version_label.setStyleSheet(f"color: {THEME['text_dim']}; border: none;")
        hb_layout.addWidget(version_label)
        
        layout.addWidget(header_bar)
        
        # Dashboard
        self._dashboard = DashboardWidget(self._context, self._registry)
        layout.addWidget(self._dashboard)
        
        # Footer
        footer = QLabel("Press [X] to minimize to tray  │  Right-click tray icon → Exit to close")
        footer.setFont(QFont(FONT_FAMILY_MONO, 9))
        footer.setStyleSheet(f"color: {THEME['text_dim']}; padding: 5px; background-color: {THEME['surface_0']};")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """Override close to minimize to tray instead."""
        event.ignore()
        self.hide()
        self.close_to_tray.emit()
