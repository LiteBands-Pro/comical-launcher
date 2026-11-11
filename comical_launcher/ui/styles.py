"""A plain, normal-looking dark theme. Flat colors, one accent, no
gradients or glow effects — the goal is something that looks like an
ordinary desktop app, not a demo reel.
"""

BG = "#1e1f22"
BG_ELEVATED = "#242529"
CARD = "#2a2b30"
BORDER = "#3a3b40"
TEXT = "#e6e6e8"
TEXT_DIM = "#9a9ba1"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2f6fd6"
DANGER = "#e0555a"
SUCCESS = "#3fb96f"

STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

QLabel {{
    background-color: transparent;
    border: none;
}}

QMainWindow {{
    background-color: {BG};
}}

#Card {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

#Sidebar {{
    background-color: {BG_ELEVATED};
    border-right: 1px solid {BORDER};
}}

QLabel#Title {{
    font-size: 18px;
    font-weight: 600;
    color: {TEXT};
}}

QLabel#Subtitle {{
    color: {TEXT_DIM};
    font-size: 12px;
}}

QLabel#Hint {{
    color: {TEXT_DIM};
    font-size: 11px;
}}

QLabel#ErrorText {{
    color: {DANGER};
    font-size: 12px;
}}

QLabel#GameTitle {{
    font-size: 16px;
    font-weight: 600;
}}

QLabel#GameStatus {{
    color: {TEXT_DIM};
    font-size: 12px;
}}

QLineEdit {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 10px;
    color: {TEXT};
    font-size: 13px;
}}

QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}

QComboBox {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    color: {TEXT};
    font-size: 13px;
    font-weight: 500;
}}

QComboBox:hover {{
    border: 1px solid {ACCENT};
}}

QComboBox:focus {{
    border: 1px solid {ACCENT};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border: none;
    background-color: transparent;
}}

QComboBox::down-arrow {{
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_DIM};
    margin-right: 4px;
}}

QComboBox::down-arrow:hover {{
    border-top: 5px solid {TEXT};
}}

/* The dropdown popup — left completely unstyled by default, which is
   what made it look mismatched against the rest of the dark theme.
   Fusion honors this even though it's a separate top-level view. */
QComboBox QAbstractItemView {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT};
    outline: none;
    padding: 4px;
    selection-background-color: rgba(59, 130, 246, 60);
    selection-color: {TEXT};
}}

QComboBox QAbstractItemView::item {{
    padding: 8px 10px;
    border-radius: 5px;
    min-height: 22px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: rgba(255, 255, 255, 18);
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: rgba(59, 130, 246, 60);
}}

QPushButton {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton:disabled {{
    background-color: {BORDER};
    color: {TEXT_DIM};
}}

QPushButton#GhostButton {{
    background-color: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_DIM};
    font-weight: 500;
}}

QPushButton#GhostButton:hover {{
    color: {TEXT};
    border: 1px solid {ACCENT};
    background-color: transparent;
}}

QPushButton#NavButton {{
    background-color: transparent;
    color: {TEXT_DIM};
    border: none;
    border-radius: 6px;
    text-align: left;
    padding: 9px 12px;
    font-weight: 500;
}}

QPushButton#NavButton:hover {{
    background-color: rgba(255, 255, 255, 12);
    color: {TEXT};
}}

QPushButton#NavButton:checked {{
    background-color: rgba(59, 130, 246, 40);
    color: {ACCENT};
}}

QProgressBar {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

QFrame#GameArt {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QFrame#Divider {{
    background-color: {BORDER};
    max-height: 1px;
}}

/* The "⋯" more-actions menu (currently uninstall only) */
QMenu {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    color: {TEXT};
}}

QMenu::item {{
    padding: 8px 20px;
    border-radius: 5px;
    background-color: transparent;
}}

QMenu::item:selected {{
    background-color: rgba(255, 255, 255, 18);
    color: {TEXT};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 4px 8px;
}}

QToolButton#GhostButton {{
    background-color: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_DIM};
    border-radius: 6px;
    font-weight: 600;
}}

QToolButton#GhostButton:hover {{
    color: {TEXT};
    border: 1px solid {ACCENT};
}}

QToolButton#GhostButton::menu-indicator {{
    image: none;
    width: 0px;
}}
"""
