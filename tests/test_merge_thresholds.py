"""Test merge with thresholds
"""

from fediblockhole.blocklists import Blocklist, parse_blocklist
from fediblockhole import merge_blocklists, apply_mergeplan

from fediblockhole.const import SeverityLevel, DomainBlock

datafile01 = "data-suspends-01.csv"
datafile02 = "data-silences-01.csv"
datafile03 = "data-noop-01.csv"

import_fields = [
    'domain',
    'severity',
    'public_comment',
    'private_comment',
    'reject_media',
    'reject_reports',
    'obfuscate'
]

def load_test_blocklist_data(datafiles):

    blocklists = []

    for df in datafiles:
        with open(df) as fp:
            data = fp.read()
            bl = parse_blocklist(data, df, 'csv', import_fields)
            blocklists.append(bl)
    
    return blocklists

def test_mergeplan_count_2():
    """Only merge a block if present in 2 or more lists
    """

    bl_1 = Blocklist('test01', {
        'onemention.example.org': DomainBlock('onemention.example.org', 'suspend', '', '', True, True, True),
        'twomention.example.org': DomainBlock('twomention.example.org', 'suspend', '', '', True, True, True),
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        })

    bl_2 = Blocklist('test2', {
        'twomention.example.org': DomainBlock('twomention.example.org', 'suspend', '', '', True, True, True),
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
    })

    bl_3 = Blocklist('test3', {
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
    })

    ml = merge_blocklists([bl_1, bl_2, bl_3], 'max', threshold=2)

    assert 'onemention.example.org' not in ml
    assert 'twomention.example.org' in ml
    assert 'threemention.example.org' in ml

def test_mergeplan_count_3():
    """Only merge a block if present in 3 or more lists
    """

    bl_1 = Blocklist('test01', {
        'onemention.example.org': DomainBlock('onemention.example.org', 'suspend', '', '', True, True, True),
        'twomention.example.org': DomainBlock('twomention.example.org', 'suspend', '', '', True, True, True),
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        })

    bl_2 = Blocklist('test2', {
        'twomention.example.org': DomainBlock('twomention.example.org', 'suspend', '', '', True, True, True),
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
    })

    bl_3 = Blocklist('test3', {
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
    })

    ml = merge_blocklists([bl_1, bl_2, bl_3], 'max', threshold=3)

    assert 'onemention.example.org' not in ml
    assert 'twomention.example.org' not in ml
    assert 'threemention.example.org' in ml

def test_mergeplan_pct_30():
    """Only merge a block if present in 2 or more lists
    """

    bl_1 = Blocklist('test01', {
        'onemention.example.org': DomainBlock('onemention.example.org', 'suspend', '', '', True, True, True),
        'twomention.example.org': DomainBlock('twomention.example.org', 'suspend', '', '', True, True, True),
        'fourmention.example.org': DomainBlock('fourmention.example.org', 'suspend', '', '', True, True, True),

        })

    bl_2 = Blocklist('test2', {
        'twomention.example.org': DomainBlock('twomention.example.org', 'suspend', '', '', True, True, True),
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        'fourmention.example.org': DomainBlock('fourmention.example.org', 'suspend', '', '', True, True, True),
    })

    bl_3 = Blocklist('test3', {
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        'fourmention.example.org': DomainBlock('fourmention.example.org', 'suspend', '', '', True, True, True),
    })

    bl_4 = Blocklist('test4', {
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        'fourmention.example.org': DomainBlock('fourmention.example.org', 'suspend', '', '', True, True, True),
    })

    ml = merge_blocklists([bl_1, bl_2, bl_3, bl_4], 'max', threshold=30, threshold_type='pct')

    assert 'onemention.example.org' not in ml
    assert 'twomention.example.org' in ml
    assert 'threemention.example.org' in ml
    assert 'fourmention.example.org' in ml

def test_mergeplan_pct_55():
    """Only merge a block if present in 2 or more lists
    """

    bl_1 = Blocklist('test01', {
        'onemention.example.org': DomainBlock('onemention.example.org', 'suspend', '', '', True, True, True),
        'twomention.example.org': DomainBlock('twomention.example.org', 'suspend', '', '', True, True, True),
        'fourmention.example.org': DomainBlock('fourmention.example.org', 'suspend', '', '', True, True, True),

        })

    bl_2 = Blocklist('test2', {
        'twomention.example.org': DomainBlock('twomention.example.org', 'suspend', '', '', True, True, True),
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        'fourmention.example.org': DomainBlock('fourmention.example.org', 'suspend', '', '', True, True, True),
    })

    bl_3 = Blocklist('test3', {
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        'fourmention.example.org': DomainBlock('fourmention.example.org', 'suspend', '', '', True, True, True),
    })

    bl_4 = Blocklist('test4', {
        'threemention.example.org': DomainBlock('threemention.example.org', 'suspend', '', '', True, True, True),
        'fourmention.example.org': DomainBlock('fourmention.example.org', 'suspend', '', '', True, True, True),
    })

    ml = merge_blocklists([bl_1, bl_2, bl_3, bl_4], 'max', threshold=55, threshold_type='pct')

    assert 'onemention.example.org' not in ml
    assert 'twomention.example.org' not in ml
    assert 'threemention.example.org' in ml
    assert 'fourmention.example.org' in ml