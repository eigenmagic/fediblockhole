"""Tests of the Rapidblock CSV parsing
"""

from fediblockhole.blocklist_parser import RapidBlockParserCSV, parse_blocklist
from fediblockhole.const import DomainBlock, BlockSeverity, SeverityLevel

csvdata = """example.org\r\nsubdomain.example.org\r\nanotherdomain.org\r\ndomain4.org\r\n"""
parser = RapidBlockParserCSV()

def test_basic_rapidblock():

    bl = parser.parse_blocklist(csvdata)
    assert len(bl) == 4
    assert bl[0].domain == 'example.org'
    assert bl[1].domain == 'subdomain.example.org'
    assert bl[2].domain == 'anotherdomain.org'
    assert bl[3].domain == 'domain4.org'

def test_severity_is_suspend():
    bl = parser.parse_blocklist(csvdata)

    for block in bl:
        assert block.severity.level == SeverityLevel.SUSPEND