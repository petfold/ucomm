"""Bridges: adapters converting external protocols into ucomm envelopes.

DESIGN.md section 10: every bridge is an inbox adapter into the same
envelope schema and policy engine ucomm uses natively -- the "attention
firewall" is a unified inbox across everything, not just Swarm-native
channels. Kept out of the top-level `ucomm` namespace, same reasoning as
`ucomm.profiles`: a layer above the kernel, not part of it.
"""
