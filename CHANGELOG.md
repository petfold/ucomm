# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

Started 2026-09-11, so 0.0.1's entry is written from the git history rather
than recorded at the time. Note that 0.0.1 was uploaded to PyPI directly rather
than by a `v*` tag push, so this repo has no release tags yet — unlike the
sibling projects, where the tag is what publishes.

## [0.0.1] — 2026-09-10

First PyPI release: universal communicator middleware for Ethereum Swarm
(working title), treating every chat, inbox and feed as one kind of thing.

### Added

- **Daemon core (M2):** directory, dashboard and hints.
- **IMAP bridge (D-5):** the conversion layer — a mail profile and
  email-to-envelope mapping — plus a live fetch loop (`ImapMailbox`).
- **Push/hint delivery interface (D-4)**, deliberately with no backend chosen.
- Test CI and the stack-wide `[test]` extra; `recordstore` unpinned.
- PyPI keywords, project URLs, and README badges.

### Changed

- **Relicensed from GPL-3.0-or-later to BSD-3-Clause**, matching the rest of
  the stack.
- Documentation: `USER_GUIDE.md` gained an introduction, a motivation and a
  milestone-by-milestone overview, with real output shown for the live Bee
  test; `DESIGN.md`/`ROADMAP.md` split call from broadcast and deferred
  broadcast; `RECOMMENDATION.md` points truth-vs-projection at ontodag's
  `PROJECTIONS.md`.
- Conventions stated explicitly: no hand-rolled crypto or parsing, and
  invariant 7 — no silent permanent dependencies.
