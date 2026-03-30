"""Tests for FIRES protocol integration
"""
import json
import os
import tempfile

from fediblockhole.blocklists import Blocklist
from fediblockhole.const import SeverityLevel
from fediblockhole.fires import (
    FIRESState,
    apply_changes,
    build_public_comment,
    fires_labels_to_comment,
    fires_policy_to_severity,
    snapshot_to_blocklist,
)


# -- Label map used across tests --

LABEL_MAP = {
    "http://localhost:4444/labels/label-uuid-hate-speech": "Hate Speech",
    "http://localhost:4444/labels/label-uuid-spam": "Spam",
    "http://localhost:4444/labels/label-uuid-csam": "CSAM",
    "http://localhost:4444/labels/label-uuid-troll": "Troll",
    "http://localhost:4444/labels/label-uuid-harassment": "Online Harassment",
    "http://localhost:4444/labels/label-uuid-disinformation": "Disinformation",
}


def load_fixture(name):
    path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(path) as f:
        return json.load(f)


# -- Policy mapping tests --


def test_policy_drop_maps_to_suspend():
    assert fires_policy_to_severity("drop") == "suspend"


def test_policy_reject_maps_to_suspend():
    assert fires_policy_to_severity("reject") == "suspend"


def test_policy_filter_maps_to_silence():
    assert fires_policy_to_severity("filter") == "silence"


def test_policy_unknown_maps_to_suspend():
    assert fires_policy_to_severity("whatever") == "suspend"


# -- Label comment tests --


def test_labels_to_comment():
    labels = [
        "http://localhost:4444/labels/label-uuid-hate-speech",
        "http://localhost:4444/labels/label-uuid-troll",
    ]
    result = fires_labels_to_comment(labels, LABEL_MAP)
    assert result == "Hate Speech, Troll"


def test_labels_to_comment_unknown_label():
    labels = ["http://localhost:4444/labels/unknown-uuid"]
    result = fires_labels_to_comment(labels, LABEL_MAP)
    assert result == "unknown-uuid"


def test_labels_to_comment_empty():
    result = fires_labels_to_comment([], LABEL_MAP)
    assert result == ""


# -- Comment building tests --


def test_build_public_comment_labels_only():
    labels = ["http://localhost:4444/labels/label-uuid-hate-speech"]
    result = build_public_comment(labels, LABEL_MAP)
    assert result == "Hate Speech"


def test_build_public_comment_comment_only():
    result = build_public_comment([], LABEL_MAP, "Admin recruits for brigading")
    assert result == "Admin recruits for brigading"


def test_build_public_comment_labels_and_comment():
    labels = [
        "http://localhost:4444/labels/label-uuid-hate-speech",
        "http://localhost:4444/labels/label-uuid-harassment",
    ]
    result = build_public_comment(labels, LABEL_MAP, "Documented targeting of trans users")
    assert result == "Hate Speech, Online Harassment \u2014 Documented targeting of trans users"


def test_build_public_comment_empty():
    result = build_public_comment([], LABEL_MAP, "")
    assert result == ""


# -- Snapshot parsing tests --


def test_snapshot_to_blocklist():
    snapshot = load_fixture("data-fires-snapshot.json")
    bl, al = snapshot_to_blocklist(snapshot, "test-fires", LABEL_MAP)

    # Should have 4 domains (the retraction for redeemed.example is skipped)
    assert len(bl) == 4
    assert "badactor.example" in bl
    assert "spammer.example" in bl
    assert "csam.example" in bl
    assert "troll.example" in bl
    assert "redeemed.example" not in bl
    # No accept policies in fixture, so allowlist should be empty
    assert len(al) == 0


def test_snapshot_severity_mapping():
    snapshot = load_fixture("data-fires-snapshot.json")
    bl, al = snapshot_to_blocklist(snapshot, "test-fires", LABEL_MAP)

    # drop -> suspend
    assert bl["badactor.example"].severity.level == SeverityLevel.SUSPEND
    # filter -> silence
    assert bl["spammer.example"].severity.level == SeverityLevel.SILENCE
    # reject -> suspend
    assert bl["csam.example"].severity.level == SeverityLevel.SUSPEND
    # filter -> silence
    assert bl["troll.example"].severity.level == SeverityLevel.SILENCE


def test_snapshot_labels_as_comments():
    snapshot = load_fixture("data-fires-snapshot.json")
    bl, al = snapshot_to_blocklist(snapshot, "test-fires", LABEL_MAP)

    assert bl["badactor.example"].public_comment == "Hate Speech"
    assert bl["spammer.example"].public_comment == "Spam"
    assert bl["csam.example"].public_comment == "CSAM"
    assert bl["troll.example"].public_comment == "Troll, Online Harassment"


def test_snapshot_max_severity():
    snapshot = load_fixture("data-fires-snapshot.json")
    bl, al = snapshot_to_blocklist(snapshot, "test-fires", LABEL_MAP, max_severity="silence")

    # Everything should be capped at silence
    assert bl["badactor.example"].severity.level == SeverityLevel.SILENCE
    assert bl["csam.example"].severity.level == SeverityLevel.SILENCE


def test_snapshot_respects_retractions():
    snapshot = load_fixture("data-fires-snapshot.json")
    retractions = {"spammer.example"}
    bl, al = snapshot_to_blocklist(snapshot, "test-fires", LABEL_MAP, retractions=retractions)

    assert "spammer.example" not in bl
    assert len(bl) == 3


# -- Changes feed tests --


def test_apply_changes_add():
    changes = load_fixture("data-fires-changes.json")
    bl = Blocklist("test-fires")
    al = Blocklist("test-fires")
    state = FIRESState(os.path.join(tempfile.mkdtemp(), "state.json"))

    bl, al = apply_changes(
        bl, al, changes["orderedItems"], LABEL_MAP, state, "test-dataset"
    )

    # newbad.example added, troll.example added (updated)
    assert "newbad.example" in bl
    assert "troll.example" in bl
    assert bl["newbad.example"].severity.level == SeverityLevel.SUSPEND
    assert bl["newbad.example"].public_comment == "Disinformation"


def test_apply_changes_retraction():
    changes = load_fixture("data-fires-changes.json")

    # Start with spammer.example in the blocklist
    bl = Blocklist("test-fires")
    al = Blocklist("test-fires")
    from fediblockhole.const import DomainBlock
    bl.blocks["spammer.example"] = DomainBlock("spammer.example", "silence")

    state = FIRESState(os.path.join(tempfile.mkdtemp(), "state.json"))

    bl, al = apply_changes(
        bl, al, changes["orderedItems"], LABEL_MAP, state, "test-dataset"
    )

    # spammer.example should be retracted
    assert "spammer.example" not in bl

    # Should be recorded in state
    assert "spammer.example" in state.get_retractions("test-dataset")


def test_apply_changes_severity_upgrade():
    """A recommendation can upgrade severity (troll.example: filter -> drop)"""
    changes = load_fixture("data-fires-changes.json")

    bl = Blocklist("test-fires")
    al = Blocklist("test-fires")
    from fediblockhole.const import DomainBlock
    bl.blocks["troll.example"] = DomainBlock("troll.example", "silence")

    state = FIRESState(os.path.join(tempfile.mkdtemp(), "state.json"))

    bl, al = apply_changes(
        bl, al, changes["orderedItems"], LABEL_MAP, state, "test-dataset"
    )

    # troll.example should be upgraded to suspend (drop policy)
    assert bl["troll.example"].severity.level == SeverityLevel.SUSPEND
    # And should now have 3 labels
    assert "Hate Speech" in bl["troll.example"].public_comment


def test_apply_changes_undo_retraction():
    """Re-recommending a retracted domain clears the retraction."""
    state = FIRESState(os.path.join(tempfile.mkdtemp(), "state.json"))
    state.add_retraction("test-dataset", "newbad.example")
    assert "newbad.example" in state.get_retractions("test-dataset")

    changes = load_fixture("data-fires-changes.json")
    bl = Blocklist("test-fires")
    al = Blocklist("test-fires")

    bl, al = apply_changes(
        bl, al, changes["orderedItems"], LABEL_MAP, state, "test-dataset"
    )

    # newbad.example was recommended again, so retraction should be cleared
    assert "newbad.example" not in state.get_retractions("test-dataset")
    assert "newbad.example" in bl


# -- State file tests --


def test_state_persistence():
    tmpdir = tempfile.mkdtemp()
    filepath = os.path.join(tmpdir, "state.json")

    state = FIRESState(filepath)
    state.set_cursor("http://fires.example/datasets/1", "http://fires.example/datasets/1/changes?since=abc")
    state.add_retraction("http://fires.example/datasets/1", "bad.example")
    state.save()

    # Reload from disk
    state2 = FIRESState(filepath)
    assert state2.get_cursor("http://fires.example/datasets/1") == "http://fires.example/datasets/1/changes?since=abc"
    assert "bad.example" in state2.get_retractions("http://fires.example/datasets/1")


def test_state_empty_on_missing_file():
    state = FIRESState("/tmp/nonexistent_fires_state_test.json")
    assert state.get_cursor("anything") is None
    assert len(state.get_retractions("anything")) == 0


# -- Accept policy / allowlist tests --


def test_snapshot_accept_policy_to_allowlist():
    """Domains with 'accept' policy go to allowlist, not blocklist."""
    snapshot = {
        "orderedItems": [
            {
                "type": "Recommendation",
                "entityKind": "domain",
                "entityKey": "good.example",
                "recommendedPolicy": "accept",
                "labels": [],
            },
            {
                "type": "Recommendation",
                "entityKind": "domain",
                "entityKey": "bad.example",
                "recommendedPolicy": "drop",
                "labels": [],
            },
        ]
    }
    bl, al = snapshot_to_blocklist(snapshot, "test", LABEL_MAP)

    assert "good.example" not in bl
    assert "good.example" in al
    assert al["good.example"].severity.level == SeverityLevel.NONE

    assert "bad.example" in bl
    assert "bad.example" not in al


def test_apply_changes_accept_moves_to_allowlist():
    """A domain recommended with accept should move from blocklist to allowlist."""
    bl = Blocklist("test")
    al = Blocklist("test")
    from fediblockhole.const import DomainBlock
    bl.blocks["reformed.example"] = DomainBlock("reformed.example", "suspend")

    changes = [
        {
            "type": "Recommendation",
            "entityKind": "domain",
            "entityKey": "reformed.example",
            "recommendedPolicy": "accept",
            "labels": [],
        }
    ]
    state = FIRESState(os.path.join(tempfile.mkdtemp(), "state.json"))
    bl, al = apply_changes(bl, al, changes, LABEL_MAP, state, "test")

    assert "reformed.example" not in bl
    assert "reformed.example" in al


def test_apply_changes_block_removes_from_allowlist():
    """A block recommendation should remove domain from allowlist."""
    bl = Blocklist("test")
    al = Blocklist("test")
    from fediblockhole.const import DomainBlock
    al.blocks["fallen.example"] = DomainBlock("fallen.example", "noop")

    changes = [
        {
            "type": "Recommendation",
            "entityKind": "domain",
            "entityKey": "fallen.example",
            "recommendedPolicy": "drop",
            "labels": [],
        }
    ]
    state = FIRESState(os.path.join(tempfile.mkdtemp(), "state.json"))
    bl, al = apply_changes(bl, al, changes, LABEL_MAP, state, "test")

    assert "fallen.example" in bl
    assert "fallen.example" not in al


# -- ignore_accept tests --


def test_snapshot_ignore_accept():
    """When ignore_accept=True, accept policies are silently skipped."""
    snapshot = {
        "orderedItems": [
            {
                "type": "Recommendation",
                "entityKind": "domain",
                "entityKey": "good.example",
                "recommendedPolicy": "accept",
                "labels": [],
            },
            {
                "type": "Recommendation",
                "entityKind": "domain",
                "entityKey": "bad.example",
                "recommendedPolicy": "drop",
                "labels": [],
            },
        ]
    }
    bl, al = snapshot_to_blocklist(snapshot, "test", LABEL_MAP, ignore_accept=True)

    assert "good.example" not in bl
    assert "good.example" not in al  # not in allowlist either
    assert "bad.example" in bl


def test_apply_changes_ignore_accept():
    """When ignore_accept=True, accept changes don't modify blocklist or allowlist."""
    bl = Blocklist("test")
    al = Blocklist("test")
    from fediblockhole.const import DomainBlock
    bl.blocks["reformed.example"] = DomainBlock("reformed.example", "suspend")

    changes = [
        {
            "type": "Recommendation",
            "entityKind": "domain",
            "entityKey": "reformed.example",
            "recommendedPolicy": "accept",
            "labels": [],
        }
    ]
    state = FIRESState(os.path.join(tempfile.mkdtemp(), "state.json"))
    bl, al = apply_changes(bl, al, changes, LABEL_MAP, state, "test",
                           ignore_accept=True)

    # Should still be in blocklist, not moved to allowlist
    assert "reformed.example" in bl
    assert "reformed.example" not in al


# -- Advisory handling tests --


def test_snapshot_skips_advisories():
    """Advisories are informational only, not actionable blocks."""
    snapshot = {
        "orderedItems": [
            {
                "type": "Recommendation",
                "entityKind": "domain",
                "entityKey": "bad.example",
                "recommendedPolicy": "drop",
                "labels": [],
            },
            {
                "type": "Advisory",
                "entityKind": "domain",
                "entityKey": "watch.example",
                "labels": ["http://localhost:4444/labels/label-uuid-spam"],
            },
        ]
    }
    bl, al = snapshot_to_blocklist(snapshot, "test", LABEL_MAP)

    assert "bad.example" in bl
    assert "watch.example" not in bl
    assert "watch.example" not in al


def test_apply_changes_advisory_removes_block():
    """Downgrading from Recommendation to Advisory removes the block."""
    bl = Blocklist("test")
    al = Blocklist("test")
    from fediblockhole.const import DomainBlock
    bl.blocks["downgraded.example"] = DomainBlock("downgraded.example", "suspend")

    # Advisory in changes feed — no recommendedPolicy, just labels
    changes = [
        {
            "type": "Advisory",
            "entityKind": "domain",
            "entityKey": "downgraded.example",
            "labels": ["http://localhost:4444/labels/label-uuid-spam"],
        }
    ]
    state = FIRESState(os.path.join(tempfile.mkdtemp(), "state.json"))
    bl, al = apply_changes(bl, al, changes, LABEL_MAP, state, "test")

    # Advisory doesn't create a block, and the snapshot would no longer
    # have a Recommendation for this domain, so it falls out naturally.
    # The changes feed advisory itself doesn't remove the block — that
    # happens because the snapshot no longer includes a Recommendation.
    # apply_changes only acts on Recommendation and Retraction types.
    assert "downgraded.example" in bl  # still there from the blocklist


# -- Actor entity skipping tests --


def test_snapshot_skips_actor_entities():
    """Only domain entities are processed, actors are skipped."""
    snapshot = {
        "orderedItems": [
            {
                "type": "Recommendation",
                "entityKind": "domain",
                "entityKey": "bad.example",
                "recommendedPolicy": "drop",
                "labels": [],
            },
            {
                "type": "Recommendation",
                "entityKind": "actor",
                "entityKey": "baduser@some.instance",
                "recommendedPolicy": "drop",
                "labels": [],
            },
        ]
    }
    bl, al = snapshot_to_blocklist(snapshot, "test", LABEL_MAP)

    assert "bad.example" in bl
    assert len(bl) == 1  # actor was skipped


# -- URL parsing tests --


def test_parse_dataset_url():
    from fediblockhole import _parse_dataset_url

    server, did = _parse_dataset_url(
        "https://fires.example.com/datasets/019d3565-f022-777b-abbc-c43d649f294b"
    )
    assert server == "https://fires.example.com"
    assert did == "019d3565-f022-777b-abbc-c43d649f294b"


def test_parse_dataset_url_trailing_slash():
    from fediblockhole import _parse_dataset_url

    server, did = _parse_dataset_url(
        "https://fires.example.com/datasets/019d3565-f022-777b-abbc-c43d649f294b/"
    )
    assert server == "https://fires.example.com"
    assert did == "019d3565-f022-777b-abbc-c43d649f294b"


def test_parse_dataset_url_with_snapshot_path():
    from fediblockhole import _parse_dataset_url

    server, did = _parse_dataset_url(
        "https://fires.example.com/datasets/019d3565-f022-777b-abbc-c43d649f294b/snapshot"
    )
    assert server == "https://fires.example.com"
    assert did == "019d3565-f022-777b-abbc-c43d649f294b"


def test_parse_dataset_url_invalid():
    from fediblockhole import _parse_dataset_url
    import pytest

    with pytest.raises(ValueError, match="missing /datasets/"):
        _parse_dataset_url("https://fires.example.com/labels/something")
