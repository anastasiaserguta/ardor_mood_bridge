import os
import threading
import time
import traceback


MOD_NAME = "ArdorMood"
POLL_SECONDS = 0.25


def _sims4_dir():
    return os.path.join(os.path.expanduser("~"), "Documents", "Electronic Arts", "The Sims 4")


MOOD_FILE = os.path.join(_sims4_dir(), "ardor_mood.txt")
LOG_FILE = os.path.join(_sims4_dir(), "ardor_mood_mod.log")

_started = False
_last_payload = None
_last_wait_log = 0


def _log(message):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as stream:
            stream.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))
    except Exception:
        pass


def _normalize_mood_name(mood):
    raw = getattr(mood, "__name__", None)
    if raw is None:
        raw = str(mood)

    raw = raw.strip()

    if "_" in raw:
        raw = raw.split("_", 1)[-1]

    return raw or "Unknown"


def _active_sim_mood():
    import services

    try:
        client_manager = services.client_manager()
    except Exception:
        return None

    if client_manager is None:
        return None

    client = client_manager.get_first_client()
    if client is None:
        return None

    active_sim = getattr(client, "active_sim", None)
    if active_sim is None:
        return None

    sim_info = getattr(active_sim, "sim_info", None)
    if sim_info is None:
        return None

    mood = sim_info.get_mood()
    intensity = sim_info.get_mood_intensity()
    mood_name = _normalize_mood_name(mood)

    sim_name = ""
    try:
        sim_name = sim_info.full_name
    except Exception:
        sim_name = ""

    if not sim_name:
        try:
            first_name = getattr(sim_info, "first_name", "") or ""
            last_name = getattr(sim_info, "last_name", "") or ""
            sim_name = ("%s %s" % (first_name, last_name)).strip()
        except Exception:
            sim_name = ""

    if not sim_name:
        try:
            sim_name = str(sim_info)
        except Exception:
            sim_name = ""

    try:
        sim_id = str(sim_info.sim_id)
    except Exception:
        sim_id = ""

    return mood_name, intensity, sim_name, sim_id


def _write_mood(payload):
    mood_name, intensity, sim_name, sim_id = payload
    temp_path = MOOD_FILE + ".tmp"
    text = "%s\n%s\n%s\n%s\n%s\n" % (mood_name, intensity, sim_name, sim_id, int(time.time()))

    with open(temp_path, "w", encoding="utf-8") as stream:
        stream.write(text)

    os.replace(temp_path, MOOD_FILE)


def _worker():
    global _last_payload
    global _last_wait_log

    _log("worker started")

    while True:
        try:
            payload = _active_sim_mood()
            if payload is not None and payload != _last_payload:
                _write_mood(payload)
                _last_payload = payload
                _log("mood=%s intensity=%s sim=%s id=%s" % payload)
            elif payload is None:
                now = time.time()
                if now - _last_wait_log > 30:
                    _last_wait_log = now
                    _log("waiting for active sim")
        except Exception:
            _log("error:\n%s" % traceback.format_exc())

        time.sleep(POLL_SECONDS)


def _start():
    global _started

    if _started:
        return

    _started = True
    _log("loaded")

    thread = threading.Thread(target=_worker)
    thread.daemon = True
    thread.start()


_start()
