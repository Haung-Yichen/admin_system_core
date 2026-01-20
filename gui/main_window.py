"""
Main Window - btop-style Dashboard UI.
Industrial-themed monitoring dashboard with gauges, LEDs, and metrics.
Dynamically renders module status cards.
"""
import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QFrame, QGridLayout, QPushButton, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QCloseEvent, QIcon
import psutil

from gui.theme import THEME, FONT_FAMILY_MONO, STYLES
from gui.components import (
    IndustrialGauge, LEDIndicator, BtopCard, MetricRow, StatBox, LargeStatBox
)

if TYPE_CHECKING:
    from core.app_context import AppContext
    from core.registry import ModuleRegistry


# Path to resources directory
RESOURCES_DIR = Path(__file__).parent.parent / "resources"

# Color palette for dynamic cards
MODULE_COLORS = [
    THEME['cpu'], THEME['mem'], THEME['net'], THEME['proc'],
    THEME['success'], THEME['warning']
]


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
        
        # Dynamic module widget references: {module_name: {key: widget}}
        self._module_widgets: Dict[str, Dict[str, Any]] = {}
        self._module_cards: Dict[str, BtopCard] = {}
        
        self._setup_ui()
        self._start_updates()
    
    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # ========================================
        # TOP SECTION: 2 Columns
        # Column 1: System Gauges & Service Status
        # Column 2: Dynamic Module Cards (scrollable)
        # ========================================
        top_section = QWidget()
        top_layout = QHBoxLayout(top_section)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)
        
        # -- COLUMN 1: System Health (fixed width) --
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
        col1.addWidget(self.card_gauges, 2)
        
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
        col1.addWidget(self.card_status, 1)
        
        # Quick Stats
        self.card_stats = BtopCard("FRAMEWORK")
        self.stat_modules = StatBox("Modules", "0", THEME['cpu'])
        self.stat_uptime = StatBox("Uptime", "0s", THEME['mem'])
        self.stat_events = StatBox("Events", "0", THEME['net'])
        
        stats_row = QHBoxLayout()
        stats_row.setSpacing(5)
        stats_row.addWidget(self.stat_modules)
        stats_row.addWidget(self.stat_uptime)
        stats_row.addWidget(self.stat_events)
        self.card_stats.add_layout(stats_row)
        col1.addWidget(self.card_stats, 1)

        top_layout.addLayout(col1, 1)
        
        # -- COLUMN 2: Dynamic Module Cards (scrollable area) --
        self.modules_scroll = QScrollArea()
        self.modules_scroll.setWidgetResizable(True)
        self.modules_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: {THEME['surface_0']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {THEME['surface_2']};
                border-radius: 4px;
            }}
        """)
        
        self.modules_container = QWidget()
        self.modules_layout = QVBoxLayout(self.modules_container)
        self.modules_layout.setContentsMargins(0, 0, 5, 0)
        self.modules_layout.setSpacing(10)
        self.modules_layout.addStretch()  # Push cards to top
        
        self.modules_scroll.setWidget(self.modules_container)
        top_layout.addWidget(self.modules_scroll, 2)  # Give modules more space
        
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
        
        main_layout.addWidget(self.card_log, 1)
    
    def _clear_logs(self) -> None:
        self.console.clear()
        self._event_count = 0
        self.stat_events.set_value("0")
    
    def _start_updates(self) -> None:
        self._event_count = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_stats)
        self._timer.start(1000)
    
    def _render_module_card(self, module_name: str, status: Dict[str, Any], color_index: int) -> BtopCard:
        """
        Dynamically render a card with smart layout.
        Prioritizes numeric metrics in a grid, shows text details in a list.
        """
        card = BtopCard(module_name.upper())
        details = status.get("details", {})
        widgets: Dict[str, Any] = {}
        
        # Split details into 'metrics' (numeric) and 'info' (text)
        metrics = {}
        info = {}
        
        for k, v in details.items():
            val_str = str(v)
            # Simple heuristic: if it looks like a number, it's a metric
            # Remove commads, %, s, ms etc for check
            clean_val = val_str.replace(",", "").replace("%", "").replace("s", "").replace("ms", "")
            if clean_val.replace(".", "").isdigit():
                metrics[k] = val_str
            else:
                info[k] = val_str
        
        layout_box = card.content_layout
        
        # 1. Render Metrics (Grid or Large Box)
        if metrics:
            if len(metrics) <= 2:
                # Extra prominence for few metrics
                row = QHBoxLayout()
                row.setSpacing(10)
                for i, (key, value) in enumerate(metrics.items()):
                    item_color = MODULE_COLORS[(color_index + i) % len(MODULE_COLORS)]
                    box = LargeStatBox(key, str(value), item_color)
                    row.addWidget(box)
                    widgets[key] = box
                layout_box.addLayout(row)
            else:
                # Grid for multiple metrics
                grid = QGridLayout()
                grid.setSpacing(8)
                items = list(metrics.items())
                for i, (key, value) in enumerate(items):
                    item_color = MODULE_COLORS[(color_index + i) % len(MODULE_COLORS)]
                    box = StatBox(key, str(value), item_color)
                    grid.addWidget(box, i // 2, i % 2)
                    widgets[key] = box
                layout_box.addLayout(grid)
            
            # Divider if we also have info
            if info:
                layout_box.addSpacing(8)
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setStyleSheet(f"background-color: {THEME['surface_2']}; border: none; max-height: 1px;")
                layout_box.addWidget(line)
                layout_box.addSpacing(4)

        # 2. Render Info (List)
        for i, (key, value) in enumerate(info.items()):
            # Cycle colors but skip red unless explicit error
            item_color = MODULE_COLORS[(color_index + i) % 4] # Keep to first 4 colors (safe)
            row = MetricRow(key, str(value), item_color)
            card.add_widget(row)
            widgets[key] = row
        
        self._module_widgets[module_name] = widgets
        return card
    
    def _update_module_cards(self) -> None:
        """Discover modules and create/update their cards dynamically."""
        modules = self._registry.get_all_modules()
        
        for i, module in enumerate(modules):
            module_name = module.get_module_name()
            
            try:
                status = module.get_status()
            except Exception:
                status = {"status": "error", "details": {}}
            
            details = status.get("details", {})
            
            # Check if card already exists
            if module_name not in self._module_cards:
                # Create new card
                card = self._render_module_card(module_name, status, i)
                self._module_cards[module_name] = card
                # Insert before the stretch
                self.modules_layout.insertWidget(self.modules_layout.count() - 1, card)
            else:
                # Update existing widgets
                widgets = self._module_widgets.get(module_name, {})
                for key, value in details.items():
                    if key in widgets:
                        widget = widgets[key]
                        # Determine color based on key content
                        color = None
                        if key.lower() in ["status", "model status"]:
                            if str(value).lower() in ["ready", "active", "ok"]:
                                color = THEME['success']
                            elif str(value).lower() in ["loading", "init", "initializing"]:
                                color = THEME['warning']
                            else:
                                color = THEME['error']
                        widget.set_value(str(value), color)
    
    def _update_stats(self) -> None:
        # Update CPU/Memory gauges
        try:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage('C:').percent if hasattr(psutil, 'disk_usage') else 0
            
            self.gauge_cpu.set_value(cpu)
            self.gauge_mem.set_value(mem)
            self.gauge_disk.set_value(disk)
        except Exception:
            pass
        
        # Update server status
        running, port = self._context.get_server_status()
        self.led_server.set_status(running)
        self.led_api.set_status(running)
        self.led_db.set_status(True)
        
        # Update modules count
        modules = self._registry.get_module_names()
        module_count = len(modules)
        self.stat_modules.set_value(str(module_count))
        self.led_modules.set_status(module_count > 0)
        
        # Update dynamic module cards
        self._update_module_cards()

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
