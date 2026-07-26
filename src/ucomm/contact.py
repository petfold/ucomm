"""Out-of-band contact exchange (M1).

Before any channel exists, two parties need a minimal way to hand each
other an address they can trust really corresponds to a key someone
controls, over a transport with no verification of its own -- a pasted
string, a QR code, a business card. `ContactCard` is that minimum: an
address plus a self-attestation signature, domain-separated from envelope
signing so a card can never be replayed as (or forged from) a signed
envelope. It catches a copy/paste error or an active tamperer on the
exchange channel before any channel or message exists.

This is deliberately NOT the identity-wot library (ROADMAP.md: root keys,
device delegation, petnames, attestations -- a standalone project tracking
the ecosystem "Swarm ID" work). No delegation, no petnames (DESIGN.md
section 7: petnames are local, never part of what's exchanged), no
rendezvous (that's issue K-5 / milestone M3, for *unsolicited* contact --
this is for two parties already coordinating out-of-band). Just: prove
control of an address before anyone builds a channel around it.
"""

from __future__ import annotations

from dataclasses import dataclass

from bee.swarm.errors import BeeError
from bee.swarm.keys import PrivateKey, verify_signature
from bee.swarm.typed_bytes import EthAddress, Signature

from .envelope import PubKey
from .signing import address_of

_DOMAIN = b"ucomm-contact-card-v1:"
_STR_PREFIX = "ucomm-contact-v1:"


def _card_bytes(address: PubKey) -> bytes:
    """Domain-separated from `ucomm.signing`'s envelope bytes: an envelope
    signature can never be replayed as a contact card, or vice versa."""
    return _DOMAIN + address.encode("ascii")


@dataclass(frozen=True)
class ContactCard:
    """A self-attested address: proof its holder controls the signing key.

    Not proof of *who* holds it -- that's for the receiver's own local
    petname/WoT judgment (DESIGN.md section 7), never something a card
    asserts about itself.
    """

    address: PubKey
    sig: str

    def to_str(self) -> str:
        """Compact form safe to paste, email, or encode as a QR code."""
        return f"{_STR_PREFIX}{self.address}:{self.sig}"

    @classmethod
    def from_str(cls, s: str) -> ContactCard:
        if not s.startswith(_STR_PREFIX):
            raise ValueError(f"not a ucomm contact card: {s!r}")
        rest = s[len(_STR_PREFIX):]
        address, sep, sig = rest.partition(":")
        if not sep:
            raise ValueError(f"malformed contact card: {s!r}")
        return cls(address=address, sig=sig)


def make_contact_card(key: PrivateKey) -> ContactCard:
    """Self-attest `key`'s address: proof of control, not proof of identity."""
    address = address_of(key)
    signature = key.sign(_card_bytes(address))
    return ContactCard(address=address, sig=signature.to_hex())


def verify_contact_card(card: ContactCard) -> bool:
    """True iff `card.sig` really proves control of `card.address`."""
    try:
        signature = Signature.from_hex(card.sig)
        expected = EthAddress.from_hex(card.address)
    except BeeError:
        return False
    return verify_signature(signature, _card_bytes(card.address), expected)
