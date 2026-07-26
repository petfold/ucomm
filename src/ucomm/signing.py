"""Envelope signing and verification (M1: real signatures over device keys).

Uses `bee.swarm.keys` (the `swarm-bee` package -- already an optional
dependency of recordstore's `feeds` extra) rather than inventing a second
crypto scheme: secp256k1 with the Ethereum signed-message digest, the same
scheme Bee verifies SOC and feed signatures against. Signing a ucomm
envelope with the same primitives Swarm itself uses means a device key can
double as a feed signer with no translation layer -- exactly what "author
logs on feeds" (ROADMAP.md milestone M1) needs.

`PubKey` in this codebase (see `ucomm.envelope`) is the signer's
Ethereum-style *address* (`PublicKey.address()`), not a raw public key.
Recoverable ECDSA signatures make that sufficient to verify: Bee identifies
SOC/feed owners the same way, by address alone.
"""

from __future__ import annotations

from dataclasses import replace

from bee.swarm.errors import BeeError
from bee.swarm.keys import PrivateKey, verify_signature
from bee.swarm.typed_bytes import EthAddress, Signature

from .encoding import canonical_bytes, to_jsonable
from .envelope import Envelope, PubKey


class InvalidSignature(ValueError):
    """An envelope's `sig` does not verify against its claimed `author`."""


def address_of(key: PrivateKey) -> PubKey:
    """The signer identity (`Envelope.author`) for `key`: its address, hex."""
    return key.public_key().address().to_hex()


def _unsigned_bytes(env: Envelope) -> bytes:
    """Canonical bytes of `env` with `sig` blanked -- what gets signed."""
    return canonical_bytes(to_jsonable(replace(env, sig="")))


def sign_envelope(env: Envelope, key: PrivateKey) -> Envelope:
    """Return a copy of `env` with `sig` set.

    `env.author` must already equal `address_of(key)` -- signing attaches a
    signature to a claimed identity, it does not assign one.
    """
    expected = address_of(key)
    if env.author != expected:
        raise ValueError(
            f"key's address {expected!r} does not match env.author {env.author!r}"
        )
    unsigned = replace(env, sig="")
    signature = key.sign(_unsigned_bytes(unsigned))
    return replace(unsigned, sig=signature.to_hex())


def verify_envelope(env: Envelope) -> bool:
    """True iff `env.sig` is a valid signature over `env` (sig blanked) by `env.author`."""
    if not env.sig:
        return False
    try:
        signature = Signature.from_hex(env.sig)
        expected = EthAddress.from_hex(env.author)
    except BeeError:
        return False
    return verify_signature(signature, _unsigned_bytes(env), expected)
