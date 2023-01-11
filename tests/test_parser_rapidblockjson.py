"""Test parsing the RapidBlock JSON format
"""
from fediblockhole.blocklist_parser import parse_blocklist

from fediblockhole.const import SeverityLevel

rapidblockjson = "data-rapidblock.json"

def test_parse_rapidblock_json():
    with open(rapidblockjson) as fp:
        data = fp.read()
        bl = parse_blocklist(data, 'rapidblock.json')

        assert bl[0].domain == '101010.pl'
        assert bl[0].severity.level == SeverityLevel.SUSPEND
        assert bl[0].public_comment == ''

        assert bl[10].domain == 'berserker.town'
        assert bl[10].severity.level == SeverityLevel.SUSPEND
        assert bl[10].public_comment == ''
        assert bl[10].private_comment == ''

def test_parse_with_comments():
    with open(rapidblockjson) as fp:
        data = fp.read()
        bl = parse_blocklist(data, 'rapidblock.json', ['domain', 'severity', 'public_comment', 'private_comment'])

        assert bl[0].domain == '101010.pl'
        assert bl[0].severity.level == SeverityLevel.SUSPEND
        assert bl[0].public_comment == 'cryptomining javascript, white supremacy'

        assert bl[10].domain == 'berserker.town'
        assert bl[10].severity.level == SeverityLevel.SUSPEND
        assert bl[10].public_comment == 'freeze peach'