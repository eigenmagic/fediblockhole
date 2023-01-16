"""Test parsing the RapidBlock JSON format
"""
from fediblockhole.blocklists import parse_blocklist

from fediblockhole.const import SeverityLevel

rapidblockjson = "data-rapidblock.json"

def test_parse_rapidblock_json():
    with open(rapidblockjson) as fp:
        data = fp.read()
        bl = parse_blocklist(data, 'pytest', 'rapidblock.json')

        assert '101010.pl' in bl
        assert bl['101010.pl'].severity.level == SeverityLevel.SUSPEND
        assert bl['101010.pl'].public_comment == ''

        assert 'berserker.town' in bl
        assert bl['berserker.town'].severity.level == SeverityLevel.SUSPEND
        assert bl['berserker.town'].public_comment == ''
        assert bl['berserker.town'].private_comment == ''

def test_parse_with_comments():
    with open(rapidblockjson) as fp:
        data = fp.read()
        bl = parse_blocklist(data, 'pytest', 'rapidblock.json', ['domain', 'severity', 'public_comment', 'private_comment'])

        assert '101010.pl' in bl
        assert bl['101010.pl'].severity.level == SeverityLevel.SUSPEND
        assert bl['101010.pl'].public_comment == 'cryptomining javascript, white supremacy'

        assert 'berserker.town' in bl
        assert bl['berserker.town'].severity.level == SeverityLevel.SUSPEND
        assert bl['berserker.town'].public_comment == 'freeze peach'