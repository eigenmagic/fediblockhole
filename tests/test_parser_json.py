"""Tests of the CSV parsing
"""

from fediblockhole.blocklists import BlocklistParserJSON, parse_blocklist
from fediblockhole.const import SeverityLevel

datafile = 'data-mastodon.json'

def load_data():
    with open(datafile) as fp:
        return fp.read()

def test_json_parser():

    data = load_data()
    parser = BlocklistParserJSON()
    bl = parser.parse_blocklist(data, 'test_json')

    assert len(bl) == 10
    assert 'example.org' in bl
    assert 'example2.org' in bl
    assert 'example3.org' in bl
    assert 'example4.org' in bl

    assert bl['example.org'].severity.level == SeverityLevel.SUSPEND
    assert bl['example2.org'].severity.level == SeverityLevel.SILENCE
    assert bl['example3.org'].severity.level == SeverityLevel.SUSPEND
    assert bl['example4.org'].severity.level == SeverityLevel.NONE

def test_ignore_comments():

    data = load_data()
    parser = BlocklistParserJSON()
    bl = parser.parse_blocklist(data, 'test_json')

    assert len(bl) == 10
    assert 'example.org' in bl
    assert 'example2.org' in bl
    assert 'example3.org' in bl
    assert 'example4.org' in bl

    assert bl['example.org'].public_comment == ''
    assert bl['example.org'].private_comment == ''
    assert bl['example3.org'].public_comment == ''
    assert bl['example4.org'].private_comment == ''