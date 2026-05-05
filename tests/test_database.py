from __future__ import annotations

from app.database import Database, TrackRecord


def test_database_tracks_history_and_favorites():
    db = Database(":memory:")
    db.init()

    db.upsert_user(1, "ali", "Ali", None)
    db.add_search(1, "test song", 1)
    db.save_tracks(
        [
            TrackRecord(
                track_id=10,
                title="Song",
                artist="Artist",
                album="Album",
                genre="Pop",
                release_date="2024-01-01T00:00:00Z",
                duration_ms=180000,
                preview_url="https://example.com/preview.m4a",
                track_url="https://example.com/track",
                artwork_url="https://example.com/art.jpg",
            )
        ]
    )

    assert db.get_track(10).title == "Song"
    assert db.add_favorite(1, 10) is True
    assert db.add_favorite(1, 10) is False
    assert len(db.get_favorites(1)) == 1
    assert db.get_history(1)[0]["query"] == "test song"
    assert db.stats()["users"] == 1

    db.close()
