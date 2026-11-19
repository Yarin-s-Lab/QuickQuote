import uuid

import pytest

from app.services.storage import InvalidStoragePathError, Storage

QUOTE_ID = "3f2b8c1e-9a4d-4e5f-8b6a-1c2d3e4f5a6b"


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "storage")


def test_path_is_uuid_pdf_under_root(storage):
    path = storage.path_for(QUOTE_ID)
    assert path.name == f"{QUOTE_ID}.pdf"
    assert path.parent == storage.root


def test_save_writes_atomically_and_leaves_no_tmp(storage):
    path = storage.save(QUOTE_ID, b"%PDF-1.7 data")
    assert path.read_bytes() == b"%PDF-1.7 data"
    assert sorted(p.name for p in storage.root.iterdir()) == [f"{QUOTE_ID}.pdf"]


def test_delete(storage):
    storage.save(QUOTE_ID, b"x")
    storage.delete(QUOTE_ID)
    storage.delete(QUOTE_ID)  # idempotent
    assert not storage.path_for(QUOTE_ID).exists()


@pytest.mark.parametrize(
    "bad",
    [
        "../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "/etc/passwd",
        "C:\\Windows\\win.ini",
        f"{QUOTE_ID}\x00.txt",
        f"../{QUOTE_ID}",
        QUOTE_ID.upper(),  # non-canonical form
        "{" + QUOTE_ID + "}",
        "",
        "not-a-uuid",
    ],
)
def test_rejects_anything_but_a_canonical_uuid(storage, bad):
    with pytest.raises(InvalidStoragePathError):
        storage.path_for(bad)


def test_random_uuids_accepted(storage):
    quote_id = str(uuid.uuid4())
    assert storage.path_for(quote_id).is_relative_to(storage.root)
