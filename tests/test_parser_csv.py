"""Tests of the CSV parsing
"""

from fediblockhole.blocklist_parser import BlocklistParserCSV, parse_blocklist
from fediblockhole.const import DomainBlock, BlockSeverity, SeverityLevel


def test_single_line():
    csvdata = "example.org"

    parser = BlocklistParserCSV()
    bl = parser.parse_blocklist(csvdata)
    assert len(bl) == 0

def test_header_only():
    csvdata = "domain,severity,public_comment"

    parser = BlocklistParserCSV()
    bl = parser.parse_blocklist(csvdata)
    assert len(bl) == 0

def test_2_blocks():
    csvdata = """domain,severity
example.org,silence
example2.org,suspend
"""

    parser = BlocklistParserCSV()
    bl = parser.parse_blocklist(csvdata)

    assert len(bl) == 2
    assert bl[0].domain == 'example.org'

def test_4_blocks():
    csvdata = """domain,severity,public_comment
example.org,silence,"test 1"
example2.org,suspend,"test 2"
example3.org,noop,"test 3"
example4.org,suspend,"test 4"
"""

    parser = BlocklistParserCSV()
    bl = parser.parse_blocklist(csvdata)

    assert len(bl) == 4
    assert bl[0].domain == 'example.org'
    assert bl[1].domain == 'example2.org'
    assert bl[2].domain == 'example3.org'
    assert bl[3].domain == 'example4.org'

    assert bl[0].severity.level == SeverityLevel.SILENCE
    assert bl[1].severity.level == SeverityLevel.SUSPEND
    assert bl[2].severity.level == SeverityLevel.NONE
    assert bl[3].severity.level == SeverityLevel.SUSPEND

def test_ignore_comments():
    csvdata = """domain,severity,public_comment,private_comment
example.org,silence,"test 1","ignore me"
example2.org,suspend,"test 2","ignote me also"
example3.org,noop,"test 3","and me"
example4.org,suspend,"test 4","also me"
"""

    parser = BlocklistParserCSV()
    bl = parser.parse_blocklist(csvdata)

    assert len(bl) == 4
    assert bl[0].domain == 'example.org'
    assert bl[1].domain == 'example2.org'
    assert bl[2].domain == 'example3.org'
    assert bl[3].domain == 'example4.org'

    assert bl[0].public_comment == ''
    assert bl[0].private_comment == ''

    assert bl[2].public_comment == ''
    assert bl[2].private_comment == ''