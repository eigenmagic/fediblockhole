"""Test the commandline defined parameters correctly
"""
from util import shim_argparse
from fediblockhole import setup_argparse, augment_args

def test_cmdline_no_configfile():
    """ Test bare command with no configfile
    """
    ap = setup_argparse()
    args = ap.parse_args([])

    assert args.config == '/etc/default/fediblockhole.conf.toml'
    assert args.mergeplan == None
    assert args.blocklist_savefile == None
    assert args.save_intermediate == False
    assert args.savedir == None
    assert args.import_fields == None
    assert args.export_fields == None

    assert args.no_fetch_url == False
    assert args.no_fetch_instance == False
    assert args.no_push_instance == False
    assert args.dryrun == False

    assert args.loglevel == None

def test_cmdline_mergeplan_min():
    """ Test setting mergeplan min
    """
    ap = setup_argparse()
    args = ap.parse_args(['-m', 'min'])

    assert args.mergeplan == 'min'

def test_set_allow_domain():
    """Set a single allow domain on commandline"""
    ap = setup_argparse()
    args = ap.parse_args(['-A', 'example.org'])

    assert args.allow_domains == ['example.org']

def test_set_multiple_allow_domains():
    """Set multiple allow domains on commandline"""
    ap = setup_argparse()
    args = ap.parse_args(['-A', 'example.org', '-A', 'example2.org', '-A', 'example3.org'])

    assert args.allow_domains == ['example.org', 'example2.org', 'example3.org']