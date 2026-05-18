"""System tray icon with start/stop controls."""
import os
import sys
import math
import threading
import logging
from pathlib import Path

logger = logging.getLogger("prc-tray")


def _create_icon_active():
    """Music-themed icon for active/running state — red with musical note."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Shadow
    draw.ellipse([2, 4, 62, 64], fill=(0, 0, 0, 40))
    # Main circle — vibrant red
    draw.ellipse([2, 2, 62, 62], fill=(230, 57, 70, 255))
    # Inner gradient ring
    draw.ellipse([5, 5, 59, 59], fill=(210, 45, 60, 255))
    draw.ellipse([8, 8, 56, 56], fill=(235, 65, 78, 255))

    # Musical note: stem + flag + note head
    # Note head (filled ellipse)
    hx, hy = 28, 38
    draw.ellipse([hx - 6, hy - 4, hx + 6, hy + 4], fill=(255, 255, 255, 245))
    # Stem (vertical line from note head going up)
    draw.rectangle([hx + 4, 18, hx + 6, hy - 2], fill=(255, 255, 255, 245))
    # Flag (curved stroke at top of stem)
    for i in range(8):
        x = hx + 6 + i
        y = 18 + int(i * 0.8)
        draw.rectangle([x, y, x + 2, y + 2], fill=(255, 255, 255, 245))

    # Gloss highlight
    draw.arc([10, 4, 54, 36], start=200, end=340, fill=(255, 255, 255, 60), width=2)

    return img


def _create_icon_inactive():
    """Muted icon for stopped/inactive state — gray with pause bars."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Shadow
    draw.ellipse([2, 4, 62, 64], fill=(0, 0, 0, 30))
    # Main circle — muted gray
    draw.ellipse([2, 2, 62, 62], fill=(80, 80, 85, 255))
    draw.ellipse([5, 5, 59, 59], fill=(65, 65, 70, 255))
    draw.ellipse([8, 8, 56, 56], fill=(95, 95, 100, 255))

    # Pause bars (two vertical bars)
    bar_w, bar_h, gap = 5, 18, 6
    cx, cy = 32, 32
    # Left bar
    draw.rounded_rectangle(
        [cx - gap - bar_w, cy - bar_h // 2, cx - gap, cy + bar_h // 2],
        radius=2, fill=(255, 255, 255, 180)
    )
    # Right bar
    draw.rounded_rectangle(
        [cx + gap - bar_w, cy - bar_h // 2, cx + gap, cy + bar_h // 2],
        radius=2, fill=(255, 255, 255, 180)
    )

    # Gloss highlight
    draw.arc([10, 4, 54, 36], start=200, end=340, fill=(255, 255, 255, 30), width=2)

    return img


def _create_icon_loading():
    """Animated-style icon for loading/processing — blue with spinner segments."""
    from PIL import Image, ImageDraw
    import math

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Shadow
    draw.ellipse([2, 4, 62, 64], fill=(0, 0, 0, 35))
    # Main circle — blue
    draw.ellipse([2, 2, 62, 62], fill=(45, 130, 220, 255))
    draw.ellipse([5, 5, 59, 59], fill=(35, 110, 195, 255))
    draw.ellipse([8, 8, 56, 56], fill=(55, 140, 230, 255))

    # Spinner — dashed arc (partial ring)
    cx, cy, r = 32, 32, 14
    for angle in range(0, 270, 30):
        rad = math.radians(angle)
        x1 = cx + int(r * math.cos(rad))
        y1 = cy + int(r * math.sin(rad))
        x2 = cx + int((r + 3) * math.cos(rad))
        y2 = cy + int((r + 3) * math.sin(rad))
        alpha = max(60, 255 - angle // 2)
        draw.line([x1, y1, x2, y2], fill=(255, 255, 255, alpha), width=3)

    # Center dot
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 255, 255, 200))

    # Gloss highlight
    draw.arc([10, 4, 54, 36], start=200, end=340, fill=(255, 255, 255, 50), width=2)

    return img


# Legacy names for backward compatibility
_create_icon_image = _create_icon_active
_create_icon_image_gray = _create_icon_inactive


def create_tray(on_exit: callable, get_status: callable = None):
    """Create system tray icon. Returns the pystray Icon instance."""
    try:
        import pystray
        from pystray import MenuItem
    except ImportError:
        logger.warning("pystray not available — running without tray icon")
        return None

    from version import __version__

    icon_active = _create_icon_active()
    icon_inactive = _create_icon_inactive()

    def on_open_browser(icon, item):
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:17171/health")

    def on_copy_secret(icon, item):
        from config import SHUTDOWN_SECRET
        try:
            import subprocess
            if sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=SHUTDOWN_SECRET.encode(), check=True)
            elif sys.platform == "win32":
                subprocess.run(["clip"], input=SHUTDOWN_SECRET.encode(), check=True)
            else:
                subprocess.run(["xclip", "-selection", "clipboard"],
                               input=SHUTDOWN_SECRET.encode(), check=True)
        except Exception:
            logger.info(f"Shutdown secret: {SHUTDOWN_SECRET}")

    def on_open_logs(icon, item):
        import subprocess
        log_file = "/tmp/prc-tray.log" if sys.platform != "win32" else os.path.join(os.environ.get("TEMP", "."), "prc-tray.log")
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", log_file])
            elif sys.platform == "win32":
                subprocess.Popen(["start", log_file], shell=True)
            else:
                subprocess.Popen(["xdg-open", log_file])
        except Exception:
            logger.info(f"Logs: {log_file}")

    def on_quit(icon, item):
        logger.info("Tray quit requested")
        icon.stop()
        on_exit()

    menu = pystray.Menu(
        MenuItem(f"PRC Tray v{__version__}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        MenuItem("Health Check", on_open_browser),
        MenuItem("Copy Shutdown Secret", on_copy_secret),
        MenuItem("Open Logs", on_open_logs),
        pystray.Menu.SEPARATOR,
        MenuItem("Quit", on_quit),
    )

    tray_icon = pystray.Icon(
        name="prc-tray",
        icon=icon_active,
        title=f"PRC Tray v{__version__} — Running",
        menu=menu,
    )

    return tray_icon
