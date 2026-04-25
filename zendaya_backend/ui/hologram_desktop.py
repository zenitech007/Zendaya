"""
Desktop Hologram Window
-----------------------
This script provides a transparent, draggable, and auto-hiding desktop window
for displaying a web-based hologram. It merges two implementations to include
the best features of both:

- Two-way communication with JavaScript via QWebChannel (from script 1).
- Singleton pattern to ensure only one hologram instance (from script 1).
- Threaded execution to prevent blocking the main application (from script 1).
- Flexible configuration for HTML path, avatar, and timeout (from script 1).
- Event filter for robust drag-and-drop window movement (from script 1).
- Double-click event to manually show/hide the window (from script 2).

The exposed 'HologramBridge' object allows JavaScript to call Python methods:
 - setEmotion(str)
 - speakAmplitude(float)
 - show()
 - hide()
 - setAvatar(str)
 - showReaction(str)
"""
import os
import sys
import threading
import time
from typing import Optional

from PyQt6 import QtWidgets, QtCore, QtWebEngineWidgets
from PyQt6.QtWebChannel import QWebChannel

# Single instance holder to ensure only one hologram window is created.
_hologram_instance = None


class HologramBridge(QtCore.QObject):
    """
    Object exposed to JavaScript via QWebChannel.
    It uses signals to communicate events from the web page to the Python backend.
    """
    emotionChanged = QtCore.pyqtSignal(str)
    amplitudeReceived = QtCore.pyqtSignal(float)
    showRequested = QtCore.pyqtSignal()
    hideRequested = QtCore.pyqtSignal()
    avatarChanged = QtCore.pyqtSignal(str)
    reactionRequested = QtCore.pyqtSignal(str)

    @QtCore.pyqtSlot(str)
    def setEmotion(self, emotion: str):
        self.emotionChanged.emit(emotion)

    @QtCore.pyqtSlot(float)
    def speakAmplitude(self, amp: float):
        self.amplitudeReceived.emit(amp)

    @QtCore.pyqtSlot()
    def show(self):
        self.showRequested.emit()

    @QtCore.pyqtSlot()
    def hide(self):
        self.hideRequested.emit()

    @QtCore.pyqtSlot(str)
    def setAvatar(self, url: str):
        self.avatarChanged.emit(url)

    @QtCore.pyqtSlot(str)
    def showReaction(self, reaction: str):
        self.reactionRequested.emit(reaction)


class HologramWindow(QtWidgets.QMainWindow):
    """
    The main window for the hologram. It's frameless, transparent, and
    hosts a QWebEngineView to render the HTML/JS content.
    """

    def __init__(self, html_path: Optional[str], avatar_url: Optional[str] = None, inactivity_timeout: int = 12):
        super().__init__()
        # If no html_path is provided, fall back to the default packaged hologram index.html
        if not html_path:
            base = os.path.dirname(__file__)
            html_path = os.path.join(base, "hologram", "index.html")

        self.html_path = html_path
        self.avatar_url = avatar_url or ""
        self.inactivity_timeout = inactivity_timeout

        # Configure window flags: frameless, always on top, and translucent
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(1450, 750, 280, 360)
        self.setWindowOpacity(0.98)
        self.setStyleSheet("background: transparent; border-radius: 16px;")# Default size and position

        # Web view setup
        self.view = QtWebEngineWidgets.QWebEngineView(self)
        self.view.setStyleSheet("background: transparent; border: none;")
        self.setCentralWidget(self.view)

        # Web channel setup for Python <-> JS communication
        self.channel = QWebChannel()
        self.bridge = HologramBridge()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        # Load the HTML file
        self.view.load(QtCore.QUrl.fromLocalFile(os.path.abspath(self.html_path)))

        # Drag support setup
        self._drag_pos = None
        self.installEventFilter(self)

        # Auto-hide timer setup
        self.hide_timer = QtCore.QTimer(self)
        self.hide_timer.setInterval(self.inactivity_timeout * 1000)
        self.hide_timer.timeout.connect(self._on_auto_hide)
        self.hide_timer.start()

        # Connect signals from the bridge to window methods
        self.bridge.emotionChanged.connect(self._on_emotion_changed)
        self.bridge.amplitudeReceived.connect(self._on_amplitude_received)
        self.bridge.showRequested.connect(self.show_hologram)
        self.bridge.hideRequested.connect(self.hide_hologram)
        self.bridge.avatarChanged.connect(self._on_avatar_changed)
        self.bridge.reactionRequested.connect(self._on_reaction_requested)

        # Internal state tracking
        self._visible = False

    # ----------------------
    # Event Handling for Interaction
    # ----------------------
    def eventFilter(self, obj, event):
        """Handles mouse events to allow dragging the frameless window."""
        t = event.type()
        if t == QtCore.QEvent.Type.MouseButtonPress:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition()
                self.reset_timer() # Reset auto-hide on user interaction
        elif t == QtCore.QEvent.Type.MouseMove and self._drag_pos:
            delta = event.globalPosition() - self._drag_pos
            self.move(self.x() + int(delta.x()), self.y() + int(delta.y()))
            self._drag_pos = event.globalPosition()
        elif t == QtCore.QEvent.Type.MouseButtonRelease:
            self._drag_pos = None
        return super().eventFilter(obj, event)

    def mouseDoubleClickEvent(self, event):
        """Toggle visibility on double-click (feature from script 2)."""
        if self.isVisible():
            self.hide_hologram()
        else:
            self.show_hologram()
        self.reset_timer()

    # ----------------------
    # Bridge Handlers (Forwarding calls to JavaScript)
    # ----------------------
    def _on_emotion_changed(self, emotion: str):
        script = f'if(window.setEmotion) window.setEmotion("{emotion}");'
        self.view.page().runJavaScript(script)

    def _on_amplitude_received(self, amp: float):
        script = f'if(window.setMouth) window.setMouth({float(amp)});'
        self.view.page().runJavaScript(script)

    def _on_avatar_changed(self, url: str):
        script = f'if(window.setAvatar) window.setAvatar("{url}");'
        self.view.page().runJavaScript(script)

    def _on_reaction_requested(self, reaction: str):
        script = f'if(window.showReaction) window.showReaction("{reaction}");'
        self.view.page().runJavaScript(script)

    # ----------------------
    # Visibility and Timer Control
    # ----------------------
    def show_hologram(self):
        """Makes the hologram window visible and active."""
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._visible = True
        self.reset_timer()
        self.view.page().runJavaScript('if(window.onHostShow) window.onHostShow();')
        print("✨ Hologram shown.")

    def hide_hologram(self):
        """Hides the hologram window."""
        self.hide()
        self._visible = False
        self.view.page().runJavaScript('if(window.onHostHide) window.onHostHide();')
        print("👻 Hologram hidden.")


    def _on_auto_hide(self):
        """Callback for the timer to automatically hide the window when idle."""
        if self._visible:
            print("💤 Auto-hiding hologram (idle).")
            self.hide_hologram()

    def reset_timer(self):
        """Resets the inactivity timer."""
        self.hide_timer.start(self.inactivity_timeout * 1000)

    # ----------------------
    # Public API (Convenience methods for Python-side control)
    # ----------------------
    def set_emotion(self, emotion: str):
        """Sets the hologram's emotion."""
        self.bridge.setEmotion(emotion)
        self.reset_timer()

    def push_amplitude(self, amp: float):
        """Updates the mouth movement based on speech amplitude."""
        self.bridge.speakAmplitude(amp)
        self.reset_timer()

    def set_avatar(self, url: str):
        """Changes the avatar image."""
        self.bridge.setAvatar(url)

    def request_reaction(self, reaction: str):
        """Triggers a specific reaction animation."""
        self.bridge.showReaction(reaction)
        self.reset_timer()


# ----------------------
# Public Helper Functions
# ----------------------
def get_hologram(html_rel_path: Optional[str] = None, avatar_url: Optional[str] = None, timeout: int = 12) -> HologramWindow:
    """
    Returns the singleton HologramWindow instance, creating it if necessary.
    This ensures that only one hologram window exists in the application.
    """
    global _hologram_instance
    if _hologram_instance is None:
        base = os.path.dirname(__file__)
        html_path = html_rel_path or os.path.join(base, "hologram", "index.html")
        _hologram_instance = HologramWindow(html_path, avatar_url=avatar_url or "", inactivity_timeout=timeout)
    return _hologram_instance


def start_hologram_in_thread(html_rel_path: Optional[str] = None, avatar_url: Optional[str] = None, timeout: int = 12) -> HologramWindow:
    """
    Starts the PyQt event loop in a daemon thread and shows the hologram.
    This is the recommended way to launch the UI without blocking a parent script.
    """
    def _run():
        # Create the Qt Application within the new thread
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        hologram = get_hologram(html_rel_path, avatar_url, timeout)
        hologram.show_hologram()
        print("🌌 Zendaya hologram window initialized in a separate thread.")
        app.exec()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    time.sleep(0.5) # Give the UI a moment to initialize
    return get_hologram()

def start_hologram() -> HologramWindow:
    """Create (if needed) and show the hologram window in the current thread.

    This is a small convenience wrapper used by some callers that expect a
    simple `start_hologram()` function. Prefer `start_hologram_in_thread`
    for non-blocking behaviour.
    """
    global _hologram_instance
    holo = get_hologram()
    try:
        holo.show_hologram()
    except Exception:
        # Best-effort: fallback to showing normally if specialized method fails
        try:
            holo.show()
        except Exception:
            pass
    return holo

# ----------------------
# Example Usage (for direct execution)
# ----------------------
if __name__ == '__main__':
    # This block allows you to run this file directly for testing purposes.
    # It will start the hologram in a new thread and then enter a loop
    # to demonstrate sending commands to it.

    print("Starting hologram for testing...")
    # NOTE: For this test to work, you need a 'hologram/index.html' file
    # relative to this script's location.
    hologram = start_hologram_in_thread(timeout=5)

    # Keep the main thread alive to see the hologram
    try:
        emotions = ["neutral", "happy", "sad", "surprised", "thinking"]
        i = 0
        while True:
            time.sleep(3)
            emotion = emotions[i % len(emotions)]
            print(f"--> Setting emotion to: {emotion}")
            hologram.set_emotion(emotion)
            i += 1
    except KeyboardInterrupt:
        print("\nExiting test.")
        # The daemon thread will exit automatically when the main script ends.
