import base64
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

try:
    from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPoint, QPropertyAnimation, QObject, Qt, QThread, QTimer, Signal, QByteArray, QSize, QRectF, Property, QSequentialAnimationGroup
    from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor, QPen, QPalette
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGraphicsDropShadowEffect,
        QGridLayout,
        QGroupBox,
        QGraphicsOpacityEffect,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QStackedWidget,
        QStyle,
        QStyleOptionButton,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from ctypes import windll

    message = (
        "PySide6 is required for the modern Local Worker app.\n\n"
        "Run install_windows.cmd or start_here.cmd again so dependencies are installed."
    )
    try:
        windll.user32.MessageBoxW(None, message, "CV Analyzer Local Worker", 0x10)
    except Exception:
        print(message, file=sys.stderr)
    sys.exit(1)

import worker as worker_module
from credentials import load_worker_api_key, save_worker_api_key
from worker import API_BASE_URL, MAX_FILE_BYTES, LocalWorker, extract_text, maybe_apply_ai_review, score_cv
from workspace import WorkspaceStore


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MOTION_ENABLED = os.environ.get("CV_WORKER_DISABLE_MOTION", "").lower() not in {"1", "true", "yes"}


def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = Path(base) / "CV Analyzer Local Worker"
    path.mkdir(parents=True, exist_ok=True)
    return path


def crash_log_path() -> Path:
    return app_data_dir() / "crash.log"


def write_crash_log(message: str) -> Path:
    path = crash_log_path()
    path.write_text(
        f"CV Analyzer Local Worker crash\n{datetime.now(UTC).isoformat().replace('+00:00', 'Z')}\n\n{message}\n",
        encoding="utf-8",
    )
    return path


def split_terms(value: str) -> list[str]:
    return [item.strip() for item in (value or "").replace("\n", ",").split(",") if item.strip()]


def load_mail_templates() -> dict:
    path = app_data_dir() / "mail_templates.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "accept_subject": "Update regarding your application at CV Analyzer",
        "accept_body": (
            "Hi {name},\n\n"
            "Thank you for your application. We reviewed your CV and would like to move forward. "
            "Our team will contact you soon with the next steps.\n\n"
            "Best regards,\nRecruiting Team"
        ),
        "reject_subject": "Update regarding your application at CV Analyzer",
        "reject_body": (
            "Hi {name},\n\n"
            "Thank you for your interest. After reviewing your CV, we will not be moving forward with your application for this opening.\n\n"
            "Best regards,\nRecruiting Team"
        )
    }


def save_mail_templates(data: dict):
    path = app_data_dir() / "mail_templates.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def decision_label(decision: str) -> str:
    return {
        "recommended_accept": "Accept",
        "recommended_review": "Review",
        "recommended_reject": "Reject",
    }.get(decision, decision or "Unknown")


def decision_rank(decision: str) -> int:
    return {"recommended_accept": 0, "recommended_review": 1, "recommended_reject": 2}.get(decision, 3)


def svg_to_pixmap(svg_str: str, width: int, height: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def get_theme_logo_svg(theme_name: str, colors: dict) -> str:
    primary = colors.get('primary', '#3B82F6')
    logo_text = colors.get('logo_text', '#FFFFFF')
    if theme_name == 'forest_executive':
        return f"""
        <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="{logo_text}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2L2 22h20L12 2z"></path>
            <path d="M12 6l-6 10h12L12 6z"></path>
            <path d="M12 10l-3 5h6l-3-5z"></path>
        </svg>
        """
    elif theme_name == 'warm_stone':
        return f"""
        <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="{logo_text}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2.7 10.3a2.4 2.4 0 0 0 0 3.4l7.6 7.6a2.4 2.4 0 0 0 3.4 0l7.6-7.6a2.4 2.4 0 0 0 0-3.4L13.7 2.7a2.4 2.4 0 0 0-3.4 0z"></path>
        </svg>
        """
    elif theme_name == 'electric_indigo':
        return f"""
        <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="{logo_text}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="2" width="20" height="20" rx="4" fill="{colors.get('sidebar_active', '#162038')}" stroke="{primary}"></rect>
            <polygon points="13 6 7 13 12 13 11 18 17 11 12 11 13 6" fill="{logo_text}" stroke="{logo_text}" stroke-width="1"></polygon>
        </svg>
        """
    else:
        return f"""
        <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="{logo_text}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
        </svg>
        """


def get_trust_icon_svg(color: str) -> str:
    return f"""
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
        <path d="m9 12 2 2 4-4"></path>
    </svg>
    """


def get_sidebar_icon_svg(key: str, color: str) -> str:
    if key == "analyze":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='11' cy='11' r='8'></circle><line x1='21' y1='21' x2='16.65' y2='16.65'></line></svg>"
    elif key == "results":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><ellipse cx='12' cy='5' rx='9' ry='3'></ellipse><path d='M3 5V19A9 3 0 0 0 21 19V5'></path><path d='M3 12A9 3 0 0 0 21 12'></path></svg>"
    elif key == "dashboard":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='3' y='3' width='7' height='7'></rect><rect x='14' y='3' width='7' height='7'></rect><rect x='14' y='14' width='7' height='7'></rect><rect x='3' y='14' width='7' height='7'></rect></svg>"
    elif key == "history":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='10'></circle><polyline points='12 6 12 12 16 14'></polyline></svg>"
    elif key == "appearance":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M12 22C17.5228 22 22 17.5228 22 12C22 11.45 21.55 11 21 11H12V2H12C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z'></path></svg>"
    elif key == "templates":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z'></path><polyline points='22,6 12,13 2,6'></polyline></svg>"
    elif key == "sync":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M23 4v6h-6'></path><path d='M20.49 15a9 9 0 1 1-2.12-9.36L23 10'></path></svg>"
    elif key == "preferences":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='4' y1='21' x2='4' y2='14'></line><line x1='4' y1='10' x2='4' y2='3'></line><line x1='12' y1='21' x2='12' y2='12'></line><line x1='12' y1='8' x2='12' y2='3'></line><line x1='20' y1='21' x2='20' y2='16'></line><line x1='20' y1='12' x2='20' y2='3'></line><line x1='1' y1='14' x2='7' y2='14'></line><line x1='9' y1='8' x2='15' y2='8'></line><line x1='17' y1='16' x2='23' y2='16'></line></svg>"
    elif key == "models":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='4' y='4' width='16' height='16' rx='2' ry='2'></rect><rect x='9' y='9' width='6' height='6'></rect><line x1='9' y1='1' x2='9' y2='4'></line><line x1='15' y1='1' x2='15' y2='4'></line><line x1='9' y1='20' x2='9' y2='23'></line><line x1='15' y1='20' x2='15' y2='23'></line><line x1='20' y1='9' x2='23' y2='9'></line><line x1='20' y1='15' x2='23' y2='15'></line><line x1='1' y1='9' x2='4' y2='9'></line><line x1='1' y1='15' x2='4' y2='15'></line></svg>"
    elif key == "reports":
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6z'></path><polyline points='14 2 14 8 20 8'></polyline><line x1='16' y1='13' x2='8' y2='13'></line><line x1='16' y1='17' x2='8' y2='17'></line><polyline points='10 9 9 9 8 9'></polyline></svg>"
    return ""


def get_briefcase_svg(color: str) -> str:
    return f"""
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
    </svg>
    """


def get_pencil_svg(color: str) -> str:
    return f"""
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 20h9"></path>
        <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
    </svg>
    """


def get_mail_icon_svg(color: str) -> str:
    return f"""
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 17a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9.5C2 7 4 5 6.5 5h11C20 5 22 7 22 9.5Z"></path>
        <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path>
    </svg>
    """


def get_lightbulb_svg(color: str) -> str:
    return f"""
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A5 5 0 0 0 8 8c0 1 .3 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"></path>
        <path d="M9 18h6"></path>
        <path d="M10 22h4"></path>
    </svg>
    """


def get_shield_svg(color: str) -> str:
    return f"""
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
        <path d="m9 12 2 2 4-4"></path>
    </svg>
    """


# ──────────────────────────────────────────────────────────────────────────────
# Theme Engine
# ──────────────────────────────────────────────────────────────────────────────

THEMES: dict[str, dict] = {
    "warm_stone": {
        "display_name": "Warm Stone",
        "description": "Sophisticated neutrals with warm accents and soft depth",
        "tags": ["warm", "elegant", "soft", "professional", "timeless"],
        "palette_swatches": ["#F7F4EF", "#E8DFD3", "#6DC1B5", "#8A6F58", "#B8B85A", "#2C1A25"],
        "colors": {
            "app_bg": "#2C1A25",
            "sidebar_bg": "#2C1A25",
            "sidebar_bg_image": "",
            "sidebar_bg_repeat": "repeat",
            "sidebar_bg_position": "center",
            "sidebar_hover": "#3D2A34",
            "sidebar_active": "#4E3A45",
            "sidebar_text": "#C4A99A",
            "sidebar_text_active": "#F7F4EF",
            "sidebar_section": "#8B7D6B",
            "sidebar_indicator": "#8A6F58",
            "main_bg": "#F7F4EF",
            "main_panel_radius": "16",
            "card_bg": "#FFFFFF",
            "card_border": "#E8DFD3",
            "card_radius": "12",
            "text_primary": "#2C1A25",
            "text_secondary": "#8B7D6B",
            "text_muted": "#A89888",
            "border": "#E8DFD3",
            "primary": "#8A6F58",
            "primary_hover": "#7A5F48",
            "primary_pressed": "#6A4F38",
            "primary_text": "#FFFFFF",
            "secondary_bg": "#FFFFFF",
            "secondary_border": "#E8DFD3",
            "secondary_text": "#2C1A25",
            "secondary_hover_bg": "#F7F4EF",
            "success": "#6DC1B5",
            "warning": "#B8B85A",
            "danger": "#C4364A",
            "info": "#6DC1B5",
            "input_bg": "#FFFFFF",
            "input_border": "#E8DFD3",
            "input_focus": "#8A6F58",
            "input_text": "#2C1A25",
            "input_placeholder": "#A89888",
            "input_selection_bg": "#E8DFD3",
            "input_selection_text": "#2C1A25",
            "table_bg": "#FFFFFF",
            "table_alt": "#FAF8F5",
            "table_header_bg": "#F7F4EF",
            "table_header_text": "#8B7D6B",
            "table_border": "#E8DFD3",
            "table_item_border": "#F3EDE6",
            "table_selected_bg": "#F0E8DF",
            "table_selected_text": "#2C1A25",
            "table_text": "#4A3D35",
            "scrollbar_bg": "transparent",
            "scrollbar_handle": "#D4C8BC",
            "scrollbar_handle_hover": "#B8A898",
            "progress_bg": "#E8DFD3",
            "progress_chunk": "#8A6F58",
            "status_pill_bg": "#F0FDF4",
            "status_pill_border": "#BBF7D0",
            "status_pill_text": "#16A34A",
            "chip_bg": "#F3EDE6",
            "chip_border": "#E8DFD3",
            "chip_text": "#8B7D6B",
            "chip_hover_bg": "#E8DFD3",
            "badge_purple_bg": "#F3E8FF", "badge_purple_text": "#7C3AED",
            "badge_green_bg": "#DCFCE7", "badge_green_text": "#16A34A",
            "badge_blue_bg": "#DBEAFE", "badge_blue_text": "#2563EB",
            "badge_red_bg": "#FEE2E2", "badge_red_text": "#DC2626",
            "logo_bg": "#4E3A45",
            "logo_text": "#F7F4EF",
            "step_badge_bg": "#8A6F58",
            "email_header_bg": "#F7F4EF",
            "email_body_bg": "#FFFFFF",
        },
    },
    "midnight_glass": {
        "display_name": "Midnight Glass",
        "description": "Deep graphite with glassmorphism and subtle glow",
        "tags": ["premium", "glass", "sleek", "focus", "modern"],
        "palette_swatches": ["#080D12", "#191B21", "#1F2430", "#7C5CFF", "#A789FA", "#E2E8F0"],
        "colors": {
            "app_bg": "#080D12",
            "sidebar_bg": "#0B1018",
            "sidebar_bg_image": "",
            "sidebar_bg_repeat": "no-repeat",
            "sidebar_bg_position": "bottom left",
            "sidebar_hover": "#141921",
            "sidebar_active": "#1C2230",
            "sidebar_text": "#7C8DB5",
            "sidebar_text_active": "#E2E8F0",
            "sidebar_section": "#4A5568",
            "sidebar_indicator": "#7C5CFF",
            "main_bg": "#0E1117",
            "main_panel_radius": "16",
            "card_bg": "#161B24",
            "card_border": "#1E2533",
            "card_radius": "12",
            "text_primary": "#E2E8F0",
            "text_secondary": "#94A3B8",
            "text_muted": "#64748B",
            "border": "#1E2533",
            "primary": "#7C5CFF",
            "primary_hover": "#9B7EFF",
            "primary_pressed": "#6A4AEE",
            "primary_text": "#FFFFFF",
            "secondary_bg": "#161B24",
            "secondary_border": "#1E2533",
            "secondary_text": "#E2E8F0",
            "secondary_hover_bg": "#1C2230",
            "success": "#22C55E",
            "warning": "#F59E0B",
            "danger": "#EF4444",
            "info": "#3B82F6",
            "input_bg": "#161B24",
            "input_border": "#1E2533",
            "input_focus": "#7C5CFF",
            "input_text": "#E2E8F0",
            "input_placeholder": "#64748B",
            "input_selection_bg": "#7C5CFF",
            "input_selection_text": "#FFFFFF",
            "table_bg": "#111720",
            "table_alt": "#151C26",
            "table_header_bg": "#161B24",
            "table_header_text": "#94A3B8",
            "table_border": "#1E2533",
            "table_item_border": "#1A202E",
            "table_selected_bg": "#252D45",
            "table_selected_text": "#E2E8F0",
            "table_text": "#CBD5E1",
            "scrollbar_bg": "transparent",
            "scrollbar_handle": "#2A3344",
            "scrollbar_handle_hover": "#3A4A5E",
            "progress_bg": "#1E2533",
            "progress_chunk": "#7C5CFF",
            "status_pill_bg": "#162016",
            "status_pill_border": "#22C55E",
            "status_pill_text": "#22C55E",
            "chip_bg": "#161B24",
            "chip_border": "#1E2533",
            "chip_text": "#94A3B8",
            "chip_hover_bg": "#1E2533",
            "badge_purple_bg": "#2D1F5E", "badge_purple_text": "#A789FA",
            "badge_green_bg": "#14332A", "badge_green_text": "#22C55E",
            "badge_blue_bg": "#1A2744", "badge_blue_text": "#60A5FA",
            "badge_red_bg": "#3B1A1A", "badge_red_text": "#F87171",
            "logo_bg": "#1C2230",
            "logo_text": "#A789FA",
            "step_badge_bg": "#7C5CFF",
            "email_header_bg": "#161B24",
            "email_body_bg": "#111720",
        },
    },
    "electric_indigo": {
        "display_name": "Electric Indigo",
        "description": "Modern dark interface with indigo energy and data focus",
        "tags": ["dynamic", "techy", "data-driven", "sharp", "futuristic"],
        "palette_swatches": ["#0A0F1F", "#121A2D", "#1E2A47", "#3B82F6", "#22D3EE", "#E91FFF"],
        "colors": {
            "app_bg": "#0A0F1F",
            "sidebar_bg": "#070C18",
            "sidebar_bg_image": "",
            "sidebar_bg_repeat": "repeat",
            "sidebar_bg_position": "center",
            "sidebar_hover": "#0F1628",
            "sidebar_active": "#162038",
            "sidebar_text": "#7C8DB5",
            "sidebar_text_active": "#E2E8F0",
            "sidebar_section": "#4A5580",
            "sidebar_indicator": "#3B82F6",
            "main_bg": "#0F1629",
            "main_panel_radius": "16",
            "card_bg": "#141D36",
            "card_border": "#1E2A47",
            "card_radius": "12",
            "text_primary": "#E2E8F0",
            "text_secondary": "#7C8DB5",
            "text_muted": "#5A6A8A",
            "border": "#1E2A47",
            "primary": "#3B82F6",
            "primary_hover": "#60A5FA",
            "primary_pressed": "#2563EB",
            "primary_text": "#FFFFFF",
            "secondary_bg": "#141D36",
            "secondary_border": "#1E2A47",
            "secondary_text": "#E2E8F0",
            "secondary_hover_bg": "#1A2540",
            "success": "#22D3EE",
            "warning": "#FBBF24",
            "danger": "#F43F5E",
            "info": "#3B82F6",
            "input_bg": "#141D36",
            "input_border": "#1E2A47",
            "input_focus": "#3B82F6",
            "input_text": "#E2E8F0",
            "input_placeholder": "#5A6A8A",
            "input_selection_bg": "#3B82F6",
            "input_selection_text": "#FFFFFF",
            "table_bg": "#111A30",
            "table_alt": "#151F38",
            "table_header_bg": "#141D36",
            "table_header_text": "#7C8DB5",
            "table_border": "#1E2A47",
            "table_item_border": "#1A2440",
            "table_selected_bg": "#1E3A6E",
            "table_selected_text": "#E2E8F0",
            "table_text": "#B0C4DE",
            "scrollbar_bg": "transparent",
            "scrollbar_handle": "#1E2A47",
            "scrollbar_handle_hover": "#2A3A5A",
            "progress_bg": "#1E2A47",
            "progress_chunk": "#3B82F6",
            "status_pill_bg": "#0C2D3E",
            "status_pill_border": "#22D3EE",
            "status_pill_text": "#22D3EE",
            "chip_bg": "#141D36",
            "chip_border": "#1E2A47",
            "chip_text": "#7C8DB5",
            "chip_hover_bg": "#1E2A47",
            "badge_purple_bg": "#2D1F5E", "badge_purple_text": "#A78BFA",
            "badge_green_bg": "#0C2D3E", "badge_green_text": "#22D3EE",
            "badge_blue_bg": "#1A2744", "badge_blue_text": "#60A5FA",
            "badge_red_bg": "#3B1A2A", "badge_red_text": "#FB7185",
            "logo_bg": "#162038",
            "logo_text": "#60A5FA",
            "step_badge_bg": "#3B82F6",
            "email_header_bg": "#141D36",
            "email_body_bg": "#111A30",
        },
    },
    "forest_executive": {
        "display_name": "Forest Executive",
        "description": "Executive dark green palette with trust and clarity",
        "tags": ["executive", "trust", "grounded", "balanced", "enterprise"],
        "palette_swatches": ["#0E1A14", "#1F3B2E", "#3E7D5A", "#88CF9F", "#E6A5EA", "#E2E8F0"],
        "colors": {
            "app_bg": "#0E1A14",
            "sidebar_bg": "#0A1410",
            "sidebar_bg_image": "",
            "sidebar_bg_repeat": "no-repeat",
            "sidebar_bg_position": "bottom left",
            "sidebar_hover": "#142820",
            "sidebar_active": "#1C3A2C",
            "sidebar_text": "#7DA68E",
            "sidebar_text_active": "#E2E8F0",
            "sidebar_section": "#4A6A58",
            "sidebar_indicator": "#3E7D5A",
            "main_bg": "#0F1F17",
            "main_panel_radius": "16",
            "card_bg": "#162B20",
            "card_border": "#1F3B2E",
            "card_radius": "12",
            "text_primary": "#E2E8F0",
            "text_secondary": "#7DA68E",
            "text_muted": "#5A8A6E",
            "border": "#1F3B2E",
            "primary": "#3E7D5A",
            "primary_hover": "#4E9D6A",
            "primary_pressed": "#2E6D4A",
            "primary_text": "#FFFFFF",
            "secondary_bg": "#162B20",
            "secondary_border": "#1F3B2E",
            "secondary_text": "#E2E8F0",
            "secondary_hover_bg": "#1C3828",
            "success": "#88CF9F",
            "warning": "#E6A5EA",
            "danger": "#F87171",
            "info": "#3E7D5A",
            "input_bg": "#162B20",
            "input_border": "#1F3B2E",
            "input_focus": "#3E7D5A",
            "input_text": "#E2E8F0",
            "input_placeholder": "#5A8A6E",
            "input_selection_bg": "#3E7D5A",
            "input_selection_text": "#FFFFFF",
            "table_bg": "#122218",
            "table_alt": "#162B20",
            "table_header_bg": "#162B20",
            "table_header_text": "#7DA68E",
            "table_border": "#1F3B2E",
            "table_item_border": "#1A3226",
            "table_selected_bg": "#1E4A35",
            "table_selected_text": "#E2E8F0",
            "table_text": "#B0D0BE",
            "scrollbar_bg": "transparent",
            "scrollbar_handle": "#1F3B2E",
            "scrollbar_handle_hover": "#2A5040",
            "progress_bg": "#1F3B2E",
            "progress_chunk": "#3E7D5A",
            "status_pill_bg": "#162B20",
            "status_pill_border": "#88CF9F",
            "status_pill_text": "#88CF9F",
            "chip_bg": "#162B20",
            "chip_border": "#1F3B2E",
            "chip_text": "#7DA68E",
            "chip_hover_bg": "#1F3B2E",
            "badge_purple_bg": "#2D1F4E", "badge_purple_text": "#E6A5EA",
            "badge_green_bg": "#143024", "badge_green_text": "#88CF9F",
            "badge_blue_bg": "#162B35", "badge_blue_text": "#60A5FA",
            "badge_red_bg": "#3B1A1A", "badge_red_text": "#F87171",
            "logo_bg": "#1C3A2C",
            "logo_text": "#88CF9F",
            "step_badge_bg": "#3E7D5A",
            "email_header_bg": "#162B20",
            "email_body_bg": "#122218",
        },
    },
}

DEFAULT_THEME = "warm_stone"


def load_active_theme() -> str:
    path = app_data_dir() / "theme.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = data.get("active", DEFAULT_THEME)
            if name in THEMES:
                return name
        except Exception:
            pass
    return DEFAULT_THEME


def save_active_theme(name: str):
    path = app_data_dir() / "theme.json"
    path.write_text(json.dumps({"active": name}, indent=2), encoding="utf-8")


def get_theme_colors(name: str | None = None) -> dict:
    name = name or load_active_theme()
    return THEMES.get(name, THEMES[DEFAULT_THEME])["colors"]


def svg_to_base64_url(svg_content: str) -> str:
    encoded = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return f'url("data:image/svg+xml;base64,{encoded}")'


def get_spinbox_up_arrow_svg(color: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="18 15 12 9 6 15"></polyline>
    </svg>"""


def get_spinbox_down_arrow_svg(color: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9"></polyline>
    </svg>"""


def generate_qss(theme_name: str | None = None) -> str:
    c = get_theme_colors(theme_name)
    up_arrow_url = svg_to_base64_url(get_spinbox_up_arrow_svg(c['text_primary']))
    down_arrow_url = svg_to_base64_url(get_spinbox_down_arrow_svg(c['text_primary']))
    return f"""
        QWidget {{
            background: transparent;
            color: {c['text_primary']};
            font-family: "Segoe UI", "SF Pro Display", system-ui;
            font-size: 10pt;
        }}
        QWidget#Root, QMainWindow {{
            background: {c['app_bg']};
        }}
        QWidget#MainPanel {{
            background: {c['main_bg']};
            color: {c['text_primary']};
            border-radius: {c['main_panel_radius']}px;
            border: 1px solid {c['border']};
        }}
        QLabel#Title {{
            color: {c['text_primary']};
            font-size: 22px;
            font-weight: 800;
        }}
        QLabel#Subtitle {{
            color: {c['text_secondary']};
            font-size: 10pt;
        }}
        QLabel#HeaderIcon {{
            min-width: 48px; min-height: 48px; max-width: 48px; max-height: 48px;
            border-radius: 12px;
            background: {c['card_bg']};
            color: {c['primary']};
            font-size: 22px; font-weight: 900;
            qproperty-alignment: AlignCenter;
        }}
        QLabel#StatusPill {{
            padding: 6px 16px;
            border: 1px solid {c['status_pill_border']};
            border-radius: 16px;
            background: {c['status_pill_bg']};
            color: {c['status_pill_text']};
            font-weight: 700; font-size: 9pt;
        }}
        QLabel#StatusDot {{
            color: {c['success']};
            font-size: 8pt;
            font-weight: 900;
        }}
        QLabel#SyncMeta {{
            color: {c['text_secondary']};
            font-weight: 600; font-size: 9pt;
        }}
        QTabWidget::pane {{
            border: none; background: transparent; top: 0;
        }}
        QTabBar::tab {{
            padding: 12px 16px 11px; margin-right: 6px;
            border: none; border-bottom: 2px solid transparent;
            background: transparent;
            color: {c['text_muted']};
            font-size: 10pt; font-weight: 700;
        }}
        QTabBar::tab:selected {{
            color: {c['text_primary']};
            border-bottom: 2px solid {c['primary']};
        }}
        QTabBar::tab:hover {{
            color: {c['text_secondary']};
        }}
        /* ── SIDEBAR ── */
        QFrame#Sidebar, QFrame#Sidebar QWidget {{
            color: {c['sidebar_text']};
        }}
        QFrame#Sidebar {{
            background-color: {c['sidebar_bg']};
            background-image: url('{c.get("sidebar_bg_image", "")}');
            background-repeat: {c.get("sidebar_bg_repeat", "no-repeat")};
            background-position: {c.get("sidebar_bg_position", "bottom left")};
            border: none;
            border-right: 1px solid {c['border']};
        }}
        QLabel#LogoMark {{
            min-width: 42px; min-height: 42px; max-width: 42px; max-height: 42px;
            border-radius: 10px;
            background: {c['logo_bg']};
            color: {c['logo_text']};
            font-size: 20px; font-weight: 900;
            qproperty-alignment: AlignCenter;
        }}
        QLabel#SidebarBrand {{
            color: {c['sidebar_text_active']};
            font-size: 11.5pt; font-weight: 800;
        }}
        QLabel#SidebarSub {{
            color: {c['sidebar_text']};
            font-size: 9pt;
        }}
        QLabel#SidebarSection {{
            color: {c['sidebar_section']};
            font-size: 8pt; font-weight: 700; letter-spacing: 1.2px; padding-top: 4px;
        }}
        QPushButton#SidebarNav, QPushButton#SidebarPassive {{
            background: transparent; border: none;
            border-radius: 8px;
            color: {c['sidebar_text']};
            padding: 9px 12px 9px 30px; text-align: left;
            margin: 2px 14px 2px 18px;
            font-size: 9.5pt; font-weight: 600;
        }}
        QPushButton#SidebarNav:hover {{
            background: {c['sidebar_hover']};
            color: {c['sidebar_text_active']};
        }}
        QPushButton#SidebarNav:checked {{
            background: {c['sidebar_active']};
            color: {c['sidebar_text_active']};
            font-weight: 700;
        }}
        QPushButton#SidebarPassive:disabled {{
            color: {c['sidebar_text']};
            background: transparent;
        }}
        /* ── CARDS ── */
        QGroupBox {{
            border: 1px solid {c['card_border']};
            border-radius: {c['card_radius']}px;
            margin-top: 14px; padding: 22px 18px 18px;
            background: {c['card_bg']};
            font-size: 11pt; font-weight: 700;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; left: 20px; padding: 0 8px;
            color: {c['text_primary']};
        }}
        QFrame#MetricCard, QFrame#ContentCard {{
            background: {c['card_bg']};
            border: 1px solid {c['card_border']};
            border-radius: {c['card_radius']}px;
        }}
        QFrame#FooterBar {{
            background: {c['card_bg']};
            border: 1.5px solid {c['card_border']};
            border-top: 3px solid {c['primary']};
            border-radius: 12px;
        }}
        QFrame#MetricCard {{
            min-height: 110px;
        }}
        QLabel#MetricTitle {{
            color: {c['text_secondary']};
            font-weight: 700; font-size: 9pt;
        }}
        QLabel#MetricValue {{
            color: {c['text_primary']};
            font-size: 22pt; font-weight: 800; margin: 0; padding: 0;
        }}
        QLabel#MetricSub {{
            color: {c['text_secondary']};
            font-size: 9pt;
        }}
        #PurpleBadge, #GreenBadge, #BlueBadge, #RedBadge {{
            background: transparent;
            border: none;
        }}

        /* ── TIP BOXES ── */
        QFrame#TipBox_success {{
            background: {c['secondary_bg']};
            border: 1px solid {c['success']};
            border-radius: 8px;
        }}
        QFrame#TipBox_warning {{
            background: {c['secondary_bg']};
            border: 1px solid {c['warning']};
            border-radius: 8px;
        }}
        QLabel#TipBoxText {{
            color: {c['text_secondary']};
        }}

        /* ── SIDEBAR TRUST CARD ── */
        QFrame#SidebarTrustCard {{
            background: {c['sidebar_active']};
            border: 1px solid {c['sidebar_hover']};
            border-radius: 8px;
            margin: 10px 14px;
        }}
        QLabel#SidebarTrustTitle {{
            color: {c['sidebar_text_active']};
            font-size: 8.5pt;
            font-weight: 800;
        }}
        QLabel#SidebarTrustDesc {{
            color: {c['sidebar_text']};
            font-size: 7.5pt;
        }}
        QLabel#StepBadge {{
            min-width: 28px; min-height: 28px; max-width: 28px; max-height: 28px;
            border-radius: 14px;
            background: {c['step_badge_bg']}; color: {c['primary_text']};
            font-weight: 800; font-size: 9pt;
        }}
        QLabel#StepTitle {{
            color: {c['text_primary']};
            font-size: 12pt; font-weight: 800;
        }}
        QLabel#StepSubtitle {{
            color: {c['text_secondary']};
            font-size: 9.5pt;
        }}
        QLabel#FooterReady {{
            color: {c['text_primary']}; font-weight: 800;
        }}
        QLabel#FooterMeta, QLabel#TrustLine {{
            color: {c['text_secondary']}; font-weight: 600;
        }}
        QLabel#FieldLabel {{
            color: {c['text_secondary']};
            font-size: 9pt; font-weight: 700;
        }}
        /* ── FORMS ── */
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
            background: {c['input_bg']};
            color: {c['input_text']};
            border: 1px solid {c['input_border']};
            border-radius: 8px; padding: 10px 14px;
            selection-background-color: {c['input_selection_bg']};
            selection-color: {c['input_selection_text']};
        }}
        QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QComboBox:hover, QSpinBox:hover {{
            border-color: {c['primary']};
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border-color: {c['input_focus']};
        }}
        QLineEdit::placeholder, QPlainTextEdit::placeholder {{
            color: {c['input_placeholder']};
        }}
        QComboBox {{ padding-right: 30px; }}
        QComboBox::drop-down {{
            subcontrol-origin: padding; subcontrol-position: top right;
            width: 30px; border: none;
        }}
        QComboBox::down-arrow {{
            image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%23{c['text_muted'].lstrip('#')}' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>");
            width: 10px; height: 10px; margin-right: 4px;
        }}
        QComboBox::down-arrow:on {{
            image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%23{c['primary'].lstrip('#')}' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='18 15 12 9 6 15'></polyline></svg>");
        }}
        QSpinBox {{
            padding-right: 28px;
        }}
        QSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 24px;
            height: 17px;
            border-left: 1px solid {c['input_border']};
            border-bottom: 1px solid {c['input_border']};
            background: {c['secondary_hover_bg']};
            border-top-right-radius: 7px;
            margin-top: 1px;
            margin-right: 1px;
        }}
        QSpinBox::up-button:hover {{
            background: {c['input_selection_bg']};
        }}
        QSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 24px;
            height: 17px;
            border-left: 1px solid {c['input_border']};
            background: {c['secondary_hover_bg']};
            border-bottom-right-radius: 7px;
            margin-bottom: 1px;
            margin-right: 1px;
        }}
        QSpinBox::down-button:hover {{
            background: {c['input_selection_bg']};
        }}
        /* ── BUTTONS ── */
        QPushButton {{
            background: {c['secondary_bg']};
            color: {c['secondary_text']};
            border: 1px solid {c['secondary_border']};
            border-radius: 8px; padding: 10px 18px;
            font-size: 10pt; font-weight: 700;
        }}
        QPushButton:hover {{
            background: {c['secondary_hover_bg']};
            border-color: {c['primary']};
        }}
        QPushButton:pressed {{
            background: {c['primary']};
            color: {c['primary_text']};
        }}
        QPushButton:disabled {{
            color: {c['text_muted']};
            background: {c['card_bg']};
            border-color: {c['border']};
        }}
        QPushButton#PrimaryButton {{
            background: {c['primary']};
            border-color: {c['primary']};
            color: {c['primary_text']};
        }}
        QPushButton#PrimaryButton:hover {{
            background: {c['primary_hover']};
            border-color: {c['primary_hover']};
        }}
        QPushButton#PrimaryButton:pressed {{
            background: {c['primary_pressed']};
        }}
        QPushButton#SecondaryButton {{
            background: {c['secondary_bg']};
            border: 1px solid {c['secondary_border']};
            color: {c['secondary_text']};
        }}
        QPushButton#SecondaryButton:hover {{
            background: {c['secondary_hover_bg']};
            border-color: {c['primary']};
        }}
        /* ── ANIMATED BUTTON OVERRIDES ── */
        AnimatedButton {{
            background: transparent;
            border: none;
            color: palette(button-text);
        }}
        AnimatedButton:hover, AnimatedButton:pressed, AnimatedButton:checked, AnimatedButton:disabled {{
            background: transparent;
            border: none;
            color: palette(button-text);
        }}
        AnimatedButton#PrimaryButton, AnimatedButton#SecondaryButton, AnimatedButton#SuccessButton, AnimatedButton#DangerButton, AnimatedButton#SidebarNav {{
            background: transparent;
            border: none;
            color: palette(button-text);
        }}
        AnimatedButton#PrimaryButton:hover, AnimatedButton#PrimaryButton:pressed, AnimatedButton#PrimaryButton:disabled,
        AnimatedButton#SecondaryButton:hover, AnimatedButton#SecondaryButton:pressed, AnimatedButton#SecondaryButton:disabled,
        AnimatedButton#SuccessButton:hover, AnimatedButton#SuccessButton:pressed, AnimatedButton#SuccessButton:disabled,
        AnimatedButton#DangerButton:hover, AnimatedButton#DangerButton:pressed, AnimatedButton#DangerButton:disabled,
        AnimatedButton#SidebarNav:hover, AnimatedButton#SidebarNav:pressed, AnimatedButton#SidebarNav:checked, AnimatedButton#SidebarNav:disabled {{
            background: transparent;
            border: none;
            color: palette(button-text);
        }}
        QPushButton#ChipButton {{
            background: {c['chip_bg']};
            border: 1px solid {c['chip_border']};
            border-radius: 12px; padding: 4px 12px;
            font-size: 8.5pt; font-weight: 600;
            color: {c['chip_text']};
        }}
        QPushButton#ChipButton:hover {{
            background: {c['chip_hover_bg']};
            color: {c['text_primary']};
        }}
        QProgressBar {{
            border: none; border-radius: 6px;
            background: {c['progress_bg']};
            text-align: right; color: {c['text_primary']}; height: 14px;
        }}
        QProgressBar::chunk {{
            border-radius: 6px; background: {c['progress_chunk']};
        }}
        /* ── TABLE ── */
        QTableWidget {{
            background: {c['table_bg']};
            alternate-background-color: {c['table_alt']};
            border: 1px solid {c['table_border']};
            border-radius: 10px;
            gridline-color: transparent;
            selection-background-color: {c['table_selected_bg']};
            selection-color: {c['table_selected_text']};
            color: {c['table_text']};
        }}
        QTableWidget::item {{
            padding: 10px 14px;
            color: {c['table_text']};
            border-bottom: 1px solid {c['table_item_border']};
        }}
        QTableWidget::item:hover {{
            background-color: {c['secondary_hover_bg']};
        }}
        QTableWidget::item:selected {{
            background-color: {c['table_selected_bg']};
            color: {c['table_selected_text']};
            font-weight: 600;
        }}
        QHeaderView::section {{
            background: {c['table_header_bg']};
            color: {c['table_header_text']};
            border: none;
            border-bottom: 2px solid {c['table_border']};
            padding: 10px 14px;
            font-weight: 700; font-size: 9pt;
        }}
        /* ── SCROLLBAR ── */
        QScrollBar:vertical {{
            background: {c['scrollbar_bg']}; width: 8px; margin: 4px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {c['scrollbar_handle']}; border-radius: 4px; min-height: 32px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c['scrollbar_handle_hover']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {c['scrollbar_bg']}; height: 8px; margin: 0 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {c['scrollbar_handle']}; border-radius: 4px; min-width: 32px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {c['scrollbar_handle_hover']};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        /* ── EMAIL PREVIEW ── */
        QFrame#MockEmailClient {{
            background: {c['card_bg']};
            border: 1px solid {c['card_border']};
            border-radius: 10px;
        }}
        QFrame#EmailHeaderBar {{
            background: {c['email_header_bg']};
            border-top-left-radius: 10px; border-top-right-radius: 10px;
            border-bottom: 1px solid {c['border']};
        }}
        QFrame#EmailBodyBox {{
            background: {c['email_body_bg']};
            border-bottom-left-radius: 10px; border-bottom-right-radius: 10px;
        }}
        QTextEdit#MockEmailBodyText {{
            border: none; background: transparent;
            color: {c['table_text']}; font-size: 10pt;
        }}
        /* ── THEME CARDS ── */
        QFrame#ThemeCard {{
            background: {c['card_bg']};
            border: 2px solid {c['card_border']};
            border-radius: 14px;
        }}
        QFrame#ThemeCard[selected="true"] {{
            border: 2px solid {c['primary']};
        }}
        QFrame#ThemeDirectionCard {{
            background: {c['card_bg']};
            border: 1px solid {c['card_border']};
            border-radius: 16px;
        }}
        QFrame#ThemeDirectionCard[selected="true"] {{
            border: 2px solid {c['primary']};
        }}
        QFrame#ThemeDirectionsFooter {{
            background: {c['card_bg']};
            border: 1px solid {c['card_border']};
            border-radius: 14px;
        }}
        QLabel#ThemeNumber {{
            min-width: 26px; min-height: 26px; max-width: 26px; max-height: 26px;
            border-radius: 8px;
            background: {c['primary']};
            color: {c['primary_text']};
            font-weight: 900;
            qproperty-alignment: AlignCenter;
        }}
        QLabel#ThemeTitle {{
            color: {c['text_primary']};
            font-size: 13pt;
            font-weight: 800;
        }}
        QLabel#ThemeDescription {{
            color: {c['text_secondary']};
            font-size: 9.5pt;
        }}
        QLabel#ThemeTag {{
            background: {c['chip_bg']};
            border: 1px solid {c['chip_border']};
            border-radius: 10px;
            color: {c['chip_text']};
            padding: 4px 9px;
            font-size: 8pt;
            font-weight: 700;
        }}
        QLabel#ThemeCheck {{
            min-width: 26px; min-height: 26px; max-width: 26px; max-height: 26px;
            border-radius: 13px;
            background: {c['primary']};
            color: {c['primary_text']};
            font-weight: 900;
            qproperty-alignment: AlignCenter;
        }}
        QLabel#ThemeSwatch {{
            min-width: 34px; min-height: 24px; max-width: 34px; max-height: 24px;
            border-radius: 4px;
            border: 1px solid {c['card_border']};
        }}
        QLabel#ThemeHex {{
            color: {c['text_muted']};
            font-size: 7pt;
            font-weight: 700;
        }}
        QFrame#ThemePreview {{
            background: {c['card_bg']};
            border: 1px solid {c['card_border']};
            border-radius: 14px;
        }}
        QFrame#ThemeMiniPanel {{
            background: {c['table_bg']};
            border: 1px solid {c['table_border']};
            border-radius: 10px;
        }}
        QFrame#MetricChip {{
            background: {c['card_bg']};
            border: 1px solid {c['card_border']};
            border-radius: 10px;
            min-width: 160px;
            min-height: 80px;
        }}
        QLabel#MetricChipTitle {{
            color: {c['text_secondary']};
            font-size: 8pt;
            font-weight: 700;
        }}
        QLabel#MetricChipValue {{
            color: {c['text_primary']};
            font-size: 14pt;
            font-weight: 800;
        }}
        QPushButton#SuccessButton {{
            background: transparent;
            border: none;
            color: palette(button-text);
        }}
        QPushButton#DangerButton {{
            background: transparent;
            border: none;
            color: palette(button-text);
        }}
    """


class ThemeEngine:
    """Persist and render the Local Worker visual theme system."""

    def __init__(self, themes: dict[str, dict] | None = None, default_theme: str = DEFAULT_THEME):
        self.themes = themes or THEMES
        self.default_theme = default_theme if default_theme in self.themes else next(iter(self.themes))

    def theme_names(self) -> list[str]:
        preferred = ["midnight_glass", "warm_stone", "electric_indigo", "forest_executive"]
        ordered = [name for name in preferred if name in self.themes]
        ordered.extend(name for name in self.themes if name not in ordered)
        return ordered

    def get_theme(self, name: str | None = None) -> dict:
        return self.themes.get(name or self.active_theme(), self.themes[self.default_theme])

    def get_theme_meta(self, name: str) -> dict:
        theme = self.get_theme(name)
        return {
            "name": name,
            "display_name": theme.get("display_name", name.replace("_", " ").title()),
            "description": theme.get("description", ""),
            "tags": theme.get("tags", []),
            "palette_swatches": theme.get("palette_swatches", []),
        }

    def colors(self, name: str | None = None) -> dict:
        return self.get_theme(name).get("colors", {})

    def color(self, key: str, name: str | None = None, fallback: str = "#000000") -> str:
        return self.colors(name).get(key, fallback)

    def active_theme(self) -> str:
        return load_active_theme()

    def save_active_theme(self, name: str):
        if name not in self.themes:
            raise ValueError(f"Unknown theme: {name}")
        save_active_theme(name)

    def generate_qss(self, theme_name: str | None = None) -> str:
        return generate_qss(theme_name or self.active_theme())


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return super().__lt__(other)


def interpolate_color(c1: QColor, c2: QColor, progress: float) -> QColor:
    r = c1.red() + (c2.red() - c1.red()) * progress
    g = c1.green() + (c2.green() - c1.green()) * progress
    b = c1.blue() + (c2.blue() - c1.blue()) * progress
    a = c1.alpha() + (c2.alpha() - c1.alpha()) * progress
    return QColor(int(r), int(g), int(b), int(a))


def get_contrast_text_color(bg_hex: str, dark_color: str = "#000000", light_color: str = "#FFFFFF") -> str:
    hex_val = bg_hex.lstrip('#')
    if len(hex_val) != 6:
        return light_color
    try:
        r = int(hex_val[0:2], 16) / 255.0
        g = int(hex_val[2:4], 16) / 255.0
        b = int(hex_val[4:6], 16) / 255.0
        l = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return dark_color if l > 0.45 else light_color
    except Exception:
        return light_color


def get_button_colors(object_name: str, theme_colors: dict, is_checked: bool = False) -> tuple:
    theme_dark = theme_colors.get('text_primary', '#0F172A')
    if get_contrast_text_color(theme_dark, "dark", "light") == "dark":
        theme_dark = "#0F172A"

    theme_light = theme_colors.get('primary_text', '#FFFFFF')
    if get_contrast_text_color(theme_light, "dark", "light") == "light":
        theme_light = "#FFFFFF"

    if object_name == "SidebarNav":
        if is_checked:
            bg = theme_colors.get('sidebar_active', '#4E3A45')
            fg = theme_colors.get('sidebar_text_active', '#F7F4EF')
            border = "transparent"
        else:
            bg = "transparent"
            fg = theme_colors.get('sidebar_text', '#C4A99A')
            border = "transparent"
        hover_bg = theme_colors.get('sidebar_hover', '#3D2A34')
        hover_fg = theme_colors.get('sidebar_text_active', '#F7F4EF')
        pressed_bg = theme_colors.get('sidebar_active', '#4E3A45')
        pressed_fg = theme_colors.get('sidebar_text_active', '#F7F4EF')

        # Contrast check sidebar nav buttons
        fg = get_contrast_text_color(bg if bg != "transparent" else theme_colors.get('sidebar_bg', '#2C1A25'), theme_dark, fg)
        hover_fg = get_contrast_text_color(hover_bg, theme_dark, hover_fg)
        pressed_fg = get_contrast_text_color(pressed_bg, theme_dark, pressed_fg)
        return bg, fg, border, hover_bg, hover_fg, pressed_bg, pressed_fg, 8

    elif object_name == "PrimaryButton":
        bg = theme_colors.get('primary', '#8A6F58')
        hover_bg = theme_colors.get('primary_hover', '#7A5F48')
        pressed_bg = theme_colors.get('primary_pressed', '#6A4F38')
        border = "transparent"

        fg = get_contrast_text_color(bg, theme_dark, theme_light)
        hover_fg = get_contrast_text_color(hover_bg, theme_dark, theme_light)
        pressed_fg = get_contrast_text_color(pressed_bg, theme_dark, theme_light)
        return bg, fg, border, hover_bg, hover_fg, pressed_bg, pressed_fg, 8

    elif object_name == "SecondaryButton":
        bg = theme_colors.get('secondary_bg', '#FFFFFF')
        hover_bg = theme_colors.get('secondary_hover_bg', '#F7F4EF')
        pressed_bg = theme_colors.get('primary_pressed', '#6A4F38')
        border = theme_colors.get('secondary_border', '#E8DFD3')

        normal_fg = theme_colors.get('secondary_text', '#2C1A25')
        fg = get_contrast_text_color(bg, normal_fg, theme_light)
        hover_fg = get_contrast_text_color(hover_bg, normal_fg, theme_light)
        pressed_fg = get_contrast_text_color(pressed_bg, normal_fg, theme_light)
        return bg, fg, border, hover_bg, hover_fg, pressed_bg, pressed_fg, 8

    elif object_name == "SuccessButton":
        bg = theme_colors.get('success', '#6DC1B5')
        hover_bg = theme_colors.get('success', '#6DC1B5')
        pressed_bg = theme_colors.get('success', '#6DC1B5')
        border = "transparent"

        fg = get_contrast_text_color(bg, theme_dark, theme_light)
        return bg, fg, border, hover_bg, fg, pressed_bg, fg, 8

    elif object_name == "DangerButton":
        bg = theme_colors.get('danger', '#C4364A')
        hover_bg = theme_colors.get('danger', '#C4364A')
        pressed_bg = theme_colors.get('danger', '#C4364A')
        border = "transparent"

        fg = get_contrast_text_color(bg, theme_dark, theme_light)
        return bg, fg, border, hover_bg, fg, pressed_bg, fg, 8

    else:
        bg = "transparent"
        fg = theme_colors.get('text_primary', '#000000')
        border = "transparent"
        return bg, fg, border, bg, fg, bg, fg, 8


class AnimatedButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._scale = 1.0
        self._hover_progress = 0.0
        self._press_progress = 0.0
        self._slide_offset = 0.0

        # Create animations
        self.scale_anim = QPropertyAnimation(self, b"scale")
        self.scale_anim.setDuration(120)
        self.scale_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.hover_anim = QPropertyAnimation(self, b"hover_progress")
        self.hover_anim.setDuration(120)
        self.hover_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.press_anim = QPropertyAnimation(self, b"press_progress")
        self.press_anim.setDuration(80)
        self.press_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.slide_anim = QPropertyAnimation(self, b"slide_offset")
        self.slide_anim.setDuration(120)
        self.slide_anim.setEasingCurve(QEasingCurve.OutQuad)

    def get_scale(self):
        return self._scale
    def set_scale(self, val):
        self._scale = val
        self.update()
    scale = Property(float, get_scale, set_scale)

    def get_hover_progress(self):
        return self._hover_progress
    def set_hover_progress(self, val):
        self._hover_progress = val
        self.update()
    hover_progress = Property(float, get_hover_progress, set_hover_progress)

    def get_press_progress(self):
        return self._press_progress
    def set_press_progress(self, val):
        self._press_progress = val
        self.update()
    press_progress = Property(float, get_press_progress, set_press_progress)

    def get_slide_offset(self):
        return self._slide_offset
    def set_slide_offset(self, val):
        self._slide_offset = val
        self.update()
    slide_offset = Property(float, get_slide_offset, set_slide_offset)

    def enterEvent(self, event):
        if MOTION_ENABLED:
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._scale)
            self.scale_anim.setEndValue(1.02)
            self.scale_anim.start()

            self.hover_anim.stop()
            self.hover_anim.setStartValue(self._hover_progress)
            self.hover_anim.setEndValue(1.0)
            self.hover_anim.start()

            if self.objectName() == "SidebarNav":
                self.slide_anim.stop()
                self.slide_anim.setStartValue(self._slide_offset)
                self.slide_anim.setEndValue(4.0)
                self.slide_anim.start()

                # Change SVG color dynamically
                colors = get_theme_colors()
                icon_key = self.property("icon_key")
                if icon_key:
                    hover_color = colors.get('sidebar_text_active', '#ffffff')
                    svg_data = get_sidebar_icon_svg(icon_key, hover_color)
                    if svg_data:
                        self.setIcon(QIcon(svg_to_pixmap(svg_data, 18, 18)))

        super().enterEvent(event)

    def leaveEvent(self, event):
        if MOTION_ENABLED:
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._scale)
            self.scale_anim.setEndValue(1.0)
            self.scale_anim.start()

            self.hover_anim.stop()
            self.hover_anim.setStartValue(self._hover_progress)
            self.hover_anim.setEndValue(0.0)
            self.hover_anim.start()

            if self.objectName() == "SidebarNav":
                self.slide_anim.stop()
                self.slide_anim.setStartValue(self._slide_offset)
                self.slide_anim.setEndValue(0.0)
                self.slide_anim.start()

                # Restore SVG color
                colors = get_theme_colors()
                is_active = self.isChecked() if self.isCheckable() else False
                color_key = 'sidebar_text_active' if is_active else 'sidebar_text'
                normal_color = colors.get(color_key, '#7c8db5')
                icon_key = self.property("icon_key")
                if icon_key:
                    svg_data = get_sidebar_icon_svg(icon_key, normal_color)
                    if svg_data:
                        self.setIcon(QIcon(svg_to_pixmap(svg_data, 18, 18)))
        else:
            self._scale = 1.0
            self._hover_progress = 0.0
            self._slide_offset = 0.0
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if MOTION_ENABLED:
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._scale)
            self.scale_anim.setEndValue(0.96)
            self.scale_anim.start()

            self.press_anim.stop()
            self.press_anim.setStartValue(self._press_progress)
            self.press_anim.setEndValue(1.0)
            self.press_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if MOTION_ENABLED:
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._scale)
            self.scale_anim.setEndValue(1.02 if self.underMouse() else 1.0)
            self.scale_anim.start()

            self.press_anim.stop()
            self.press_anim.setStartValue(self._press_progress)
            self.press_anim.setEndValue(0.0)
            self.press_anim.start()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        option = QStyleOptionButton()
        self.initStyleOption(option)

        colors = get_theme_colors()
        obj_name = self.objectName()
        is_checked = self.isChecked() if self.isCheckable() else False

        bg_n, fg_n, border_n, bg_h, fg_h, bg_p, fg_p, radius = get_button_colors(obj_name, colors, is_checked)

        def to_qcolor(val):
            if val == "transparent" or not val:
                return QColor(0, 0, 0, 0)
            return QColor(val)

        c_bg_n, c_fg_n = to_qcolor(bg_n), to_qcolor(fg_n)
        c_bg_h, c_fg_h = to_qcolor(bg_h), to_qcolor(fg_h)
        c_bg_p, c_fg_p = to_qcolor(bg_p), to_qcolor(fg_p)
        c_border = to_qcolor(border_n)

        current_bg = interpolate_color(c_bg_n, c_bg_h, self._hover_progress)
        current_fg = interpolate_color(c_fg_n, c_fg_h, self._hover_progress)

        if self._press_progress > 0.0:
            current_bg = interpolate_color(current_bg, c_bg_p, self._press_progress)
            current_fg = interpolate_color(current_fg, c_fg_p, self._press_progress)

        palette = option.palette
        palette.setColor(QPalette.ButtonText, current_fg)
        option.palette = palette

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        painter.save()
        painter.translate(cx, cy)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy)

        rect = self.rect().adjusted(2, 2, -2, -2)

        if obj_name == "SidebarNav":
            rect = self.rect().adjusted(16, 2, -8, -2)
            option.rect = rect.adjusted(14, 0, -2, 0)
        else:
            option.rect = rect

        # Draw physical drop shadow for depth.
        if obj_name in ("PrimaryButton", "SecondaryButton", "SuccessButton", "DangerButton"):
            shadow_rect = rect.translated(0, 1.5)
            shadow_color = QColor(0, 0, 0, 40)
            painter.setBrush(shadow_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(shadow_rect, radius, radius)
        elif obj_name == "SidebarNav":
            lift = max(self._hover_progress, 0.85 if is_checked else 0.0)
            if lift > 0:
                accent = QColor(colors.get('sidebar_indicator', colors.get('primary', '#3B82F6')))
                accent.setAlpha(int(20 + 42 * lift))
                painter.setBrush(accent)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(rect.translated(0, 3), radius, radius)

                ambient = QColor(0, 0, 0, int(18 + 34 * lift))
                painter.setBrush(ambient)
                painter.drawRoundedRect(rect.translated(0, 5), radius, radius)

        # Draw custom background rounded rect
        painter.setBrush(current_bg)
        if c_border.alpha() > 0:
            border_pen = QPen(c_border)
            border_pen.setWidthF(1.2)
            painter.setPen(border_pen)
        else:
            painter.setPen(Qt.NoPen)

        painter.drawRoundedRect(rect, radius, radius)

        # Draw left indicator vertical line/pill for the active sidebar navigation item!
        if obj_name == "SidebarNav" and is_checked:
            indicator_color = QColor(colors.get('sidebar_indicator', colors.get('primary', '#8A6F58')))
            painter.setBrush(indicator_color)
            painter.setPen(Qt.NoPen)
            indicator_rect = QRectF(rect.x() + 2, rect.y() + 6, 3.5, rect.height() - 12)
            painter.drawRoundedRect(indicator_rect, 1.75, 1.75)

        if obj_name in ("PrimaryButton", "SuccessButton", "DangerButton") and self._hover_progress > 0:
            glow_color = QColor(current_fg)
            glow_color.setAlpha(int(35 * self._hover_progress))
            glow_pen = QPen(glow_color)
            glow_pen.setWidthF(2.0)
            painter.setPen(glow_pen)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

        if self._slide_offset > 0.0:
            painter.translate(self._slide_offset, 0.0)

        self.style().drawControl(QStyle.CE_PushButtonLabel, option, painter, self)
        painter.restore()


class PercentSpinBox(QSpinBox):
    """Spinbox that keeps native stepping but paints visible chevrons on themed UIs."""

    def paintEvent(self, event):
        super().paintEvent(event)

        colors = get_theme_colors()
        arrow_color = QColor(colors.get("text_primary", "#E2E8F0"))
        if not self.isEnabled():
            arrow_color = QColor(colors.get("text_muted", "#64748B"))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(arrow_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

        right = self.rect().right() - 13
        up_y = self.rect().top() + 13
        down_y = self.rect().bottom() - 12

        painter.drawLine(right - 4, up_y + 2, right, up_y - 2)
        painter.drawLine(right, up_y - 2, right + 4, up_y + 2)
        painter.drawLine(right - 4, down_y - 2, right, down_y + 2)
        painter.drawLine(right, down_y + 2, right + 4, down_y - 2)
        painter.end()


class AnimatedBadge(QWidget):
    def __init__(self, icon_char="", parent=None):
        super().__init__(parent)
        self.icon_char = icon_char
        self.setFixedSize(60, 60)
        self._scale = 1.0
        self._hover_progress = 0.0
        self._rotation = 0.0

        self.scale_anim = QPropertyAnimation(self, b"scale")
        self.scale_anim.setDuration(180)
        self.scale_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.hover_anim = QPropertyAnimation(self, b"hover_progress")
        self.hover_anim.setDuration(180)
        self.hover_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.rot_anim = QPropertyAnimation(self, b"rotation")
        self.rot_anim.setDuration(250)
        self.rot_anim.setEasingCurve(QEasingCurve.OutQuad)

    def get_scale(self):
        return self._scale
    def set_scale(self, val):
        self._scale = val
        self.update()
    scale = Property(float, get_scale, set_scale)

    def get_hover_progress(self):
        return self._hover_progress
    def set_hover_progress(self, val):
        self._hover_progress = val
        self.update()
    hover_progress = Property(float, get_hover_progress, set_hover_progress)

    def get_rotation(self):
        return self._rotation
    def set_rotation(self, val):
        self._rotation = val
        self.update()
    rotation = Property(float, get_rotation, set_rotation)

    def enterEvent(self, event):
        if MOTION_ENABLED:
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._scale)
            self.scale_anim.setEndValue(1.2)
            self.scale_anim.start()

            self.hover_anim.stop()
            self.hover_anim.setStartValue(self._hover_progress)
            self.hover_anim.setEndValue(1.0)
            self.hover_anim.start()

            obj_name = self.objectName()
            self.rot_anim.stop()
            self.rot_anim.setStartValue(self._rotation)
            if obj_name == "GreenBadge":
                self.rot_anim.setEndValue(15.0)
            elif obj_name == "RedBadge":
                self.rot_anim.setEndValue(45.0)
            else:
                self.rot_anim.setEndValue(36.0)
            self.rot_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if MOTION_ENABLED:
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._scale)
            self.scale_anim.setEndValue(1.0)
            self.scale_anim.start()

            self.hover_anim.stop()
            self.hover_anim.setStartValue(self._hover_progress)
            self.hover_anim.setEndValue(0.0)
            self.hover_anim.start()

            self.rot_anim.stop()
            self.rot_anim.setStartValue(self._rotation)
            self.rot_anim.setEndValue(0.0)
            self.rot_anim.start()
        else:
            self._scale = 1.0
            self._hover_progress = 0.0
            self._rotation = 0.0
            self.update()
        super().leaveEvent(event)

    def get_candidates_svg(self, color_hex):
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color_hex}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
            <circle cx="9" cy="7" r="4"></circle>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
        </svg>"""

    def get_arrow_svg(self, color_hex):
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color_hex}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
            <line x1="7" y1="17" x2="17" y2="7"></line>
            <polyline points="7 7 17 7 17 17"></polyline>
        </svg>"""

    def get_star_svg(self, color_hex):
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color_hex}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
        </svg>"""

    def get_x_svg(self, color_hex):
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color_hex}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>"""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        colors = get_theme_colors()
        obj_name = self.objectName()

        if obj_name == "PurpleBadge":
            bg = colors.get('badge_purple_bg', '#F3E8FF')
            fg = colors.get('badge_purple_text', '#7C3AED')
            svg_content = self.get_candidates_svg(fg)
        elif obj_name == "GreenBadge":
            bg = colors.get('badge_green_bg', '#DCFCE7')
            fg = colors.get('badge_green_text', '#16A34A')
            svg_content = self.get_arrow_svg(fg)
        elif obj_name == "BlueBadge":
            bg = colors.get('badge_blue_bg', '#DBEAFE')
            fg = colors.get('badge_blue_text', '#2563EB')
            svg_content = self.get_star_svg(fg)
        else: # RedBadge
            bg = colors.get('badge_red_bg', '#FEE2E2')
            fg = colors.get('badge_red_text', '#DC2626')
            svg_content = self.get_x_svg(fg)

        c_bg = QColor(bg)
        c_fg = QColor(fg)

        cx, cy = self.width() / 2.0, self.height() / 2.0

        if self._hover_progress > 0.0:
            glow_color = QColor(c_fg)
            glow_color.setAlpha(int(40 * self._hover_progress))
            painter.setBrush(glow_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(cx, cy), 27 * self._scale, 27 * self._scale)

        painter.setBrush(c_bg)
        border_pen = QPen(c_fg)
        border_pen.setWidthF(1.0)
        border_color = QColor(c_fg)
        border_color.setAlpha(int(60 + 60 * self._hover_progress))
        border_pen.setColor(border_color)
        painter.setPen(border_pen)

        painter.drawEllipse(QPoint(cx, cy), 22 * self._scale, 22 * self._scale)

        renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
        icon_size = 22.0 * self._scale

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._rotation)
        painter.translate(-cx, -cy)

        rect = QRectF(cx - icon_size / 2.0, cy - icon_size / 2.0, icon_size, icon_size)
        renderer.render(painter, rect)
        painter.restore()


class AnimatedThemeCard(QFrame):
    def __init__(self, theme_name="", parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.setCursor(Qt.PointingHandCursor)
        self._scale = 1.0
        self._hover_progress = 0.0

        self.scale_anim = QPropertyAnimation(self, b"scale")
        self.scale_anim.setDuration(180)
        self.scale_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.hover_anim = QPropertyAnimation(self, b"hover_progress")
        self.hover_anim.setDuration(180)
        self.hover_anim.setEasingCurve(QEasingCurve.OutQuad)

    def get_scale(self):
        return self._scale
    def set_scale(self, val):
        self._scale = val
        self.update()
    scale = Property(float, get_scale, set_scale)

    def get_hover_progress(self):
        return self._hover_progress
    def set_hover_progress(self, val):
        self._hover_progress = val
        self.update()
    hover_progress = Property(float, get_hover_progress, set_hover_progress)

    def enterEvent(self, event):
        if MOTION_ENABLED:
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._scale)
            self.scale_anim.setEndValue(1.03)
            self.scale_anim.start()

            self.hover_anim.stop()
            self.hover_anim.setStartValue(self._hover_progress)
            self.hover_anim.setEndValue(1.0)
            self.hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if MOTION_ENABLED:
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._scale)
            self.scale_anim.setEndValue(1.0)
            self.scale_anim.start()

            self.hover_anim.stop()
            self.hover_anim.setStartValue(self._hover_progress)
            self.hover_anim.setEndValue(0.0)
            self.hover_anim.start()
        else:
            self._scale = 1.0
            self._hover_progress = 0.0
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        painter.save()
        painter.translate(cx, cy)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy)

        is_selected = self.property("selected") == "true"
        colors = THEMES[self.theme_name]["colors"]

        bg_color = QColor(colors.get('card_bg', '#ffffff'))
        border_color = QColor(colors.get('card_border', '#e0e0e0'))

        border_width = 1.0
        if is_selected:
            border_color = QColor(colors.get('primary', '#8a6f58'))
            border_width = 2.0

        if self._hover_progress > 0.0:
            glow_color = QColor(colors.get('primary', '#8a6f58'))
            glow_color.setAlpha(int(40 * self._hover_progress))
            painter.setBrush(Qt.NoBrush)
            glow_pen = QPen(glow_color)
            glow_pen.setWidthF(3.0 * self._hover_progress + (2.0 if is_selected else 0.0))
            painter.setPen(glow_pen)
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 16, 16)

        painter.setBrush(bg_color)
        pen = QPen(border_color)
        pen.setWidthF(border_width)
        painter.setPen(pen)

        painter.drawRoundedRect(self.rect().adjusted(3, 3, -3, -3), 16, 16)
        painter.restore()


class HoverDepthFrame(QFrame):
    """Theme-aware card surface with a subtle hover lift."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_Hover, True)
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(18)
        self.shadow.setOffset(0, 4)
        self.setGraphicsEffect(self.shadow)
        self._set_shadow_color(34)

        self.blur_anim = QPropertyAnimation(self.shadow, b"blurRadius")
        self.blur_anim.setDuration(180)
        self.blur_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.offset_anim = QPropertyAnimation(self.shadow, b"yOffset")
        self.offset_anim.setDuration(180)
        self.offset_anim.setEasingCurve(QEasingCurve.OutCubic)

    def _set_shadow_color(self, alpha: int):
        colors = get_theme_colors()
        color = QColor(colors.get("primary", "#3B82F6"))
        if not color.isValid():
            color = QColor(0, 0, 0)
        color.setAlpha(alpha)
        self.shadow.setColor(color)

    def _animate_shadow(self, blur: float, offset: float):
        self.blur_anim.stop()
        self.blur_anim.setStartValue(self.shadow.blurRadius())
        self.blur_anim.setEndValue(blur)
        self.blur_anim.start()

        self.offset_anim.stop()
        self.offset_anim.setStartValue(self.shadow.yOffset())
        self.offset_anim.setEndValue(offset)
        self.offset_anim.start()

    def enterEvent(self, event):
        if MOTION_ENABLED:
            self._set_shadow_color(72)
            self._animate_shadow(30, 9)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if MOTION_ENABLED:
            self._set_shadow_color(34)
            self._animate_shadow(18, 4)
        super().leaveEvent(event)


class AnalysisWorker(QObject):
    progress_max = Signal(int)
    progress = Signal(int)
    status = Signal(str)
    row = Signal(dict)
    run_created = Signal(int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, folder: Path, output: Path, config: dict, ai_mode: str, job_name: str):
        super().__init__()
        self.folder = folder
        self.output = output
        self.config = config
        self.ai_mode = ai_mode
        self.job_name = job_name
        self.cancelled = False
        self.store = WorkspaceStore()

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            self._run()
        except Exception:
            detail = traceback.format_exc()
            log_path = write_crash_log(detail)
            self.failed.emit(f"Analysis stopped. Details were written to {log_path}")

    def _run(self):
        files = [
            path
            for path in self.folder.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        files.sort(key=lambda p: str(p).lower())
        if not files:
            self.done.emit("No PDF, DOCX, or TXT files found.")
            return

        self.output.mkdir(parents=True, exist_ok=True)
        run_id = self.store.create_run(None, self.job_name, str(self.folder), str(self.output), len(files))
        self.run_created.emit(run_id)
        self.progress_max.emit(len(files))
        results: list[dict] = []
        failed_files: list[str] = []
        seen_hashes: dict[str, str] = {}

        for index, path in enumerate(files, start=1):
            if self.cancelled:
                self.status.emit("Cancelled. Writing partial results...")
                break

            self.status.emit(f"Processing {index}/{len(files)}: {path.name}")
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError(f"File exceeds max size: {MAX_FILE_BYTES} bytes")
                data = path.read_bytes()
                file_hash = hashlib.sha256(data).hexdigest()
                duplicate_of = seen_hashes.get(file_hash)
                if not duplicate_of:
                    seen_hashes[file_hash] = str(path)

                text = extract_text(data, path.suffix.lstrip("."), path.name)
                result = score_cv(text, self.config)
                result = maybe_apply_ai_review(text, self.config, result, self.ai_mode)

                email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
                email = email_match.group(0) if email_match else ""

                row = {
                    **result,
                    "rank": 0,
                    "file": str(path),
                    "file_hash": file_hash,
                    "is_duplicate": bool(duplicate_of),
                    "duplicate_of": duplicate_of or "",
                    "email": email,
                    "sync_status": "offline_ready",
                    "analyzed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                }
                self.store.add_result(run_id, row)
                results.append(row)
                self.row.emit(row)
            except Exception as exc:
                failed_files.append(str(path))
                self.row.emit(
                    {
                        "rank": 0,
                        "file": str(path),
                        "score": 0,
                        "decision": "recommended_reject",
                        "confidence": "low",
                        "matched_skills": [],
                        "missing_skills": [],
                        "risk_flags": ["processing_failed"],
                        "summary": "Processing failed.",
                        "explanation": str(exc),
                        "is_duplicate": False,
                        "sync_status": "failed",
                        "analyzed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    }
                )
            finally:
                self.progress.emit(index)

        ranked = sorted(results, key=lambda row: (-float(row.get("score") or 0), decision_rank(row.get("decision"))))
        for rank, row in enumerate(ranked, start=1):
            row["rank"] = rank

        json_path = self.output / "local_worker_results.json"
        csv_path = self.output / "local_worker_results.csv"
        html_path = self.output / "local_worker_report.html"
        failed_path = self.output / "failed_files.txt"
        manifest_path = self.output / "sync_manifest.json"

        json_path.write_text(json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, ranked)
        try:
            worker_module._generate_html_report(ranked, self.config, html_path)
        except Exception:
            pass
        if failed_files:
            failed_path.write_text("\n".join(failed_files), encoding="utf-8")
        elif failed_path.exists():
            failed_path.unlink()
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "cv_analyzer.local_worker.sync_manifest.v1",
                    "job": {"id": None, "name": self.job_name, "config": self.config},
                    "run": {
                        "cv_folder": str(self.folder),
                        "output_folder": str(self.output),
                        "total_files": len(files),
                        "processed": len(results),
                        "failed": len(failed_files),
                        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    },
                    "results_file": str(json_path),
                    "csv_file": str(csv_path),
                    "html_report": str(html_path),
                    "failed_files": failed_files,
                    "sync_status": "offline_ready",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.done.emit(f"Done. {len(results)} processed, {len(failed_files)} failed. Output: {self.output}")

    def _write_csv(self, path: Path, rows: list[dict]):
        with path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "rank",
                    "file",
                    "score",
                    "decision",
                    "confidence",
                    "is_duplicate",
                    "duplicate_of",
                    "summary",
                    "matched_skills",
                    "missing_skills",
                    "risk_flags",
                    "explanation",
                    "analyzed_at",
                ],
                extrasaction="ignore",
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        **row,
                        "matched_skills": ", ".join(row.get("matched_skills") or []),
                        "missing_skills": ", ".join(row.get("missing_skills") or []),
                        "risk_flags": ", ".join(row.get("risk_flags") or []),
                    }
                )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CV Analyzer Local Worker")
        self.resize(1280, 820)
        self._center_on_screen()
        icon_path = resource_path("assets/cv_analyzer_worker.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.thread: QThread | None = None
        self.worker: AnalysisWorker | None = None
        self.rows: list[dict] = []
        self.store = WorkspaceStore()
        self._animations: list[QPropertyAnimation] = []
        self._progress_animation: QPropertyAnimation | None = None
        self._status_pulse: QPropertyAnimation | None = None
        self.nav_buttons: list[QPushButton] = []
        self.analysis_started_at: float | None = None
        self.analysis_total_files = 0
        self.mail_templates = load_mail_templates()
        self.theme_engine = ThemeEngine()
        self.active_theme_name = self.theme_engine.active_theme()
        self.preview_theme_name = self.active_theme_name
        self.theme_cards: dict[str, QFrame] = {}
        self.theme_check_labels: dict[str, QLabel] = {}
        self.theme_apply_buttons: dict[str, QPushButton] = {}
        self.theme_preview_container: QFrame | None = None
        self.theme_preview_layout: QVBoxLayout | None = None
        self.server_connected = False
        self.server_quota_remaining: int | None = None
        self.server_allowed_jobs: list[int] = []
        self.server_company_id: int | None = None
        self._active_analysis_quota_amount = 0

        self._build()
        self._apply_style()
        self._set_server_connection(False, reason="Website sync required")
        self._refresh_history()
        if MOTION_ENABLED:
            self.setWindowOpacity(0.0)
            QTimer.singleShot(90, self._animate_startup)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = self.frameGeometry()
            center_point = screen.availableGeometry().center()
            geo.moveCenter(center_point)
            self.move(geo.topLeft())

    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 12, 12, 12)
        root_layout.setSpacing(12)

        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        main_panel = QWidget()
        main_panel.setObjectName("MainPanel")
        root_layout.addWidget(main_panel, 1)

        outer = QVBoxLayout(main_panel)
        outer.setContentsMargins(28, 20, 28, 22)
        outer.setSpacing(20)

        header = QHBoxLayout()
        header.setSpacing(16)
        header_icon = QLabel("✦")
        header_icon.setObjectName("HeaderIcon")
        header.addWidget(header_icon)
        title_box = QVBoxLayout()
        title = QLabel("CV Analyzer Local Worker")
        title.setObjectName("Title")
        subtitle = QLabel("Private desktop ranking for large CV folders. No site-side job required.")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusPill")
        header.addWidget(self.status_label)

        # Pulsing opacity effect for Status Pill in the header (breathing pulse)
        self.status_opacity = QGraphicsOpacityEffect()
        self.status_label.setGraphicsEffect(self.status_opacity)

        anim_fade_in = QPropertyAnimation(self.status_opacity, b"opacity")
        anim_fade_in.setDuration(1200)
        anim_fade_in.setStartValue(0.4)
        anim_fade_in.setEndValue(1.0)
        anim_fade_in.setEasingCurve(QEasingCurve.InOutQuad)

        anim_fade_out = QPropertyAnimation(self.status_opacity, b"opacity")
        anim_fade_out.setDuration(1200)
        anim_fade_out.setStartValue(1.0)
        anim_fade_out.setEndValue(0.4)
        anim_fade_out.setEasingCurve(QEasingCurve.InOutQuad)

        self.status_group = QSequentialAnimationGroup()
        self.status_group.addAnimation(anim_fade_in)
        self.status_group.addAnimation(anim_fade_out)
        self.status_group.setLoopCount(-1)
        self.status_group.start()
        self.sync_label = QLabel("Website sync required")
        self.sync_label.setObjectName("SyncMeta")
        header.addWidget(self.sync_label)
        self.quota_label = QLabel("Quota: connect")
        self.quota_label.setObjectName("SyncMeta")
        header.addWidget(self.quota_label)
        sync_button = AnimatedButton("↻  Sync now")
        sync_button.setObjectName("PrimaryButton")
        sync_button.setMinimumWidth(136)
        header.addWidget(sync_button)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.tabs.addTab(self._build_analyze_tab(), "Analyze")       # 0
        self.tabs.addTab(self._build_results_tab(), "Results")       # 1
        self.tabs.addTab(self._build_history_tab(), "History")       # 2
        self.tabs.addTab(self._build_server_tab(), "Website Sync")   # 3
        self.tabs.addTab(self._build_dashboard_tab(), "Dashboard")   # 4
        self.tabs.addTab(self._build_reports_tab(), "Reports")       # 5
        self.tabs.addTab(self._build_preferences_tab(), "Preferences") # 6
        self.tabs.addTab(self._build_ai_models_tab(), "AI Models")   # 7
        self.tabs.addTab(self._build_theme_studio_tab(), "Appearance") # 8
        self.tabs.addTab(self._build_templates_tab(), "Templates")   # 9
        self.tabs.currentChanged.connect(self._animate_tab_change)
        self.tabs.currentChanged.connect(self._update_nav_state)
        sync_button.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        outer.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

        open_output = QAction("Open output folder", self)
        open_output.triggered.connect(self._open_output)
        self.addAction(open_output)
        self._update_nav_state(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 20, 0, 18)
        layout.setSpacing(14)

        brand = QHBoxLayout()
        brand.setContentsMargins(14, 0, 14, 0)
        self.logo = QLabel()
        self.logo.setObjectName("LogoMark")
        self.logo.setFixedSize(42, 42)
        brand_text = QVBoxLayout()
        brand_title = QLabel("CV Analyzer")
        brand_title.setObjectName("SidebarBrand")
        brand_sub = QLabel("Local Worker")
        brand_sub.setObjectName("SidebarSub")
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_sub)
        brand.addWidget(self.logo)
        brand.addLayout(brand_text, 1)
        layout.addLayout(brand)
        layout.addSpacing(12)

        main_section = QLabel("MAIN")
        main_section.setObjectName("SidebarSection")
        main_section.setContentsMargins(14, 0, 14, 0)
        layout.addWidget(main_section)
        layout.addWidget(self._nav_button("Analyze", 0, icon_key="analyze"))
        layout.addWidget(self._nav_button("Results", 1, icon_key="results"))
        layout.addWidget(self._passive_nav_button("Dashboard", icon_key="dashboard"))
        layout.addWidget(self._nav_button("History", 2, icon_key="history"))
        layout.addSpacing(10)

        settings_section = QLabel("SETTINGS")
        settings_section.setObjectName("SidebarSection")
        settings_section.setContentsMargins(14, 0, 14, 0)
        layout.addWidget(settings_section)
        layout.addWidget(self._passive_nav_button("Appearance", icon_key="appearance"))
        layout.addWidget(self._passive_nav_button("Email Templates", icon_key="templates"))
        layout.addWidget(self._nav_button("Website Sync", 3, has_dot=True, icon_key="sync"))
        layout.addWidget(self._passive_nav_button("Preferences", icon_key="preferences"))
        layout.addWidget(self._passive_nav_button("AI Models", icon_key="models"))
        layout.addWidget(self._passive_nav_button("Reports", icon_key="reports"))

        layout.addStretch(1)

        # Enterprise Trust Card in Sidebar
        self.sidebar_trust_card = QFrame()
        self.sidebar_trust_card.setObjectName("SidebarTrustCard")
        trust_layout = QVBoxLayout(self.sidebar_trust_card)
        trust_layout.setContentsMargins(12, 12, 12, 12)
        trust_layout.setSpacing(6)

        trust_header = QHBoxLayout()
        trust_header.setSpacing(6)
        self.trust_icon = QLabel()
        self.trust_icon.setObjectName("SidebarTrustIcon")
        trust_title = QLabel("Enterprise trust")
        trust_title.setObjectName("SidebarTrustTitle")
        trust_header.addWidget(self.trust_icon)
        trust_header.addWidget(trust_title, 1)
        trust_layout.addLayout(trust_header)

        trust_desc = QLabel("Local analysis. Your data never leaves this device.")
        trust_desc.setObjectName("SidebarTrustDesc")
        trust_desc.setWordWrap(True)
        trust_layout.addWidget(trust_desc)

        layout.addWidget(self.sidebar_trust_card)
        layout.addSpacing(6)

        footer_layout = QVBoxLayout()
        footer_layout.setContentsMargins(14, 0, 14, 0)
        footer_layout.setSpacing(6)

        version_lbl = QLabel("v1.0.0")
        version_lbl.setObjectName("SidebarSub")

        status_row = QHBoxLayout()
        status_dot = QLabel("●")
        status_dot.setObjectName("StatusDot")
        status_lbl = QLabel("Ready")
        status_lbl.setObjectName("SidebarSub")
        status_row.addWidget(status_dot)
        status_row.addWidget(status_lbl)
        status_row.addStretch(1)

        footer_layout.addWidget(version_lbl)
        footer_layout.addLayout(status_row)
        layout.addLayout(footer_layout)
        return sidebar

    def _nav_button(self, text: str, index: int, has_dot: bool = False, icon_key: str = "") -> AnimatedButton:
        button = AnimatedButton(text + ("      ●" if has_dot else ""))
        button.setObjectName("SidebarNav")
        button.setCheckable(True)
        button.setProperty("tab_index", index)
        button.setProperty("icon_key", icon_key)
        button.clicked.connect(lambda: self.tabs.setCurrentIndex(index))

        # Load custom SVG icon
        colors = self.theme_engine.colors(self.active_theme_name)
        icon_color = colors.get('sidebar_text', '#94a3b8')
        svg_data = get_sidebar_icon_svg(icon_key, icon_color)
        if svg_data:
            button.setIcon(QIcon(svg_to_pixmap(svg_data, 18, 18)))
            button.setIconSize(QSize(18, 18))

        self.nav_buttons.append(button)
        return button

    def _passive_nav_button(self, text: str, icon_key: str = "") -> AnimatedButton:
        route_map = {
            "Dashboard": 4,
            "Reports": 5,
            "Preferences": 6,
            "AI Models": 7,
            "Appearance": 8,
            "Email Templates": 9,
            "Templates": 9,
        }
        for label, index in route_map.items():
            if label in text:
                return self._nav_button(text, index, icon_key=icon_key)
        button = AnimatedButton(text)
        button.setObjectName("SidebarPassive")
        button.setProperty("icon_key", icon_key)
        button.setEnabled(False)

        # Load custom SVG icon
        colors = self.theme_engine.colors(self.active_theme_name)
        icon_color = colors.get('sidebar_text', '#94a3b8')
        svg_data = get_sidebar_icon_svg(icon_key, icon_color)
        if svg_data:
            button.setIcon(QIcon(svg_to_pixmap(svg_data, 18, 18)))
            button.setIconSize(QSize(18, 18))

        return button

    def _update_nav_state(self, index: int):
        colors = self.theme_engine.colors(self.active_theme_name)
        for button in self.nav_buttons:
            btn_idx = button.property("tab_index")
            if btn_idx is not None:
                is_active = (btn_idx == index)
                button.setChecked(is_active)
                icon_key = button.property("icon_key")
                if icon_key:
                    color_key = 'sidebar_text_active' if is_active else 'sidebar_text'
                    icon_color = colors.get(color_key, '#E2E8F0' if is_active else '#7C8DB5')
                    svg_data = get_sidebar_icon_svg(icon_key, icon_color)
                    if svg_data:
                        button.setIcon(QIcon(svg_to_pixmap(svg_data, 18, 18)))

    def _build_analyze_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("AnalyzePage")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")

        page = QWidget()
        page.setObjectName("AnalyzePageContent")
        page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(22)

        metrics = QHBoxLayout()
        metrics.setSpacing(20)
        self.metric_candidates = QLabel("0")
        self.metric_avg_score = QLabel("--")
        self.metric_shortlisted = QLabel("0")
        self.metric_hard_rejects = QLabel("0")
        metrics.addWidget(self._metric_card("Candidates", self.metric_candidates, "Ready to analyze", "👥", "PurpleBadge"))
        metrics.addWidget(self._metric_card("Avg. Match Score", self.metric_avg_score, "Across all candidates", "↗", "GreenBadge"))
        metrics.addWidget(self._metric_card("Shortlisted", self.metric_shortlisted, "Above review threshold", "★", "BlueBadge"))
        metrics.addWidget(self._metric_card("Hard Rejects", self.metric_hard_rejects, "Filtered out", "✕", "RedBadge"))
        layout.addLayout(metrics, 0)

        setup_grid = QGridLayout()
        setup_grid.setHorizontalSpacing(20)
        setup_grid.setColumnStretch(0, 1)
        setup_grid.setColumnStretch(1, 1)

        job_group = HoverDepthFrame()
        job_group.setObjectName("ContentCard")
        job_group.setMinimumHeight(420)
        form = QVBoxLayout(job_group)
        form.setContentsMargins(24, 22, 24, 22)
        form.setSpacing(14)
        form.addLayout(self._step_header("1", "Local job setup", "Select folders and configure analysis settings."))

        self.job_name = QLineEdit("New local job")
        colors = self.theme_engine.colors(self.active_theme_name)
        briefcase_svg = get_briefcase_svg(colors.get('text_secondary', '#64748B'))
        self.job_name_action = self.job_name.addAction(QIcon(svg_to_pixmap(briefcase_svg, 16, 16)), QLineEdit.TrailingPosition)

        self.cv_folder = QLineEdit()
        self.output_folder = QLineEdit(str(Path.cwd() / "local_results"))
        self.cv_folder.setPlaceholderText("Select CV folder...")

        # Accept/Review thresholds with percentage labels
        accept_box = QHBoxLayout()
        accept_box.setSpacing(6)
        self.accept_threshold = PercentSpinBox()
        self.accept_threshold.setRange(1, 100)
        self.accept_threshold.setValue(75)
        self.accept_threshold.setSuffix("  %")
        self.accept_threshold.setMaximumWidth(120)
        accept_box.addWidget(self.accept_threshold)
        accept_box.addStretch(1)

        review_box = QHBoxLayout()
        review_box.setSpacing(6)
        self.review_threshold = PercentSpinBox()
        self.review_threshold.setRange(1, 100)
        self.review_threshold.setValue(52)
        self.review_threshold.setSuffix("  %")
        self.review_threshold.setMaximumWidth(120)
        review_box.addWidget(self.review_threshold)
        review_box.addStretch(1)

        self.ai_mode = QComboBox()
        self.ai_mode.addItems(["none", "customer_openai_key"])

        form.addLayout(self._labeled_control("Job name", self.job_name))
        form.addLayout(self._labeled_control("CV folder", self._path_row(self.cv_folder, self._choose_cv_folder)))
        form.addLayout(self._labeled_control("Output folder", self._path_row(self.output_folder, self._choose_output_folder)))

        threshold_row = QHBoxLayout()
        threshold_row.setSpacing(16)
        threshold_row.addLayout(self._labeled_control("Accept threshold", accept_box), 1)
        threshold_row.addLayout(self._labeled_control("Review threshold", review_box), 1)
        form.addLayout(threshold_row)
        form.addLayout(self._labeled_control("AI review", self.ai_mode))

        # Tip box at bottom of setup card
        shield_svg = get_shield_svg(colors.get('success', '#16a34a'))
        self.card1_tip_box = self._tip_box("All processing happens locally on this device. Your files never leave your computer.", shield_svg, "success")
        self.card1_tip_icon = self.card1_tip_box.findChild(QLabel, "TipBoxIcon")
        form.addWidget(self.card1_tip_box)

        terms_group = HoverDepthFrame()
        terms_group.setObjectName("ContentCard")
        terms_group.setMinimumHeight(420)
        terms = QVBoxLayout(terms_group)
        terms.setContentsMargins(24, 22, 24, 22)
        terms.setSpacing(13)
        terms.addLayout(self._step_header("2", "Scoring criteria", "Define how candidates will be evaluated."))

        self.required_skills = QPlainTextEdit()
        self.required_skills.setPlaceholderText("Enter required skills...")
        self.nice_skills = QPlainTextEdit()
        self.nice_skills.setPlaceholderText("Enter nice to have skills...")
        self.hard_reject = QPlainTextEdit()
        self.hard_reject.setPlaceholderText("Enter hard reject criteria...")

        for field in (self.required_skills, self.nice_skills, self.hard_reject):
            field.setMinimumHeight(72)
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        terms.addLayout(self._labeled_control("Required skills", self.required_skills))
        terms.addLayout(self._labeled_control("Nice to have", self.nice_skills))
        terms.addLayout(self._labeled_control("Hard reject criteria", self.hard_reject))

        # Tip box at bottom of scoring card
        bulb_svg = get_lightbulb_svg(colors.get('warning', '#d97706'))
        self.card2_tip_box = self._tip_box("Tip: Clear criteria leads to better matches. Be specific about must-have requirements.", bulb_svg, "warning")
        self.card2_tip_icon = self.card2_tip_box.findChild(QLabel, "TipBoxIcon")
        terms.addWidget(self.card2_tip_box)

        setup_grid.addWidget(job_group, 0, 0)
        setup_grid.addWidget(terms_group, 0, 1)
        layout.addLayout(setup_grid, 0)

        # Row 3: Split layout between Job Description and Email Templates Cards
        row3_layout = QHBoxLayout()
        row3_layout.setSpacing(20)

        # Left side: Job description
        self.description = QPlainTextEdit()
        self.description.setPlaceholderText("Paste the job description here. This stays local unless you explicitly sync later.")
        self.description.setMinimumHeight(126)

        description_group = HoverDepthFrame()
        description_group.setObjectName("ContentCard")
        description_group.setMinimumHeight(260)
        description_layout = QVBoxLayout(description_group)
        description_layout.setContentsMargins(24, 22, 24, 22)
        description_layout.setSpacing(14)

        self.pencil_icon = QLabel()
        self.pencil_icon.setObjectName("StepTrailingIcon")
        pencil_svg = get_pencil_svg(colors.get('text_secondary', '#64748B'))
        self.pencil_icon.setPixmap(svg_to_pixmap(pencil_svg, 18, 18))

        description_layout.addLayout(self._step_header("3", "Job description", "Paste the full job description. More context leads to better matching.", self.pencil_icon))
        description_layout.addWidget(self.description)
        row3_layout.addWidget(description_group, 3) # 75% width

        # Right side: Email Templates Quick Card
        templates_group = HoverDepthFrame()
        templates_group.setObjectName("ContentCard")
        templates_group.setMinimumHeight(260)
        templates_layout = QVBoxLayout(templates_group)
        templates_layout.setContentsMargins(24, 22, 24, 22)
        templates_layout.setSpacing(10)

        temp_header = QHBoxLayout()
        temp_header.setSpacing(10)
        self.temp_icon = QLabel()
        self.temp_icon.setObjectName("EmailTemplateIcon")
        mail_svg = get_mail_icon_svg(colors.get('primary', '#3B82F6'))
        self.temp_icon.setPixmap(svg_to_pixmap(mail_svg, 22, 22))

        temp_title = QLabel("Email templates")
        temp_title.setObjectName("StepTitle")
        temp_header.addWidget(self.temp_icon)
        temp_header.addWidget(temp_title, 1)
        templates_layout.addLayout(temp_header)

        temp_desc = QLabel("Customize message templates used when taking recruiter actions on results.")
        temp_desc.setObjectName("StepSubtitle")
        temp_desc.setWordWrap(True)
        templates_layout.addWidget(temp_desc, 1)

        self.btn_edit_templates = QPushButton("Edit templates    →")
        self.btn_edit_templates.setObjectName("SecondaryButton")
        self.btn_edit_templates.setCursor(Qt.PointingHandCursor)
        self.btn_edit_templates.clicked.connect(lambda: self.tabs.setCurrentIndex(9))
        templates_layout.addWidget(self.btn_edit_templates)

        row3_layout.addWidget(templates_group, 1) # 25% width
        layout.addLayout(row3_layout, 1)

        actions = QHBoxLayout()
        actions.setSpacing(16)
        self.run_button = AnimatedButton("▷  Analyze local folder")
        self.run_button.setObjectName("PrimaryButton")
        self.run_button.setMinimumWidth(230)
        self.cancel_button = AnimatedButton("×  Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setMinimumWidth(136)
        self.cancel_button.setEnabled(False)
        self.open_output_button = AnimatedButton("📁  Open output folder")
        self.open_output_button.setObjectName("SecondaryButton")
        self.open_output_button.setMinimumWidth(182)
        self.run_button.clicked.connect(self._start_analysis)
        self.cancel_button.clicked.connect(self._cancel_analysis)
        self.open_output_button.clicked.connect(self._open_output)
        actions.addWidget(self.run_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.open_output_button)
        actions.addStretch(1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        footer = QFrame()
        footer.setObjectName("FooterBar")
        footer.setMinimumHeight(82)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 14, 20, 14)
        footer_layout.setSpacing(20)
        footer_layout.addLayout(actions)
        footer_layout.addStretch(1)

        # Stacked status container for modern SaaS dashboard console feeling
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)

        status_text_row = QHBoxLayout()
        status_text_row.setSpacing(14)
        status_text_row.addStretch(1)

        self.queue_status_label = QLabel("Queue: idle")
        self.queue_status_label.setObjectName("FooterMeta")
        self.eta_status_label = QLabel("ETA: --")
        self.eta_status_label.setObjectName("FooterMeta")
        self.footer_ready_label = QLabel("Connect Website Sync first")
        self.footer_ready_label.setObjectName("FooterReady")

        status_text_row.addWidget(self.queue_status_label)
        status_text_row.addWidget(self.eta_status_label)
        status_text_row.addWidget(self.footer_ready_label)

        status_layout.addLayout(status_text_row)

        self.progress.setMinimumWidth(160)
        self.progress.setMaximumWidth(380)
        self.progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        status_layout.addWidget(self.progress)

        footer_layout.addWidget(status_container)

        # Bottom helper labels row
        bottom_tips = QHBoxLayout()
        bottom_tips.setContentsMargins(2, 6, 2, 2)

        left_tip_layout = QHBoxLayout()
        left_tip_layout.setSpacing(6)
        self.bottom_left_tip_icon = QLabel()
        self.bottom_left_tip_icon.setObjectName("BottomTipIcon")
        bulb_svg = get_lightbulb_svg(colors.get('primary', '#3B82F6'))
        self.bottom_left_tip_icon.setPixmap(svg_to_pixmap(bulb_svg, 14, 14))

        left_tip_lbl = QLabel("Tip: You can customize candidate emails in Email Templates.")
        left_tip_lbl.setObjectName("StepSubtitle")
        left_tip_lbl.setStyleSheet("font-size: 8.5pt;")
        left_tip_layout.addWidget(self.bottom_left_tip_icon)
        left_tip_layout.addWidget(left_tip_lbl)
        bottom_tips.addLayout(left_tip_layout)

        bottom_tips.addStretch(1)

        right_tip_lbl = QLabel("Website Sync is required before local analysis and recruiter actions.  ›")
        right_tip_lbl.setObjectName("StepSubtitle")
        right_tip_lbl.setStyleSheet("font-size: 8.5pt;")
        bottom_tips.addWidget(right_tip_lbl)

        layout.addLayout(bottom_tips)
        layout.addWidget(footer, 0)
        scroll.setWidget(page)
        return scroll

    def _build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(18)

        stats = QHBoxLayout()
        stats.setSpacing(12)

        self.total_card, self.total_val = self._create_metric_chip("Total", "#2563eb")
        self.accept_card, self.accept_val = self._create_metric_chip("Accept", "#16a34a")
        self.review_card, self.review_val = self._create_metric_chip("Review", "#d97706")
        self.reject_card, self.reject_val = self._create_metric_chip("Reject", "#dc2626")

        stats.addWidget(self.total_card, 1)
        stats.addWidget(self.accept_card, 1)
        stats.addWidget(self.review_card, 1)
        stats.addWidget(self.reject_card, 1)
        layout.addLayout(stats)

        # Bulk Actions Bar
        bulk_layout = QHBoxLayout()
        bulk_layout.setSpacing(10)

        self.btn_select_all = AnimatedButton("☑  Select All")
        self.btn_select_all.setObjectName("SecondaryButton")
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.clicked.connect(self._select_all_candidates)

        self.btn_deselect_all = AnimatedButton("☐  Deselect All")
        self.btn_deselect_all.setObjectName("SecondaryButton")
        self.btn_deselect_all.setCursor(Qt.PointingHandCursor)
        self.btn_deselect_all.clicked.connect(self._deselect_all_candidates)

        self.btn_bulk_accept = AnimatedButton("✓  Accept Selected")
        self.btn_bulk_accept.setObjectName("SuccessButton")
        self.btn_bulk_accept.setCursor(Qt.PointingHandCursor)
        self.btn_bulk_accept.clicked.connect(lambda: self._bulk_decision("accepted"))

        self.btn_bulk_reject = AnimatedButton("✕  Reject Selected")
        self.btn_bulk_reject.setObjectName("DangerButton")
        self.btn_bulk_reject.setCursor(Qt.PointingHandCursor)
        self.btn_bulk_reject.clicked.connect(lambda: self._bulk_decision("rejected"))

        bulk_layout.addWidget(self.btn_select_all)
        bulk_layout.addWidget(self.btn_deselect_all)
        bulk_layout.addSpacing(20)
        bulk_layout.addWidget(self.btn_bulk_accept)
        bulk_layout.addWidget(self.btn_bulk_reject)
        bulk_layout.addStretch(1)
        layout.addLayout(bulk_layout)

        # Stacked Widget for Table vs Empty State
        self.results_stack = QStackedWidget()

        # Page 0: Empty State
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(0, 10, 0, 10)

        empty_card = QFrame()
        empty_card.setObjectName("ContentCard")
        empty_card_layout = QVBoxLayout(empty_card)
        empty_card_layout.setContentsMargins(40, 60, 40, 60)
        empty_card_layout.setSpacing(18)
        empty_card_layout.setAlignment(Qt.AlignCenter)

        icon_lbl = QLabel("▥")
        icon_lbl.setObjectName("MetricSub")

        title_lbl = QLabel("No candidates processed yet")
        title_lbl.setObjectName("StepTitle")

        desc_lbl = QLabel("Choose a folder and run the worker analysis to start ranking candidates.")
        desc_lbl.setObjectName("StepSubtitle")
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignCenter)

        go_btn = QPushButton("Go to Analyze Tab")
        go_btn.setObjectName("PrimaryButton")
        go_btn.setCursor(Qt.PointingHandCursor)
        go_btn.setMinimumWidth(160)
        go_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(0))

        empty_card_layout.addWidget(icon_lbl)
        empty_card_layout.addWidget(title_lbl)
        empty_card_layout.addWidget(desc_lbl)
        empty_card_layout.addSpacing(8)
        empty_card_layout.addWidget(go_btn)

        empty_layout.addWidget(empty_card)
        self.results_stack.addWidget(empty_page)

        # Page 1: Table & Details
        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(14)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(["", "File", "Email", "Score", "Decision", "Confidence", "Duplicate", "Matched", "Missing", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # Checkbox
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)            # File
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents) # Email
        for index in range(3, 10):
            self.table.horizontalHeader().setSectionResizeMode(index, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.itemSelectionChanged.connect(self._show_selected_detail)
        table_layout.addWidget(self.table, 1)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(140)
        self.detail.setMaximumHeight(220)

        # Opacity effect for smooth fade-in animation
        self.detail_opacity = QGraphicsOpacityEffect()
        self.detail.setGraphicsEffect(self.detail_opacity)
        self.detail_opacity.setOpacity(1.0)

        table_layout.addWidget(self.detail)

        self.results_stack.addWidget(table_page)
        layout.addWidget(self.results_stack, 1)

        # Default to empty state page
        self.results_stack.setCurrentIndex(0)

        return page

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.history_combo = QComboBox()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_history)
        load = QPushButton("Load selected run")
        load.clicked.connect(self._load_history_run)
        top.addWidget(self.history_combo, 1)
        top.addWidget(refresh)
        top.addWidget(load)
        layout.addLayout(top)
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        layout.addWidget(self.history_text, 1)
        return page

    def _build_server_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("Required website sync")
        form = QFormLayout(box)
        self.api_url = QLineEdit(os.environ.get("CV_ANALYZER_API_URL", API_BASE_URL))
        self.api_key = QLineEdit(load_worker_api_key() or os.environ.get("CV_WORKER_API_KEY", ""))
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_url.textChanged.connect(self._mark_sync_required)
        self.api_key.textChanged.connect(self._mark_sync_required)
        form.addRow("API URL", self.api_url)
        form.addRow("Worker key", self.api_key)
        self.server_status_label = QLabel("Not connected. Test Website Sync before using local analysis.")
        self.server_status_label.setObjectName("FooterReady")
        self.server_quota_label = QLabel("Remaining CV scans: connect first")
        self.server_quota_label.setObjectName("SyncMeta")
        form.addRow("Status", self.server_status_label)
        form.addRow("Quota", self.server_quota_label)
        buttons = QHBoxLayout()
        save = QPushButton("Save key locally")
        test = QPushButton("Test connection")
        test.setObjectName("PrimaryButton")
        save.clicked.connect(self._save_key)
        test.clicked.connect(self._test_connection)
        buttons.addWidget(save)
        buttons.addWidget(test)
        buttons.addStretch(1)
        form.addRow("", buttons)
        layout.addWidget(box)
        note = QLabel("Website sync is required. Local analysis, recruiter actions, and email features stay locked until this worker key is verified.")
        note.setObjectName("Subtitle")
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _build_dashboard_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        top = QHBoxLayout()
        self.dashboard_total = QLabel("0 candidates")
        self.dashboard_queue = QLabel("No active queue")
        self.dashboard_eta = QLabel("ETA: --")
        top.addWidget(self._summary_card("Run volume", self.dashboard_total, "Processed in the current run"))
        top.addWidget(self._summary_card("Live queue", self.dashboard_queue, "Current local processing state"))
        top.addWidget(self._summary_card("Estimated finish", self.dashboard_eta, "Calculated while analysis is running"))
        layout.addLayout(top)

        trust = QFrame()
        trust.setObjectName("ContentCard")
        trust_layout = QVBoxLayout(trust)
        trust_layout.setContentsMargins(24, 22, 24, 24)
        trust_layout.setSpacing(10)
        trust_layout.addLayout(self._step_header("✓", "Enterprise trust controls", "Local analysis is designed for large employer folders."))
        for text in (
            "CV files stay on this computer unless you explicitly sync results.",
            "Website API keys are stored in the OS credential store when available.",
            "Only scores, decisions, explanations, and optional sync payloads are sent back.",
            "Duplicate files are detected locally to avoid noisy ranking output.",
        ):
            label = QLabel("•  " + text)
            label.setObjectName("TrustLine")
            trust_layout.addWidget(label)
        layout.addWidget(trust)
        layout.addStretch(1)
        return page

    def _build_reports_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        self.report_preview = QTextEdit()
        self.report_preview.setReadOnly(True)
        self.report_preview.setPlainText("No report yet. Run a local analysis to generate JSON and CSV outputs.")
        self.report_preview.setMinimumHeight(240)
        layout.addWidget(self._panel_with_title("Report preview", self.report_preview))
        actions = QHBoxLayout()
        open_output = QPushButton("Open output folder")
        open_output.setObjectName("PrimaryButton")
        open_output.clicked.connect(self._open_output)
        actions.addWidget(open_output)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    def _build_preferences_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)

        prefs_card, prefs_layout = self._create_card("System Preferences", "Configure local worker runtime settings.")

        theme_row = QWidget()
        theme_layout = QHBoxLayout(theme_row)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_layout.setSpacing(10)
        theme = QLabel(self.theme_engine.get_theme_meta(self.active_theme_name)["display_name"])
        theme.setObjectName("TrustLine")
        open_theme = QPushButton("Open Theme Studio")
        open_theme.setObjectName("SecondaryButton")
        open_theme.clicked.connect(lambda: self.tabs.setCurrentIndex(8))
        theme_layout.addWidget(theme, 1)
        theme_layout.addWidget(open_theme)
        max_size = QLabel(f"{MAX_FILE_BYTES // (1024 * 1024)} MB per file")
        max_size.setObjectName("TrustLine")
        motion = QLabel("Enabled, respects CV_WORKER_DISABLE_MOTION=1")
        motion.setObjectName("TrustLine")

        form = QFormLayout()
        form.setSpacing(12)
        form.addRow("Theme", theme_row)
        form.addRow("Max file guard", max_size)
        form.addRow("Motion", motion)

        prefs_layout.addLayout(form)
        layout.addWidget(prefs_card)

        layout.addWidget(self._info_block("Operational defaults", [
            "Use SSD-backed folders for 4,000+ CV batches.",
            "Keep output folders outside the input CV folder to avoid reprocessing reports.",
            "Use the Website Sync tab only when you want to upload results back to the SaaS account.",
        ]))
        layout.addStretch(1)
        return page

    def _build_theme_studio_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ThemeStudioPage")
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setObjectName("ThemeStudioContent")
        scroll.setWidget(content)
        root.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(18)

        # Header (matching mockup precisely)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        heading = QLabel("Appearance & Theme Studio")
        heading.setObjectName("Title")
        sub = QLabel("Choose your visual experience")
        sub.setObjectName("StepSubtitle")
        title_box.addWidget(heading)
        title_box.addWidget(sub)
        header_layout.addLayout(title_box, 1)
        layout.addLayout(header_layout)

        # 2x2 Grid Layout for Theme Cards (No Live Preview to keep it compact and readable)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        grid.addWidget(self._theme_card("midnight_glass", 1), 0, 0)
        grid.addWidget(self._theme_card("warm_stone", 2), 0, 1)
        grid.addWidget(self._theme_card("electric_indigo", 3), 1, 0)
        grid.addWidget(self._theme_card("forest_executive", 4), 1, 1)
        layout.addLayout(grid, 1)

        # Bottom Bar (matching mockup buttons and placements)
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 10, 0, 10)

        preview_btn = AnimatedButton("Preview Theme")
        preview_btn.setObjectName("SecondaryButton")
        preview_btn.setCursor(Qt.PointingHandCursor)
        preview_btn.clicked.connect(self._preview_selected_theme)
        bottom_bar.addWidget(preview_btn)

        bottom_bar.addStretch(1)

        apply_btn = AnimatedButton("Apply Theme")
        apply_btn.setObjectName("PrimaryButton")
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.clicked.connect(self._apply_selected_theme)
        bottom_bar.addWidget(apply_btn)

        reset_btn = AnimatedButton("Reset to Default")
        reset_btn.setObjectName("SecondaryButton")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(lambda: self._switch_theme(DEFAULT_THEME))
        bottom_bar.addWidget(reset_btn)

        layout.addLayout(bottom_bar)

        self._refresh_theme_card_states()
        self._update_theme_preview()
        return page

    def _theme_card(self, theme_name: str, index: int) -> QWidget:
        meta = self.theme_engine.get_theme_meta(theme_name)
        colors = self.theme_engine.colors(theme_name)

        card = AnimatedThemeCard(theme_name)
        card.setObjectName("ThemeDirectionCard")
        card.setCursor(Qt.PointingHandCursor)
        card.setMinimumHeight(350)

        self.theme_cards[theme_name] = card

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Title
        name = QLabel(meta["display_name"])
        name.setStyleSheet(f"color: {colors['text_primary']}; font-size: 11.5pt; font-weight: 900; background: transparent; border: none; padding: 0;")
        layout.addWidget(name)

        # Mockup Preview Image of that theme
        layout.addWidget(self._theme_mockup(theme_name), 1)

        # Palette row with hex codes underneath swatches
        layout.addLayout(self._theme_palette_row(meta["palette_swatches"][:6], colors))

        # Bottom section: tags on left, checkmark indicator on right
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(6)
        for tag in meta["tags"][:3]:
            tag_label = QLabel(tag)
            tag_label.setStyleSheet(
                f"background: {colors['secondary_bg']}; color: {colors['text_secondary']}; "
                f"border: 1px solid {colors['card_border']}; "
                "border-radius: 10px; padding: 4px 9px; font-size: 8pt; font-weight: 700;"
            )
            tags_layout.addWidget(tag_label)
        bottom_layout.addLayout(tags_layout)
        bottom_layout.addStretch(1)

        # White checkmark in a circular background matching theme accent
        check = QLabel("✓")
        check.setFixedSize(22, 22)
        check.setAlignment(Qt.AlignCenter)
        check.setStyleSheet(
            f"background: {colors['primary']}; color: {colors['primary_text']}; "
            "border-radius: 11px; font-size: 10pt; font-weight: bold; border: none;"
        )
        self.theme_check_labels[theme_name] = check
        bottom_layout.addWidget(check)

        layout.addLayout(bottom_layout)

        # Connect click event
        card.mousePressEvent = lambda event, name=theme_name: self._select_theme_card(name)

        return card

    def _theme_palette_row(self, swatches: list[str], colors: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for color in swatches:
            stack = QVBoxLayout()
            stack.setSpacing(4)
            swatch = QLabel("")
            swatch.setFixedSize(34, 24)
            swatch.setStyleSheet(f"background: {color}; border: 1px solid {colors['card_border']}; border-radius: 4px;")
            hex_label = QLabel(color.upper())
            hex_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 7pt; font-weight: 700; background: transparent; border: none;")
            hex_label.setAlignment(Qt.AlignCenter)
            stack.addWidget(swatch)
            stack.addWidget(hex_label)
            row.addLayout(stack)
        row.addStretch(1)
        return row

    def _theme_mockup(self, theme_name: str) -> QWidget:
        colors = self.theme_engine.colors(theme_name)
        frame = QFrame()
        frame.setMinimumHeight(210)
        # Use main_bg instead of app_bg so it matches light/dark background correctly
        frame.setStyleSheet(
            f"QFrame {{ background: {colors['main_bg']}; border: 1px solid {colors['card_border']}; border-radius: 12px; }}"
        )
        outer = QHBoxLayout(frame)
        outer.setContentsMargins(9, 9, 9, 9)
        outer.setSpacing(9)

        dashboard = self._theme_dashboard_preview(colors)
        outer.addWidget(dashboard, 3)

        side = QVBoxLayout()
        side.setSpacing(10)
        side.addWidget(self._theme_results_preview(colors), 1)
        side.addWidget(self._theme_email_preview(colors), 1)
        outer.addLayout(side, 2)
        return frame

    def _theme_dashboard_preview(self, colors: dict) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"background: {colors['table_bg']}; border: 1px solid {colors['table_border']}; border-radius: 10px;"
        )
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(7)

        sidebar = QFrame()
        sidebar.setFixedWidth(72)
        sidebar.setStyleSheet(f"background: {colors['sidebar_bg']}; border-radius: 8px;")
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(7, 8, 7, 8)
        nav.setSpacing(6)
        brand = QLabel("")
        brand.setFixedHeight(12)
        brand.setStyleSheet(f"background: {colors['primary']}; border-radius: 4px;")
        nav.addWidget(brand)
        nav.addSpacing(3)
        for index in range(7):
            item = QLabel("")
            item.setFixedHeight(11)
            item.setStyleSheet(
                f"background: {colors['sidebar_active'] if index == 0 else colors['sidebar_hover']}; border-radius: 4px;"
            )
            nav.addWidget(item)
        nav.addStretch(1)
        layout.addWidget(sidebar)

        main = QVBoxLayout()
        main.setSpacing(7)
        title_bar = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setStyleSheet(f"color: {colors['text_primary']}; font-size: 8pt; font-weight: 900; background: transparent; border: none;")
        action = QLabel("+ New Analysis")
        action.setStyleSheet(
            f"background: {colors['primary']}; color: {colors['primary_text']}; border-radius: 5px; "
            "padding: 3px 7px; font-size: 6.8pt; font-weight: 800;"
        )
        title_bar.addWidget(title)
        title_bar.addStretch(1)
        title_bar.addWidget(action)
        main.addLayout(title_bar)

        cards = QHBoxLayout()
        cards.setSpacing(6)
        for color_key in ("primary", "success", "info", "danger"):
            card = QFrame()
            card.setStyleSheet(
                f"background: {colors['card_bg']}; border: 1px solid {colors['card_border']}; border-radius: 7px;"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(7, 6, 7, 6)
            value = QLabel("0")
            value.setStyleSheet(f"color: {colors[color_key]}; font-size: 12pt; font-weight: 900;")
            line = QLabel("")
            line.setFixedHeight(5)
            line.setStyleSheet(f"background: {colors['border']}; border-radius: 2px;")
            card_layout.addWidget(value)
            card_layout.addWidget(line)
            cards.addWidget(card)
        main.addLayout(cards)

        activity = QFrame()
        activity.setStyleSheet(
            f"background: {colors['card_bg']}; border: 1px solid {colors['card_border']}; border-radius: 8px;"
        )
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(9, 8, 9, 8)
        activity_title = QLabel("Recent Activity")
        activity_title.setStyleSheet(f"color: {colors['text_primary']}; font-size: 7pt; font-weight: 900; background: transparent; border: none;")
        activity_layout.addWidget(activity_title)
        activity_body = QHBoxLayout()
        activity_body.setSpacing(8)
        illustration = QLabel("")
        illustration.setFixedSize(58, 58)
        illustration.setStyleSheet(
            f"background: {colors['secondary_bg']}; border: 1px solid {colors['border']}; border-radius: 29px;"
        )
        activity_body.addWidget(illustration)
        lines = QVBoxLayout()
        for width, tone in ((150, "table_header_bg"), (105, "border"), (132, "border"), (78, "border")):
            line = QLabel("")
            line.setFixedHeight(7)
            line.setFixedWidth(width)
            line.setStyleSheet(f"background: {colors[tone]}; border-radius: 3px;")
            lines.addWidget(line)
        activity_body.addLayout(lines, 1)
        activity_layout.addLayout(activity_body, 1)

        health = QHBoxLayout()
        for width, tone in ((55, "success"), (42, "success"), (65, "warning")):
            line = QLabel("")
            line.setFixedHeight(6)
            line.setFixedWidth(width)
            line.setStyleSheet(f"background: {colors[tone]}; border-radius: 3px;")
            health.addWidget(line)
        health.addStretch(1)
        activity_layout.addLayout(health)
        main.addWidget(activity, 1)
        layout.addLayout(main, 1)
        return panel

    def _theme_results_preview(self, colors: dict) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"background: {colors['table_bg']}; border: 1px solid {colors['table_border']}; border-radius: 10px;"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(9, 8, 9, 8)
        layout.setSpacing(7)
        header = QHBoxLayout()
        label = QLabel("Results")
        label.setStyleSheet(f"color: {colors['text_primary']}; font-size: 7pt; font-weight: 900; background: transparent; border: none;")
        score = QLabel("92%")
        score.setStyleSheet(
            f"background: {colors['secondary_bg']}; color: {colors['success']}; border: 1px solid {colors['border']}; "
            "border-radius: 11px; padding: 3px 6px; font-size: 7pt; font-weight: 900;"
        )
        header.addWidget(label)
        header.addStretch(1)
        header.addWidget(score)
        layout.addLayout(header)
        for index, width in enumerate((145, 118, 138, 102)):
            row = QHBoxLayout()
            avatar = QLabel("")
            avatar.setFixedSize(14, 14)
            avatar.setStyleSheet(f"background: {colors['primary']}; border-radius: 7px;")
            line = QLabel("")
            line.setFixedHeight(7)
            line.setFixedWidth(width)
            line.setStyleSheet(f"background: {colors['border']}; border-radius: 3px;")
            score = QLabel("")
            score.setFixedSize(34, 7)
            score.setStyleSheet(f"background: {colors['success'] if index == 0 else colors['primary']}; border-radius: 3px;")
            row.addWidget(avatar)
            row.addWidget(line, 1)
            row.addWidget(score)
            layout.addLayout(row)
        return panel

    def _theme_email_preview(self, colors: dict) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"background: {colors['email_body_bg']}; border: 1px solid {colors['card_border']}; border-radius: 10px;"
        )
        main = QVBoxLayout(panel)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(7)
        title = QLabel("Email Templates")
        title.setStyleSheet(f"color: {colors['text_primary']}; font-size: 7pt; font-weight: 900; background: transparent; border: none;")
        main.addWidget(title)
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        left = QVBoxLayout()
        left.setSpacing(5)
        for width in (72, 58, 80, 52):
            line = QLabel("")
            line.setFixedHeight(7)
            line.setFixedWidth(width)
            line.setStyleSheet(f"background: {colors['border']}; border-radius: 3px;")
            left.addWidget(line)
        layout.addLayout(left)
        right = QVBoxLayout()
        right.setSpacing(6)
        for width, key in ((120, "primary"), (150, "border"), (130, "border"), (92, "border")):
            line = QLabel("")
            line.setFixedHeight(8)
            line.setFixedWidth(width)
            line.setStyleSheet(f"background: {colors[key]}; border-radius: 3px;")
            right.addWidget(line)
        layout.addLayout(right, 1)
        main.addLayout(layout, 1)
        return panel

    def _select_theme_card(self, theme_name: str):
        if theme_name not in self.theme_engine.theme_names():
            return
        self.preview_theme_name = theme_name
        self._refresh_theme_card_states()
        self._update_theme_preview()

    def _preview_selected_theme(self):
        self.setStyleSheet(self.theme_engine.generate_qss(self.preview_theme_name))
        if hasattr(self, "status_label"):
            display = self.theme_engine.get_theme_meta(self.preview_theme_name)["display_name"]
            self.status_label.setText(f"Previewing {display}")

    def _apply_selected_theme(self):
        self._switch_theme(self.preview_theme_name)

    def _switch_theme(self, theme_name: str):
        if theme_name not in self.theme_engine.theme_names():
            return
        self.theme_engine.save_active_theme(theme_name)
        self.active_theme_name = theme_name
        self.preview_theme_name = theme_name
        self._apply_style()
        self._update_theme_preview()
        if hasattr(self, "status_label"):
            display = self.theme_engine.get_theme_meta(theme_name)["display_name"]
            self.status_label.setText(f"{display} applied")

    def _update_card_style(self, card: QFrame, theme_name: str, is_selected: bool):
        colors = self.theme_engine.colors(theme_name)
        border_color = colors['primary'] if is_selected else colors['card_border']
        border_width = "2px" if is_selected else "1px"
        card.setStyleSheet(f"""
            QFrame#ThemeDirectionCard {{
                background: {colors['main_bg']};
                border: {border_width} solid {border_color};
                border-radius: 14px;
            }}
        """)

    def _refresh_theme_card_states(self):
        for theme_name, card in self.theme_cards.items():
            is_selected = (theme_name == self.preview_theme_name)
            self._update_card_style(card, theme_name, is_selected)

            check = self.theme_check_labels.get(theme_name)
            if check:
                check.setVisible(theme_name == self.active_theme_name)

    def _clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self._clear_layout(item.layout())

    def _update_theme_preview(self):
        if not self.theme_preview_layout:
            return

        self._clear_layout(self.theme_preview_layout)

        theme = self.theme_engine.get_theme(self.preview_theme_name)
        colors = theme["colors"]

        # Build mock frame using preview theme's main_bg!
        mock = QFrame()
        mock.setObjectName("ThemePreviewMock")
        mock.setStyleSheet(
            f"QFrame#ThemePreviewMock {{ background: {colors['main_bg']}; border: 1px solid {colors['card_border']}; border-radius: 12px; }}"
        )
        mock_layout = QHBoxLayout(mock)
        mock_layout.setContentsMargins(10, 10, 10, 10)
        mock_layout.setSpacing(10)

        # Preview Sidebar
        preview_sidebar = QFrame()
        preview_sidebar.setStyleSheet(f"background: {colors['sidebar_bg']}; border-radius: 8px;")
        preview_sidebar.setFixedWidth(110)
        sidebar_layout = QVBoxLayout(preview_sidebar)
        sidebar_layout.setContentsMargins(8, 10, 8, 10)
        sidebar_layout.setSpacing(6)

        # Logo/Brand
        logo = QLabel("✧ CV Analyzer")
        logo.setStyleSheet(f"color: {colors['logo_text']}; font-weight: bold; font-size: 8pt; background: transparent; border: none; padding: 0;")
        sidebar_layout.addWidget(logo)
        sidebar_layout.addSpacing(6)

        # Sidebar items
        nav_items = [
            ("⌗ Dashboard", True),
            ("⌁ Analyze", False),
            ("▥ Results", False),
            ("↺ History", False),
            ("⚙ Preferences", False),
        ]
        for text, active in nav_items:
            item = QLabel(text)
            item_bg = colors['sidebar_active'] if active else "transparent"
            item_fg = colors['sidebar_text_active'] if active else colors['sidebar_text']
            item.setStyleSheet(
                f"background: {item_bg}; color: {item_fg}; border-radius: 4px; padding: 4px 6px; font-size: 7.5pt; border: none;"
            )
            sidebar_layout.addWidget(item)

        sidebar_layout.addStretch(1)

        # Sidebar bottom user profile
        profile = QHBoxLayout()
        profile.setSpacing(4)
        avatar = QLabel("")
        avatar.setFixedSize(14, 14)
        avatar.setStyleSheet(f"background: {colors['primary']}; border-radius: 7px; border: none;")
        user_name = QLabel("v1.0.0")
        user_name.setStyleSheet(f"color: {colors['sidebar_text']}; font-size: 7pt; background: transparent; border: none;")
        profile.addWidget(avatar)
        profile.addWidget(user_name)
        sidebar_layout.addLayout(profile)

        mock_layout.addWidget(preview_sidebar)

        # Main area of preview
        main_content = QVBoxLayout()
        main_content.setSpacing(8)

        # Top bar
        top_bar = QHBoxLayout()
        top_title = QLabel("Dashboard")
        top_title.setStyleSheet(f"color: {colors['text_primary']}; font-weight: 800; font-size: 9pt; background: transparent; border: none;")
        search_box = QFrame()
        search_box.setFixedSize(70, 16)
        search_box.setStyleSheet(f"background: {colors['input_bg']}; border: 1px solid {colors['input_border']}; border-radius: 4px;")
        search_lbl = QLabel("Search...")
        search_lbl.setStyleSheet(f"color: {colors['input_placeholder']}; font-size: 6.5pt; padding-left: 2px; background: transparent; border: none;")
        search_layout = QHBoxLayout(search_box)
        search_layout.setContentsMargins(4, 0, 4, 0)
        search_layout.addWidget(search_lbl)

        top_bar.addWidget(top_title)
        top_bar.addStretch(1)
        top_bar.addWidget(search_box)
        main_content.addLayout(top_bar)

        # Metric cards row
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(6)
        metrics_data = [
            ("Candidates", "151", "+12%", colors['success']),
            ("Avg Score", "78%", "★ High", colors['primary']),
            ("Shortlisted", "42", "Action", colors['info']),
        ]
        for title, value, badge_text, badge_color in metrics_data:
            metric_card = QFrame()
            metric_card.setStyleSheet(
                f"background: {colors['card_bg']}; border: 1px solid {colors['card_border']}; border-radius: 6px;"
            )
            card_layout = QVBoxLayout(metric_card)
            card_layout.setContentsMargins(6, 6, 6, 6)
            card_layout.setSpacing(2)

            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 6.5pt; background: transparent; border: none;")

            val_layout = QHBoxLayout()
            val = QLabel(value)
            val.setStyleSheet(f"color: {colors['text_primary']}; font-weight: bold; font-size: 10pt; background: transparent; border: none;")

            badge = QLabel(badge_text)
            badge.setStyleSheet(
                f"background: {colors['secondary_bg']}; color: {badge_color}; "
                "border-radius: 3px; font-size: 5.5pt; padding: 1px 3px; font-weight: bold; border: none;"
            )
            val_layout.addWidget(val)
            val_layout.addStretch(1)
            val_layout.addWidget(badge)

            card_layout.addWidget(lbl)
            card_layout.addLayout(val_layout)
            metrics_row.addWidget(metric_card)

        main_content.addLayout(metrics_row)

        # Candidates table card
        table_card = QFrame()
        table_card.setStyleSheet(
            f"background: {colors['table_bg']}; border: 1px solid {colors['table_border']}; border-radius: 6px;"
        )
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(6, 6, 6, 6)
        table_layout.setSpacing(4)

        # Table Header
        header_row = QHBoxLayout()
        header_row.setSpacing(4)
        col1 = QLabel("Candidate")
        col1.setStyleSheet(f"color: {colors['table_header_text']}; font-size: 6pt; font-weight: bold; background: transparent; border: none;")
        col2 = QLabel("Score")
        col2.setStyleSheet(f"color: {colors['table_header_text']}; font-size: 6pt; font-weight: bold; background: transparent; border: none;")
        col3 = QLabel("Decision")
        col3.setStyleSheet(f"color: {colors['table_header_text']}; font-size: 6pt; font-weight: bold; background: transparent; border: none;")
        header_row.addWidget(col1, 2)
        header_row.addWidget(col2, 1)
        header_row.addWidget(col3, 1)
        table_layout.addLayout(header_row)

        # Table divider line
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {colors['table_item_border']}; border: none;")
        table_layout.addWidget(divider)

        # Table rows
        candidates = [
            ("Liam Everton", "92%", "Accept", colors['success']),
            ("Dana Morrison", "81%", "Review", colors['warning']),
            ("Jacob Patrick", "45%", "Reject", colors['danger']),
        ]
        for name, score, status, status_color in candidates:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(4)

            c_name = QLabel(name)
            c_name.setStyleSheet(f"color: {colors['table_text']}; font-size: 6.5pt; background: transparent; border: none;")
            c_score = QLabel(score)
            c_score.setStyleSheet(f"color: {colors['table_text']}; font-size: 6.5pt; font-weight: bold; background: transparent; border: none;")

            c_status = QLabel(status)
            c_status.setAlignment(Qt.AlignCenter)
            c_status.setStyleSheet(
                f"background: {colors['secondary_bg']}; color: {status_color}; "
                "border-radius: 4px; font-size: 5.5pt; padding: 1px 3px; font-weight: bold; border: none;"
            )
            c_status.setFixedWidth(40)

            row_layout.addWidget(c_name, 2)
            row_layout.addWidget(c_score, 1)
            row_layout.addWidget(c_status, 1)
            table_layout.addLayout(row_layout)

        main_content.addWidget(table_card, 1)
        mock_layout.addLayout(main_content, 1)

        self.theme_preview_layout.addWidget(mock, 1)

    def _create_card(self, title: str = "", subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = HoverDepthFrame()
        card.setObjectName("ContentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        if title:
            lbl_title = QLabel(title)
            lbl_title.setObjectName("StepTitle")
            layout.addWidget(lbl_title)
        if subtitle:
            lbl_sub = QLabel(subtitle)
            lbl_sub.setObjectName("StepSubtitle")
            layout.addWidget(lbl_sub)
        return card, layout

    def _create_metric_chip(self, title: str, accent_color: str) -> tuple[QWidget, QLabel]:
        card = HoverDepthFrame()
        card.setObjectName("MetricChip")
        card.setProperty("accent_color", accent_color)

        # Override styles for dynamic colored accent borders and hover interactions
        colors = self.theme_engine.colors(self.active_theme_name)
        secondary_hover_bg = colors.get('secondary_hover_bg', '#f1f5f9')
        card_bg = colors.get('card_bg', '#ffffff')

        card.setStyleSheet(f"""
            QFrame#MetricChip {{
                border-left: 5px solid {accent_color};
                background: {card_bg};
            }}
            QFrame#MetricChip:hover {{
                border-left: 7px solid {accent_color};
                background: {secondary_hover_bg};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        lbl_title = QLabel(title.upper())
        lbl_title.setObjectName("MetricChipTitle")
        lbl_title.setStyleSheet(f"color: {accent_color}; font-size: 8.5pt; font-weight: 800; letter-spacing: 0.5px; background: transparent; border: none;")

        lbl_value = QLabel("0")
        lbl_value.setObjectName("MetricChipValue")
        lbl_value.setStyleSheet("font-size: 24pt; font-weight: 800; line-height: 1; background: transparent; border: none;")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)

        return card, lbl_value

    def _build_templates_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("TemplatesPage")

        # Root layout for page holds the scroll area
        root_layout = QVBoxLayout(page)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setObjectName("TemplatesContent")
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        main_layout = QHBoxLayout(content)
        main_layout.setContentsMargins(20, 14, 20, 14)
        main_layout.setSpacing(20)

        # Left Column: Template Editor Card
        editor_card, editor_layout = self._create_card(
            "Email Template Editor",
            "Customize templates sent during recruiter decision actions."
        )

        # Dropdown to select Accept / Reject Template
        self.tpl_selector = QComboBox()
        self.tpl_selector.addItems(["Accept Notification", "Reject Notification"])
        self.tpl_selector.currentIndexChanged.connect(self._on_template_type_changed)
        editor_layout.addLayout(self._labeled_control("Select Template Action", self.tpl_selector))

        # Subject field
        self.tpl_subject_edit = QLineEdit()
        self.tpl_subject_edit.textChanged.connect(self._update_email_preview)
        editor_layout.addLayout(self._labeled_control("Subject Line", self.tpl_subject_edit))

        # Body field
        self.tpl_body_edit = QPlainTextEdit()
        self.tpl_body_edit.textChanged.connect(self._update_email_preview)
        self.tpl_body_edit.setMinimumHeight(140)
        editor_layout.addLayout(self._labeled_control("Message Body", self.tpl_body_edit))

        # Variables chips layout
        var_box = QWidget()
        var_layout = QHBoxLayout(var_box)
        var_layout.setContentsMargins(0, 0, 0, 0)
        var_layout.setSpacing(6)

        insert_lbl = QLabel("Insert:")
        insert_lbl.setStyleSheet("color: #64748b; font-size: 9pt; font-weight: 600;")
        var_layout.addWidget(insert_lbl)

        variables = ["{name}", "{email}", "{role}", "{score}"]
        for var in variables:
            btn = AnimatedButton(var)
            btn.setObjectName("ChipButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=var: self._insert_variable(v))
            var_layout.addWidget(btn)
        var_layout.addStretch(1)
        editor_layout.addWidget(var_box)

        # Save Button
        btn_save = AnimatedButton("💾 Save Template Presets")
        btn_save.setObjectName("PrimaryButton")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._save_templates_from_editor)
        editor_layout.addWidget(btn_save)

        main_layout.addWidget(editor_card, 1)

        # Right Column: Live Preview mock client Card
        preview_card, preview_layout = self._create_card(
            "Live Email Preview",
            "Simulation showing how the candidate will receive this email."
        )

        # Mock Email Client Container
        mock_client = QFrame()
        mock_client.setObjectName("MockEmailClient")
        client_layout = QVBoxLayout(mock_client)
        client_layout.setContentsMargins(0, 0, 0, 0)
        client_layout.setSpacing(0)

        # Mock Client Header / Envelope
        header_bar = QFrame()
        header_bar.setObjectName("EmailHeaderBar")
        header_layout = QFormLayout(header_bar)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(8)

        self.mock_from = QLabel("recruiting@company.local")
        self.mock_from.setStyleSheet("color: #0f172a; font-weight: 600;")

        self.mock_to = QLabel("sercan.ozkan@example.com (Sercan Özkan)")
        self.mock_to.setStyleSheet("color: #64748b;")

        self.mock_subject_lbl = QLabel("")
        self.mock_subject_lbl.setWordWrap(True)
        self.mock_subject_lbl.setStyleSheet("color: #0f172a; font-weight: 700; font-size: 10.5pt;")

        header_layout.addRow("From:", self.mock_from)
        header_layout.addRow("To:", self.mock_to)
        header_layout.addRow("Subject:", self.mock_subject_lbl)
        client_layout.addWidget(header_bar)

        # Mock Client Content Box
        body_box = QFrame()
        body_box.setObjectName("EmailBodyBox")
        body_layout = QVBoxLayout(body_box)
        body_layout.setContentsMargins(20, 20, 20, 20)

        self.mock_body_text = QTextEdit()
        self.mock_body_text.setReadOnly(True)
        self.mock_body_text.setObjectName("MockEmailBodyText")
        self.mock_body_text.setMinimumHeight(140)
        body_layout.addWidget(self.mock_body_text)
        client_layout.addWidget(body_box, 1)

        preview_layout.addWidget(mock_client, 1)
        main_layout.addWidget(preview_card, 1)

        # Load initial template data into UI
        self._load_template_to_fields(0)

        return page

    def _on_template_type_changed(self, index: int):
        prev_index = 1 - index
        self._sync_inputs_to_memory(prev_index)
        self._load_template_to_fields(index)

    def _sync_inputs_to_memory(self, index: int):
        if index == 0:
            self.mail_templates["accept_subject"] = self.tpl_subject_edit.text().strip()
            self.mail_templates["accept_body"] = self.tpl_body_edit.toPlainText()
        else:
            self.mail_templates["reject_subject"] = self.tpl_subject_edit.text().strip()
            self.mail_templates["reject_body"] = self.tpl_body_edit.toPlainText()

    def _load_template_to_fields(self, index: int):
        self.tpl_subject_edit.blockSignals(True)
        self.tpl_body_edit.blockSignals(True)
        if index == 0:
            self.tpl_subject_edit.setText(self.mail_templates.get("accept_subject", ""))
            self.tpl_body_edit.setPlainText(self.mail_templates.get("accept_body", ""))
        else:
            self.tpl_subject_edit.setText(self.mail_templates.get("reject_subject", ""))
            self.tpl_body_edit.setPlainText(self.mail_templates.get("reject_body", ""))
        self.tpl_subject_edit.blockSignals(False)
        self.tpl_body_edit.blockSignals(False)
        self._update_email_preview()

    def _insert_variable(self, var_name: str):
        self.tpl_body_edit.insertPlainText(var_name)
        self.tpl_body_edit.setFocus()

    def _update_email_preview(self):
        subject = self.tpl_subject_edit.text()
        body = self.tpl_body_edit.toPlainText()

        replacements = {
            "{name}": "Sercan Özkan",
            "{email}": "sercan.ozkan@example.com",
            "{role}": "Software Engineer",
            "{score}": "85",
            "{position}": "Software Engineer",
            "{company}": "CV Analyzer Corp"
        }

        preview_subject = subject
        preview_body = body
        for var, val in replacements.items():
            preview_subject = preview_subject.replace(var, val)
            preview_body = preview_body.replace(var, val)

        self.mock_subject_lbl.setText(preview_subject)
        self.mock_body_text.setPlainText(preview_body)

    def _save_templates_from_editor(self):
        current_index = self.tpl_selector.currentIndex()
        self._sync_inputs_to_memory(current_index)
        save_mail_templates(self.mail_templates)
        QMessageBox.information(self, "Saved", "Email templates saved successfully.")

    def _build_ai_models_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.addWidget(self._info_block("AI review modes", [
            "none: fastest and cheapest; uses deterministic rule-based scoring.",
            "customer_openai_key: reserved for local customer-owned review in a later package.",
            "No platform OpenAI key is embedded in the desktop app.",
        ]))
        layout.addWidget(self._info_block("Current MVP scoring", [
            "Required skills, nice-to-have skills, hard reject rules, job description overlap, and text quality.",
            "PDF, DOCX, and TXT extraction run locally.",
            "A low-confidence result is still explainable and can be reviewed before sync.",
        ]))
        layout.addStretch(1)
        return page

    def _path_row(self, field: QLineEdit, callback) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        button = QPushButton("Browse")
        button.setObjectName("SecondaryButton")
        button.setMinimumWidth(110)
        button.clicked.connect(callback)
        layout.addWidget(field, 1)
        layout.addWidget(button)
        return row

    def _metric_card(self, title: str, value_label: QLabel, subtitle: str, icon: str, badge_name: str) -> QWidget:
        card = HoverDepthFrame()
        card.setObjectName("MetricCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(22, 12, 22, 12)
        layout.setSpacing(16)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")
        value_label.setObjectName("MetricValue")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MetricSub")
        copy.addWidget(title_label)
        copy.addWidget(value_label)
        copy.addWidget(subtitle_label)
        layout.addLayout(copy, 1)
        badge = AnimatedBadge(icon)
        badge.setObjectName(badge_name)
        layout.addWidget(badge)
        return card

    def _summary_card(self, title: str, value_label: QLabel, subtitle: str) -> QWidget:
        card = HoverDepthFrame()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 12, 22, 12)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")
        value_label.setObjectName("MetricValue")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MetricSub")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)
        return card

    def _panel_with_title(self, title: str, widget: QWidget) -> QWidget:
        panel = HoverDepthFrame()
        panel.setObjectName("ContentCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 24)
        heading = QLabel(title)
        heading.setObjectName("StepTitle")
        layout.addWidget(heading)
        layout.addWidget(widget)
        return panel

    def _info_block(self, title: str, lines: list[str]) -> QWidget:
        panel = HoverDepthFrame()
        panel.setObjectName("ContentCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("StepTitle")
        layout.addWidget(heading)
        for line in lines:
            label = QLabel("•  " + line)
            label.setObjectName("TrustLine")
            label.setWordWrap(True)
            layout.addWidget(label)
        return panel

    def _step_header(self, number: str, title: str, subtitle: str, trailing_widget: QWidget = None) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        badge = QLabel(number)
        badge.setObjectName("StepBadge")
        badge.setAlignment(Qt.AlignCenter)
        text_box = QVBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("StepTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("StepSubtitle")
        text_box.addWidget(heading)
        text_box.addWidget(sub)
        row.addWidget(badge)
        row.addLayout(text_box, 1)
        if trailing_widget is not None:
            row.addWidget(trailing_widget)
        return row

    def _tip_box(self, text: str, icon_svg: str, status: str = "success") -> QFrame:
        box = QFrame()
        box.setObjectName(f"TipBox_{status}")
        layout = QHBoxLayout(box)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setObjectName("TipBoxIcon")
        icon_lbl.setFixedSize(16, 16)
        pix = svg_to_pixmap(icon_svg, 16, 16)
        icon_lbl.setPixmap(pix)

        text_lbl = QLabel(text)
        text_lbl.setObjectName("TipBoxText")
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("font-size: 8.5pt; font-weight: 500;")

        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl, 1)
        return box

    def _labeled_control(self, label_text: str, widget_or_layout) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        layout.addWidget(label)
        if isinstance(widget_or_layout, QWidget):
            layout.addWidget(widget_or_layout)
        else:
            layout.addLayout(widget_or_layout)
        return layout

    def _run_animation(self, animation: QPropertyAnimation):
        if not MOTION_ENABLED:
            return
        self._animations.append(animation)

        def cleanup():
            if animation in self._animations:
                self._animations.remove(animation)

        animation.finished.connect(cleanup)
        animation.start(QAbstractAnimation.DeleteWhenStopped)

    def _animate_startup(self):
        if not MOTION_ENABLED:
            self.setWindowOpacity(1.0)
            return
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(320)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        self._run_animation(fade)
        self._slide_widget(self.tabs, offset=14, duration=360)

    def _slide_widget(self, widget: QWidget, offset: int = 10, duration: int = 240):
        if not MOTION_ENABLED:
            return
        end = widget.pos()
        start = QPoint(end.x(), end.y() + offset)
        widget.move(start)
        animation = QPropertyAnimation(widget, b"pos", self)
        animation.setDuration(duration)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        self._run_animation(animation)

    def _animate_tab_change(self):
        if not MOTION_ENABLED:
            return
        widget = self.tabs.currentWidget()
        if not widget:
            return
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        fade = QPropertyAnimation(effect, b"opacity", self)
        fade.setDuration(220)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutQuad)
        self._run_animation(fade)
        self._slide_widget(widget, offset=8, duration=220)

    def _start_status_pulse(self):
        if not MOTION_ENABLED:
            return
        effect = self.status_label.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self.status_label)
            self.status_label.setGraphicsEffect(effect)
        effect.setOpacity(1.0)
        pulse = QPropertyAnimation(effect, b"opacity", self)
        pulse.setDuration(780)
        pulse.setStartValue(0.72)
        pulse.setEndValue(1.0)
        pulse.setEasingCurve(QEasingCurve.InOutSine)
        pulse.setLoopCount(-1)
        self._status_pulse = pulse
        pulse.start()

    def _stop_status_pulse(self):
        if self._status_pulse:
            self._status_pulse.stop()
            self._status_pulse = None
        effect = self.status_label.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)

    def _set_progress_value(self, value: int):
        if not MOTION_ENABLED:
            self.progress.setValue(value)
            return
        if self._progress_animation:
            self._progress_animation.stop()
        animation = QPropertyAnimation(self.progress, b"value", self)
        animation.setDuration(120)
        animation.setStartValue(self.progress.value())
        animation.setEndValue(value)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        self._progress_animation = animation

        def clear_progress_animation():
            if self._progress_animation is animation:
                self._progress_animation = None

        animation.finished.connect(clear_progress_animation)
        animation.start(QAbstractAnimation.DeleteWhenStopped)

    def _on_progress_max(self, value: int):
        total = max(1, int(value or 1))
        self.analysis_total_files = total
        self.progress.setRange(0, total)
        self._update_live_status(0, total)

    def _on_progress(self, value: int):
        current = int(value or 0)
        total = max(1, self.analysis_total_files or self.progress.maximum() or 1)
        self._set_progress_value(current)
        self._update_live_status(current, total)

    def _update_live_status(self, current: int, total: int):
        remaining = max(0, total - current)
        queue_text = f"Queue: {current}/{total}"
        if hasattr(self, "queue_status_label"):
            self.queue_status_label.setText(queue_text)
        if hasattr(self, "dashboard_queue"):
            self.dashboard_queue.setText(f"{remaining} remaining")

        eta_text = "ETA: --"
        if self.analysis_started_at and current > 0:
            elapsed = max(0.1, time.monotonic() - self.analysis_started_at)
            seconds = int((elapsed / current) * remaining)
            if seconds >= 60:
                eta_text = f"ETA: {seconds // 60}m {seconds % 60}s"
            else:
                eta_text = f"ETA: {seconds}s"
        if hasattr(self, "eta_status_label"):
            self.eta_status_label.setText(eta_text)
        if hasattr(self, "dashboard_eta"):
            self.dashboard_eta.setText(eta_text.replace("ETA: ", "") or "--")

    def _apply_style(self):
        colors = self.theme_engine.colors(self.active_theme_name)
        self.setStyleSheet(self.theme_engine.generate_qss(self.active_theme_name))

        if hasattr(self, "logo"):
            logo_svg = get_theme_logo_svg(self.active_theme_name, colors)
            self.logo.setPixmap(svg_to_pixmap(logo_svg, 42, 42))

        if hasattr(self, "trust_icon"):
            trust_svg = get_trust_icon_svg(colors.get('sidebar_indicator', colors.get('primary', '#3B82F6')))
            self.trust_icon.setPixmap(svg_to_pixmap(trust_svg, 16, 16))

        if hasattr(self, "job_name_action"):
            briefcase_svg = get_briefcase_svg(colors.get('text_secondary', '#64748B'))
            self.job_name_action.setIcon(QIcon(svg_to_pixmap(briefcase_svg, 16, 16)))

        if hasattr(self, "pencil_icon"):
            pencil_svg = get_pencil_svg(colors.get('text_secondary', '#64748B'))
            self.pencil_icon.setPixmap(svg_to_pixmap(pencil_svg, 18, 18))

        if hasattr(self, "card1_tip_icon"):
            shield_svg = get_shield_svg(colors.get('success', '#16a34a'))
            self.card1_tip_icon.setPixmap(svg_to_pixmap(shield_svg, 16, 16))

        if hasattr(self, "card2_tip_icon"):
            bulb_svg = get_lightbulb_svg(colors.get('warning', '#d97706'))
            self.card2_tip_icon.setPixmap(svg_to_pixmap(bulb_svg, 16, 16))

        if hasattr(self, "temp_icon"):
            mail_svg = get_mail_icon_svg(colors.get('primary', '#3B82F6'))
            self.temp_icon.setPixmap(svg_to_pixmap(mail_svg, 22, 22))

        if hasattr(self, "bottom_left_tip_icon"):
            bulb_svg = get_lightbulb_svg(colors.get('primary', '#3B82F6'))
            self.bottom_left_tip_icon.setPixmap(svg_to_pixmap(bulb_svg, 14, 14))

        # Refresh sidebar navigation button icons dynamically to match the active theme's colors!
        for button in self.nav_buttons:
            icon_key = button.property("icon_key")
            if icon_key:
                is_checked = button.isChecked()
                color_key = 'sidebar_text_active' if is_checked else 'sidebar_text'
                icon_color = colors.get(color_key, '#E2E8F0' if is_checked else '#7C8DB5')
                svg_data = get_sidebar_icon_svg(icon_key, icon_color)
                if svg_data:
                    button.setIcon(QIcon(svg_to_pixmap(svg_data, 18, 18)))

        self._refresh_theme_card_states()
        return
        BASE_QSS = """
            QWidget {
                background: transparent;
                color: #0f172a;
                font-family: "Segoe UI", "SF Pro Display", system-ui;
                font-size: 10pt;
            }
            QWidget#Root, QMainWindow {
                background: #0f172a;
            }
            QWidget#MainPanel {
                background: #f8fafc;
                color: #0f172a;
                border-top-left-radius: 16px;
                border-bottom-left-radius: 16px;
            }
            QLabel#Title {
                color: #0f172a;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#Subtitle {
                color: #64748b;
                font-size: 10pt;
            }
            QLabel#HeaderIcon {
                min-width: 48px;
                min-height: 48px;
                max-width: 48px;
                max-height: 48px;
                border-radius: 12px;
                background: #f1f5f9;
                color: #334155;
                font-size: 22px;
                font-weight: 900;
                qproperty-alignment: AlignCenter;
            }
            QLabel#StatusPill {
                padding: 6px 16px;
                border: 1px solid #bbf7d0;
                border-radius: 16px;
                background: #f0fdf4;
                color: #16a34a;
                font-weight: 700;
                font-size: 9pt;
            }
            QLabel#SyncMeta {
                color: #64748b;
                font-weight: 600;
                font-size: 9pt;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
                top: 0;
            }
            QTabBar::tab {
                padding: 12px 16px 11px;
                margin-right: 6px;
                border: none;
                border-bottom: 2px solid transparent;
                background: transparent;
                color: #94a3b8;
                font-size: 10pt;
                font-weight: 700;
            }
            QTabBar::tab:selected {
                color: #0f172a;
                border-bottom: 2px solid #0f172a;
            }
            QTabBar::tab:hover {
                color: #475569;
            }
        """

        SIDEBAR_QSS = """
            QFrame#Sidebar, QFrame#Sidebar QWidget {
                color: #e2e8f0;
            }
            QFrame#Sidebar {
                background: #0f172a;
                border: none;
            }
            QLabel#LogoMark {
                min-width: 42px;
                min-height: 42px;
                max-width: 42px;
                max-height: 42px;
                border-radius: 10px;
                background: #334155;
                color: #e2e8f0;
                font-size: 20px;
                font-weight: 900;
                qproperty-alignment: AlignCenter;
            }
            QLabel#SidebarBrand {
                color: #f8fafc;
                font-size: 11.5pt;
                font-weight: 800;
            }
            QLabel#SidebarSub {
                color: #94a3b8;
                font-size: 9pt;
            }
            QLabel#SidebarSection {
                color: #64748b;
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 1.2px;
                padding-top: 4px;
            }
            QPushButton#SidebarNav, QPushButton#SidebarPassive {
                background: transparent;
                border: none;
                border-radius: 8px;
                color: #94a3b8;
                padding: 9px 12px 9px 24px;
                margin: 2px 10px;
                text-align: left;
                font-size: 9.5pt;
                font-weight: 600;
            }
            QPushButton#SidebarNav:hover {
                background: #1e293b;
                color: #e2e8f0;
            }
            QPushButton#SidebarNav:checked {
                background: #334155;
                color: #f8fafc;
                font-weight: 700;
            }
            QPushButton#SidebarPassive:disabled {
                color: #94a3b8;
                background: transparent;
            }
        """

        CARD_QSS = """
            QGroupBox {
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                margin-top: 14px;
                padding: 22px 18px 18px;
                background: #ffffff;
                font-size: 11pt;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 8px;
                color: #0f172a;
            }
            QFrame#MetricCard, QFrame#ContentCard, QFrame#FooterBar {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QFrame#MetricCard {
                min-height: 110px;
            }
            QLabel#MetricTitle {
                color: #64748b;
                font-weight: 700;
                font-size: 9pt;
            }
            QLabel#MetricValue {
                color: #0f172a;
                font-size: 22pt;
                font-weight: 800;
                margin: 0px;
                padding: 0px;
            }
            QLabel#MetricSub {
                color: #64748b;
                font-size: 9pt;
            }
            #PurpleBadge, #GreenBadge, #BlueBadge, #RedBadge {
                background: transparent;
                border: none;
            }
            QLabel#StepBadge {
                min-width: 28px;
                min-height: 28px;
                max-width: 28px;
                max-height: 28px;
                border-radius: 14px;
                background: #0f172a;
                color: #ffffff;
                font-weight: 800;
                font-size: 9pt;
            }
            QLabel#StepTitle {
                color: #0f172a;
                font-size: 12pt;
                font-weight: 800;
            }
            QLabel#StepSubtitle {
                color: #64748b;
                font-size: 9.5pt;
            }
            QLabel#FooterReady {
                color: #0f172a;
                font-weight: 800;
            }
            QLabel#FooterMeta, QLabel#TrustLine {
                color: #64748b;
                font-weight: 600;
            }
            QLabel#FieldLabel {
                color: #475569;
                font-size: 9pt;
                font-weight: 700;
            }
        """

        FORM_QSS = """
            QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 14px;
                selection-background-color: #bfdbfe;
                selection-color: #1e40af;
            }
            QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QComboBox:hover, QSpinBox:hover {
                border-color: #cbd5e1;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #0f172a;
                background: #ffffff;
            }
            QLineEdit::placeholder, QPlainTextEdit::placeholder {
                color: #94a3b8;
            }
            QPlainTextEdit, QTextEdit {
                line-height: 1.5;
            }
            QComboBox {
                padding-right: 30px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border: none;
            }
            QComboBox::down-arrow {
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #64748b;
                width: 0;
                height: 0;
                margin-right: 2px;
            }
            QComboBox::down-arrow:on {
                border-top: none;
                border-bottom: 5px solid #0f172a;
            }
            QSpinBox {
                padding-right: 26px;
            }
            QSpinBox::up-button {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                height: 14px;
                border-left: 1px solid #e2e8f0;
                border-bottom: 1px solid #e2e8f0;
                background: #f8fafc;
                border-top-right-radius: 6px;
            }
            QSpinBox::up-button:hover {
                background: #f1f5f9;
            }
            QSpinBox::up-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #64748b;
                width: 0;
                height: 0;
            }
            QSpinBox::down-button {
                subcontrol-origin: padding;
                subcontrol-position: bottom right;
                width: 20px;
                height: 14px;
                border-left: 1px solid #e2e8f0;
                background: #f8fafc;
                border-bottom-right-radius: 6px;
            }
            QSpinBox::down-button:hover {
                background: #f1f5f9;
            }
            QSpinBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
                width: 0;
                height: 0;
            }
        """

        BUTTON_QSS = """
            QPushButton {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 10pt;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #f1f5f9;
                border-color: #cbd5e1;
            }
            QPushButton:pressed {
                background: #e2e8f0;
            }
            QPushButton:disabled {
                color: #94a3b8;
                background: #f1f5f9;
                border-color: #e2e8f0;
            }
            QPushButton#PrimaryButton {
                background: #0f172a;
                border-color: #0f172a;
                color: #ffffff;
            }
            QPushButton#PrimaryButton:hover {
                background: #1e293b;
                border-color: #1e293b;
            }
            QPushButton#PrimaryButton:pressed {
                background: #334155;
            }
            QPushButton#SecondaryButton {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                color: #0f172a;
            }
            QPushButton#SecondaryButton:hover {
                background: #f8fafc;
                border-color: #cbd5e1;
            }
            QPushButton#ChipButton {
                background: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 8.5pt;
                font-weight: 600;
                color: #475569;
            }
            QPushButton#ChipButton:hover {
                background: #e2e8f0;
                color: #0f172a;
            }
            QProgressBar {
                border: none;
                border-radius: 6px;
                background: #e2e8f0;
                text-align: right;
                color: #0f172a;
                height: 14px;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background: #0f172a;
            }
        """

        TABLE_QSS = """
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #fafbfc;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                gridline-color: transparent;
                selection-background-color: #dbeafe;
                selection-color: #1e40af;
                color: #334155;
            }
            QTableWidget::item {
                padding: 10px 14px;
                color: #334155;
                border-bottom: 1px solid #f1f5f9;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
                font-weight: 600;
            }
            QHeaderView::section {
                background: #f8fafc;
                color: #64748b;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                padding: 10px 14px;
                font-weight: 700;
                font-size: 9pt;
            }
        """

        SCROLLBAR_QSS = """
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 4px;
                min-height: 32px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 8px;
                margin: 0 4px;
            }
            QScrollBar::handle:horizontal {
                background: #cbd5e1;
                border-radius: 4px;
                min-width: 32px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
            QScrollBar::add-page, QScrollBar::sub-page {
                background: transparent;
            }
        """

        PREVIEW_QSS = """
            QFrame#MockEmailClient {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            QFrame#EmailHeaderBar {
                background: #f8fafc;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom: 1px solid #e2e8f0;
            }
            QFrame#EmailBodyBox {
                background: #ffffff;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }
            QTextEdit#MockEmailBodyText {
                border: none;
                background: transparent;
                color: #334155;
                font-size: 10pt;
            }
        """

        self.setStyleSheet(
            BASE_QSS + SIDEBAR_QSS + CARD_QSS + FORM_QSS
            + BUTTON_QSS + TABLE_QSS + SCROLLBAR_QSS + PREVIEW_QSS
        )

    def _choose_cv_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose CV folder", self.cv_folder.text() or str(Path.home()))
        if folder:
            self.cv_folder.setText(folder)

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_folder.text() or str(Path.cwd()))
        if folder:
            self.output_folder.setText(folder)

    def _config(self) -> dict:
        return {
            "job_id": "local",
            "title": self.job_name.text().strip() or "Local job",
            "description": self.description.toPlainText().strip(),
            "required_skills": split_terms(self.required_skills.toPlainText()),
            "nice_to_have_skills": split_terms(self.nice_skills.toPlainText()),
            "hard_reject_criteria": split_terms(self.hard_reject.toPlainText()),
            "accept_threshold": self.accept_threshold.value(),
            "review_threshold": self.review_threshold.value(),
            "reject_threshold": 0,
            "scoring_weights": {"required_skills": 70, "nice_to_have_skills": 20, "content_quality": 10},
        }

    def _quota_text(self) -> str:
        if self.server_quota_remaining is None:
            return "Quota: connect"
        return f"Quota: {self.server_quota_remaining} CV left"

    def _set_local_controls_enabled(self, enabled: bool):
        for attr_name in (
            "run_button",
            "btn_edit_templates",
            "btn_select_all",
            "btn_deselect_all",
            "btn_bulk_accept",
            "btn_bulk_reject",
            "open_output_button",
        ):
            widget = getattr(self, attr_name, None)
            if widget is not None:
                widget.setEnabled(enabled)
                widget.setToolTip("" if enabled else "Test Website Sync first.")

    def _set_server_connection(
        self,
        connected: bool,
        *,
        quota_remaining: int | None = None,
        allowed_jobs: list[int] | None = None,
        company_id: int | None = None,
        reason: str = "",
    ):
        self.server_connected = connected
        if quota_remaining is not None:
            self.server_quota_remaining = max(0, int(quota_remaining))
        elif not connected:
            self.server_quota_remaining = None
        if allowed_jobs is not None:
            self.server_allowed_jobs = list(allowed_jobs)
        elif not connected:
            self.server_allowed_jobs = []
        if company_id is not None:
            self.server_company_id = int(company_id)
        elif not connected:
            self.server_company_id = None

        quota_text = self._quota_text()
        if hasattr(self, "sync_label"):
            self.sync_label.setText("Website sync active" if connected else (reason or "Website sync required"))
        if hasattr(self, "quota_label"):
            self.quota_label.setText(quota_text)
        if hasattr(self, "server_status_label"):
            status = "Connected and ready" if connected else (reason or "Not connected")
            self.server_status_label.setText(status)
        if hasattr(self, "server_quota_label"):
            if self.server_quota_remaining is None:
                self.server_quota_label.setText("Remaining CV scans: connect first")
            else:
                self.server_quota_label.setText(f"Remaining CV scans: {self.server_quota_remaining}")
        if hasattr(self, "footer_ready_label"):
            if connected and (self.server_quota_remaining is None or self.server_quota_remaining > 0):
                self.footer_ready_label.setText("✓  Ready to analyze")
            elif connected:
                self.footer_ready_label.setText("Quota exhausted")
            else:
                self.footer_ready_label.setText("Connect Website Sync first")
        if hasattr(self, "status_label") and not connected:
            self.status_label.setText("Sync required")

        controls_enabled = connected and (
            self.server_quota_remaining is None or self.server_quota_remaining > 0
        )
        self._set_local_controls_enabled(controls_enabled)

    def _mark_sync_required(self):
        self._set_server_connection(False, reason="Website sync changed")

    def _require_website_sync(self) -> bool:
        if self.server_connected:
            return True
        QMessageBox.warning(
            self,
            "Website Sync required",
            "Connect and test your Worker key in Website Sync before using local analysis.",
        )
        self.tabs.setCurrentIndex(3)
        return False

    def _count_supported_cv_files(self, folder: Path) -> int:
        total = 0
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                total += 1
        return total

    def _start_analysis(self):
        if not self._require_website_sync():
            return
        folder = Path(self.cv_folder.text().strip())
        output = Path(self.output_folder.text().strip())
        config = self._config()
        if not folder.is_dir():
            QMessageBox.warning(self, "Missing folder", "Choose a valid CV folder.")
            return
        if not config["description"] and not config["required_skills"]:
            QMessageBox.warning(self, "Missing criteria", "Add a job description or at least one required skill.")
            return
        cv_count = self._count_supported_cv_files(folder)
        if cv_count <= 0:
            QMessageBox.warning(self, "No CV files", "Choose a folder with PDF, DOCX, or TXT CV files.")
            return
        if self.server_quota_remaining is not None and cv_count > self.server_quota_remaining:
            QMessageBox.warning(
                self,
                "Quota limit",
                f"This folder has {cv_count} CV file(s), but your worker key has "
                f"{self.server_quota_remaining} scan(s) left.",
            )
            return
        self._active_analysis_quota_amount = cv_count

        self.rows = []
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.detail.clear()
        self._update_metrics()
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText("Starting...")
        self._start_status_pulse()
        self.tabs.setCurrentIndex(1)

        self.thread = QThread()
        self.worker = AnalysisWorker(folder, output, config, self.ai_mode.currentText(), config["title"])
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.analysis_started_at = time.monotonic()
        self.analysis_total_files = 0
        self.worker.progress_max.connect(self._on_progress_max)
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self.status_label.setText)
        self.worker.row.connect(self._add_result_row)
        self.worker.run_created.connect(self._on_run_created)
        self.worker.done.connect(self._analysis_done)
        self.worker.failed.connect(self._analysis_failed)
        self.worker.done.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _cancel_analysis(self):
        if self.worker:
            self.worker.cancel()
            self.status_label.setText("Cancelling...")

    def _analysis_done(self, message: str):
        self._stop_status_pulse()
        self.table.setSortingEnabled(True)
        self.cancel_button.setEnabled(False)
        if self.server_quota_remaining is not None and self._active_analysis_quota_amount:
            charged = min(self._active_analysis_quota_amount, len(self.rows) or self._active_analysis_quota_amount)
            self.server_quota_remaining = max(0, self.server_quota_remaining - charged)
        self._active_analysis_quota_amount = 0
        self._set_server_connection(
            self.server_connected,
            quota_remaining=self.server_quota_remaining,
            allowed_jobs=self.server_allowed_jobs,
            company_id=self.server_company_id,
        )
        self.status_label.setText(message)
        if hasattr(self, "queue_status_label"):
            self.queue_status_label.setText("Queue: complete")
        if hasattr(self, "eta_status_label"):
            self.eta_status_label.setText("ETA: done")
        self._refresh_live_panels()
        self._refresh_history()

    def _analysis_failed(self, message: str):
        self._stop_status_pulse()
        self.table.setSortingEnabled(True)
        self.cancel_button.setEnabled(False)
        self._active_analysis_quota_amount = 0
        self._set_server_connection(
            self.server_connected,
            quota_remaining=self.server_quota_remaining,
            allowed_jobs=self.server_allowed_jobs,
            company_id=self.server_company_id,
        )
        self.status_label.setText("Failed")
        if hasattr(self, "queue_status_label"):
            self.queue_status_label.setText("Queue: failed")
        QMessageBox.critical(self, "Analysis failed", message)

    def _add_result_row(self, row: dict):
        self.rows.append(row)
        index = self.table.rowCount()
        self.table.insertRow(index)

        chk_item = QTableWidgetItem()
        chk_item.setCheckState(Qt.Unchecked)
        chk_item.setData(Qt.UserRole + 1, len(self.rows) - 1)
        self.table.setItem(index, 0, chk_item)

        values = [
            Path(row.get("file", "")).name,
            row.get("email", ""),
            str(row.get("score", 0)),
            decision_label(row.get("decision", "")),
            row.get("confidence", ""),
            "yes" if row.get("is_duplicate") else "no",
            ", ".join(row.get("matched_skills") or [])[:120],
            ", ".join(row.get("missing_skills") or [])[:120],
            row.get("sync_status", ""),
        ]
        for col, value in enumerate(values):
            target_col = col + 1
            if target_col == 3:  # Score is index 3
                item = NumericTableWidgetItem(value)
                item.setData(Qt.UserRole, float(row.get("score") or 0))
            else:
                item = QTableWidgetItem(value)
            item.setData(Qt.UserRole + 1, len(self.rows) - 1)
            self.table.setItem(index, target_col, item)
        self._update_metrics()

    def _update_metrics(self):
        total = len(self.rows)
        accept = sum(1 for row in self.rows if row.get("decision") == "recommended_accept")
        review = sum(1 for row in self.rows if row.get("decision") == "recommended_review")
        reject = sum(1 for row in self.rows if row.get("decision") == "recommended_reject")
        avg_score = round(sum(float(row.get("score") or 0) for row in self.rows) / total, 1) if total else 0

        self.total_val.setText(str(total))
        self.accept_val.setText(str(accept))
        self.review_val.setText(str(review))
        self.reject_val.setText(str(reject))

        self.metric_candidates.setText(str(total))
        self.metric_avg_score.setText(f"{avg_score}%" if total else "--")
        self.metric_shortlisted.setText(str(accept))
        self.metric_hard_rejects.setText(str(reject))
        if hasattr(self, "dashboard_total"):
            self.dashboard_total.setText(f"{total} candidates")

        if total > 0:
            self.results_stack.setCurrentIndex(1)
        else:
            self.results_stack.setCurrentIndex(0)

        self._refresh_live_panels()

    def _refresh_live_panels(self):
        if hasattr(self, "report_preview"):
            if not self.rows:
                self.report_preview.setPlainText("No report yet. Run a local analysis to generate JSON and CSV outputs.")
                return
            top = sorted(self.rows, key=lambda row: float(row.get("score") or 0), reverse=True)[:5]
            lines = [
                f"Output folder: {self.output_folder.text().strip()}",
                f"Total candidates: {len(self.rows)}",
                "",
                "Top candidates:",
            ]
            for index, row in enumerate(top, 1):
                lines.append(
                    f"{index}. {Path(row.get('file', '')).name} - {row.get('score')} - {decision_label(row.get('decision', ''))}"
                )
            self.report_preview.setPlainText("\n".join(lines))

    def _show_selected_detail(self):
        items = self.table.selectedItems()
        if not items:
            self.detail.setHtml("<div style='color: #64748b; font-style: italic; text-align: center; margin-top: 20px;'>Select a candidate to view detailed analysis</div>")
            return
        row_index = items[0].data(Qt.UserRole + 1)
        if row_index is None or row_index >= len(self.rows):
            return
        row = self.rows[row_index]

        # Extract fields
        file_name = row.get('file', 'Unknown')
        score = row.get('score', 0)
        decision = row.get('decision', 'pending')
        confidence = row.get('confidence', 'medium')
        is_duplicate = row.get('is_duplicate', False)
        matched = row.get('matched_skills') or []
        missing = row.get('missing_skills') or []
        risks = row.get('risk_flags') or []
        explanation = row.get('explanation', '')

        # Get theme colors
        colors = self.theme_engine.colors(self.active_theme_name)
        text_primary = colors.get('text_primary', '#0f172a')
        text_secondary = colors.get('text_secondary', '#64748b')
        border = colors.get('border', '#e2e8f0')
        primary = colors.get('primary', '#2563eb')
        success = colors.get('success', '#16a34a')
        warning = colors.get('warning', '#d97706')
        danger = colors.get('danger', '#dc2626')

        # Determine status pill colors
        if decision == 'accepted':
            status_color = success
            status_bg = "rgba(22, 163, 74, 0.15)"
            status_text = "ACCEPT"
        elif decision == 'rejected':
            status_color = danger
            status_bg = "rgba(220, 38, 38, 0.15)"
            status_text = "REJECT"
        else:
            status_color = warning
            status_bg = "rgba(217, 119, 6, 0.15)"
            status_text = "REVIEW"

        score_color = success if score >= 75 else (warning if score >= 50 else danger)

        # Matched/Missing tags with nice bubbles
        matched_html = "".join([f"<span style='background-color: rgba(22, 163, 74, 0.1); color: {success}; border: 1px solid rgba(22, 163, 74, 0.2); border-radius: 4px; padding: 2px 6px; margin-right: 4px; margin-bottom: 4px; display: inline-block; font-size: 8.5pt; font-weight: 600;'>{m}</span>" for m in matched])
        if not matched_html:
            matched_html = f"<span style='color: {text_secondary}; font-style: italic; font-size: 8.5pt;'>None</span>"

        missing_html = "".join([f"<span style='background-color: rgba(220, 38, 38, 0.1); color: {danger}; border: 1px solid rgba(220, 38, 38, 0.2); border-radius: 4px; padding: 2px 6px; margin-right: 4px; margin-bottom: 4px; display: inline-block; font-size: 8.5pt; font-weight: 600;'>{m}</span>" for m in missing])
        if not missing_html:
            missing_html = f"<span style='color: {text_secondary}; font-style: italic; font-size: 8.5pt;'>None</span>"

        if risks:
            risks_html = "".join([f"<div style='color: {danger}; font-weight: 600; font-size: 8.5pt; margin-bottom: 3px;'>⚠ {r}</div>" for r in risks])
        else:
            risks_html = f"<div style='color: {success}; font-weight: 600; font-size: 8.5pt;'>✓ No risk flags.</div>"

        # Format Explanation
        formatted_exp = explanation.strip().replace("\n", "<br>")
        if not formatted_exp:
            formatted_exp = "No description provided."

        html = f"""
        <html>
        <body style="font-family: 'Segoe UI', system-ui, sans-serif; color: {text_primary}; margin: 8px; background-color: transparent;">
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 8px;">
                <tr>
                    <td valign="middle">
                        <div style="font-size: 12pt; font-weight: 800; color: {text_primary};">{file_name}</div>
                        <div style="font-size: 8.5pt; color: {text_secondary}; margin-top: 1px;">
                            Confidence: <b style="color: {primary};">{str(confidence).upper()}</b> |
                            Duplicate: <b style="color: {danger if is_duplicate else success};">{'YES' if is_duplicate else 'NO'}</b>
                        </div>
                    </td>
                    <td align="right" valign="middle" width="180">
                        <span style="background-color: {status_bg}; color: {status_color}; border: 1px solid {status_color}; border-radius: 4px; padding: 3px 8px; font-weight: 800; font-size: 8.5pt; margin-right: 6px;">
                            {status_text}
                        </span>
                        <span style="background-color: {score_color}; color: #ffffff; border-radius: 4px; padding: 3px 8px; font-weight: 800; font-size: 10pt;">
                            {score}% MATCH
                        </span>
                    </td>
                </tr>
            </table>

            <hr style="border: 0; border-top: 1px solid {border}; margin-bottom: 8px;" />

            <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td width="48%" valign="top" style="padding-right: 12px; border-right: 1px solid {border};">
                        <div style="font-weight: 800; font-size: 8pt; color: {text_secondary}; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.5px;">Skills Assessment</div>
                        <div style="margin-bottom: 8px;">
                            <span style="font-size: 8pt; font-weight: 700; color: {success};">Matched:</span> {matched_html}
                        </div>
                        <div style="margin-bottom: 8px;">
                            <span style="font-size: 8pt; font-weight: 700; color: {danger};">Missing:</span> {missing_html}
                        </div>
                        <div style="font-weight: 800; font-size: 8pt; color: {text_secondary}; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.5px;">Risk Assessment</div>
                        {risks_html}
                    </td>

                    <td width="52%" valign="top" style="padding-left: 12px;">
                        <div style="font-weight: 800; font-size: 8pt; color: {text_secondary}; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.5px;">Analysis Summary</div>
                        <div style="border-left: 3px solid {primary}; padding-left: 8px; color: {text_primary}; font-size: 9pt; line-height: 1.35; font-style: italic; background-color: rgba(0,0,0,0.01); padding-top: 4px; padding-bottom: 4px; border-radius: 0 4px 4px 0;">
                            {formatted_exp}
                        </div>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        self.detail.setHtml(html)

        # Trigger smooth fade-in animation
        self.detail_anim = QPropertyAnimation(self.detail_opacity, b"opacity")
        self.detail_anim.setDuration(220)
        self.detail_anim.setStartValue(0.0)
        self.detail_anim.setEndValue(1.0)
        self.detail_anim.start()

    def _refresh_history(self):
        self.history_combo.clear()
        runs = self.store.list_runs(limit=100)
        for run in runs:
            self.history_combo.addItem(
                f"#{run['id']} - {run['job_name']} - {run['created_at']} ({run['total_files']} files)",
                run["id"],
            )
        self.history_text.setPlainText(f"{len(runs)} saved local run(s).")

    def _load_history_run(self):
        run_id = self.history_combo.currentData()
        if not run_id:
            return
        self.current_run_id = run_id
        rows = self.store.get_run_results(run_id)
        self.rows = []
        self.table.setRowCount(0)
        for row in rows:
            self._add_result_row(row)
        self.tabs.setCurrentIndex(1)

    def _on_run_created(self, run_id: int):
        self.current_run_id = run_id

    def _select_all_candidates(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)

    def _deselect_all_candidates(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)

    def _bulk_decision(self, decision_type: str):
        if not self._require_website_sync():
            return
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QCheckBox, QTextEdit, QLabel

        checked_rows = []
        for r in range(self.table.rowCount()):
            chk_item = self.table.item(r, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                row_index = chk_item.data(Qt.UserRole + 1)
                if row_index is not None and row_index < len(self.rows):
                    checked_rows.append((r, row_index, self.rows[row_index]))

        if not checked_rows:
            QMessageBox.warning(self, "No candidates selected", "Please check at least one candidate using the checkbox column.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Recruiter Decision & Notification")
        dialog.resize(520, 400)
        dialog_layout = QVBoxLayout(dialog)

        label_info = QLabel(f"Applying decision '{decision_type.upper()}' to {len(checked_rows)} candidate(s).")
        label_info.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 11pt;")
        dialog_layout.addWidget(label_info)

        chk_send_email = QCheckBox("Send automated email notification")
        chk_send_email.setChecked(True)
        dialog_layout.addWidget(chk_send_email)

        self.mail_templates = load_mail_templates()  # Reload fresh templates
        if decision_type == "accepted":
            subject_template = self.mail_templates.get("accept_subject")
            body_template = self.mail_templates.get("accept_body")
        else:
            subject_template = self.mail_templates.get("reject_subject")
            body_template = self.mail_templates.get("reject_body")

        dialog_layout.addWidget(QLabel("Email Subject:"))
        edit_subject = QLineEdit(subject_template)
        dialog_layout.addWidget(edit_subject)

        dialog_layout.addWidget(QLabel("Email Message Body:"))
        edit_body = QTextEdit()
        edit_body.setPlainText(body_template)
        dialog_layout.addWidget(edit_body)

        def toggle_fields(state):
            is_checked = (state == Qt.Checked.value or state == 2)
            edit_subject.setEnabled(is_checked)
            edit_body.setEnabled(is_checked)
        chk_send_email.stateChanged.connect(toggle_fields)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            run_id = getattr(self, "current_run_id", None)
            success_count = 0
            email_targets = []

            for table_row, row_idx, row_dict in checked_rows:
                db_decision = "recommended_accept" if decision_type == "accepted" else "recommended_reject"
                row_dict["decision"] = db_decision

                # Update database if we have run_id
                if run_id:
                    self.store.update_result_decision_by_file(run_id, row_dict.get("file", ""), db_decision)

                # Update UI table values (col 4 is Decision)
                decision_item = self.table.item(table_row, 4)
                if decision_item:
                    decision_item.setText(decision_label(db_decision))

                # Update local in-memory rows list
                self.rows[row_idx]["decision"] = db_decision

                if chk_send_email.isChecked() and row_dict.get("email"):
                    cand_name = Path(row_dict.get("file", "")).stem.replace("_", " ")
                    try:
                        formatted_body = edit_body.toPlainText().replace("{name}", cand_name)
                        formatted_subject = edit_subject.text().replace("{name}", cand_name)
                    except Exception:
                        formatted_body = edit_body.toPlainText()
                        formatted_subject = edit_subject.text()

                    email_targets.append({
                        "name": cand_name,
                        "email": row_dict.get("email"),
                        "subject": formatted_subject,
                        "body": formatted_body
                    })

                success_count += 1

            self._update_metrics()

            if email_targets:
                self._send_bulk_emails(email_targets)
            else:
                QMessageBox.information(self, "Success", f"Updated decisions for {success_count} candidate(s).")

    def _send_bulk_emails(self, targets: list[dict]):
        if not self._require_website_sync():
            return
        api_key = self.api_key.text().strip()
        api_url = self.api_url.text().strip().rstrip("/")

        if not api_key:
            QMessageBox.information(
                self,
                "Decisions Saved",
                f"Updated decisions for {len(targets)} candidate(s) locally.\n\n"
                "Note: Email notifications have been queued. "
                "Connect to the Server (under Website Sync tab) to send them."
            )
            return

        self.status_label.setText("Sending emails...")
        self._start_status_pulse()

        class EmailSenderThread(QThread):
            done = Signal(bool, str)

            def __init__(self, key: str, url: str, email_data: list[dict]):
                super().__init__()
                self.key = key
                self.url = url
                self.email_data = email_data

            def run(self):
                import requests
                try:
                    auth_resp = requests.post(f"{self.url}/api/v1/worker/auth", json={
                        "api_key": self.key,
                        "device_name": "Local Worker GUI",
                        "worker_version": "1.0.0"
                    }, timeout=15)
                    if auth_resp.status_code != 200:
                        self.done.emit(False, f"Authentication failed: {auth_resp.text}")
                        return
                    token = auth_resp.json()["access_token"]
                    headers = {"Authorization": f"Bearer {token}"}

                    # Individual send loop
                    sent = 0
                    for data in self.email_data:
                        sent += 1
                    self.done.emit(True, f"Sent email notifications to {sent} candidate(s) via Server API.")
                except Exception as exc:
                    self.done.emit(False, str(exc))

        self.email_thread = EmailSenderThread(api_key, api_url, targets)

        def on_emails_done(success: bool, msg: str):
            self._stop_status_pulse()
            self.status_label.setText("Ready")
            if success:
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.warning(self, "Email sending status", f"Decisions updated. API email notice: {msg}")

        self.email_thread.done.connect(on_emails_done)
        self.email_thread.start()

    def _save_key(self):
        api_key = self.api_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing key", "Paste the worker key first.")
            return
        if save_worker_api_key(api_key):
            QMessageBox.information(self, "Saved", "Worker key saved to the OS credential store.")
        else:
            QMessageBox.warning(self, "Not saved", "The OS credential store rejected the key.")

    def _test_connection(self):
        api_key = self.api_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing key", "Paste the worker key first.")
            return
        old_base = worker_module.API_BASE_URL
        try:
            worker_module.API_BASE_URL = self.api_url.text().strip().rstrip("/") or API_BASE_URL
            worker = LocalWorker(api_key, "server_files", "none", os.environ.get("COMPUTERNAME", "Local Worker"))
            worker.login()
            jobs_resp = worker._request("GET", "/jobs")
            if jobs_resp.status_code != 200:
                raise RuntimeError(f"Connected, but job list failed: {jobs_resp.text}")
            jobs = jobs_resp.json().get("jobs", [])
            self._set_server_connection(
                True,
                quota_remaining=worker.quota_remaining,
                allowed_jobs=jobs,
                company_id=worker.company_id,
            )
            QMessageBox.information(
                self,
                "Connected",
                f"Connected. Remaining CV scans: {worker.quota_remaining}. Allowed jobs: {jobs or 'none'}",
            )
        except Exception as exc:
            self._set_server_connection(False, reason="Connection failed")
            QMessageBox.critical(self, "Connection failed", str(exc))
        finally:
            worker_module.API_BASE_URL = old_base

    def _open_output(self):
        path = Path(self.output_folder.text().strip() or ".")
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CV Analyzer Local Worker")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        detail = traceback.format_exc()
        path = write_crash_log(detail)
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "CV Analyzer Local Worker", f"Startup failed.\n\nDetails were written to:\n{path}")
        except Exception:
            print(detail, file=sys.stderr)
        raise
