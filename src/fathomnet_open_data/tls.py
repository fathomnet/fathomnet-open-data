"""TLS settings for image hosts whose servers send an incomplete certificate chain.

Browsers fill in a missing intermediate from the certificate's AIA URL; Python does not. For the
hosts below we add that intermediate to certifi's roots. Each one is cross-signed by a root that
certifi already trusts, so no new trust anchor is introduced.
"""

import functools
import tempfile
from importlib import resources
from urllib.parse import urlsplit

import certifi

# Host -> certificate files under fathomnet_open_data/certs/ that its server omits.
MISSING_CHAIN_CERTS = {
    "hurlimage.soest.hawaii.edu": ("emsign-root-tls-ca-g1-cross.pem",),
}


@functools.cache
def _bundle(names: tuple[str, ...]) -> str:
    """Path to a CA bundle of certifi's roots plus the given certificates."""
    parts = [certifi.contents()]
    certs = resources.files("fathomnet_open_data") / "certs"
    parts += [(certs / name).read_text() for name in names]
    with tempfile.NamedTemporaryFile("w", prefix="fathomnet-ca-", suffix=".pem", delete=False) as f:
        f.write("\n".join(parts))
    return f.name


def verify_for(url: str) -> str | bool:
    """Value for requests' `verify`: a custom bundle for listed hosts, else the default."""
    names = MISSING_CHAIN_CERTS.get(urlsplit(url).hostname or "")
    return _bundle(names) if names else True
