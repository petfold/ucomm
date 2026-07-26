"""Rendezvous interface (DESIGN.md section 6, issue K-5).

Rendezvous covers the two multi-writer needs of the system: unsolicited first
contact (open mailboxes) and discovery of open channels. Everything among known
contacts runs on author logs + PSS and does not come through here.

Planned implementations:
- InMemoryRendezvous (below): tests and M0 prototyping.
- PssShimRendezvous (M2/M3 interim): PSS-based contact requests to a full node.
- GsocRendezvous (M3 target): Graffiti Single-Owner Chunk mailboxes. NOTE the
  Bee constraints: subscriber must be a full node in the mined identifier's
  neighborhood; GSOC wants MUTABLE stamps (unlike feeds). Admission control
  (stamp proof + optional RLN + bond, ATTENTION.md section 4) is enforced by
  the subscriber, not the network.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Protocol

from .envelope import Envelope

AdmitFn = Callable[[str, Envelope], bool]


class Rendezvous(Protocol):
    """Many-writers-to-one-address drop point with subscriber-side admission."""

    def post(self, address: str, env: Envelope) -> bool:
        """Attempt to deposit an envelope at an address. Returns admission result."""
        ...

    def poll(self, address: str) -> Iterable[Envelope]:
        """Drain envelopes deposited at an address (subscriber side)."""
        ...


class InMemoryRendezvous:
    """Process-local Rendezvous for tests. Admission hook mirrors the real design."""

    def __init__(self, admit: AdmitFn | None = None) -> None:
        self._boxes: dict[str, list[Envelope]] = defaultdict(list)
        self._admit: AdmitFn = admit or (lambda address, env: True)

    def post(self, address: str, env: Envelope) -> bool:
        if not self._admit(address, env):
            return False
        self._boxes[address].append(env)
        return True

    def poll(self, address: str) -> list[Envelope]:
        drained, self._boxes[address] = self._boxes[address], []
        return drained
