from __future__ import annotations

from html import escape
from typing import Any

from app.database import TrackRecord


SEARCH = "\U0001F50E"
CLOCK = "\U0001F558"
STAR = "\u2B50"
CHART = "\U0001F4CA"
INFO = "\u2139\ufe0f"
HELLO = "\U0001F44B"
MUSIC = "\U0001F3B5"
PLAY = "\u25B6\ufe0f"
GLOBE = "\U0001F310"
TRASH = "\U0001F5D1"
WARNING = "\u26A0\ufe0f"
SAD = "\U0001F615"
HEADPHONES = "\U0001F3A7"
MIC = "\U0001F399"
USER_ICON = "\U0001F464"
DISC = "\U0001F4BF"
MIXER = "\U0001F39A"
CALENDAR = "\U0001F4C5"
TIMER = "\u23F1"
USERS = "\U0001F465"
SHIELD = "\U0001F6E1"
MEGAPHONE = "\U0001F4E3"
ID_CARD = "\U0001FAAA"
LEFT_ARROW = "\u2B05\ufe0f"
RIGHT_ARROW = "\u27A1\ufe0f"


MAIN_MENU: dict[str, Any] = {
    "keyboard": [
        [f"{SEARCH} Musiqa qidirish", f"{CLOCK} Tarix"],
        [f"{STAR} Saqlanganlar", f"{CHART} Statistika"],
        [f"{INFO} Yordam"],
    ],
    "resize_keyboard": True,
    "input_field_placeholder": "Qo'shiq nomi yoki ijrochini yozing...",
}


def start_text(first_name: str | None = None) -> str:
    name = f", {escape(first_name)}" if first_name else ""
    return (
        f"{HELLO} Salom{name}!\n\n"
        "Men qo'shiq nomi yoki ijrochi bo'yicha musiqa topib beraman.\n"
        f"{SEARCH} Qidirish uchun shunchaki yozing: <b>Imagine Dragons Believer</b>\n\n"
        "Natijalarda 30 soniyalik qonuniy preview, albom, janr va havola chiqadi."
    )


HELP_TEXT = (
    f"{INFO} <b>Yordam</b>\n\n"
    f"{SEARCH} <b>Qidirish:</b> qo'shiq nomi, ijrochi yoki albom yozing.\n"
    "Masalan: <code>Shakira Waka Waka</code>\n\n"
    f"{CLOCK} <b>/history</b> - oxirgi qidiruvlaringiz\n"
    f"{STAR} <b>/favorites</b> - saqlangan treklar\n"
    f"{CHART} <b>/stats</b> - bot statistikasi\n\n"
    "Eslatma: bot musiqani noqonuniy yuklab bermaydi; preview va rasmiy havolalarni ko'rsatadi."
)


def search_results_keyboard(tracks: list[TrackRecord]) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    for index, track in enumerate(tracks, start=1):
        title = shorten(f"{index}. {MUSIC} {track.artist} - {track.title}", 54)
        rows.append([{"text": title, "callback_data": f"track:{track.track_id}"}])

    rows.append(
        [
            {"text": f"{CLOCK} Tarix", "callback_data": "menu:history"},
            {"text": f"{STAR} Saqlanganlar", "callback_data": "menu:favorites"},
        ]
    )
    return {"inline_keyboard": rows}


def paginated_tracks_keyboard(
    tracks: list[TrackRecord],
    session_id: str,
    mode: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    total_pages = max(1, (len(tracks) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    page_tracks = tracks[start : start + page_size]

    rows: list[list[dict[str, str]]] = []
    for offset, track in enumerate(page_tracks, start=1):
        index = start + offset
        title = shorten(f"{index}. {MUSIC} {track.title}", 54)
        rows.append([{"text": title, "callback_data": f"track:{track.track_id}"}])

    switch_mode = "recent" if mode == "top" else "top"
    switch_text = f"{CALENDAR} Oxirgi chiqqanlar" if mode == "top" else f"{STAR} Top qo'shiqlar"
    rows.append([{"text": switch_text, "callback_data": f"artist:{session_id}:{switch_mode}:0"}])

    nav_row: list[dict[str, str]] = []
    if page > 0:
        nav_row.append({"text": f"{LEFT_ARROW} Oldingi", "callback_data": f"artist:{session_id}:{mode}:{page - 1}"})
    nav_row.append({"text": f"{page + 1}/{total_pages}", "callback_data": f"artist:{session_id}:{mode}:{page}"})
    if page < total_pages - 1:
        nav_row.append({"text": f"Keyingi sahifa {RIGHT_ARROW}", "callback_data": f"artist:{session_id}:{mode}:{page + 1}"})
    rows.append(nav_row)

    rows.append(
        [
            {"text": f"{CLOCK} Tarix", "callback_data": "menu:history"},
            {"text": f"{STAR} Saqlanganlar", "callback_data": "menu:favorites"},
        ]
    )
    return {"inline_keyboard": rows}


def track_keyboard(track: TrackRecord) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = [
        [
            {"text": f"{STAR} Saqlash", "callback_data": f"fav:add:{track.track_id}"},
            {"text": f"{TRASH} O'chirish", "callback_data": f"fav:remove:{track.track_id}"},
        ]
    ]
    if track.preview_url:
        rows.append([{"text": f"{PLAY} Preview ochish", "url": track.preview_url}])
    if track.track_url:
        rows.append([{"text": f"{GLOBE} Rasmiy havola", "url": track.track_url}])
    rows.append([{"text": f"{SEARCH} Yangi qidiruv", "callback_data": "menu:search"}])
    return {"inline_keyboard": rows}


def track_caption(track: TrackRecord) -> str:
    parts = [
        f"{MUSIC} <b>{escape(track.title)}</b>",
        f"{USER_ICON} Ijrochi: <b>{escape(track.artist)}</b>",
    ]
    if track.album:
        parts.append(f"{DISC} Albom: {escape(track.album)}")
    if track.genre:
        parts.append(f"{MIXER} Janr: {escape(track.genre)}")
    if track.release_date:
        parts.append(f"{CALENDAR} Yil: {escape(track.release_date[:4])}")
    if track.duration_ms:
        parts.append(f"{TIMER} Davomiyligi: {format_duration(track.duration_ms)}")
    if track.preview_url or track.track_url:
        parts.append(f"{INFO} Preview va havolalar iTunes tomonidan taqdim etilgan.")
    return "\n".join(parts)


def favorites_text(tracks: list[TrackRecord]) -> str:
    if not tracks:
        return f"{STAR} Hali saqlangan treklar yo'q."
    lines = [f"{STAR} <b>Saqlangan treklar</b>"]
    for index, track in enumerate(tracks, start=1):
        lines.append(f"{index}. {escape(track.artist)} - {escape(track.title)}")
    return "\n".join(lines)


def history_text(items: list[dict[str, object]]) -> str:
    if not items:
        return f"{CLOCK} Hali qidiruv tarixi yo'q."
    lines = [f"{CLOCK} <b>Oxirgi qidiruvlar</b>"]
    for index, item in enumerate(items, start=1):
        query = escape(str(item["query"]))
        result_count = item["result_count"]
        created_at = item["created_at"]
        lines.append(f"{index}. {query} - {result_count} ta natija ({created_at})")
    return "\n".join(lines)


def stats_text(stats: dict[str, int]) -> str:
    return (
        f"{CHART} <b>Bot statistikasi</b>\n\n"
        f"{USERS} Foydalanuvchilar: {stats['users']}\n"
        f"{SEARCH} Qidiruvlar: {stats['searches']}\n"
        f"{MUSIC} Treklar bazada: {stats['tracks']}\n"
        f"{STAR} Saqlanganlar: {stats['favorites']}"
    )


def admin_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": f"{CHART} Statistika", "callback_data": "admin:stats"},
                {"text": f"{USERS} Userlar", "callback_data": "admin:users"},
            ],
            [
                {"text": f"{CLOCK} Qidiruvlar", "callback_data": "admin:searches"},
                {"text": f"{MEGAPHONE} Broadcast", "callback_data": "admin:broadcast_help"},
            ],
        ]
    }


def format_duration(milliseconds: int) -> str:
    seconds = milliseconds // 1000
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def shorten(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "..."
