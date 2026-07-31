import json
import os


DEFAULT_MOOD_COLORS = {
    "angry": (195, 25, 43),
    "uncomfortable": (226, 98, 70),
    "tense": (223, 132, 28),
    "embarrassed": (225, 192, 67),
    "energized": (157, 201, 72),
    "happy": (40, 181, 82),
    "inspired": (51, 188, 193),
    "confident": (68, 140, 200),
    "sad": (44, 68, 170),
    "focused": (112, 56, 236),
    "dazed": (129, 109, 204),
    "playful": (182, 70, 173),
    "flirty": (238, 93, 165),
    "scared": (126, 18, 96),
    "terrified": (126, 18, 96),
    "bored": (129, 135, 133),
    "fine": (233, 233, 233),
    "asleep": (77, 77, 112),
    "possessed": (77, 77, 112),
    "recharge": (77, 77, 112),
}

INTENSE_MOOD_COLORS = {
    "angry_very": (231, 48, 55),
    "angry_extreme": (255, 0, 20),
    "embarrassed_very": (255, 208, 84),
    "embarrassed_extreme": (255, 180, 20),
    "energized_very": (191, 235, 70),
    "happy_very": (68, 220, 98),
    "inspired_very": (58, 230, 230),
    "confident_very": (80, 174, 245),
    "sad_very": (42, 82, 220),
    "focused_very": (142, 82, 255),
    "playful_very": (218, 82, 208),
    "playful_extreme": (255, 82, 212),
    "flirty_very": (255, 106, 186),
    "scared_very": (160, 22, 126),
    "scared_extreme": (195, 20, 155),
    "terrified_very": (195, 20, 155),
    "tense_very": (255, 152, 26),
    "uncomfortable_very": (255, 112, 80),
    "dazed_very": (158, 130, 235),
    "bored_very": (150, 158, 154),
}

DEFAULT_MOOD_COLORS.update(INTENSE_MOOD_COLORS)

MOOD_ALIASES = {
    "aroused": "flirty",
    "depressed": "sad_very",
    "elated": "happy_very",
    "enraged": "angry_extreme",
    "fearless": "confident_very",
    "furious": "angry_very",
    "horny": "flirty_very",
    "humiliated": "embarrassed_very",
    "hysterical": "playful_extreme",
    "imaginative": "inspired_very",
    "in_the_zone": "focused_very",
    "miserable": "uncomfortable_very",
    "mortified": "embarrassed_extreme",
    "pumped": "energized_very",
    "silly": "playful_very",
    "stressed": "tense_very",
    "stress": "tense_very",
    "very_stressed": "tense_very",
}

MOOD_LABELS = {
    "angry": "Angry / злость",
    "uncomfortable": "Uncomfortable / дискомфорт",
    "tense": "Tense / Stressed / напряжение",
    "embarrassed": "Embarrassed / смущение",
    "energized": "Energized / бодрость",
    "happy": "Happy / счастье",
    "inspired": "Inspired / вдохновение",
    "confident": "Confident / уверенность",
    "sad": "Sad / грусть",
    "focused": "Focused / внимательность",
    "dazed": "Dazed / ошалелость",
    "playful": "Playful / игривость",
    "flirty": "Flirty / кокетливость",
    "scared": "Scared / страх",
    "terrified": "Terrified / ужас",
    "bored": "Bored / скука",
    "fine": "Fine / нормально",
    "asleep": "Asleep / сон",
    "possessed": "Possessed / одержимость",
    "recharge": "Recharge / перезарядка",
    "angry_very": "Very Angry / очень злая",
    "angry_extreme": "Enraged / в ярости",
    "embarrassed_very": "Very Embarrassed / очень смущена",
    "embarrassed_extreme": "Mortified / унижена",
    "energized_very": "Very Energized / очень бодрая",
    "happy_very": "Very Happy / очень счастливая",
    "inspired_very": "Very Inspired / очень вдохновлена",
    "confident_very": "Very Confident / очень уверена",
    "sad_very": "Very Sad / очень грустная",
    "focused_very": "Very Focused / очень внимательная",
    "playful_very": "Very Playful / очень игривая",
    "playful_extreme": "Hysterical / истерика",
    "flirty_very": "Very Flirty / очень кокетливая",
    "scared_very": "Very Scared / очень испуганная",
    "scared_extreme": "Terrified / в ужасе",
    "terrified_very": "Terrified+ / сильный ужас",
    "tense_very": "Very Tense / Very Stressed / очень напряжена",
    "uncomfortable_very": "Very Uncomfortable / очень дискомфортно",
    "dazed_very": "Very Dazed / очень ошалевшая",
    "bored_very": "Very Bored / очень скучно",
}

MOOD_ORDER = [
    "fine",
    "happy",
    "focused",
    "inspired",
    "confident",
    "energized",
    "playful",
    "flirty",
    "sad",
    "angry",
    "tense",
    "uncomfortable",
    "embarrassed",
    "bored",
    "dazed",
    "scared",
    "terrified",
    "asleep",
    "possessed",
    "recharge",
    "happy_very",
    "focused_very",
    "inspired_very",
    "confident_very",
    "energized_very",
    "playful_very",
    "playful_extreme",
    "flirty_very",
    "sad_very",
    "angry_very",
    "angry_extreme",
    "tense_very",
    "uncomfortable_very",
    "embarrassed_very",
    "embarrassed_extreme",
    "bored_very",
    "dazed_very",
    "scared_very",
    "scared_extreme",
    "terrified_very",
]


def default_color_config_path():
    configured = os.environ.get("ARDOR_MOOD_COLORS")
    if configured:
        return configured

    if os.name == "nt":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")

    return os.path.join(root, "ArdorMoodBridge", "mood_colors.json")


def normalize_mood_name(name):
    result = (name or "").strip().lower().replace("-", "_").replace(" ", "_")

    if result.startswith("mood_"):
        result = result.split("_", 1)[-1]

    return MOOD_ALIASES.get(result, result)


def clamp_channel(value):
    return max(0, min(255, int(value)))


def normalize_rgb(value):
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) == 6:
            return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)

    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return clamp_channel(value[0]), clamp_channel(value[1]), clamp_channel(value[2])

    raise ValueError("RGB color must be #RRGGBB or [r, g, b].")


def rgb_to_hex(rgb):
    red, green, blue = normalize_rgb(rgb)
    return "#{:02X}{:02X}{:02X}".format(red, green, blue)


def load_mood_colors(path=None):
    colors = dict(DEFAULT_MOOD_COLORS)
    path = path or default_color_config_path()

    if not os.path.exists(path):
        return colors

    with open(path, "r", encoding="utf-8") as stream:
        data = json.load(stream)

    if not isinstance(data, dict):
        raise ValueError("Mood color config must be a JSON object.")

    for mood, value in data.items():
        normalized_mood = normalize_mood_name(mood)
        if not normalized_mood:
            continue
        colors[normalized_mood] = normalize_rgb(value)

    return colors


def save_mood_colors(colors, path=None):
    path = path or default_color_config_path()
    folder = os.path.dirname(path)

    if folder:
        os.makedirs(folder, exist_ok=True)

    normalized = {}
    for mood in MOOD_ORDER:
        if mood in colors:
            normalized[mood] = rgb_to_hex(colors[mood])

    for mood in sorted(colors):
        if mood not in normalized:
            normalized[mood] = rgb_to_hex(colors[mood])

    with open(path, "w", encoding="utf-8") as stream:
        json.dump(normalized, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

    return path
