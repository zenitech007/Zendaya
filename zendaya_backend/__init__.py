"""
Zendaya AI Assistant Backend Package
------------------------------------

This file marks the 'zendaya_backend' directory as a Python package.
To avoid circular dependencies and import-time side effects, all major
service initializations (like database connections and AI clients) are
handled within the main application entrypoint (main.py) during the
application's lifespan events.
"""

# Keep this file simple to ensure clean and predictable imports.

