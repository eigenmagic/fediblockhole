"""Test the commandline defined parameters correctly
"""

from fediblockhole import setup_argparse


def test_cmdline_no_configfile():
    """Test bare command with no configfile"""
    ap = setup_argparse()
    args = ap.parse_args([])

    assert args.config == "/etc/default/fediblockhole.conf.toml"
    assert args.mergeplan is None
    assert args.blocklist_savefile is None
    assert args.save_intermediate is False
    assert args.savedir is None
    assert args.import_fields is None
    assert args.export_fields is None

    assert args.no_fetch_url is False
    assert args.no_fetch_instance is False
    assert args.no_push_instance is False
    assert args.dryrun is False

    assert args.loglevel is None


def test_cmdline_mergeplan_min():
    """Test setting mergeplan min"""
    ap = setup_argparse()
    args = ap.parse_args(["-m", "min"])

    assert args.mergeplan == "min"


def test_set_allow_domain():
    """Set a single allow domain on commandline"""
    ap = setup_argparse()
    args = ap.parse_args(["-A", "example.org"])

    assert args.allow_domains == ["example.org"]


def test_set_multiple_allow_domains():
    """Set multiple allow domains on commandline"""
    ap = setup_argparse()
    args = ap.parse_args(
        ["-A", "example.org", "-A", "example2.org", "-A", "example3.org"]
    )

    assert args.allow_domains == ["example.org", "example2.org", "example3.org"]
