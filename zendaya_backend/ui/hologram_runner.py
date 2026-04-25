"""
This script is the dedicated entry point for launching the Zendaya Hologram UI.
It ensures that the QApplication is properly instantiated in its own process
before any QWidget is created, which resolves the common PyQt startup error.

This process will connect back to the FastAPI backend via WebSockets to receive
commands for state changes (e.g., emotion, visibility).
"""

import sys
import logging

# Set up basic logging for the UI process
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [HologramUI] - %(levelname)s - %(message)s",
)

def main():
    """Initializes the Qt Application and runs the hologram."""
    try:
        # It's crucial that this import happens inside the main guard
        # to avoid any Qt-related code running on module import.
        from PyQt6.QtWidgets import QApplication
        # We assume your main UI widget is defined in hologram_desktop.py
        # and that it handles WebSocket connections internally.
        from zendaya_backend.ui.hologram_desktop import start_hologram

    except ImportError as e:
        logging.error(f"Failed to import necessary modules. Make sure PyQt6 is installed and hologram_desktop.py exists. Error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during module import: {e}")
        sys.exit(1)

    # 1. Construct the QApplication FIRST.
    app = QApplication(sys.argv)
    logging.info("QApplication constructed.")

    # 2. Now it's safe to create QWidget instances.
    hologram = start_hologram()  # Assuming this class exists and connects to the WebSocket
    logging.info("HologramWidget instantiated.")

    # The HologramWidget itself should handle when to show.
    # For example, after a successful WebSocket connection.
    # hologram.show() # Or let the widget decide when to show.

    # 3. Start the Qt event loop.
    logging.info("Starting Qt event loop.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
