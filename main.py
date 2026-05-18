"""PRC Tray — local streaming URL extractor.

Runs a local HTTP server on 127.0.0.1:17171 that wraps yt-dlp.
Controlled via system tray icon. Auto-shuts down after idle timeout.

Usage:
    python main.py              # Run with tray icon
    python main.py --no-tray    # Run headless (for scripts/CI)
"""
import sys
import time
import signal
import logging
import argparse
import threading

import uvicorn

import config
from server import app, set_shutdown_callback

# ── Logging ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("prc-tray")

# ── Shutdown control ──────────────────────────────────────────────────────

_shutdown_event = threading.Event()


def request_shutdown():
    """Called by tray, API, or signal handler."""
    logger.info("Shutdown requested")
    _shutdown_event.set()


def idle_watchdog():
    """Background thread that checks idle timeout."""
    from server import get_idle_seconds
    while not _shutdown_event.is_set():
        _shutdown_event.wait(timeout=30)  # Check every 30s
        if _shutdown_event.is_set():
            break
        idle = get_idle_seconds()
        if idle > config.IDLE_TIMEOUT:
            logger.info(f"Idle for {idle:.0f}s (timeout: {config.IDLE_TIMEOUT}s) — shutting down")
            request_shutdown()
            break


def run_server():
    """Run uvicorn in a thread so we can also run the tray."""
    uvicorn_config = uvicorn.Config(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level="warning",  # uvicorn's own logs, our logs are separate
        access_log=False,
    )
    server = uvicorn.Server(uvicorn_config)
    server.run()


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PRC Tray")
    parser.add_argument("--no-tray", action="store_true", help="Run without system tray icon")
    args = parser.parse_args()

    # Wire up shutdown callback
    set_shutdown_callback(request_shutdown)

    # Signal handlers
    signal.signal(signal.SIGINT, lambda *_: request_shutdown())
    signal.signal(signal.SIGTERM, lambda *_: request_shutdown())

    logger.info(f"Starting PRC Tray on http://{config.HOST}:{config.PORT}")
    logger.info(f"Shutdown secret: {config.SHUTDOWN_SECRET}")
    logger.info(f"Idle timeout: {config.IDLE_TIMEOUT}s")

    # Start idle watchdog
    watchdog = threading.Thread(target=idle_watchdog, daemon=True)
    watchdog.start()

    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    if args.no_tray:
        # Headless mode — block until shutdown
        logger.info("Running in headless mode (no tray)")
        _shutdown_event.wait()
    else:
        # Tray mode
        from tray import create_tray
        tray = create_tray(on_exit=request_shutdown)
        if tray:
            logger.info("Tray icon active")
            # pystray blocks on run(), so we need to stop it on shutdown
            def stop_tray_on_shutdown():
                _shutdown_event.wait()
                try:
                    tray.stop()
                except Exception:
                    pass

            tray_watcher = threading.Thread(target=stop_tray_on_shutdown, daemon=True)
            tray_watcher.start()

            try:
                tray.run()
            except Exception as e:
                logger.warning(f"Tray error: {e}")
        else:
            logger.info("No tray available, running headless")
            _shutdown_event.wait()

    # Cleanup
    logger.info("Daemon stopped")
    sys.exit(0)


if __name__ == "__main__":
    main()
