from fathomnet_open_data.api import FathomNetClient


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return FakeResponse(self.handler(url, params or {}))


def test_iter_images_pages_until_total_pages():
    def handler(url, params):
        page = params["page"]
        return {"content": [{"uuid": f"{page}-{i}"} for i in range(2)], "totalPages": 3}

    session = FakeSession(handler)
    images = list(FathomNetClient("https://x/api/", session).iter_images(page_size=2))
    assert len(images) == 6
    assert session.calls[0] == ("https://x/api/images", {"page": 0, "size": 2, "sort": "id"})


def test_iter_images_empty():
    session = FakeSession(lambda url, params: {"content": [], "totalPages": 0})
    assert list(FathomNetClient(session=session).iter_images()) == []
    assert len(session.calls) == 1


def test_iter_upload_image_uuids_offsets():
    data = [{"uuid": str(i)} for i in range(5)]

    def handler(url, params):
        return data[params["offset"] : params["offset"] + params["limit"]]

    session = FakeSession(handler)
    uuids = list(FathomNetClient(session=session).iter_upload_image_uuids("u", page_size=2))
    assert uuids == ["0", "1", "2", "3", "4"]
    assert [p["offset"] for _, p in session.calls] == [0, 2, 4]
