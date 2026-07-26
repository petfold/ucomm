"""ucomm: universal communicator middleware for Ethereum Swarm (working title)."""

from .attention import Decision, Intensity, PolicyState, SenderContext, decide
from .contact import ContactCard, make_contact_card, verify_contact_card
from .envelope import AttentionClaim, Envelope, EventKind, Genesis, GenesisError, TimeWindow
from .log import AuthorLog, merge_causal
from .rendezvous import InMemoryRendezvous, Rendezvous
from .signing import InvalidSignature, address_of, sign_envelope, verify_envelope
from .store import RecordStoreAuthorLog, envelope_to_record, record_to_envelope

__all__ = [
    "AttentionClaim",
    "AuthorLog",
    "ContactCard",
    "Decision",
    "Envelope",
    "EventKind",
    "Genesis",
    "GenesisError",
    "InMemoryRendezvous",
    "Intensity",
    "InvalidSignature",
    "PolicyState",
    "RecordStoreAuthorLog",
    "Rendezvous",
    "SenderContext",
    "TimeWindow",
    "address_of",
    "decide",
    "envelope_to_record",
    "make_contact_card",
    "merge_causal",
    "record_to_envelope",
    "sign_envelope",
    "verify_contact_card",
    "verify_envelope",
]
