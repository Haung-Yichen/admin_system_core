"""
Theme Configuration - Btop Tokyo Night Style.
Centralized color palette and styling for the GUI.
"""

# --- UI Theme (Btop Default - True Black with Cyan/Green/Red) ---
THEME = {
    # Base Colors - Pure Black
    "bg_base": "#0d0d0d",      # Main background (almost pure black)
    "bg_mantle": "#000000",    # Darker background (pure black)
    "bg_crust": "#000000",     # Terminal bg (pure black)
    
    # Surface/Panel - Dark Grey
    "surface_0": "#1a1a1a",    # Card/Panel bg
    "surface_1": "#262626",    # Hover
    "surface_2": "#404040",    # Borders (grey like terminal)
    
    # Text
    "text_main": "#e0e0e0",    # Primary text (white-ish)
    "text_sub": "#b0b0b0",     # Secondary text
    "text_dim": "#707070",     # Dim/comments
    
    # Accents (Btop Default - Cyan/Green/Red gradient style)
    "cpu": "#00bcd4",     # Cyan - CPU (btop default)
    "mem": "#4caf50",     # Green - Memory  
    "net": "#8bc34a",     # Light Green - Network
    "proc": "#00acc1",    # Teal - Processes
    "temp": "#ff5252",    # Red - Temperature
    
    # Functional
    "success": "#4caf50",  # Green
    "warning": "#ffc107",  # Amber/Yellow
    "error": "#ff5252",    # Red
    "active": "#00bcd4",   # Cyan
}

# --- Fonts ---
FONT_FAMILY_UI = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"


def build_styles():
    """Generate QSS stylesheet dictionary based on THEME."""
    return {
        "window": f"background-color: {THEME['bg_base']};",
        
        "card": f"""
            QFrame {{
                background-color: {THEME['surface_0']};
                border: 1px solid {THEME['surface_2']};
                border-radius: 4px; 
            }}
        """,
        "card_title": f"""
            QLabel {{
                color: {THEME['text_main']};
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """,
        
        "btn": f"""
            QPushButton {{
                background-color: {THEME['bg_base']};
                color: {THEME['text_main']};
                border: 1px solid {THEME['surface_2']};
                border-radius: 4px;
                padding: 8px 15px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {THEME['surface_1']};
                border-color: {THEME['cpu']};
            }}
            QPushButton:pressed {{
                background-color: {THEME['cpu']}; 
            }}
        """,
        
        "btn_action": f"""
            QPushButton {{
                background-color: {THEME['bg_base']};
                color: {THEME['cpu']};
                border: 1px solid {THEME['cpu']};
                border-radius: 4px;
                padding: 8px 15px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 10pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {THEME['cpu']};
                color: {THEME['bg_base']};
            }}
        """,
        
        "log": f"""
            QTextEdit {{
                background-color: {THEME['bg_crust']}; 
                color: {THEME['text_main']};
                font-family: {FONT_FAMILY_MONO};
                font-size: 10pt;
                border: 1px solid {THEME['surface_2']};
                border-radius: 4px;
                selection-background-color: {THEME['cpu']};
                selection-color: {THEME['bg_base']};
            }}
            QScrollBar:vertical {{
                border: none;
                background: {THEME['bg_base']};
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: {THEME['surface_2']};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """
    }


STYLES = build_styles()
