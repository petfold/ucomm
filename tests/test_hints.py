"""Push/hint delivery abstraction tests (issue D-4)."""

from ucomm import InMemoryHints


def test_poll_with_no_hints_returns_empty():
    hints = InMemoryHints()
    assert hints.poll() == []


def test_publish_then_poll_drains_it():
    hints = InMemoryHints()
    hints.publish("ch1")
    assert hints.poll() == ["ch1"]


def test_poll_clears_pending_hints():
    hints = InMemoryHints()
    hints.publish("ch1")
    hints.poll()
    assert hints.poll() == []


def test_repeated_hints_for_same_channel_are_deduplicated():
    hints = InMemoryHints()
    hints.publish("ch1")
    hints.publish("ch1")
    hints.publish("ch1")
    assert hints.poll() == ["ch1"]


def test_multiple_channels_all_drained_sorted():
    hints = InMemoryHints()
    hints.publish("ch2")
    hints.publish("ch1")
    hints.publish("ch3")
    assert hints.poll() == ["ch1", "ch2", "ch3"]


def test_hints_after_a_poll_are_independent_of_earlier_ones():
    hints = InMemoryHints()
    hints.publish("ch1")
    hints.poll()
    hints.publish("ch2")
    assert hints.poll() == ["ch2"]


def test_missing_a_hint_never_breaks_polling():
    # The whole point of the interface: a daemon that never consults hints
    # at all is a valid, fully-functional (just less timely) user of it.
    hints = InMemoryHints()
    hints.publish("ch1")
    # ... daemon never calls poll() ...
    from ucomm import ChannelDirectory, DirectoryEntry, PolicyState, build_dashboard

    directory = ChannelDirectory()
    directory.add(DirectoryEntry(channel="ch1"))
    dash = build_dashboard(directory, {}, PolicyState(threshold=20), {}, 0.0)
    assert dash.active == ()
    assert dash.obsolete == ()
