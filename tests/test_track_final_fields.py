from app.models.track import Track


def test_final_comment_follows_overridden_subgenre_and_explicit_clear_is_kept():
    track = Track(file_path="/tmp/a.mp3", filename="a.mp3", existing_comment="original", proposed_subgenre="proposal", override_subgenre="curated")
    assert track.final_comment == "curated"
    track.override_subgenre = ""
    assert track.final_subgenre == ""
    assert track.final_comment == "original"
