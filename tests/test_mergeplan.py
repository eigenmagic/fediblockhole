"""Various mergeplan tests
"""

from fediblockhole.blocklists import parse_blocklist
from fediblockhole import merge_blocklists, merge_comments, apply_mergeplan

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

def test_mergeplan_max():
    """Test 'max' mergeplan"""
    blocklists = load_test_blocklist_data([datafile01, datafile02])
    bl = merge_blocklists(blocklists, 'max')
    assert len(bl) == 13

    for key in bl:
        assert bl[key].severity.level == SeverityLevel.SUSPEND

def test_mergeplan_min():
    """Test 'max' mergeplan"""
    blocklists = load_test_blocklist_data([datafile01, datafile02])

    bl = merge_blocklists(blocklists, 'min')
    assert len(bl) == 13

    for key in bl:
        assert bl[key].severity.level == SeverityLevel.SILENCE

def test_mergeplan_default():
    """Default mergeplan is max, so see if it's chosen"""
    blocklists = load_test_blocklist_data([datafile01, datafile02])

    bl = merge_blocklists(blocklists)
    assert len(bl) == 13

    for key in bl:
        assert bl[key].severity.level == SeverityLevel.SUSPEND

def test_mergeplan_3_max():
    """3 datafiles and mergeplan of 'max'"""
    blocklists = load_test_blocklist_data([datafile01, datafile02, datafile03])

    bl = merge_blocklists(blocklists, 'max')
    assert len(bl) == 13

    for key in bl:
        assert bl[key].severity.level == SeverityLevel.SUSPEND
        assert bl[key].reject_media == True
        assert bl[key].reject_reports == True
        assert bl[key].obfuscate == True

def test_mergeplan_3_min():
    """3 datafiles and mergeplan of 'min'"""
    blocklists = load_test_blocklist_data([datafile01, datafile02, datafile03])

    bl = merge_blocklists(blocklists, 'min')
    assert len(bl) == 13

    for key in bl:
        assert bl[key].severity.level == SeverityLevel.NONE
        assert bl[key].reject_media == False
        assert bl[key].reject_reports == False
        assert bl[key].obfuscate == False

def test_mergeplan_noop_v_silence_max():
    """Mergeplan of max should choose silence over noop"""
    blocklists = load_test_blocklist_data([datafile02, datafile03])

    bl = merge_blocklists(blocklists, 'max')
    assert len(bl) == 13

    for key in bl:
        assert bl[key].severity.level == SeverityLevel.SILENCE

def test_mergeplan_noop_v_silence_min():
    """Mergeplan of min should choose noop over silence"""
    blocklists = load_test_blocklist_data([datafile02, datafile03])

    bl = merge_blocklists(blocklists, 'min')
    assert len(bl) == 13

    for key in bl:
        assert bl[key].severity.level == SeverityLevel.NONE

def test_merge_public_comment():
    blocklists = load_test_blocklist_data([datafile01, datafile02, datafile03])

    bl = merge_blocklists(blocklists, 'min')
    assert len(bl) == 13

    assert bl['public-comment.example.org'].public_comment == 'This is a public comment'

def test_merge_private_comment():
    blocklists = load_test_blocklist_data([datafile01, datafile02, datafile03])

    bl = merge_blocklists(blocklists, 'min')
    assert len(bl) == 13

    assert bl['private-comment.example.org'].private_comment == 'This is a private comment'

def test_merge_public_comments():
    blocklists = load_test_blocklist_data([datafile01, datafile02, datafile03])

    bl = merge_blocklists(blocklists, 'min')
    assert len(bl) == 13

    assert bl['diff-comment.example.org'].public_comment == 'Suspend public comment, Silence public comment, Noop public comment'

def test_merge_duplicate_comments():
    """The same comment on multiple sources shouldn't get added
    """
    blocklists = load_test_blocklist_data([datafile01, datafile02, datafile03])

    bl = merge_blocklists(blocklists, 'min')
    assert len(bl) == 13

    # Nope, this breaks. Need to rethink duplicate comment merge.
    # assert bl['2diff-comment.example.org'].public_comment == 'Suspend comment 1, Public duplicate'

def test_merge_comments_none():

    a = None
    b = None

    r = merge_comments(a, b)

    assert r == ''

def test_merge_comments_empty():

    a = ''
    b = ''

    r = merge_comments(a, b)

    assert r == ''

def test_merge_comments_left():

    a = 'comment to merge'
    b = ''

    r = merge_comments(a, b)

    assert r == 'comment to merge'

def test_merge_comments_right():

    a = ''
    b = 'comment to merge'

    r = merge_comments(a, b)

    assert r == 'comment to merge'

def test_merge_comments_same():

    a = 'comment to merge'
    b = 'comment to merge'

    r = merge_comments(a, b)

    assert r == 'comment to merge'

def test_merge_comments_diff():

    a = 'comment A'
    b = 'comment B'

    r = merge_comments(a, b)

    assert r == 'comment A, comment B'

def test_merge_comments_dups():

    a = "boring, nazis, lack of moderation, flagged, special"
    b = "spoon, nazis, flagged, lack of moderation, happy, fork"

    r = merge_comments(a, b)

    assert r == 'boring, nazis, lack of moderation, flagged, special, spoon, happy, fork'

def test_mergeplan_same_min_bools_false():
    """Test merging with mergeplan 'max' and False values doesn't change them
    """
    a = DomainBlock('example.org', 'noop', '', '', False, False, False)
    b = DomainBlock('example.org', 'noop', '', '', False, False, False)

    r = apply_mergeplan(a, b, 'max')

    assert r.reject_media == False
    assert r.reject_reports == False
    assert r.obfuscate == False

def test_mergeplan_same_min_bools_true():
    """Test merging with mergeplan 'max' and True values doesn't change them
    """
    a = DomainBlock('example.org', 'noop', '', '', True, False, True)
    b = DomainBlock('example.org', 'noop', '', '', True, False, True)

    r = apply_mergeplan(a, b, 'max')

    assert r.reject_media == True
    assert r.reject_reports == False
    assert r.obfuscate == True

def test_mergeplan_max_bools():
    a = DomainBlock('example.org', 'suspend', '', '', True, True, True)
    b = DomainBlock('example.org', 'noop', '', '', False, False, False)

    r = apply_mergeplan(a, b, 'max')

    assert r.reject_media == True
    assert r.reject_reports == True
    assert r.obfuscate == True