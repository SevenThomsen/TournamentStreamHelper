import json
import re
import threading
import time
from urllib.parse import parse_qs, urlparse

from loguru import logger
from qtpy.QtCore import QObject, Signal
import requests


class NexusRoomClientSignals(QObject):
    room_updated = Signal(dict)
    connection_status_changed = Signal(bool, str)
    error_occurred = Signal(str)


class NexusRoomClient(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = NexusRoomClientSignals()
        self.is_running = False
        self.worker_thread = None
        self.current_session = None
        self.slug = None
        self.token = None
        self.stream_url = None
        self.snapshot_url = None

    def parse_url(self, raw_url: str):
        raw_url = raw_url.strip()
        parsed = urlparse(raw_url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc or "thenexus.gg"
        origin = f"{scheme}://{netloc}"

        query = parse_qs(parsed.query)
        token = query.get("token", [None])[0]

        # Extract slug from path: e.g. /matches/slug-123/live or /api/live-match/slug-123
        path = parsed.path.strip("/")
        match = re.search(r'(?:matches|live-match|room)/([^/]+)', path)
        slug = match.group(1) if match else path.split("/")[-1]

        return origin, slug, token

    def connect_url(self, raw_url: str):
        self.disconnect()

        try:
            origin, slug, token = self.parse_url(raw_url)
        except Exception as e:
            logger.error(f"[NexusRoomClient] Failed to parse URL '{raw_url}': {e}")
            self.signals.error_occurred.emit(f"Invalid Nexus URL: {e}")
            return False

        if not slug:
            self.signals.error_occurred.emit("Could not find match slug in URL.")
            return False

        self.slug = slug
        self.token = token
        token_param = f"?token={token}" if token else ""
        self.stream_url = f"{origin}/api/live-match/{slug}/stream{token_param}"
        self.snapshot_url = f"{origin}/api/live-match/{slug}{token_param}"

        self.is_running = True
        self.worker_thread = threading.Thread(
            target=self._stream_worker, daemon=True, name=f"NexusStream-{slug}"
        )
        self.worker_thread.start()
        return True

    def disconnect(self):
        self.is_running = False
        if self.current_session:
            try:
                self.current_session.close()
            except Exception:
                pass
            self.current_session = None

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread = None

        self.slug = None
        self.token = None
        self.signals.connection_status_changed.emit(False, "Disconnected")

    def _fetch_snapshot(self):
        try:
            resp = requests.get(self.snapshot_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.signals.room_updated.emit(data)
                return True
            else:
                logger.warning(
                    f"[NexusRoomClient] Snapshot HTTP {resp.status_code}: {resp.text}"
                )
        except Exception as e:
            logger.debug(f"[NexusRoomClient] Initial snapshot fetch failed: {e}")
        return False

    def _stream_worker(self):
        logger.info(f"[NexusRoomClient] Starting stream client for {self.slug}")
        self.signals.connection_status_changed.emit(False, f"Connecting to {self.slug}...")

        # Immediate pre-fetch for instant UI population
        self._fetch_snapshot()

        while self.is_running:
            try:
                self.current_session = requests.Session()
                logger.info(f"[NexusRoomClient] Connecting to {self.stream_url}")

                with self.current_session.get(
                    self.stream_url,
                    stream=True,
                    timeout=(10, 60),
                    headers={"Accept": "text/event-stream"},
                ) as resp:
                    if resp.status_code == 401:
                        self.signals.error_occurred.emit(
                            "Unauthorized: Invalid or expired Nexus stream token."
                        )
                        self.signals.connection_status_changed.emit(
                            False, "Unauthorized (Token Expired)"
                        )
                        self.is_running = False
                        break

                    if resp.status_code != 200:
                        self.signals.connection_status_changed.emit(
                            False, f"HTTP {resp.status_code}"
                        )
                        time.sleep(3)
                        continue

                    self.signals.connection_status_changed.emit(
                        True, f"Connected ({self.slug})"
                    )

                    for raw_line in resp.iter_lines(decode_unicode=True):
                        if not self.is_running:
                            break

                        if not raw_line:
                            continue

                        line = raw_line.strip()
                        if line.startswith("data:"):
                            payload_str = line[5:].strip()
                            try:
                                payload = json.loads(payload_str)
                                self.signals.room_updated.emit(payload)
                            except Exception as parse_err:
                                logger.error(
                                    f"[NexusRoomClient] JSON parse error: {parse_err}"
                                )

            except Exception as e:
                if not self.is_running:
                    break
                logger.warning(f"[NexusRoomClient] Stream disconnected: {e}. Reconnecting in 3s...")
                self.signals.connection_status_changed.emit(False, "Reconnecting...")
                time.sleep(3)

        self.signals.connection_status_changed.emit(False, "Disconnected")
