"""Tests of the CSV parsing
"""

from fediblockhole.blocklist_parser import BlocklistParserJSON, parse_blocklist
from fediblockhole.const import DomainBlock, BlockSeverity, SeverityLevel

datafile = 'data-mastodon.json'

def load_data():
    with open(datafile) as fp:
        return fp.read()

def test_json_parser():

    data = load_data()
    parser = BlocklistParserJSON()
    bl = parser.parse_blocklist(data)

    assert len(bl) == 10
    assert bl[0].domain == 'example.org'
    assert bl[1].domain == 'example2.org'
    assert bl[2].domain == 'example3.org'
    assert bl[3].domain == 'example4.org'

    assert bl[0].severity.level == SeverityLevel.SUSPEND
    assert bl[1].severity.level == SeverityLevel.SILENCE
    assert bl[2].severity.level == SeverityLevel.SUSPEND
    assert bl[3].severity.level == SeverityLevel.NONE

def test_ignore_comments():

    data = load_data()
    parser = BlocklistParserJSON()
    bl = parser.parse_blocklist(data)

    assert len(bl) == 10
    assert bl[0].domain == 'example.org'
    assert bl[1].domain == 'example2.org'
    assert bl[2].domain == 'example3.org'
    assert bl[3].domain == 'example4.org'

    assert bl[0].public_comment == ''
    assert bl[0].private_comment == ''

    assert bl[2].public_comment == ''
    assert bl[2].private_comment == ''