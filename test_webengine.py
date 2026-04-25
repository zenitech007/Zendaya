import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl  # <-- import QUrl

app = QApplication(sys.argv)

# Create a browser window
browser = QWebEngineView()
browser.setWindowTitle("PyQt6 WebEngine Test")
browser.resize(800, 600)

# Load a website using QUrl
browser.setUrl(QUrl("https://www.python.org"))
browser.show()

sys.exit(app.exec())
