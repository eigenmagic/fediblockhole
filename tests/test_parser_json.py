"""Tests of the CSV parsing
"""

from fediblockhole.blocklists import BlocklistParserJSON
from fediblockhole.const import SeverityLevel


def test_json_parser(data_mastodon_json):

    parser = BlocklistParserJSON()
    bl = parser.parse_blocklist(data_mastodon_json, "test_json")

    assert len(bl) == 10
    assert "example.org" in bl
    assert "example2.org" in bl
    assert "example3.org" in bl
    assert "example4.org" in bl

    assert bl["example.org"].severity.level == SeverityLevel.SUSPEND
    assert bl["example2.org"].severity.level == SeverityLevel.SILENCE
    assert bl["example3.org"].severity.level == SeverityLevel.SUSPEND
    assert bl["example4.org"].severity.level == SeverityLevel.NONE


def test_ignore_comments(data_mastodon_json):

    parser = BlocklistParserJSON()
    bl = parser.parse_blocklist(data_mastodon_json, "test_json")

    assert len(bl) == 10
    assert "example.org" in bl
    assert "example2.org" in bl
    assert "example3.org" in bl
    assert "example4.org" in bl

    assert bl["example.org"].public_comment == ""
    assert bl["example.org"].private_comment == ""
    assert bl["example3.org"].public_comment == ""
    assert bl["example4.org"].private_comment == ""
