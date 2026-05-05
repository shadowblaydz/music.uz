from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request

from app.database import TrackRecord


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
MAX_ITUNES_LIMIT = 200


class MusicSearchError(RuntimeError):
    pass


class ArtistNotFoundError(MusicSearchError):
    pass


class ArtistCatalog:
    def __init__(
        self,
        artist_id: int,
        artist_name: str,
        top_tracks: list[TrackRecord],
        recent_tracks: list[TrackRecord],
    ) -> None:
        self.artist_id = artist_id
        self.artist_name = artist_name
        self.top_tracks = top_tracks
        self.recent_tracks = recent_tracks


async def search_tracks(query: str, limit: int = 8) -> list[TrackRecord]:
    clean_query = " ".join(query.split())
    if not clean_query:
        return []

    return await asyncio.to_thread(search_tracks_sync, clean_query, limit)


def search_tracks_sync(query: str, limit: int = 8) -> list[TrackRecord]:
    clean_query = " ".join(query.split())
    if not clean_query:
        return []

    payload = _request_json(
        ITUNES_SEARCH_URL,
        {
            "term": clean_query,
            "media": "music",
            "entity": "song",
            "limit": max(1, min(limit, MAX_ITUNES_LIMIT)),
        },
    )

    return _items_to_tracks(payload.get("results", []))


def search_artist_catalog_sync(query: str, limit: int = MAX_ITUNES_LIMIT) -> ArtistCatalog | None:
    artist = search_artist_sync(query)
    if not artist:
        return None

    top_tracks = lookup_artist_songs_sync(artist["artist_id"], limit=limit)
    recent_tracks = lookup_artist_songs_sync(artist["artist_id"], limit=limit, sort="recent")
    return ArtistCatalog(
        artist_id=artist["artist_id"],
        artist_name=artist["artist_name"],
        top_tracks=top_tracks,
        recent_tracks=recent_tracks,
    )


def search_artist_sync(query: str) -> dict[str, int | str] | None:
    clean_query = " ".join(query.split())
    if not clean_query:
        return None

    payload = _request_json(
        ITUNES_SEARCH_URL,
        {
            "term": clean_query,
            "media": "music",
            "entity": "musicArtist",
            "attribute": "artistTerm",
            "limit": 5,
        },
    )
    results = payload.get("results", [])
    if not results:
        return None

    normalized_query = _normalize_name(clean_query)
    for item in results:
        artist_id = item.get("artistId")
        artist_name = item.get("artistName")
        if not artist_id or not artist_name:
            continue
        normalized_name = _normalize_name(str(artist_name))
        if normalized_query == normalized_name or (
            len(normalized_query) >= 4 and normalized_query in normalized_name
        ):
            return {"artist_id": int(artist_id), "artist_name": str(artist_name)}

    return None


def lookup_artist_songs_sync(
    artist_id: int,
    limit: int = MAX_ITUNES_LIMIT,
    sort: str | None = None,
) -> list[TrackRecord]:
    params: dict[str, str | int] = {
        "id": artist_id,
        "entity": "song",
        "limit": max(1, min(limit, MAX_ITUNES_LIMIT)),
    }
    if sort:
        params["sort"] = sort

    payload = _request_json(ITUNES_LOOKUP_URL, params)
    return _items_to_tracks(payload.get("results", []))


def _request_json(url: str, params: dict[str, str | int]) -> dict[str, object]:
    encoded_params = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{encoded_params}",
        headers={"User-Agent": "musiqa-topuvchi-telegram-bot/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except OSError as exc:
        raise MusicSearchError("Musiqa qidiruv xizmati bilan aloqa bo'lmadi.") from exc
    except json.JSONDecodeError as exc:
        raise MusicSearchError("Musiqa qidiruv xizmati noto'g'ri javob qaytardi.") from exc


def _items_to_tracks(items: list[dict[str, object]]) -> list[TrackRecord]:
    tracks: list[TrackRecord] = []
    seen_ids: set[int] = set()
    for item in items:
        track_id = item.get("trackId")
        title = item.get("trackName")
        artist = item.get("artistName")
        if not track_id or not title or not artist:
            continue
        track_id = int(track_id)
        if track_id in seen_ids:
            continue
        seen_ids.add(track_id)

        artwork = item.get("artworkUrl100")
        if artwork:
            artwork = str(artwork).replace("100x100bb", "600x600bb")

        tracks.append(
            TrackRecord(
                track_id=track_id,
                title=str(title),
                artist=str(artist),
                album=_optional_text(item.get("collectionName")),
                genre=_optional_text(item.get("primaryGenreName")),
                release_date=_optional_text(item.get("releaseDate")),
                duration_ms=_optional_int(item.get("trackTimeMillis")),
                preview_url=_optional_text(item.get("previewUrl")),
                track_url=_optional_text(item.get("trackViewUrl")),
                artwork_url=artwork,
            )
        )

    return tracks


def _normalize_name(value: str) -> str:
    return " ".join(value.casefold().replace("&", "and").split())


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
