from scripts.upload_index import upload_index


class FakePaginator:
    def __init__(self, keys):
        self.keys = keys

    def paginate(self, Bucket, Prefix):
        yield {"Contents": [{"Key": key} for key in self.keys if key.startswith(Prefix)]}


class FakeS3:
    def __init__(self, existing):
        self.existing = existing
        self.deleted = []
        self.uploaded = []

    def get_paginator(self, name):
        return FakePaginator(self.existing)

    def delete_objects(self, Bucket, Delete):
        self.deleted += [obj["Key"] for obj in Delete["Objects"]]

    def upload_file(self, path, bucket, key):
        self.uploaded.append(key)


def test_upload_replaces_previous_index(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    (tmp_path / "abc").mkdir()
    (tmp_path / "abc" / "data.bin").write_text("x")
    s3 = FakeS3(existing=["index/current/antigo.bin", "outro/arquivo"])

    count = upload_index(tmp_path, "bucket", "index/current", s3=s3)

    assert count == 2
    assert s3.deleted == ["index/current/antigo.bin"]
    assert sorted(s3.uploaded) == ["index/current/abc/data.bin", "index/current/manifest.json"]
