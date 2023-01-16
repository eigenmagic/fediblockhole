""" Test allowlists
"""
import pytest

from util import shim_argparse
from fediblockhole.const import DomainBlock
from fediblockhole import fetch_allowlists, apply_allowlists

def test_cmdline_allow_removes_domain():
    """Test that -A <domain> removes entries from merged
    """
    conf = shim_argparse(['-A', 'removeme.org'])

    merged = {
        'example.org': DomainBlock('example.org'),
        'example2.org': DomainBlock('example2.org'),
        'removeme.org': DomainBlock('removeme.org'),
        'keepblockingme.org': DomainBlock('keepblockingme.org'),
    }

    # allowlists = {
    #     'testlist': [ DomainBlock('removeme.org', 'noop'), ]
    # }
    
    merged = apply_allowlists(merged, conf, {})

    with pytest.raises(KeyError):
        merged['removeme.org']

def test_allowlist_removes_domain():
    """Test that an item in an allowlist removes entries from merged
    """
    conf = shim_argparse()

    merged = {
        'example.org': DomainBlock('example.org'),
        'example2.org': DomainBlock('example2.org'),
        'removeme.org': DomainBlock('removeme.org'),
        'keepblockingme.org': DomainBlock('keepblockingme.org'),
    }

    allowlists = {
        'testlist': [ DomainBlock('removeme.org', 'noop'), ]
    }
    
    merged = apply_allowlists(merged, conf, allowlists)

    with pytest.raises(KeyError):
        merged['removeme.org']

def test_allowlist_removes_tld():
    """Test that an item in an allowlist removes entries from merged
    """
    conf = shim_argparse()

    merged = {
        '.cf': DomainBlock('.cf'),
        'example.org': DomainBlock('example.org'),
        '.tk': DomainBlock('.tk'),
        'keepblockingme.org': DomainBlock('keepblockingme.org'),
    }

    allowlists = {
        'list1': [
            DomainBlock('.cf', 'noop'), 
            DomainBlock('.tk', 'noop'), 
        ]
    }
    
    merged = apply_allowlists(merged, conf, allowlists)

    with pytest.raises(KeyError):
        merged['.cf']

    with pytest.raises(KeyError):
        merged['.tk']