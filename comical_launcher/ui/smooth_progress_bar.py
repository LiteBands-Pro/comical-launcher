"""A QProgressBar that eases toward new values instead of jumping
instantly — this is what makes download progress feel smooth rather than
jittery, especially since progress updates arrive several times a second."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QProgressBar


class SmoothProgressBar(QProgressBar):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setRange(0, 100)
        self.setTextVisible(False)
        self._animation = QPropertyAnimation(self, b"value", self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_value_animated(self, value: int) -> None:
        self._animation.stop()
        self._animation.setStartValue(self.value())
        self._animation.setEndValue(value)
        self._animation.start()
