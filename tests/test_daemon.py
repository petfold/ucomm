"""Channel directory + graded dashboard tests (issue D-1/D-2)."""

from ucomm import (
    AttentionClaim,
    ChannelDirectory,
    DirectoryEntry,
    Envelope,
    EventKind,
    Intensity,
    PolicyState,
    SenderContext,
    TimeWindow,
    build_dashboard,
    directory_read_state,
)

NOW = 1_000_000.0
WINDOW = TimeWindow(start=NOW - 10, end=NOW + 7200)
EXPIRED = TimeWindow(start=NOW - 7200, end=NOW - 1)
KNOWN = SenderContext(known_contact=True)


def invitation(channel, importance, urgency, seq=1, window=WINDOW, sender="alice"):
    return Envelope(
        channel=channel, author=sender, seq=seq, kind=EventKind.INVITATION,
        attention=AttentionClaim(importance=importance, urgency=urgency, relevance=window),
    )


def message(channel, seq=1, sender="alice"):
    return Envelope(channel=channel, author=sender, seq=seq, kind=EventKind.MESSAGE)


def receipt(channel, acked, seq=1, sender="alice"):
    return Envelope(channel=channel, author=sender, seq=seq, kind=EventKind.RECEIPT,
                     inline=acked.encode("ascii"))


def test_empty_directory_gives_empty_dashboard():
    directory = ChannelDirectory()
    dash = build_dashboard(directory, {}, PolicyState(threshold=20), {}, NOW)
    assert dash.active == ()
    assert dash.obsolete == ()


def test_channel_not_in_directory_is_ignored():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    events = {"ch2": [invitation("ch2", 30, 30)]}
    dash = build_dashboard(directory, events, PolicyState(threshold=20), {"alice": KNOWN}, NOW)
    assert dash.active == ()


def test_messages_are_not_dashboard_material():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    events = {"ch1": [message("ch1")]}
    dash = build_dashboard(directory, events, PolicyState(threshold=20), {"alice": KNOWN}, NOW)
    assert dash.active == ()
    assert dash.obsolete == ()


def test_expired_invitation_is_obsolete_not_active():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    events = {"ch1": [invitation("ch1", 30, 30, window=EXPIRED)]}
    dash = build_dashboard(directory, events, PolicyState(threshold=20), {"alice": KNOWN}, NOW)
    assert dash.active == ()
    assert len(dash.obsolete) == 1


def test_active_includes_sub_threshold_filed_items():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    events = {"ch1": [invitation("ch1", 2, 2)]}  # Attila's tennis schedule: low priority
    dash = build_dashboard(directory, events, PolicyState(threshold=20), {"alice": KNOWN}, NOW)
    assert len(dash.active) == 1
    assert dash.active[0].decision.intensity is Intensity.FILED
    assert dash.obsolete == ()


def test_active_sorted_by_effective_priority_descending():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    events = {"ch1": [
        invitation("ch1", 2, 2, seq=1),     # low
        invitation("ch1", 30, 30, seq=2),   # smoke from the house
        invitation("ch1", 10, 5, seq=3),    # medium
    ]}
    dash = build_dashboard(directory, events, PolicyState(threshold=20), {"alice": KNOWN}, NOW)
    priorities = [item.decision.effective_priority for item in dash.active]
    assert priorities == sorted(priorities, reverse=True)
    assert len(dash.active) == 3


def test_directory_channel_offset_mutes_without_making_it_obsolete():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1", channel_offset=-100))
    events = {"ch1": [invitation("ch1", 30, 30)]}
    policy = PolicyState(threshold=20, channel_offsets=directory.channel_offsets)
    dash = build_dashboard(directory, events, policy, {"alice": KNOWN}, NOW)
    assert len(dash.active) == 1  # still active -- not expired, just muted
    assert dash.active[0].decision.intensity is Intensity.FILED
    assert dash.obsolete == ()


def test_unknown_sender_defaults_to_stranger_ceiling():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    events = {"ch1": [invitation("ch1", 50, 50, sender="mallory")]}
    dash = build_dashboard(directory, events, PolicyState(threshold=20), {}, NOW)
    assert len(dash.active) == 1
    assert dash.active[0].decision.intensity is Intensity.FILED  # no ceiling headroom


def test_channel_directory_add_remove_iterate():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    directory.add(DirectoryEntry(channel="ch2"))
    assert len(directory) == 2
    assert "ch1" in directory
    directory.remove("ch1")
    assert "ch1" not in directory
    assert [e.channel for e in directory] == ["ch2"]


def test_channel_offsets_property_reflects_entries():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1", channel_offset=-30))
    directory.add(DirectoryEntry(channel="ch2", channel_offset=0))
    assert directory.channel_offsets == {"ch1": -30, "ch2": 0}


def test_dashboard_is_recomputed_not_cached():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    events = {"ch1": [invitation("ch1", 30, 30)]}
    policy = PolicyState(threshold=20)
    dash1 = build_dashboard(directory, events, policy, {"alice": KNOWN}, NOW)
    events["ch1"] = []  # the "source of truth" changes
    dash2 = build_dashboard(directory, events, policy, {"alice": KNOWN}, NOW)
    assert len(dash1.active) == 1
    assert dash2.active == ()


def test_directory_read_state_aggregates_across_channels():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    directory.add(DirectoryEntry(channel="ch2"))
    events = {
        "ch1": [receipt("ch1", "hash1", sender="alice")],
        "ch2": [receipt("ch2", "hash2", sender="bob")],
    }
    assert directory_read_state(directory, events) == {
        "ch1": {"alice": "hash1"},
        "ch2": {"bob": "hash2"},
    }


def test_directory_read_state_ignores_channels_outside_directory():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    events = {"ch1": [], "ch2": [receipt("ch2", "hash2")]}
    assert directory_read_state(directory, events) == {"ch1": {}}


def test_directory_read_state_empty_channel_gives_empty_map():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    assert directory_read_state(directory, {}) == {"ch1": {}}


def test_directory_read_state_dedupes_via_merge_causal():
    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    r = receipt("ch1", "hash1", sender="alice")
    events = {"ch1": [r, r]}  # delivered twice, e.g. seen via two member logs
    assert directory_read_state(directory, events) == {"ch1": {"alice": "hash1"}}
