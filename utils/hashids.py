from __future__ import annotations

from django.conf import settings
from hashids import Hashids


def get_hashids() -> Hashids:
    """Create a configured Hashids instance using Django settings."""

    hashid_kwargs = {
        "salt": settings.DJANGO_HASHIDS_SALT,
        "min_length": getattr(settings, "DJANGO_HASHIDS_MIN_LENGTH", 0),
    }

    alphabet = getattr(settings, "DJANGO_HASHIDS_ALPHABET", None)
    if alphabet:
        hashid_kwargs["alphabet"] = alphabet

    return Hashids(**hashid_kwargs)


_hashids = get_hashids()


class HashidConverter:
    """Path converter that obfuscates integer IDs using Hashids."""

    regex = r"[0-9A-Za-z]+"

    def to_python(self, value: str) -> int:
        decoded = _hashids.decode(value)
        if not decoded:
            raise ValueError("Invalid hashid")
        return decoded[0]

    def to_url(self, value: int) -> str:
        return _hashids.encode(int(value))
