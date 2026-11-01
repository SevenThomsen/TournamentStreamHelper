import os
import qdarktheme

# Color Palette inspired by SSBU Stream Automation (SZN Stream Automation)
PALETTE = {
    "bg": "#121214",
    "panel": "#18181b",
    "panel_header": "#202024",
    "input": "#202024",
    "dropdown_bg": "#121214",
    "border": "#2e2e33",
    "border_focus": "#818cf8",
    "text": "#ececed",
    "text_muted": "#8e8e93",
    "status_ok": "#22c55e",
    "status_err": "#ef4444",
    "status_warn": "#eab308",
    "accent": "#818cf8",
    "accent_hover": "#6366f1",
    "accent_subtle": "rgba(129, 140, 248, 0.14)",
    "accent_text": "#c7d2fe",
    "btn_primary": "#6366f1",
    "btn_primary_hover": "#4f46e5",
    "btn_secondary": "#27272a",
    "btn_secondary_hover": "#323236",
    "btn_danger": "#8f3232",
    "btn_danger_hover": "#7a2828",
    "btn_danger_border": "#9f3e3e",
    "btn_danger_text": "#ffffff",
}


ICON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons")).replace("\\", "/")

def get_dark_theme_qss() -> str:
    return f"""
    * {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 11px;
    }}

    /* Global Window Background */
    QMainWindow, QDialog, QWidget#centralWidget {{
        background-color: {PALETTE["bg"]};
        color: {PALETTE["text"]};
    }}

    /* Compact Card Group Boxes */
    QGroupBox {{
        background-color: {PALETTE["panel"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 6px;
        margin-top: 14px;
        padding: 6px 4px 4px 4px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 8px;
        top: 2px;
        padding: 0 4px;
        color: {PALETTE["accent"]};
        background-color: {PALETTE["panel"]};
        border-radius: 3px;
        font-size: 10px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }}

    /* Score Column GroupBox - Seamless Folder Tab Title */
    QGroupBox#scoreGroupBox {{
        background-color: {PALETTE["panel"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 6px;
        border-top-left-radius: 0px;
        margin-top: 24px;
        padding: 10px 6px 6px 6px;
        font-weight: 600;
    }}
    QGroupBox#scoreGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: -3px;
        top: 0px;
        padding: 4px 14px;
        color: {PALETTE["accent"]};
        background-color: {PALETTE["panel"]};
        border: 1px solid {PALETTE["border"]};
        border-bottom: 2px solid {PALETTE["panel"]};
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }}

    /* Team column main container (borderless wrapper around player list) */
    QGroupBox#groupBox {{
        background-color: transparent;
        border: none;
        margin-top: 4px;
        padding: 0px;
    }}

    /* Player slot container inside team cards - distinct card container per player */
    TSHScoreboardPlayerWidget,
    TSHTeamPlayerWidget {{
        background-color: {PALETTE["panel"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 6px;
        margin: 0px 0px 8px 0px;
        padding: 6px 4px 4px 4px;
    }}
    TSHScoreboardPlayerWidget QGroupBox#characters,
    TSHTeamPlayerWidget QGroupBox#characters {{
        background-color: transparent;
        border: 1px solid {PALETTE["border"]};
        border-radius: 4px;
        margin-top: 14px;
        padding: 4px;
    }}
    TSHScoreboardPlayerWidget QGroupBox#characters::title,
    TSHTeamPlayerWidget QGroupBox#characters::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 8px;
        top: 2px;
        padding: 0 4px;
        color: {PALETTE["accent"]};
        background-color: {PALETTE["panel"]};
        font-size: 10px;
        font-weight: bold;
    }}

    /* Compact Buttons */
    QPushButton {{
        background-color: {PALETTE["btn_secondary"]};
        color: {PALETTE["text"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 500;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background-color: {PALETTE["btn_secondary_hover"]};
        border-color: #3e3e44;
    }}
    QPushButton:pressed {{
        background-color: #1f1f22;
        border-color: {PALETTE["accent"]};
    }}
    QPushButton:disabled {{
        background-color: #161618;
        color: #555558;
        border-color: #222226;
    }}

    /* Icon-only buttons (up/down arrows, clear, settings icons) */
    QPushButton:empty, QPushButton[text=""] {{
        padding: 0px;
        min-width: 18px;
        min-height: 18px;
    }}

    /* Tool Buttons */
    QToolButton {{
        background-color: {PALETTE["btn_secondary"]};
        color: {PALETTE["text"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 4px;
        padding: 2px;
        min-height: 18px;
    }}
    QToolButton:hover {{
        background-color: {PALETTE["btn_secondary_hover"]};
        border-color: #3e3e44;
    }}
    QToolButton:pressed {{
        background-color: #1f1f22;
    }}
    /* Hide the overlapping menu arrow indicator on tool buttons (e.g. eye button) */
    QToolButton::menu-indicator {{
        image: none;
        width: 0px;
        height: 0px;
    }}

    /* Color picker buttons - crisp square */
    QToolButton[class*="Color"], TSHColorButton {{
        border: 1px solid {PALETTE["border"]};
        border-radius: 4px;
        min-width: 22px;
        max-width: 22px;
        min-height: 22px;
        max-height: 22px;
    }}

    /* Compact Line Edits & Text Areas */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {PALETTE["input"]};
        color: {PALETTE["text"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 4px;
        padding: 2px 5px;
        min-height: 18px;
        font-size: 11px;
        selection-background-color: {PALETTE["accent"]};
        selection-color: #ffffff;
    }}
    QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
        border-color: #3e3e44;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {PALETTE["border_focus"]};
        background-color: #242429;
    }}

    /* Compact SpinBoxes */
    QAbstractSpinBox {{
        background-color: {PALETTE["input"]};
        color: {PALETTE["text"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 4px;
        padding: 1px 18px 1px 5px;
        min-height: 20px;
        font-size: 11px;
    }}
    QAbstractSpinBox:hover {{
        border-color: #3e3e44;
    }}
    QAbstractSpinBox:focus {{
        border: 1px solid {PALETTE["border_focus"]};
    }}
    QAbstractSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 13px;
        top: 2px;
        bottom: 0px;
        right: 2px;
        border: none;
        background: transparent;
    }}
    QAbstractSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 13px;
        top: 0px;
        bottom: 2px;
        right: 2px;
        border: none;
        background: transparent;
    }}
    QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover,
    QAbstractSpinBox::up-button:hover:on, QAbstractSpinBox::down-button:hover:on,
    QAbstractSpinBox::up-button:pressed, QAbstractSpinBox::down-button:pressed {{
        border: none;
        background: transparent;
    }}
    QAbstractSpinBox::up-arrow,
    QAbstractSpinBox::up-arrow:on {{
        image: url({ICON_DIR}/arrow_up_spin.svg);
        width: 9px;
        height: 5px;
    }}
    QAbstractSpinBox::up-arrow:hover {{
        image: url({ICON_DIR}/arrow_up_spin_hover.svg);
    }}
    QAbstractSpinBox::up-arrow:disabled,
    QAbstractSpinBox::up-arrow:off {{
        image: url({ICON_DIR}/arrow_up_spin_disabled.svg);
    }}
    QAbstractSpinBox::down-arrow,
    QAbstractSpinBox::down-arrow:on {{
        image: url({ICON_DIR}/arrow_down_spin.svg);
        width: 9px;
        height: 5px;
    }}
    QAbstractSpinBox::down-arrow:hover {{
        image: url({ICON_DIR}/arrow_down_spin_hover.svg);
    }}
    QAbstractSpinBox::down-arrow:disabled,
    QAbstractSpinBox::down-arrow:off {{
        image: url({ICON_DIR}/arrow_down_spin_disabled.svg);
    }}

    /* Compact ComboBoxes */
    QComboBox {{
        background-color: {PALETTE["input"]};
        color: {PALETTE["text"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 4px;
        padding: 1px 20px 1px 6px;
        min-height: 20px;
        font-size: 11px;
    }}
    QComboBox:hover {{
        border-color: #3e3e44;
    }}
    QComboBox:focus {{
        border: 1px solid {PALETTE["border_focus"]};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: border;
        subcontrol-position: center right;
        width: 18px;
        border-left: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {PALETTE["panel"]};
        color: {PALETTE["text"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 4px;
        selection-background-color: {PALETTE["btn_secondary"]};
        selection-color: {PALETTE["accent"]};
        padding: 2px;
        font-size: 11px;
    }}

    /* Main Window Top Dock Tabs (Scoreboard Manager, Commentary, etc.) - Pill / Button Tabs */
    QMainWindow > QTabBar {{
        background: transparent;
        border: none;
        qproperty-drawBase: 0;
        margin: 2px 4px;
    }}
    QMainWindow > QTabBar::tab {{
        background-color: transparent;
        color: {PALETTE["text_muted"]};
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 500;
        margin: 2px 2px;
    }}
    QMainWindow > QTabBar::tab:hover:!selected {{
        color: {PALETTE["text"]};
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid transparent;
    }}
    QMainWindow > QTabBar::tab:selected {{
        color: {PALETTE["accent"]};
        background-color: {PALETTE["accent_subtle"]};
        border: 1px solid {PALETTE["accent"]};
        font-weight: 600;
    }}

    /* Inner QTabWidget Tabs (Scoreboard 1, 2, 3...) - Seamless Container Blend */
    QTabWidget::pane {{
        border: 1px solid {PALETTE["border"]};
        border-radius: 6px;
        border-top-left-radius: 0px;
        background-color: {PALETTE["panel"]};
        top: -1px;
    }}
    QTabWidget > QTabBar {{
        qproperty-drawBase: 0;
    }}
    QTabWidget > QTabBar::tab:top {{
        background-color: #151518;
        color: {PALETTE["text_muted"]};
        border: 1px solid {PALETTE["border"]};
        border-bottom: 1px solid {PALETTE["border"]};
        padding: 5px 14px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 3px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabWidget > QTabBar::tab:top:first,
    QTabWidget > QTabBar::tab:top:only-one {{
        margin-left: 0px;
    }}
    QTabWidget > QTabBar::tab:top:hover:!selected {{
        color: {PALETTE["text"]};
        background-color: #1e1e23;
        border-color: #3e3e46;
    }}
    QTabWidget > QTabBar::tab:top:selected,
    QTabWidget > QTabBar::tab:top:selected:enabled,
    QTabWidget > QTabBar::tab:top:only-one:selected:enabled {{
        color: {PALETTE["accent"]};
        background-color: {PALETTE["panel"]};
        border: 1px solid {PALETTE["border"]};
        border-bottom: 2px solid {PALETTE["panel"]};
        margin-bottom: -1px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}

    /* Scroll Area Clean Styling */
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}

    /* Scrollbars matching modern subtle web scrollbar - slim 4px, sleek pill handle */
    QScrollBar,
    QScrollBar:vertical,
    QScrollBar:vertical:hover,
    QScrollBar:horizontal,
    QScrollBar:horizontal:hover {{
        background: transparent;
        background-color: transparent;
        border: none;
    }}
    QScrollBar:vertical,
    QScrollBar:vertical:hover {{
        width: 4px;
        margin: 0px 0px 0px 2px;
    }}
    QScrollBar:horizontal,
    QScrollBar:horizontal:hover {{
        height: 4px;
        margin: 2px 0px 0px 0px;
    }}
    QScrollBar::handle:vertical {{
        background-color: #3e3e44;
        min-height: 24px;
        border-radius: 2px;
        margin: 0px;
        border: none;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {PALETTE["accent"]};
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: #3e3e44;
        min-width: 24px;
        border-radius: 2px;
        margin: 0px;
        border: none;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {PALETTE["accent"]};
        margin: 0px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        width: 0px;
        height: 0px;
        background: transparent;
        border: none;
    }}
    QScrollBar::up-arrow, QScrollBar::down-arrow,
    QScrollBar::left-arrow, QScrollBar::right-arrow,
    QScrollBar::up-arrow:enabled, QScrollBar::down-arrow:enabled,
    QScrollBar::left-arrow:enabled, QScrollBar::right-arrow:enabled {{
        image: none;
        width: 0px;
        height: 0px;
        background: transparent;
        border: none;
    }}

    /* CheckBoxes & RadioButtons */
    QCheckBox, QRadioButton {{
        color: {PALETTE["text"]};
        spacing: 6px;
        font-size: 11px;
        border: none;
        background: transparent;
    }}
    QCheckBox:hover, QRadioButton:hover {{
        border: none;
        background: transparent;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {PALETTE["border"]};
        border-radius: 3px;
        background-color: {PALETTE["input"]};
        image: none;
    }}
    QRadioButton::indicator {{
        border-radius: 7px;
    }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border-color: {PALETTE["accent"]};
        background-color: #28282e;
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {PALETTE["accent"]};
        border-color: {PALETTE["accent"]};
        image: url({ICON_DIR}/check_white.svg);
    }}
    QCheckBox::indicator:checked:hover, QRadioButton::indicator:checked:hover {{
        background-color: {PALETTE["accent_hover"]};
        border-color: {PALETTE["accent_hover"]};
    }}
    QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
        border-color: #222226;
        background-color: #161618;
    }}
    QCheckBox::indicator:checked:disabled, QRadioButton::indicator:checked:disabled {{
        background-color: #3b3b44;
        border-color: #3b3b44;
        image: url({ICON_DIR}/check_white.svg);
    }}

    /* Menus & Dropdown Context Menus */
    QMenu {{
        background-color: {PALETTE["panel"]};
        border: 1px solid {PALETTE["border"]};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 4px 12px;
        border-radius: 4px;
        color: {PALETTE["text"]};
    }}
    QMenu::item:selected {{
        background-color: {PALETTE["btn_secondary_hover"]};
        color: #ffffff;
    }}
    QMenu::item:disabled {{
        color: #555558;
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {PALETTE["border"]};
        margin: 4px 6px;
    }}
    QMenu::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {PALETTE["border"]};
        border-radius: 3px;
        background-color: {PALETTE["input"]};
        margin-left: 6px;
        margin-right: 6px;
        image: none;
    }}
    QMenu::indicator:hover {{
        border-color: {PALETTE["accent"]};
    }}
    QMenu::indicator:checked {{
        background-color: {PALETTE["accent"]};
        border-color: {PALETTE["accent"]};
        image: url({ICON_DIR}/check_white.svg);
    }}

    /* Primary Accent Action Buttons */
    QPushButton#btSet, QPushButton#btSave,
    QPushButton#btSelectSet,
    QPushButton#setTournamentBt {{
        background-color: {PALETTE["btn_primary"]};
        color: #ffffff;
        border: 1px solid {PALETTE["accent"]};
        font-weight: 600;
    }}
    QPushButton#btSet:hover, QPushButton#btSave:hover,
    QPushButton#btSelectSet:hover,
    QPushButton#setTournamentBt:hover {{
        background-color: {PALETTE["btn_primary_hover"]};
    }}

    /* The Nexus Live Button - Emerald background with dark currant text and icon */
    QPushButton#btNexusLive {{
        background-color: #50C878;
        color: #1a1921;
        border: 1px solid #43ad66;
        font-weight: 700;
        padding: 2px 8px;
    }}
    QPushButton#btNexusLive:hover {{
        background-color: #45b76b;
        border-color: #3aa05c;
    }}
    QPushButton#btNexusLive:pressed {{
        background-color: #3aa05c;
        border-color: #318a4e;
    }}

    /* Top Tournament Toolbar Button Heights */
    QPushButton#setTournamentBt, QPushButton#btLoadPlayerSet, QPushButton#btPullCompletedSets {{
        padding: 2px 8px;
        min-height: 20px;
        max-height: 22px;
    }}

    /* Danger / Clear Buttons */
    QPushButton#btClear {{
        border-color: {PALETTE["btn_danger_border"]};
    }}
    QPushButton#btClear:hover {{
        background-color: {PALETTE["btn_danger"]};
        color: {PALETTE["btn_danger_text"]};
    }}

    /* Reset Score Button - always filled with danger red background */
    QPushButton#btResetScore {{
        background-color: {PALETTE["btn_danger"]};
        border: 1px solid {PALETTE["btn_danger_border"]};
        color: {PALETTE["btn_danger_text"]};
        font-weight: 600;
    }}
    QPushButton#btResetScore:hover {{
        background-color: {PALETTE["btn_danger_hover"]};
        border-color: #b84a4a;
    }}
    QPushButton#btResetScore:pressed {{
        background-color: #6e2424;
        border-color: {PALETTE["btn_danger_border"]};
    }}

    /* Status Badges & Labels */
    QLabel {{
        color: {PALETTE["text"]};
        font-size: 11px;
    }}
    QLabel#lblNexusStatus {{
        font-weight: 600;
        font-size: 11px;
        letter-spacing: 0.3px;
    }}

    /* Headers and Toolbars */
    QToolBar {{
        background-color: {PALETTE["panel"]};
        border-bottom: 1px solid {PALETTE["border"]};
        padding: 2px;
        spacing: 4px;
    }}
    QStatusBar {{
        background-color: {PALETTE["panel"]};
        border-top: 1px solid {PALETTE["border"]};
        color: {PALETTE["text_muted"]};
        font-size: 10px;
    }}
    """


def ApplyTheme(is_light: bool = False):
    """
    Applies the custom theme to the active QApplication.
    Uses custom colors and QSS inspired by SSBU Stream Automation in dark mode,
    or falls back to qdarktheme light theme if light mode is selected.
    """
    if is_light:
        qdarktheme.setup_theme("light")
        return

    custom_colors = {
        "background": PALETTE["bg"],
        "foreground": PALETTE["text"],
        "primary": PALETTE["accent"],
        "border": PALETTE["border"],
        "input.background": PALETTE["input"],
        "inputButton.hoverBackground": PALETTE["border"],
        "tab.activeBackground": PALETTE["panel"],
        "tab.hoverBackground": PALETTE["panel_header"],
        "list.hoverBackground": PALETTE["panel_header"],
        "list.alternateBackground": PALETTE["panel"],
        "menubar.selectionBackground": PALETTE["panel_header"],
        "scrollbar.background": "#00000000",
        "scrollbarSlider.background": PALETTE["border"],
        "scrollbarSlider.hoverBackground": "#3e3e44",
        "scrollbarSlider.activeBackground": PALETTE["accent"],
        "statusBar.background": PALETTE["panel"],
        "toolbar.background": PALETTE["panel"],
    }

    qdarktheme.setup_theme(
        theme="dark",
        corner_shape="rounded",
        custom_colors=custom_colors,
        additional_qss=get_dark_theme_qss()
    )
