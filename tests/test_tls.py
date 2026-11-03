from pathlib import Path

import certifi

from fathomnet_open_data import tls


def test_default_verification_for_other_hosts():
    assert tls.verify_for("https://storage.googleapis.com/x/a.jpg") is True
    assert tls.verify_for("not a url") is True


def test_hurl_bundle_adds_missing_chain_cert_to_certifi_roots():
    path = tls.verify_for("https://hurlimage.soest.hawaii.edu/SupplementalPhotos/a.jpg")
    bundle = Path(path).read_text()
    assert certifi.contents() in bundle
    assert bundle.count("BEGIN CERTIFICATE") == certifi.contents().count("BEGIN CERTIFICATE") + 1


def test_every_listed_cert_is_packaged():
    for names in tls.MISSING_CHAIN_CERTS.values():
        for name in names:
            text = (Path(tls.__file__).parent / "certs" / name).read_text()
            assert "BEGIN CERTIFICATE" in text
