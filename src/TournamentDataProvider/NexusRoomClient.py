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
        self._connection_generation = 0
        self.worker_thread = None
        self.current_session = None
        self.current_response = None
        self.slug = None
        self.token = None
        self.stream_url = None
        self.snapshot_url = None

    @staticmethod
    def is_valid_nexus_host(netloc: str) -> bool:
        """Validate host is thenexus.gg, a subdomain (e.g. qa.thenexus.gg), Cloud Run, or localhost."""
        if not netloc:
            return False
        host = netloc.split(":")[0].lower()
        if host in ("localhost", "127.0.0.1"):
            return True
        if host == "thenexus.gg" or host.endswith(".thenexus.gg"):
            return True
        if host.endswith(".a.run.app"):
            return True
        return False

    def parse_url(self, raw_url: str):
        raw_url = raw_url.strip()
        if not raw_url:
            raise ValueError("URL cannot be empty.")

        # Ensure scheme is present for urlparse
        if not re.match(r"^[a-zA-Z]+://", raw_url):
            if raw_url.startswith("localhost") or raw_url.startswith("127.0.0.1"):
                raw_url = "http://" + raw_url
            else:
                raw_url = "https://" + raw_url

        parsed = urlparse(raw_url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc

        if not self.is_valid_nexus_host(netloc):
            raise ValueError(
                f'Invalid host "{netloc}". URL must be from thenexus.gg, qa.thenexus.gg, Cloud Run, or localhost.'
            )

        origin = f"{scheme}://{netloc}"
        query = parse_qs(parsed.query)
        token = query.get("token", [None])[0]

        # Extract slug from path: e.g. /matches/slug-123/live or /api/live-match/slug-123 or /room/slug-123
        path = parsed.path.strip("/")
        match = re.search(r"(?:matches|live-match|room)/([^/?#]+)", path)
        if not match:
            raise ValueError(
                "Could not find match slug in URL. Expected path containing /matches/<slug> or /room/<slug>."
            )
        slug = match.group(1)

        return origin, slug, token

    def connect_url(self, raw_url: str):
        self.disconnect()

        try:
            origin, slug, token = self.parse_url(raw_url)
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[NexusRoomClient] Failed to parse URL '{raw_url}': {err_msg}")
            self.signals.error_occurred.emit(err_msg)
            self.signals.connection_status_changed.emit(False, "Invalid URL")
            return False, err_msg

        if not slug:
            err_msg = "Could not find match slug in URL."
            self.signals.error_occurred.emit(err_msg)
            self.signals.connection_status_changed.emit(False, "Missing Slug")
            return False, err_msg

        self.slug = slug
        self.token = token
        token_param = f"?token={token}" if token else ""
        self.stream_url = f"{origin}/api/live-match/{slug}/stream{token_param}"
        self.snapshot_url = f"{origin}/api/live-match/{slug}{token_param}"

        parsed_origin = urlparse(origin)
        host = parsed_origin.netloc.split(":")[0].lower()
        # Firebase Hosting (used by thenexus.gg and *.thenexus.gg) buffers chunked SSE responses from Cloud Run rewrites.
        # For these domains, we immediately start in snapshot polling mode (every 2s), matching the web app.
        # Direct Cloud Run (*.a.run.app) or localhost can use real-time SSE streaming with fallback to polling.
        use_polling = host == "thenexus.gg" or host.endswith(".thenexus.gg")

        self._connection_generation += 1
        current_gen = self._connection_generation
        self.is_running = True

        target_worker = self._polling_worker if use_polling else self._stream_worker
        worker_name = f"Nexus{'Poll' if use_polling else 'Stream'}-{slug}-{current_gen}"

        self.worker_thread = threading.Thread(
            target=target_worker,
            args=(current_gen,),
            daemon=True,
            name=worker_name,
        )
        self.worker_thread.start()
        return True, ""

    def disconnect(self):
        self.is_running = False
        self._connection_generation += 1

        # 1. Forcibly close active HTTP streaming response to unblock reading socket
        if self.current_response:
            try:
                self.current_response.close()
                if hasattr(self.current_response, "raw") and self.current_response.raw:
                    self.current_response.raw.close()
                    sock = getattr(self.current_response.raw, "_fp", None)
                    if sock and hasattr(sock, "close"):
                        sock.close()
            except Exception:
                pass
            self.current_response = None

        # 2. Close session adapter pool
        if self.current_session:
            try:
                self.current_session.close()
            except Exception:
                pass
            self.current_session = None

        # 3. Wait briefly for worker thread to terminate cleanly
        if self.worker_thread and self.worker_thread.is_alive():
            if threading.current_thread() != self.worker_thread:
                self.worker_thread.join(timeout=0.5)
            self.worker_thread = None

        self.slug = None
        self.token = None
        self.signals.connection_status_changed.emit(False, "Disconnected")

    def _fetch_snapshot(self, session=None):
        try:
            s = session or self.current_session or requests
            resp = s.get(self.snapshot_url, timeout=5)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    return True, data, 200
                except Exception as json_err:
                    logger.warning(f"[NexusRoomClient] Snapshot JSON decode error: {json_err}")
                    return False, None, 200
            elif resp.status_code == 401:
                return False, None, 401
            elif resp.status_code == 404:
                return False, None, 404
            elif resp.status_code == 429:
                return False, None, 429
            else:
                logger.warning(
                    f"[NexusRoomClient] Snapshot HTTP {resp.status_code}: {resp.text}"
                )
                return False, None, resp.status_code
        except Exception as e:
            logger.debug(f"[NexusRoomClient] Snapshot fetch failed: {e}")
            return False, None, 0

    def _polling_worker(self, generation: int):
        logger.info(
            f"[NexusRoomClient] Starting polling client for {self.slug} (gen {generation})"
        )
        self.signals.connection_status_changed.emit(False, f"Connecting to {self.slug}...")

        session = requests.Session()
        self.current_session = session
        last_payload_str = None
        consecutive_errors = 0
        is_connected = False

        while self.is_running and self._connection_generation == generation:
            success, data, status_code = self._fetch_snapshot(session)

            if not self.is_running or self._connection_generation != generation:
                break

            if success and data is not None:
                consecutive_errors = 0
                if not is_connected:
                    is_connected = True
                    self.signals.connection_status_changed.emit(
                        True, f"Connected ({self.slug})"
                    )

                try:
                    payload_str = json.dumps(data, sort_keys=True)
                except Exception:
                    payload_str = None

                if payload_str != last_payload_str:
                    last_payload_str = payload_str
                    self.signals.room_updated.emit(data)

                poll_delay = 2.0
            elif status_code == 401:
                self.signals.error_occurred.emit(
                    "Unauthorized: Invalid or expired Nexus stream token."
                )
                self.signals.connection_status_changed.emit(
                    False, "Unauthorized (Token Expired)"
                )
                self.is_running = False
                break
            elif status_code == 404:
                self.signals.error_occurred.emit(
                    f"Match room '{self.slug}' not found on server (HTTP 404)."
                )
                self.signals.connection_status_changed.emit(
                    False, "Room Not Found (404)"
                )
                self.is_running = False
                break
            elif status_code == 429:
                logger.warning(
                    "[NexusRoomClient] Server returned 429 Too Many Requests (Rate exceeded). Backing off for 15s..."
                )
                self.signals.connection_status_changed.emit(
                    False, "Rate Limited (429)"
                )
                poll_delay = 15.0
            else:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    if is_connected:
                        is_connected = False
                        self.signals.connection_status_changed.emit(False, "Reconnecting...")
                poll_delay = min(2.0 * (1.5 ** min(consecutive_errors, 5)), 15.0)

            # Interruptible sleep in 0.2s slices
            sleep_ticks = int(poll_delay / 0.2)
            for _ in range(sleep_ticks):
                if not self.is_running or self._connection_generation != generation:
                    break
                time.sleep(0.2)

        if self._connection_generation == generation:
            self.signals.connection_status_changed.emit(False, "Disconnected")

    def _stream_worker(self, generation: int):
        logger.info(
            f"[NexusRoomClient] Starting stream client for {self.slug} (gen {generation})"
        )
        self.signals.connection_status_changed.emit(False, f"Connecting to {self.slug}...")

        # 1. Fetch initial snapshot for instant UI hydration
        success, initial_data, status_code = self._fetch_snapshot()
        if not self.is_running or self._connection_generation != generation:
            return

        if success and initial_data is not None:
            self.signals.room_updated.emit(initial_data)
            self.signals.connection_status_changed.emit(
                True, f"Connected ({self.slug})"
            )
        elif status_code == 401:
            self.signals.error_occurred.emit(
                "Unauthorized: Invalid or expired Nexus stream token."
            )
            self.signals.connection_status_changed.emit(
                False, "Unauthorized (Token Expired)"
            )
            self.is_running = False
            return
        elif status_code == 404:
            self.signals.error_occurred.emit(
                f"Match room '{self.slug}' not found on server (HTTP 404)."
            )
            self.signals.connection_status_changed.emit(
                False, "Room Not Found (404)"
            )
            self.is_running = False
            return

        backoff_delay = 3

        while self.is_running and self._connection_generation == generation:
            try:
                session = requests.Session()
                self.current_session = session
                logger.info(f"[NexusRoomClient] Connecting to {self.stream_url}")

                # Use a 5s read timeout for response headers so we detect buffering edge proxies fast
                with session.get(
                    self.stream_url,
                    stream=True,
                    timeout=(5, 30),
                    headers={"Accept": "text/event-stream"},
                ) as resp:
                    if not self.is_running or self._connection_generation != generation:
                        break

                    self.current_response = resp

                    if resp.status_code == 401:
                        self.signals.error_occurred.emit(
                            "Unauthorized: Invalid or expired Nexus stream token."
                        )
                        self.signals.connection_status_changed.emit(
                            False, "Unauthorized (Token Expired)"
                        )
                        self.is_running = False
                        break

                    if resp.status_code == 404:
                        self.signals.error_occurred.emit(
                            f"Match room '{self.slug}' not found on server (HTTP 404)."
                        )
                        self.signals.connection_status_changed.emit(
                            False, "Room Not Found (404)"
                        )
                        self.is_running = False
                        break

                    if resp.status_code == 429:
                        logger.warning(
                            "[NexusRoomClient] Server returned 429 Too Many Requests (Rate exceeded). Backing off for 15s..."
                        )
                        self.signals.connection_status_changed.emit(
                            False, "Rate Limited (429)"
                        )
                        for _ in range(15):
                            if not self.is_running or self._connection_generation != generation:
                                break
                            time.sleep(1)
                        continue

                    if resp.status_code != 200:
                        self.signals.connection_status_changed.emit(
                            False, f"HTTP {resp.status_code}"
                        )
                        time.sleep(backoff_delay)
                        backoff_delay = min(backoff_delay * 1.5, 30)
                        continue

                    # Validate that response is an event-stream
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "text/event-stream" not in content_type:
                        logger.info(
                            f"[NexusRoomClient] Not text/event-stream ({content_type}). Falling back to snapshot polling."
                        )
                        self._polling_worker(generation)
                        return

                    self.signals.connection_status_changed.emit(
                        True, f"Connected ({self.slug})"
                    )
                    backoff_delay = 3

                    try:
                        for raw_line in resp.iter_lines(decode_unicode=True):
                            if not self.is_running or self._connection_generation != generation:
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
                    finally:
                        self.current_response = None

            except Exception as e:
                if not self.is_running or self._connection_generation != generation:
                    break
                logger.info(
                    f"[NexusRoomClient] Stream disconnected or buffered ({e}). Falling back to snapshot polling."
                )
                self._polling_worker(generation)
                return

        if self._connection_generation == generation:
            self.signals.connection_status_changed.emit(False, "Disconnected")
