from __future__ import annotations

import functools
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrackRecord:
    track_id: int
    title: str
    artist: str
    album: str | None
    genre: str | None
    release_date: str | None
    duration_ms: int | None
    preview_url: str | None
    track_url: str | None
    artwork_url: str | None


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if str(path) == ":memory:":
            self.connection = sqlite3.connect(":memory:")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def init(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    result_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS tracks (
                    track_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    album TEXT,
                    genre TEXT,
                    release_date TEXT,
                    duration_ms INTEGER,
                    preview_url TEXT,
                    track_url TEXT,
                    artwork_url TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER NOT NULL,
                    track_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, track_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (track_id) REFERENCES tracks(track_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_searches_user_id ON searches(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
                CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
                """
            )

    def upsert_user(
        self,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (user_id, username, first_name, last_name),
            )

    def add_search(self, user_id: int, query: str, result_count: int) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO searches (user_id, query, result_count)
                VALUES (?, ?, ?)
                """,
                (user_id, query, result_count),
            )

    def save_tracks(self, tracks: Iterable[TrackRecord]) -> None:
        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO tracks (
                    track_id, title, artist, album, genre, release_date,
                    duration_ms, preview_url, track_url, artwork_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    title = excluded.title,
                    artist = excluded.artist,
                    album = excluded.album,
                    genre = excluded.genre,
                    release_date = excluded.release_date,
                    duration_ms = excluded.duration_ms,
                    preview_url = excluded.preview_url,
                    track_url = excluded.track_url,
                    artwork_url = excluded.artwork_url,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        track.track_id,
                        track.title,
                        track.artist,
                        track.album,
                        track.genre,
                        track.release_date,
                        track.duration_ms,
                        track.preview_url,
                        track.track_url,
                        track.artwork_url,
                    )
                    for track in tracks
                ],
            )

    @functools.lru_cache(maxsize=1024)
    def get_track(self, track_id: int) -> TrackRecord | None:
        row = self.connection.execute(
            "SELECT * FROM tracks WHERE track_id = ?",
            (track_id,),
        ).fetchone()
        return _row_to_track(row) if row else None

    def add_favorite(self, user_id: int, track_id: int) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO favorites (user_id, track_id)
                VALUES (?, ?)
                """,
                (user_id, track_id),
            )
        return cursor.rowcount > 0

    def remove_favorite(self, user_id: int, track_id: int) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                """
                DELETE FROM favorites
                WHERE user_id = ? AND track_id = ?
                """,
                (user_id, track_id),
            )
        return cursor.rowcount > 0

    def get_favorites(self, user_id: int, limit: int = 10) -> list[TrackRecord]:
        rows = self.connection.execute(
            """
            SELECT tracks.*
            FROM favorites
            JOIN tracks ON tracks.track_id = favorites.track_id
            WHERE favorites.user_id = ?
            ORDER BY favorites.created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [_row_to_track(row) for row in rows]

    def get_history(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT query, result_count, created_at
            FROM searches
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_user_ids(self) -> list[int]:
        rows = self.connection.execute(
            "SELECT user_id FROM users ORDER BY last_seen_at DESC"
        ).fetchall()
        return [int(row["user_id"]) for row in rows]

    def get_users(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT user_id, username, first_name, last_name, created_at, last_seen_at
            FROM users
            ORDER BY last_seen_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_searches(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT searches.query, searches.result_count, searches.created_at,
                   users.user_id, users.username, users.first_name
            FROM searches
            LEFT JOIN users ON users.user_id = searches.user_id
            ORDER BY searches.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, int]:
        row = self.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM users) AS users,
                (SELECT COUNT(*) FROM searches) AS searches,
                (SELECT COUNT(*) FROM tracks) AS tracks,
                (SELECT COUNT(*) FROM favorites) AS favorites
            """
        ).fetchone()
        return dict(row)


def _row_to_track(row: sqlite3.Row) -> TrackRecord:
    return TrackRecord(
        track_id=row["track_id"],
        title=row["title"],
        artist=row["artist"],
        album=row["album"],
        genre=row["genre"],
        release_date=row["release_date"],
        duration_ms=row["duration_ms"],
        preview_url=row["preview_url"],
        track_url=row["track_url"],
        artwork_url=row["artwork_url"],
    )
