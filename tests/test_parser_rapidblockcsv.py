"""Tests of the Rapidblock CSV parsing
"""

from fediblockhole.blocklists import RapidBlockParserCSV, parse_blocklist
from fediblockhole.const import DomainBlock, BlockSeverity, SeverityLevel

csvdata = """example.org\r\nsubdomain.example.org\r\nanotherdomain.org\r\ndomain4.org\r\n"""
parser = RapidBlockParserCSV()

def test_basic_rapidblock():

    bl = parser.parse_blocklist(csvdata)
    assert len(bl) == 4
    assert 'example.org' in bl
    assert 'subdomain.example.org' in bl
    assert 'anotherdomain.org' in bl
    assert 'domain4.org' in bl

def test_severity_is_suspend():
    bl = parser.parse_blocklist(csvdata)

    for block in bl.values():
        assert block.severity.level == SeverityLevel.SUSPEND