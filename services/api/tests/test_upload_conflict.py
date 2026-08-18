"""Unit tests for library object-key minting.

The API mints an opaque `library/<user>/<YYYY>/<MM>/<asset_id>.<ext>` key at
presign time — the browser never chooses where its bytes land, and the user's
real filename is preserved in the sidecar, not the key. Each upload gets a
fresh asset id, so B2 versioning is never relied on for de-dup.
"""

from app.service.upload import asset_id_from_key, mint_asset_key


def test_mint_key_is_opaque_and_prefixed():
    asset_id, key = mint_asset_key("image/jpeg")
    assert key.startswith("library/demo/")
    assert key.endswith(f"{asset_id}.jpg")


def test_each_upload_gets_a_fresh_asset_id():
    first_id, first_key = mint_asset_key("image/png")
    second_id, second_key = mint_asset_key("image/png")
    assert first_id != second_id
    assert first_key != second_key


def test_asset_id_roundtrips_from_key():
    asset_id, key = mint_asset_key("video/mp4")
    assert asset_id_from_key(key) == asset_id
    assert key.endswith(".mp4")
