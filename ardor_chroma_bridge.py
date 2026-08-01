import argparse
import ctypes
import logging
import os
import time
import uuid
from threading import Lock, Thread

from flask import Flask, jsonify, request
import hid

from ardor_mood_colors import (
    DEFAULT_MOOD_COLORS,
    default_color_config_path,
    load_mood_colors,
    normalize_mood_name,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("SimsArdorBridge")
logging.getLogger("werkzeug").setLevel(logging.WARNING)

app = Flask(__name__)

VENDOR_ID = 0x320F
PRODUCT_ID = 0x5055

BASE = "/razer/chromasdk"
SESSION_ID = 12345

EVISION_USAGE_PAGE = 0xFF1C
EVISION_CMD_BEGIN = 0x01
EVISION_CMD_END = 0x02
EVISION_CMD_SET_PARAMETER = 0x06
EVISION_CMD_WRITE_CUSTOM_COLOR_DATA = 0x11
EVISION_MODE_STATIC = 0x06
EVISION_MODE_CUSTOM = 0x14
EVISION_BRIGHTNESS_HIGHEST = 0x04
EVISION_SPEED_NORMAL = 0x03
EVISION_MAX_COLOR_PACKET_SIZE = 0x36

hid_lock = Lock()
effect_cache = {}
selected_hid_path = None
selected_protocol = "auto"
selected_transport = "write"
selected_brightness = EVISION_BRIGHTNESS_HIGHEST
selected_color_config_path = None
color_cache = {}
color_cache_mtime = None


def format_hex(value):
    if value is None:
        return "None"
    return f"0x{int(value):04X}"


def list_hid_devices():
    devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)

    if not devices:
        logger.warning("HID: Устройства %04X:%04X не найдены.", VENDOR_ID, PRODUCT_ID)
        return []

    logger.info("HID: Найдено интерфейсов для %04X:%04X: %s", VENDOR_ID, PRODUCT_ID, len(devices))

    for idx, device in enumerate(devices):
        logger.info("")
        logger.info("[%s]", idx)
        logger.info("path: %r", device.get("path"))
        logger.info("manufacturer_string: %s", device.get("manufacturer_string"))
        logger.info("product_string: %s", device.get("product_string"))
        logger.info("serial_number: %s", device.get("serial_number"))
        logger.info("interface_number: %s", device.get("interface_number"))
        logger.info("usage_page: %s", format_hex(device.get("usage_page")))
        logger.info("usage: %s", format_hex(device.get("usage")))

    return devices


def json_safe_hid_device(device):
    result = {}

    for key, value in device.items():
        if isinstance(value, bytes):
            result[key] = value.decode("utf-8", errors="replace")
        else:
            result[key] = value

    return result


def choose_hid_path(path_index=None, path_contains=None):
    devices = list_hid_devices()

    if not devices:
        raise RuntimeError("Клавиатура не найдена.")

    if path_index is not None:
        if path_index < 0 or path_index >= len(devices):
            raise RuntimeError(f"Нет HID-интерфейса с индексом {path_index}.")
        logger.info("HID: Выбран интерфейс по индексу %s.", path_index)
        return devices[path_index]["path"]

    if path_contains:
        needle = path_contains.lower()
        for device in devices:
            path_text = repr(device.get("path", b"")).lower()
            if needle in path_text:
                logger.info("HID: Выбран интерфейс по фрагменту path: %s.", path_contains)
                return device["path"]

    for device in devices:
        if device.get("usage_page") == EVISION_USAGE_PAGE:
            logger.info("HID: Выбран интерфейс по usage_page %s.", format_hex(EVISION_USAGE_PAGE))
            return device["path"]

    for device in devices:
        if device.get("interface_number") == 1 and device.get("usage_page") != 0x0001:
            logger.info("HID: Выбран interface_number=1 не из keyboard usage page.")
            return device["path"]

    for device in devices:
        if device.get("interface_number") == 1:
            logger.warning("HID: Беру interface_number=1, но он похож на обычную клавиатуру.")
            return device["path"]

    logger.warning("HID: Не нашла явный RGB-интерфейс, беру первый найденный.")
    return devices[0]["path"]


def evision_checksum(packet):
    total = sum(packet[3:64])
    packet[1] = total & 0xFF
    packet[2] = (total >> 8) & 0xFF


def hid_write_read(dev, packet, label, read_response=True):
    written = 0

    if selected_transport in ("set_output", "both"):
        ok = native_set_output_report(selected_hid_path, packet)
        logger.debug("HID %s: set_output_report %s: %s ...", label, ok, packet[:16])
        written = len(packet) if ok else -1

    if selected_transport in ("write", "both"):
        written = dev.write(packet)
        logger.debug("HID %s: write %s bytes: %s ...", label, written, packet[:16])

    if read_response and selected_transport in ("write", "both"):
        try:
            response = dev.read(64, timeout_ms=200)
            logger.debug("HID %s: read: %s ...", label, response[:16])
        except Exception as exc:
            logger.debug("HID %s: read timeout/error: %s", label, exc)

    return written


def path_to_windows_string(path):
    if isinstance(path, bytes):
        return path.decode("utf-8", errors="replace")
    return str(path)


def native_set_output_report(path, packet):
    if os.name != "nt":
        logger.error("HID: HidD_SetOutputReport доступен только на Windows.")
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    hid_dll = ctypes.WinDLL("hid", use_last_error=True)

    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p

    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_int

    hid_set_output_report = hid_dll.HidD_SetOutputReport
    hid_set_output_report.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
    hid_set_output_report.restype = ctypes.c_ubyte

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x00000080
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    handle = create_file(
        path_to_windows_string(path),
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )

    if handle == INVALID_HANDLE_VALUE:
        logger.error("HID: CreateFileW failed, GetLastError=%s", ctypes.get_last_error())
        return False

    try:
        report = (ctypes.c_ubyte * len(packet))(*packet)
        ok = bool(hid_set_output_report(handle, report, len(packet)))

        if not ok:
            logger.error("HID: HidD_SetOutputReport failed, GetLastError=%s", ctypes.get_last_error())

        return ok

    finally:
        close_handle(handle)


def parse_hex_bytes(text):
    cleaned = (
        text.replace(",", " ")
        .replace(":", " ")
        .replace(";", " ")
        .replace("\\x", " ")
        .replace("0x", " ")
    )
    values = []

    for part in cleaned.split():
        values.append(int(part, 16) & 0xFF)

    return values


def clamp_brightness(value):
    return max(1, min(4, int(value)))


def evision_simple_command(dev, command):
    packet = [0x00] * 64
    packet[0] = 0x04
    packet[1] = command
    packet[2] = 0x00
    packet[3] = command
    hid_write_read(dev, packet, f"evision-cmd-{command:02X}")


def evision_set_mode_ex(dev, mode, red, green, blue):
    packet = [0x00] * 64
    packet[0] = 0x04
    packet[3] = EVISION_CMD_SET_PARAMETER
    packet[4] = 8
    packet[5] = 0
    packet[8] = mode
    packet[9] = selected_brightness
    packet[10] = EVISION_SPEED_NORMAL
    packet[11] = 0
    packet[12] = 0
    packet[13] = red
    packet[14] = green
    packet[15] = blue
    evision_checksum(packet)
    hid_write_read(dev, packet, "evision-mode-ex")


def evision_send_custom_data(dev, color_data):
    packet_offset = 0

    while packet_offset < len(color_data):
        chunk = color_data[packet_offset:packet_offset + EVISION_MAX_COLOR_PACKET_SIZE]
        packet = [0x00] * 64
        packet[0] = 0x04
        packet[3] = EVISION_CMD_WRITE_CUSTOM_COLOR_DATA
        packet[4] = len(chunk)
        packet[5] = packet_offset & 0xFF
        packet[6] = (packet_offset >> 8) & 0xFF
        packet[8:8 + len(chunk)] = chunk
        evision_checksum(packet)
        hid_write_read(dev, packet, "evision-custom-data")
        packet_offset += len(chunk)


def send_evision_static(dev, red, green, blue):
    evision_set_mode_ex(dev, EVISION_MODE_STATIC, red, green, blue)


def send_evision_custom(dev, red, green, blue):
    color_data = []

    for _ in range(108):
        color_data.extend([red, green, blue])

    evision_simple_command(dev, EVISION_CMD_BEGIN)
    evision_send_custom_data(dev, color_data)
    evision_simple_command(dev, EVISION_CMD_END)
    evision_set_mode_ex(dev, EVISION_MODE_CUSTOM, red, green, blue)


def send_official_static(dev, red, green, blue):
    evision_simple_command(dev, EVISION_CMD_BEGIN)
    time.sleep(0.002)

    packet = [0x00] * 64
    packet[0] = 0x04
    packet[3] = EVISION_CMD_SET_PARAMETER
    packet[4] = 0x22
    packet[9] = EVISION_MODE_STATIC
    packet[10] = selected_brightness
    packet[12] = 0xFF
    packet[14] = red
    packet[15] = green
    packet[16] = blue
    packet[17] = EVISION_MODE_STATIC
    packet[26] = EVISION_SPEED_NORMAL
    packet[28] = 0xFF
    evision_checksum(packet)
    hid_write_read(dev, packet, "official-static")
    time.sleep(0.02)

    evision_simple_command(dev, EVISION_CMD_END)


def send_legacy_direct(dev, red, green, blue):
    init_packet = [0x00] * 65
    init_packet[1] = 0x05
    init_packet[2] = 0x01
    init_packet[3] = 0x01
    hid_write_read(dev, init_packet, "legacy-init", read_response=False)
    time.sleep(0.01)

    for packet_idx in range(4):
        payload = [packet_idx, 15]

        for _ in range(15):
            payload.extend([red, green, blue])

        packet = [0x00] * 65
        packet[1] = 0x05
        packet[2] = 0x02

        for i, value in enumerate(payload):
            if i + 3 < len(packet):
                packet[i + 3] = value & 0xFF

        hid_write_read(dev, packet, f"legacy-rgb-{packet_idx}", read_response=False)
        time.sleep(0.002)


def guardian17_send_packet(dev, channel_group, command, values):
    packet = [0x00] * 64
    packet[0] = 0x04
    packet[1] = 0xFF
    packet[2] = channel_group
    packet[3] = command

    for idx, value in enumerate(values):
        if idx + 4 < len(packet):
            packet[idx + 4] = int(value) & 0xFF

    hid_write_read(dev, packet, f"guardian17-{channel_group:02X}-{command:02X}")


def send_guardian17(dev, red, green, blue):
    # Guardian.exe uses 17-byte HidD_SetOutputReport packets for lighting data.
    # It clamps color channel values to 0xF7 before sending.
    red = min(int(red) & 0xFF, 0xF7)
    green = min(int(green) & 0xFF, 0xF7)
    blue = min(int(blue) & 0xFF, 0xF7)

    channels = [
        (0xAA, 0xAD, red),
        (0xAB, 0xAE, green),
        (0xAC, 0xAF, blue),
    ]

    for first_command, second_command, value in channels:
        first_chunk = [value] * 7
        second_chunk = [value] * 6

        for channel_group in (0x22, 0x44):
            guardian17_send_packet(dev, channel_group, first_command, first_chunk)
            time.sleep(0.002)
            guardian17_send_packet(dev, channel_group, second_command, second_chunk)
            time.sleep(0.002)


def open_selected_device():
    if selected_hid_path is None:
        raise RuntimeError("HID path не выбран.")

    dev = hid.device()
    dev.open_path(selected_hid_path)
    return dev


def send_rgb_to_keyboard(red, green, blue):
    red = int(red) & 0xFF
    green = int(green) & 0xFF
    blue = int(blue) & 0xFF

    with hid_lock:
        dev = None
        try:
            dev = open_selected_device()

            if selected_protocol == "evision_static":
                send_evision_static(dev, red, green, blue)
            elif selected_protocol == "evision_custom":
                send_evision_custom(dev, red, green, blue)
            elif selected_protocol == "official_static":
                send_official_static(dev, red, green, blue)
            elif selected_protocol == "legacy_direct":
                send_legacy_direct(dev, red, green, blue)
            elif selected_protocol == "guardian17":
                send_guardian17(dev, red, green, blue)
            elif selected_protocol == "auto":
                send_official_static(dev, red, green, blue)
                time.sleep(0.05)
                send_evision_static(dev, red, green, blue)
                time.sleep(0.05)
                send_evision_custom(dev, red, green, blue)
                time.sleep(0.05)
                send_legacy_direct(dev, red, green, blue)
                time.sleep(0.05)
                send_guardian17(dev, red, green, blue)
            else:
                raise RuntimeError(f"Неизвестный протокол: {selected_protocol}")

            return True

        except Exception as exc:
            logger.error("HID: Не удалось отправить RGB(%s, %s, %s): %s", red, green, blue, exc)
            return False

        finally:
            if dev:
                try:
                    dev.close()
                except Exception:
                    pass


def default_mood_file_path():
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(home, "Documents", "Electronic Arts", "The Sims 4", "ardor_mood.txt")


def get_mood_colors():
    global color_cache
    global color_cache_mtime

    path = selected_color_config_path or default_color_config_path()

    try:
        current_mtime = os.path.getmtime(path)
    except OSError:
        current_mtime = None

    if not color_cache or current_mtime != color_cache_mtime:
        try:
            color_cache = load_mood_colors(path)
            color_cache_mtime = current_mtime
            if current_mtime is None:
                logger.debug("Mood colors: использую встроенную палитру.")
            else:
                logger.info("Mood colors: загружен конфиг %s", path)
        except Exception as exc:
            logger.error("Mood colors: не удалось прочитать %s: %s", path, exc)
            color_cache = dict(DEFAULT_MOOD_COLORS)
            color_cache_mtime = current_mtime

    return color_cache


def mood_to_rgb(name):
    mood = normalize_mood_name(name)
    return get_mood_colors().get(mood)


def parse_mood_intensity(value):
    text = str(value or "").strip().lower()

    if not text:
        return 0.0

    try:
        return float(text)
    except ValueError:
        pass

    for marker in ("extreme", "enraged", "hysterical", "mortified", "terrified"):
        if marker in text:
            return 2.0

    for marker in ("very", "high", "strong"):
        if marker in text:
            return 1.0

    return 0.0


def mood_to_rgb_for_intensity(name, intensity):
    mood = normalize_mood_name(name)
    value = parse_mood_intensity(intensity)
    colors = get_mood_colors()
    candidates = []

    if mood in ("angry", "playful", "embarrassed", "scared") and value >= 2:
        candidates.append(f"{mood}_extreme")

    if mood == "terrified" and value >= 1:
        candidates.append("terrified_very")

    if value >= 1:
        candidates.append(f"{mood}_very")

    candidates.append(mood)

    for candidate in candidates:
        rgb = colors.get(candidate)
        if rgb:
            return candidate, rgb

    return mood, None


def configure_bridge(
    path_index=None,
    path_contains=None,
    protocol="official_static",
    transport="write",
    color_config=None,
    brightness=EVISION_BRIGHTNESS_HIGHEST,
):
    global selected_hid_path
    global selected_protocol
    global selected_transport
    global selected_brightness
    global selected_color_config_path
    global color_cache
    global color_cache_mtime

    selected_protocol = protocol
    selected_transport = transport
    selected_brightness = clamp_brightness(brightness)
    selected_color_config_path = color_config or default_color_config_path()
    color_cache = {}
    color_cache_mtime = None
    selected_hid_path = choose_hid_path(path_index, path_contains)

    logger.info("HID: Активный path: %r", selected_hid_path)
    logger.info("HID: Протокол: %s", selected_protocol)
    logger.info("HID: Транспорт: %s", selected_transport)
    logger.info("HID: Яркость: %s/4", selected_brightness)
    logger.info("Mood colors: конфиг %s", selected_color_config_path)

    return selected_hid_path


def read_mood_file(path):
    with open(path, "r", encoding="utf-8") as stream:
        lines = [line.strip() for line in stream.readlines()]

    if not lines:
        return None

    mood = lines[0]
    intensity = lines[1] if len(lines) > 1 else ""
    sim_name = lines[2] if len(lines) > 2 else ""
    sim_id = lines[3] if len(lines) > 3 else ""
    timestamp = lines[4] if len(lines) > 4 else ""
    return mood, intensity, sim_name, sim_id, timestamp


def mood_watch_loop(path, interval, stop_event=None):
    logger.info("Mood watch: читаю %s", path)
    last_seen = None
    last_rgb = None

    while not (stop_event and stop_event.is_set()):
        try:
            payload = read_mood_file(path)

            if payload and payload != last_seen:
                mood, intensity, sim_name, sim_id, timestamp = payload
                color_key, rgb = mood_to_rgb_for_intensity(mood, intensity)

                if rgb:
                    logger.info(
                        "Mood watch: %s intensity=%s color=%s sim=%s id=%s -> RGB%s",
                        mood,
                        intensity,
                        color_key,
                        sim_name,
                        sim_id,
                        rgb,
                    )
                    if rgb != last_rgb:
                        send_rgb_to_keyboard(*rgb)
                        last_rgb = rgb
                else:
                    logger.warning("Mood watch: неизвестное настроение %r из %s", mood, path)

                last_seen = payload

        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.error("Mood watch: ошибка чтения %s: %s", path, exc)

        if stop_event:
            stop_event.wait(interval)
        else:
            time.sleep(interval)

    logger.info("Mood watch: остановлен.")


def start_mood_watch(path, interval, stop_event=None):
    thread = Thread(target=mood_watch_loop, args=(path, interval, stop_event), daemon=True)
    thread.start()
    return thread


def bgr_int_to_rgb(color_int):
    color_int = int(color_int) & 0x00FFFFFF
    red = color_int & 0x0000FF
    green = (color_int & 0x00FF00) >> 8
    blue = (color_int & 0xFF0000) >> 16
    return red, green, blue


def extract_average_rgb(data):
    if not data:
        return None

    effect = data.get("effect")
    param = data.get("param")

    if effect == "CHROMA_STATIC" and isinstance(param, dict) and "color" in param:
        return bgr_int_to_rgb(param["color"])

    matrix = None

    if isinstance(param, list):
        matrix = param
    elif isinstance(param, dict):
        if "custom" in param:
            matrix = param["custom"]
        elif isinstance(param.get("color"), list):
            matrix = param["color"]
        elif isinstance(param.get("key"), list):
            matrix = param["key"]

    if not matrix:
        return None

    red_total = 0
    green_total = 0
    blue_total = 0
    count = 0

    for row in matrix:
        if not isinstance(row, list):
            continue

        for color_int in row:
            if not isinstance(color_int, int):
                continue

            color_int = color_int & 0x00FFFFFF

            if color_int == 0:
                continue

            red, green, blue = bgr_int_to_rgb(color_int)
            red_total += red
            green_total += green
            blue_total += blue
            count += 1

    if count == 0:
        return None

    return (
        int(red_total / count),
        int(green_total / count),
        int(blue_total / count),
    )


@app.route(BASE, methods=["GET"])
def chroma_version():
    return jsonify({
        "core": "3.26.00",
        "device": "3.26.00",
        "version": "3.26.00",
    }), 200


@app.route(BASE, methods=["POST"])
def chroma_init():
    req_data = request.get_json(silent=True) or {}
    app_title = req_data.get("title", "Unknown app")
    logger.info("Chroma SDK: init от '%s'", app_title)
    return jsonify({
        "sessionid": SESSION_ID,
        "uri": f"http://127.0.0.1:54235{BASE}/{SESSION_ID}",
    }), 200


@app.route(f"{BASE}/<int:sid>/heartbeat", methods=["PUT"])
@app.route(f"{BASE}/<int:sid>", methods=["PUT"])
@app.route("/<int:sid>/heartbeat", methods=["PUT"])
@app.route("/<int:sid>", methods=["PUT"])
def chroma_heartbeat(sid):
    logger.debug("Chroma SDK: heartbeat sid=%s", sid)
    return jsonify({"tick": int(time.time())}), 200


@app.route(f"{BASE}/<int:sid>/keyboard", methods=["PUT", "POST"])
@app.route("/<int:sid>/keyboard", methods=["PUT", "POST"])
def chroma_keyboard(sid):
    data = request.get_json(silent=True) or {}
    avg = extract_average_rgb(data)

    if avg:
        logger.info("Chroma SDK: keyboard sid=%s -> RGB%s", sid, avg)
        send_rgb_to_keyboard(*avg)
    else:
        logger.debug("Chroma SDK: keyboard frame без понятного цвета: %s", data)

    if request.method == "POST":
        effect_id = str(uuid.uuid4())
        effect_cache[effect_id] = avg
        return jsonify({"result": 0, "id": effect_id}), 200

    return jsonify({"result": 0}), 200


@app.route(f"{BASE}/<int:sid>/effect", methods=["PUT"])
@app.route("/<int:sid>/effect", methods=["PUT"])
def chroma_effect(sid):
    data = request.get_json(silent=True) or {}
    effect_id = data.get("id")
    avg = effect_cache.get(effect_id)

    if avg:
        logger.info("Chroma SDK: apply effect sid=%s id=%s -> RGB%s", sid, effect_id, avg)
        send_rgb_to_keyboard(*avg)
    else:
        logger.debug("Chroma SDK: apply effect sid=%s id=%s", sid, effect_id)

    return jsonify({"result": 0}), 200


@app.route(f"{BASE}/<int:sid>/mouse", methods=["PUT", "POST"])
@app.route(f"{BASE}/<int:sid>/mousepad", methods=["PUT", "POST"])
@app.route(f"{BASE}/<int:sid>/headset", methods=["PUT", "POST"])
@app.route(f"{BASE}/<int:sid>/keypad", methods=["PUT", "POST"])
@app.route(f"{BASE}/<int:sid>/chromalink", methods=["PUT", "POST"])
def chroma_other_devices(sid):
    return jsonify({"result": 0}), 200


@app.route("/hid/list", methods=["GET"])
def hid_list_route():
    devices = [json_safe_hid_device(device) for device in hid.enumerate(VENDOR_ID, PRODUCT_ID)]
    return jsonify(devices), 200


@app.route("/test/red", methods=["GET"])
def test_red_route():
    send_rgb_to_keyboard(255, 0, 0)
    return jsonify({"result": 0, "color": "red", "protocol": selected_protocol}), 200


@app.route("/test/green", methods=["GET"])
def test_green_route():
    send_rgb_to_keyboard(0, 255, 0)
    return jsonify({"result": 0, "color": "green", "protocol": selected_protocol}), 200


@app.route("/test/blue", methods=["GET"])
def test_blue_route():
    send_rgb_to_keyboard(0, 0, 255)
    return jsonify({"result": 0, "color": "blue", "protocol": selected_protocol}), 200


@app.route("/test/rgb/<int:red>/<int:green>/<int:blue>", methods=["GET"])
def test_rgb_route(red, green, blue):
    send_rgb_to_keyboard(red, green, blue)
    return jsonify({
        "result": 0,
        "rgb": [red & 0xFF, green & 0xFF, blue & 0xFF],
        "protocol": selected_protocol,
    }), 200


@app.route("/test/mood/<mood>", methods=["GET"])
def test_mood_route(mood):
    rgb = mood_to_rgb(mood)

    if not rgb:
        return jsonify({
            "result": 1,
            "error": "unknown mood",
            "mood": mood,
            "known": sorted(get_mood_colors()),
        }), 404

    send_rgb_to_keyboard(*rgb)
    return jsonify({
        "result": 0,
        "mood": mood,
        "rgb": rgb,
        "protocol": selected_protocol,
    }), 200


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def log_unknown_route(path):
    data = request.get_data(cache=False, as_text=True)
    logger.warning(
        "HTTP: unknown route %s %s body=%r",
        request.method,
        request.path,
        data[:500],
    )
    return jsonify({"result": 0, "unknown": request.path}), 200


def run_color_test():
    logger.info("TEST: красный")
    send_rgb_to_keyboard(255, 0, 0)
    time.sleep(1)

    logger.info("TEST: зеленый")
    send_rgb_to_keyboard(0, 255, 0)
    time.sleep(1)

    logger.info("TEST: синий")
    send_rgb_to_keyboard(0, 0, 255)
    time.sleep(1)


def send_raw_hex_report(hex_text):
    packet = parse_hex_bytes(hex_text)

    if not packet:
        raise RuntimeError("Пустой hex-пакет.")

    with hid_lock:
        dev = None
        try:
            dev = open_selected_device()
            hid_write_read(dev, packet, "raw-hex")
        finally:
            if dev:
                dev.close()


def parse_args():
    parser = argparse.ArgumentParser(description="The Sims 4 Chroma REST -> Ardor Guardian RGB bridge.")
    parser.add_argument("--list", action="store_true", help="Показать HID-интерфейсы и выйти.")
    parser.add_argument("--test", action="store_true", help="Прогнать RGB-тест без Flask.")
    parser.add_argument("--port", type=int, default=54235, help="Порт Chroma REST-сервера.")
    parser.add_argument("--path-index", type=int, default=None, help="Индекс HID-интерфейса из --list.")
    parser.add_argument("--path-contains", default=None, help="Фрагмент HID path для выбора интерфейса.")
    parser.add_argument(
        "--protocol",
        choices=("auto", "official_static", "evision_static", "evision_custom", "legacy_direct", "guardian17"),
        default=os.environ.get("ARDOR_PROTOCOL", "auto"),
        help="Протокол отправки RGB.",
    )
    parser.add_argument(
        "--transport",
        choices=("write", "set_output", "both"),
        default=os.environ.get("ARDOR_TRANSPORT", "write"),
        help="Как отправлять HID report: hid.write или Windows HidD_SetOutputReport.",
    )
    parser.add_argument(
        "--brightness",
        type=int,
        default=int(os.environ.get("ARDOR_BRIGHTNESS", EVISION_BRIGHTNESS_HIGHEST)),
        help="Яркость подсветки 1..4, где 4 - максимум.",
    )
    parser.add_argument("--debug", action="store_true", help="Подробные HID-логи.")
    parser.add_argument(
        "--mood-watch",
        action="store_true",
        help="Читать настроение активного сима из ardor_mood.txt и красить клавиатуру.",
    )
    parser.add_argument(
        "--mood-file",
        default=os.environ.get("ARDOR_MOOD_FILE", default_mood_file_path()),
        help="Путь к файлу настроения, который пишет Sims script mod.",
    )
    parser.add_argument(
        "--mood-interval",
        type=float,
        default=0.5,
        help="Как часто проверять файл настроения.",
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Не запускать Flask; полезно для режима только mood-watch и будущего exe.",
    )
    parser.add_argument(
        "--color-config",
        default=os.environ.get("ARDOR_MOOD_COLORS", default_color_config_path()),
        help="JSON-файл с цветами настроений.",
    )
    parser.add_argument(
        "--send-hex",
        default=None,
        help="Отправить сырой HID report, например: \"04 01 00 01 ...\".",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.list:
        list_hid_devices()
        return

    configure_bridge(
        path_index=args.path_index,
        path_contains=args.path_contains,
        protocol=args.protocol,
        transport=args.transport,
        brightness=args.brightness,
        color_config=args.color_config,
    )

    if args.send_hex:
        send_raw_hex_report(args.send_hex)
        return

    if args.test:
        run_color_test()
        return

    if args.mood_watch:
        start_mood_watch(args.mood_file, args.mood_interval)

    if args.no_server:
        if not args.mood_watch:
            raise RuntimeError("--no-server имеет смысл только вместе с --mood-watch.")

        logger.info("Mood watch: Flask отключен, работаю только как file watcher.")
        while True:
            time.sleep(3600)

    logger.info("Chroma SDK: сервер запущен на http://127.0.0.1:%s%s", args.port, BASE)
    logger.info("Chroma SDK: тесты доступны: /test/red /test/green /test/blue /hid/list")

    app.run(
        port=args.port,
        host="127.0.0.1",
        debug=False,
        use_reloader=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
