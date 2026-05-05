from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
import uuid
from html import escape
from typing import Any

from app.audio_recognition import RecognitionError, RecognitionResult, recognize_audio_file
from app.config import Settings
from app.database import Database, TrackRecord
from app.music_search import ArtistCatalog, MusicSearchError, search_artist_catalog_sync, search_tracks_sync
from app.ui import (
    CHART,
    CLOCK,
    CALENDAR,
    DISC,
    GLOBE,
    HEADPHONES,
    HELP_TEXT,
    ID_CARD,
    MAIN_MENU,
    MEGAPHONE,
    MIC,
    MUSIC,
    SAD,
    SEARCH,
    SHIELD,
    STAR,
    TRASH,
    USERS,
    USER_ICON,
    WARNING,
    TIMER,
    admin_keyboard,
    favorites_text,
    history_text,
    paginated_tracks_keyboard,
    search_results_keyboard,
    start_text,
    stats_text,
    track_caption,
    track_keyboard,
)

logger = logging.getLogger(__name__)
ARTIST_PAGE_SIZE = 10
MAX_ARTIST_SESSIONS = 100


COMMANDS = [
    {"command": "start", "description": "Botni ishga tushirish"},
    {"command": "search", "description": "Musiqa qidirish"},
    {"command": "history", "description": "Qidiruv tarixi"},
    {"command": "favorites", "description": "Saqlangan treklar"},
    {"command": "stats", "description": "Bot statistikasi"},
    {"command": "id", "description": "Telegram ID ni ko'rish"},
    {"command": "admin", "description": "Admin panel"},
    {"command": "broadcast", "description": "Admin: hammaga xabar yuborish"},
    {"command": "help", "description": "Yordam"},
]


class TelegramApiError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, payload: dict[str, Any] | None = None, timeout: int = 40) -> Any:
        data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise TelegramApiError(f"Telegram HTTP {exc.code}: {body}") from exc
        except OSError as exc:
            raise TelegramApiError(f"Telegram bilan aloqa bo'lmadi: {exc}") from exc

        result = json.loads(body)
        if not result.get("ok"):
            raise TelegramApiError(result.get("description", "Telegram API xatosi"))
        return result.get("result")

    def get_updates(self, offset: int | None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": 30,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload, timeout=40)

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = "HTML",
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        self.call("sendMessage", payload)

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = "HTML",
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        self.call("editMessageText", payload)

    def send_photo(
        self,
        chat_id: int,
        photo: str,
        caption: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "photo": photo,
            "caption": caption,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        self.call("sendPhoto", payload)

    def send_chat_action(self, chat_id: int, action: str) -> None:
        self.call("sendChatAction", {"chat_id": chat_id, "action": action})

    def get_file(self, file_id: str) -> dict[str, Any]:
        return self.call("getFile", {"file_id": file_id})

    def download_file(self, file_path: str, max_bytes: int = 10_000_000) -> bytes:
        url = f"{self.base_url.replace('/bot', '/file/bot', 1)}/{file_path}"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read(max_bytes + 1)
        except OSError as exc:
            raise TelegramApiError(f"Telegram faylini yuklab bo'lmadi: {exc}") from exc

        if len(data) > max_bytes:
            raise TelegramApiError("Audio fayl juda katta. 20 soniyagacha qisqa audio yuboring.")
        return data

    def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        self.call("answerCallbackQuery", payload)

    def set_my_commands(self) -> None:
        self.call("setMyCommands", {"commands": COMMANDS})

    def delete_webhook(self) -> None:
        self.call("deleteWebhook", {"drop_pending_updates": False})

    def get_me(self) -> dict[str, Any]:
        return self.call("getMe")


class MusicBot:
    def __init__(self, settings: Settings, database: Database) -> None:
        self.settings = settings
        self.db = database
        self.telegram = TelegramClient(settings.bot_token)
        self.offset: int | None = None
        self.artist_sessions: dict[str, dict[str, Any]] = {}

    def run_forever(self) -> None:
        me = self.telegram.get_me()
        self.telegram.delete_webhook()
        self.telegram.set_my_commands()
        username = me.get("username", "unknown")
        logger.info("Bot ishga tushdi: @%s", username)
        print(f"Bot ishga tushdi: @{username}. To'xtatish uchun Ctrl+C bosing.")

        while True:
            try:
                for update in self.telegram.get_updates(self.offset):
                    self.offset = int(update["update_id"]) + 1
                    self.handle_update(update)
            except KeyboardInterrupt:
                raise
            except TelegramApiError as exc:
                logger.warning("Telegram API xatosi: %s", exc)
                time.sleep(5)
            except Exception:
                logger.exception("Kutilmagan xatolik")
                time.sleep(3)

    def handle_update(self, update: dict[str, Any]) -> None:
        if "message" in update:
            self.handle_message(update["message"])
        elif "callback_query" in update:
            self.handle_callback(update["callback_query"])

    def handle_message(self, message: dict[str, Any]) -> None:
        chat_id = message["chat"]["id"]
        user = message.get("from", {})
        self.remember_user(user)

        text = (message.get("text") or "").strip()
        if text:
            self.handle_text(chat_id, user, text)
            return

        audio = message.get("audio")
        voice = message.get("voice")
        audio_payload = audio or voice
        if audio_payload:
            if self.settings.audd_api_token:
                if self.try_recognize_audio(chat_id, user, audio_payload, is_voice=bool(voice)):
                    return

            performer = audio.get("performer") if audio else None
            title = audio.get("title") if audio else None
            if performer or title:
                query = " ".join(part for part in [performer, title] if part)
                self.telegram.send_message(
                    chat_id,
                    f"{HEADPHONES} Audio metadata topildi: <b>{escape(query)}</b>\nQidiryapman...",
                    MAIN_MENU,
                )
                self.run_search(chat_id, user, query)
                return

        if voice or audio:
            self.telegram.send_message(
                chat_id,
                f"{MIC} Audio tanish uchun AudD token kerak. "
                "Hozircha qo'shiq nomi yoki ijrochini yozing, men qidirib beraman.",
                MAIN_MENU,
            )

    def handle_text(self, chat_id: int, user: dict[str, Any], text: str) -> None:
        command, *args = text.split(maxsplit=1)
        command = command.split("@", 1)[0].casefold()

        if command == "/start":
            self.telegram.send_message(chat_id, start_text(user.get("first_name")), MAIN_MENU)
            return
        if command == "/help":
            self.telegram.send_message(chat_id, HELP_TEXT, MAIN_MENU)
            return
        if command == "/history":
            self.send_history(chat_id, user)
            return
        if command == "/favorites":
            self.send_favorites(chat_id, user)
            return
        if command == "/stats":
            self.send_stats(chat_id)
            return
        if command == "/id":
            self.send_id(chat_id, user)
            return
        if command == "/admin":
            self.send_admin_panel(chat_id, user)
            return
        if command == "/broadcast":
            self.handle_broadcast_command(chat_id, user, args[0] if args else "")
            return
        if command == "/search":
            if not args:
                self.telegram.send_message(
                    chat_id,
                    f"{SEARCH} Qidirish uchun: <code>/search qo'shiq nomi</code>",
                    MAIN_MENU,
                )
                return
            self.run_search(chat_id, user, args[0])
            return

        normalized = text.casefold()
        if "yordam" in normalized or normalized == "help":
            self.telegram.send_message(chat_id, HELP_TEXT, MAIN_MENU)
            return
        if "tarix" in normalized or normalized == "history":
            self.send_history(chat_id, user)
            return
        if "saqlangan" in normalized or normalized == "favorites":
            self.send_favorites(chat_id, user)
            return
        if "statistika" in normalized or normalized == "stats":
            self.send_stats(chat_id)
            return
        if "qidirish" in normalized or normalized == "search":
            self.telegram.send_message(
                chat_id,
                f"{SEARCH} Qaysi musiqani qidiramiz? Qo'shiq nomi yoki ijrochini yozing.",
                MAIN_MENU,
            )
            return

        self.run_search(chat_id, user, text)

    def run_search(self, chat_id: int, user: dict[str, Any], query: str) -> None:
        if not query or len(query) < 2:
            self.telegram.send_message(chat_id, "Kamida 2 ta belgi yozing.", MAIN_MENU)
            return

        self.telegram.send_chat_action(chat_id, "typing")
        try:
            artist_catalog = search_artist_catalog_sync(query)
            if artist_catalog and (artist_catalog.top_tracks or artist_catalog.recent_tracks):
                self.send_artist_catalog(chat_id, user, query, artist_catalog)
                return

            tracks = search_tracks_sync(query)
        except MusicSearchError as exc:
            logger.warning("Music search failed: %s", exc)
            self.telegram.send_message(
                chat_id,
                f"{WARNING} Qidiruvda xatolik bo'ldi. Birozdan keyin qayta urinib ko'ring.",
                MAIN_MENU,
            )
            return

        user_id = user.get("id")
        if user_id:
            self.db.add_search(int(user_id), query, len(tracks))
        self.db.save_tracks(tracks)

        if not tracks:
            self.telegram.send_message(
                chat_id,
                f"{SAD} <b>{escape(query)}</b> bo'yicha natija topilmadi.",
                MAIN_MENU,
            )
            return

        self.telegram.send_message(
            chat_id,
            f"{SEARCH} <b>{escape(query)}</b> bo'yicha topilgan natijalar:",
            search_results_keyboard(tracks),
        )

    def handle_callback(self, callback: dict[str, Any]) -> None:
        callback_id = callback["id"]
        message = callback.get("message") or {}
        chat_id = message.get("chat", {}).get("id")
        user = callback.get("from", {})
        data = callback.get("data") or ""
        if not chat_id:
            return

        self.remember_user(user)
        if data.startswith("admin:") and not self.is_admin(user):
            self.telegram.answer_callback_query(callback_id, "Ruxsat yo'q")
            return

        self.telegram.answer_callback_query(callback_id)

        if data == "admin:stats":
            self.send_stats(chat_id)
            return
        if data == "admin:users":
            self.send_admin_users(chat_id)
            return
        if data == "admin:searches":
            self.send_admin_searches(chat_id)
            return
        if data == "admin:broadcast_help":
            self.telegram.send_message(
                chat_id,
                f"{MEGAPHONE} Hammaga xabar yuborish:\n\n"
                "<code>/broadcast Salom! Botga yangi funksiya qo'shildi.</code>",
            )
            return

        if data.startswith("artist:"):
            self.handle_artist_callback(chat_id, message.get("message_id"), data)
            return

        if data == "menu:history":
            self.send_history(chat_id, user)
            return
        if data == "menu:favorites":
            self.send_favorites(chat_id, user)
            return
        if data == "menu:search":
            self.telegram.send_message(
                chat_id,
                f"{SEARCH} Qidirish uchun qo'shiq nomi yoki ijrochini yozing.",
                MAIN_MENU,
            )
            return
        if data.startswith("track:"):
            track = self.db.get_track(int(data.split(":", 1)[1]))
            if not track:
                self.telegram.send_message(chat_id, "Bu trek bazadan topilmadi. Qayta qidirib ko'ring.")
                return
            self.send_track_details(chat_id, track)
            return
        if data.startswith("fav:add:"):
            track_id = int(data.rsplit(":", 1)[1])
            added = self.db.add_favorite(int(user["id"]), track_id)
            self.telegram.send_message(
                chat_id,
                f"{STAR} Saqlandi." if added else f"{STAR} Bu trek oldin saqlangan.",
            )
            return
        if data.startswith("fav:remove:"):
            track_id = int(data.rsplit(":", 1)[1])
            removed = self.db.remove_favorite(int(user["id"]), track_id)
            self.telegram.send_message(
                chat_id,
                f"{TRASH} O'chirildi." if removed else "Bu trek saqlanganlarda yo'q.",
            )

    def send_track_details(self, chat_id: int, track: TrackRecord) -> None:
        caption = track_caption(track)
        if track.artwork_url:
            try:
                self.telegram.send_photo(chat_id, track.artwork_url, caption, track_keyboard(track))
                return
            except TelegramApiError:
                logger.warning("sendPhoto failed, falling back to sendMessage", exc_info=True)

        self.telegram.send_message(chat_id, caption, track_keyboard(track))

    def send_artist_catalog(
        self,
        chat_id: int,
        user: dict[str, Any],
        original_query: str,
        catalog: ArtistCatalog,
    ) -> None:
        tracks_to_save = catalog.top_tracks + catalog.recent_tracks
        self.db.save_tracks(tracks_to_save)
        if user.get("id"):
            total_results = max(len(catalog.top_tracks), len(catalog.recent_tracks))
            self.db.add_search(int(user["id"]), original_query, total_results)

        session_id = self.create_artist_session(catalog)
        mode = "top" if catalog.top_tracks else "recent"
        self.send_artist_page(chat_id, session_id, mode, 0)

    def create_artist_session(self, catalog: ArtistCatalog) -> str:
        session_id = uuid.uuid4().hex[:8]
        self.artist_sessions[session_id] = {
            "artist_id": catalog.artist_id,
            "artist_name": catalog.artist_name,
            "top": catalog.top_tracks,
            "recent": catalog.recent_tracks,
        }

        while len(self.artist_sessions) > MAX_ARTIST_SESSIONS:
            oldest_session = next(iter(self.artist_sessions))
            del self.artist_sessions[oldest_session]
        return session_id

    def handle_artist_callback(self, chat_id: int, message_id: int | None, data: str) -> None:
        parts = data.split(":")
        if len(parts) != 4:
            self.telegram.send_message(chat_id, "Sahifa ma'lumoti noto'g'ri. Qayta qidirib ko'ring.")
            return

        _, session_id, mode, raw_page = parts
        try:
            page = int(raw_page)
        except ValueError:
            page = 0

        self.send_artist_page(chat_id, session_id, mode, page, message_id)

    def send_artist_page(
        self,
        chat_id: int,
        session_id: str,
        mode: str,
        page: int,
        message_id: int | None = None,
    ) -> None:
        session = self.artist_sessions.get(session_id)
        if not session:
            self.telegram.send_message(
                chat_id,
                "Bu sahifa eskirgan. Artist nomini qayta yozing.",
                MAIN_MENU,
            )
            return

        mode = "recent" if mode == "recent" else "top"
        tracks: list[TrackRecord] = session["recent"] if mode == "recent" else session["top"]
        if not tracks and mode == "top":
            mode = "recent"
            tracks = session["recent"]
        if not tracks:
            self.telegram.send_message(chat_id, "Bu artist uchun qo'shiqlar topilmadi.", MAIN_MENU)
            return

        total_pages = max(1, (len(tracks) + ARTIST_PAGE_SIZE - 1) // ARTIST_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        start = page * ARTIST_PAGE_SIZE + 1
        end = min(len(tracks), (page + 1) * ARTIST_PAGE_SIZE)
        mode_label = "Top qo'shiqlar" if mode == "top" else "Oxirgi chiqqanlar"
        artist_name = escape(str(session["artist_name"]))
        text = (
            f"{MUSIC} <b>{artist_name}</b>\n"
            f"{STAR if mode == 'top' else CALENDAR} <b>{mode_label}</b>\n"
            f"Natijalar: {start}-{end} / {len(tracks)}"
        )
        keyboard = paginated_tracks_keyboard(
            tracks,
            session_id,
            mode,
            page,
            ARTIST_PAGE_SIZE,
        )

        if message_id:
            try:
                self.telegram.edit_message_text(chat_id, message_id, text, keyboard)
                return
            except TelegramApiError:
                logger.warning("editMessageText failed, sending a new page", exc_info=True)
        self.telegram.send_message(chat_id, text, keyboard)

    def try_recognize_audio(
        self,
        chat_id: int,
        user: dict[str, Any],
        audio_payload: dict[str, Any],
        is_voice: bool,
    ) -> bool:
        file_id = audio_payload.get("file_id")
        if not file_id:
            return False

        file_size = int(audio_payload.get("file_size") or 0)
        if file_size and file_size > 10_000_000:
            self.telegram.send_message(
                chat_id,
                f"{WARNING} Audio juda katta. Shazamga o'xshash tanish uchun 20 soniyagacha qisqa audio yuboring.",
                MAIN_MENU,
            )
            return True

        self.telegram.send_chat_action(chat_id, "typing")
        try:
            file_info = self.telegram.get_file(file_id)
            file_path = file_info["file_path"]
            data = self.telegram.download_file(file_path)
            filename = audio_payload.get("file_name") or ("voice.ogg" if is_voice else "audio.mp3")
            mime_type = audio_payload.get("mime_type") or ("audio/ogg" if is_voice else "audio/mpeg")
            result = recognize_audio_file(
                self.settings.audd_api_token,
                filename,
                data,
                mime_type,
            )
        except (TelegramApiError, RecognitionError) as exc:
            logger.warning("Audio recognition failed: %s", exc)
            self.telegram.send_message(
                chat_id,
                f"{WARNING} Audio tanishda xatolik bo'ldi. "
                "Qo'shiq nomi yoki ijrochini yozsangiz, qidirib beraman.",
                MAIN_MENU,
            )
            return True

        if not result:
            self.telegram.send_message(
                chat_id,
                f"{SAD} Audio ichidan qo'shiq topilmadi. "
                "Aniqroq bo'lishi uchun 10-20 soniyalik musiqali parcha yuboring.",
                MAIN_MENU,
            )
            return True

        self.send_recognition_result(chat_id, result)
        self.run_search(chat_id, user, f"{result.artist} {result.title}")
        return True

    def send_recognition_result(self, chat_id: int, result: RecognitionResult) -> None:
        lines = [
            f"{HEADPHONES} <b>Audio tanildi</b>",
            f"{MUSIC} <b>{escape(result.title)}</b>",
            f"{USER_ICON} Ijrochi: <b>{escape(result.artist)}</b>",
        ]
        if result.album:
            lines.append(f"{DISC} Albom: {escape(result.album)}")
        if result.release_date:
            lines.append(f"{CALENDAR} Sana: {escape(result.release_date)}")
        if result.timecode:
            lines.append(f"{TIMER} Fragment joyi: {escape(result.timecode)}")
        if result.song_link:
            lines.append(f"{GLOBE} Havola: {escape(result.song_link)}")
        self.telegram.send_message(chat_id, "\n".join(lines), MAIN_MENU)

    def send_history(self, chat_id: int, user: dict[str, Any]) -> None:
        history = self.db.get_history(int(user["id"])) if user.get("id") else []
        self.telegram.send_message(chat_id, history_text(history), MAIN_MENU)

    def send_favorites(self, chat_id: int, user: dict[str, Any]) -> None:
        favorites = self.db.get_favorites(int(user["id"])) if user.get("id") else []
        reply_markup = search_results_keyboard(favorites) if favorites else MAIN_MENU
        self.telegram.send_message(chat_id, favorites_text(favorites), reply_markup)

    def send_stats(self, chat_id: int) -> None:
        self.telegram.send_message(chat_id, stats_text(self.db.stats()), MAIN_MENU)

    def send_id(self, chat_id: int, user: dict[str, Any]) -> None:
        user_id = user.get("id")
        username = user.get("username")
        username_line = f"\nUsername: @{escape(username)}" if username else ""
        self.telegram.send_message(
            chat_id,
            f"{ID_CARD} Sizning Telegram ID: <code>{user_id}</code>{username_line}",
            MAIN_MENU,
        )

    def send_admin_panel(self, chat_id: int, user: dict[str, Any]) -> None:
        if not self.is_admin(user):
            self.telegram.send_message(chat_id, "Ruxsat yo'q.")
            return

        stats = self.db.stats()
        self.telegram.send_message(
            chat_id,
            f"{SHIELD} <b>Admin panel</b>\n\n"
            f"{USERS} Userlar: {stats['users']}\n"
            f"{SEARCH} Qidiruvlar: {stats['searches']}\n"
            f"{STAR} Saqlanganlar: {stats['favorites']}\n\n"
            f"{HEADPHONES} Audio tanish: {'yoqilgan' if self.settings.audd_api_token else 'ochirilgan'}\n"
            f"{MEGAPHONE} Hammaga xabar: <code>/broadcast matn</code>",
            admin_keyboard(),
        )

    def send_admin_users(self, chat_id: int) -> None:
        users = self.db.get_users(limit=10)
        if not users:
            self.telegram.send_message(chat_id, f"{USERS} Hali userlar yo'q.")
            return

        lines = [f"{USERS} <b>Oxirgi userlar</b>"]
        for index, item in enumerate(users, start=1):
            name = " ".join(
                part for part in [item.get("first_name"), item.get("last_name")] if part
            ) or "No name"
            username = f" @{item['username']}" if item.get("username") else ""
            lines.append(
                f"{index}. <code>{item['user_id']}</code> - {escape(name)}{escape(username)}"
            )
        self.telegram.send_message(chat_id, "\n".join(lines), admin_keyboard())

    def send_admin_searches(self, chat_id: int) -> None:
        searches = self.db.get_recent_searches(limit=10)
        if not searches:
            self.telegram.send_message(chat_id, f"{CLOCK} Hali qidiruvlar yo'q.")
            return

        lines = [f"{CLOCK} <b>Oxirgi qidiruvlar</b>"]
        for index, item in enumerate(searches, start=1):
            user_label = item.get("username") or item.get("first_name") or item.get("user_id")
            lines.append(
                f"{index}. {escape(str(item['query']))} - {item['result_count']} ta "
                f"(<code>{escape(str(user_label))}</code>)"
            )
        self.telegram.send_message(chat_id, "\n".join(lines), admin_keyboard())

    def handle_broadcast_command(self, chat_id: int, user: dict[str, Any], text: str) -> None:
        if not self.is_admin(user):
            self.telegram.send_message(chat_id, "Ruxsat yo'q.")
            return
        if not text.strip():
            self.telegram.send_message(
                chat_id,
                f"{MEGAPHONE} Ishlatish:\n<code>/broadcast Hammaga salom!</code>",
            )
            return

        sent = 0
        failed = 0
        for user_id in self.db.get_user_ids():
            try:
                self.telegram.send_message(
                    user_id,
                    f"{MEGAPHONE} <b>Admin xabari</b>\n\n{escape(text)}",
                    MAIN_MENU,
                )
                sent += 1
                time.sleep(0.05)
            except TelegramApiError as exc:
                failed += 1
                logger.warning("Broadcast failed for %s: %s", user_id, exc)

        self.telegram.send_message(
            chat_id,
            f"{MEGAPHONE} Broadcast tugadi.\nYuborildi: {sent}\nXato: {failed}",
            admin_keyboard(),
        )

    def is_admin(self, user: dict[str, Any]) -> bool:
        user_id = user.get("id")
        return bool(user_id and int(user_id) in self.settings.admin_ids)

    def remember_user(self, user: dict[str, Any]) -> None:
        if not user.get("id"):
            return
        self.db.upsert_user(
            int(user["id"]),
            user.get("username"),
            user.get("first_name"),
            user.get("last_name"),
        )
