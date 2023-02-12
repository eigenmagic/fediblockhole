"""Tests of the CSV parsing
"""

from fediblockhole.blocklists import BlocklistParserMastodonCSV
from fediblockhole.const import SeverityLevel


def test_single_line():
    csvdata = "example.org"
    origin = "csvfile"

    parser = BlocklistParserMastodonCSV()
    bl = parser.parse_blocklist(csvdata, origin)
    assert len(bl) == 0

def test_header_only():
    csvdata = "#domain,#severity,#public_comment"
    origin = "csvfile"

    parser = BlocklistParserMastodonCSV()
    bl = parser.parse_blocklist(csvdata, origin)
    assert len(bl) == 0

def test_2_blocks():
    csvdata = """domain,severity
example.org,silence
example2.org,suspend
"""
    origin = "csvfile"

    parser = BlocklistParserMastodonCSV()
    bl = parser.parse_blocklist(csvdata, origin)

    assert len(bl) == 2
    assert 'example.org' in bl

def test_4_blocks():
    csvdata = """domain,severity,public_comment
example.org,silence,"test 1"
example2.org,suspend,"test 2"
example3.org,noop,"test 3"
example4.org,suspend,"test 4"
"""
    origin = "csvfile"

    parser = BlocklistParserMastodonCSV()
    bl = parser.parse_blocklist(csvdata, origin)

    assert len(bl) == 4
    assert 'example.org' in bl
    assert 'example2.org' in bl
    assert 'example3.org' in bl
    assert 'example4.org' in bl

    assert bl['example.org'].severity.level == SeverityLevel.SILENCE
    assert bl['example2.org'].severity.level == SeverityLevel.SUSPEND
    assert bl['example3.org'].severity.level == SeverityLevel.NONE
    assert bl['example4.org'].severity.level == SeverityLevel.SUSPEND

def test_ignore_comments():
    csvdata = """domain,severity,public_comment,private_comment
example.org,silence,"test 1","ignore me"
example2.org,suspend,"test 2","ignote me also"
example3.org,noop,"test 3","and me"
example4.org,suspend,"test 4","also me"
"""
    origin = "csvfile"

    parser = BlocklistParserMastodonCSV()
    bl = parser.parse_blocklist(csvdata, origin)

    assert len(bl) == 4
    assert 'example.org' in bl
    assert 'example2.org' in bl
    assert 'example3.org' in bl
    assert 'example4.org' in bl

    assert bl['example.org'].public_comment == ''
    assert bl['example.org'].private_comment == ''
    assert bl['example3.org'].public_comment == ''
    assert bl['example4.org'].private_comment == ''