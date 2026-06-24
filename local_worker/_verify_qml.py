"""Headless QML load verification — loads Main.qml offscreen and reports
runtime QML errors/warnings without needing a display. Verification gate for
local-worker QML edits."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

_messages: list[str] = []


def _handler(mode, ctx, msg):
    _messages.append(msg)


from PySide6.QtCore import QCoreApplication, QUrl, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

import qml_gui

qInstallMessageHandler(_handler)
QCoreApplication.setOrganizationName("CV Analyzer")
QCoreApplication.setApplicationName("CV Analyzer Local Worker")
QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)

backend = qml_gui.LocalWorkerBackend()
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(qml_gui.resource_path("qml/Main.qml"))))

ok = bool(engine.rootObjects())
_IGNORE = ("QFontDatabase", "Cannot find font", "Qt no longer ships fonts")
errors = [
    m for m in _messages
    if ("is not defined" in m or "Error" in m or "Unable" in m or "Cannot" in m)
    and not any(ig in m for ig in _IGNORE)
]
type_errors = [m for m in _messages if "TypeError" in m or "ReferenceError" in m]

print("LOADED:", ok)
print("rootObjects:", len(engine.rootObjects()))
print("total qml messages:", len(_messages))
print("error-like messages:", len(errors))
for m in errors[:30]:
    print("  !", m)
sys.exit(0 if ok and not errors else 2)
