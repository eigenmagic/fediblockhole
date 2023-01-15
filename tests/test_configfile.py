"""Test the config file is loading parameters correctly
"""
from util import shim_argparse
from fediblockhole import setup_argparse, augment_args

def test_parse_tomldata():
    tomldata = """
# Test TOML config for FediBlockHole

blocklist_instance_sources = []  

blocklist_url_sources = []  

save_intermediate = true

import_fields = ['public_comment']
"""
    ap = setup_argparse()
    args = ap.parse_args([])
    args = augment_args(args, tomldata)

    assert args.blocklist_instance_sources == []
    assert args.blocklist_url_sources == []
    assert args.save_intermediate == True
    assert args.import_fields == ['public_comment']

def test_set_mergeplan_max():
    tomldata = """mergeplan = 'max'
    """
    args = shim_argparse([], tomldata)

    assert args.mergeplan == 'max'

def test_set_mergeplan_min():
    tomldata = """mergeplan = 'min'
    """
    args = shim_argparse([], tomldata)

    assert args.mergeplan == 'min'

def test_set_allowlists():
    tomldata = """# Comment on config
allowlist_url_sources = [ { url='file:///path/to/allowlist', format='csv'} ] 
"""
    args = shim_argparse([], tomldata)

    assert args.mergeplan == 'max'
    assert args.allowlist_url_sources == [{
        'url': 'file:///path/to/allowlist',
        'format': 'csv',
        }]
