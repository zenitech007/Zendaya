import socket

def is_connected(host="8.8.8.8", port=53, timeout=3):
    """
    Checks if the PC is connected to the internet.
    Default uses Google DNS (8.8.8.8).
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False
