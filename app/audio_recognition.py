from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


AUDD_ENDPOINT = "https://api.audd.io/"


@dataclass(frozen=True)
class RecognitionResult:
    artist: str
    title: str
    album: str | None
    release_date: str | None
    song_link: str | None
    timecode: str | None


class RecognitionError(RuntimeError):
    pass


def recognize_audio_file(
    api_token: str,
    filename: str,
    data: bytes,
    mime_type: str | None = None,
) -> RecognitionResult | None:
    if not api_token:
        raise RecognitionError("AUDD_API_TOKEN sozlanmagan.")
    if not data:
        raise RecognitionError("Audio fayl bo'sh.")

    body, content_type = _multipart_body(
        fields={
            "api_token": api_token,
            "return": "apple_music,spotify",
        },
        file_field="file",
        filename=filename or "audio.ogg",
        file_data=data,
        mime_type=mime_type or "application/octet-stream",
    )
    request = urllib.request.Request(
        AUDD_ENDPOINT,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RecognitionError(f"AudD HTTP {exc.code}: {detail}") from exc
    except OSError as exc:
        raise RecognitionError(f"AudD bilan aloqa bo'lmadi: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RecognitionError("AudD noto'g'ri JSON javob qaytardi.") from exc

    if payload.get("status") != "success":
        error = payload.get("error") or payload
        raise RecognitionError(f"AudD xatosi: {error}")

    result = payload.get("result")
    if not result:
        return None

    artist = result.get("artist")
    title = result.get("title")
    if not artist or not title:
        return None

    return RecognitionResult(
        artist=str(artist),
        title=str(title),
        album=_optional_text(result.get("album")),
        release_date=_optional_text(result.get("release_date")),
        song_link=_optional_text(result.get("song_link")),
        timecode=_optional_text(result.get("timecode")),
    )


def _multipart_body(
    fields: dict[str, str],
    file_field: str,
    filename: str,
    file_data: bytes,
    mime_type: str,
) -> tuple[bytes, str]:
    boundary = f"----musiqa-bot-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    safe_filename = filename.replace('"', "")
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{safe_filename}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
            file_data,
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
