"""Parse various blocklist data formats
"""
from typing import Iterable
from .const import DomainBlock, BlockSeverity

import csv
import json

import logging
log = logging.getLogger('fediblockhole')

class BlocklistParser(object):
    """
    Base class for parsing blocklists
    """
    preparse = False

    def __init__(self, import_fields: list=['domain', 'severity'], 
        max_severity: str='suspend'):
        """Create a Parser

        @param import_fields: an optional list of fields to limit the parser to.
            Ignore any fields in a block item that aren't in import_fields.
        """
        self.import_fields = import_fields
        self.max_severity = BlockSeverity(max_severity)

    def preparse(self, blockdata) -> Iterable:
        """Some raw datatypes need to be converted into an iterable
        """
        raise NotImplementedError

    def parse_blocklist(self, blockdata) -> dict[DomainBlock]:
        """Parse an iterable of blocklist items
        @param blocklist: An Iterable of blocklist items
        @returns: A dict of DomainBlocks, keyed by domain
        """
        if self.preparse:
            blockdata = self.preparse(blockdata)

        parsed_list = []
        for blockitem in blockdata:
            parsed_list.append(self.parse_item(blockitem))
        return parsed_list
    
    def parse_item(self, blockitem) -> DomainBlock:
        """Parse an individual block item

        @param blockitem: an individual block to be parsed
        @param import_fields: fields of a block we will import
        """
        raise NotImplementedError

class BlocklistParserJSON(BlocklistParser):
    """Parse a JSON formatted blocklist"""
    preparse = True

    def preparse(self, blockdata) -> Iterable:
        """Parse the blockdata as JSON
        """
        return json.loads(blockdata)

    def parse_item(self, blockitem: str) -> DomainBlock:
        # Remove fields we don't want to import
        origitem = blockitem.copy()
        for key in origitem:
            if key not in self.import_fields:
                del blockitem[key]

        # Convert dict to NamedTuple with the double-star operator
        # See: https://docs.python.org/3/tutorial/controlflow.html#tut-unpacking-arguments
        block = DomainBlock(**blockitem)
        if block.severity > self.max_severity:
            block.severity = self.max_severity
        return block

class BlocklistParserCSV(BlocklistParser):
    """ Parse CSV formatted blocklists

    The parser expects the CSV data to include a header with the field names.
    """
    preparse = True

    def preparse(self, blockdata) -> Iterable:
        """Use a csv.DictReader to create an iterable from the blockdata
        """
        return csv.DictReader(blockdata.split('\n'))

    def parse_item(self, blockitem: dict) -> DomainBlock:
        # Coerce booleans from string to Python bool
        # FIXME: Is this still necessary with the DomainBlock object?
        for boolkey in ['reject_media', 'reject_reports', 'obfuscate']:
            if boolkey in blockitem:
                blockitem[boolkey] = str2bool(blockitem[boolkey])

        # Remove fields we don't want to import
        origitem = blockitem.copy()
        for key in origitem:
            if key not in self.import_fields:
                log.debug(f"ignoring field '{key}'")
                del blockitem[key]

        # Convert dict to DomainBlock with the double-star operator
        # See: https://docs.python.org/3/tutorial/controlflow.html#tut-unpacking-arguments
        block = DomainBlock(**blockitem)
        if block.severity > self.max_severity:
            block.severity = self.max_severity
        return block

class RapidBlockParserCSV(BlocklistParserCSV):
    """ Parse RapidBlock CSV blocklists

    RapidBlock CSV blocklists are just a newline separated list of domains.
    """
    def preparse(self, blockdata) -> Iterable:
        """Prepend a 'domain' field header to the data
        """
        log.debug(f"blockdata: {blockdata[:100]}")
        blockdata = ''.join(["domain\r\n", blockdata])

        return csv.DictReader(blockdata.split('\r\n'))

class RapidBlockParserJSON(BlocklistParserJSON):
    """Parse RapidBlock JSON formatted blocklists
    """
    def preparse(self, blockdata) -> Iterable:
        rb_dict = json.loads(blockdata)
        # We want to iterate over all the dictionary items
        return rb_dict['blocks'].items()

    def parse_item(self, blockitem: tuple) -> DomainBlock:
        """Parse an individual item in a RapidBlock list
        """
        # Each item is a tuple of:
        # (domain, {dictionary of attributes})
        domain = blockitem[0]

        # RapidBlock has a binary block level which we map
        # to 'suspend' if True, and 'noop' if False.
        isblocked = blockitem[1]['isBlocked']
        if isblocked:
            severity = 'suspend'
        else:
            severity = 'noop'
        
        if 'public_comment' in self.import_fields:
            public_comment = blockitem[1]['reason']
        else:
            public_comment = ''
        
        # There's a 'tags' field as well, but we can't
        # do much with that in Mastodon yet

        block = DomainBlock(domain, severity, public_comment)
        if block.severity > self.max_severity:
            block.severity = self.max_severity

        return block

def str2bool(boolstring: str) -> bool:
    """Helper function to convert boolean strings to actual Python bools
    """
    boolstring = boolstring.lower()
    if boolstring in ['true', 't', '1', 'y', 'yes']:
        return True
    elif boolstring in ['', 'false', 'f', '0', 'n', 'no']:
        return False
    else:
        raise ValueError(f"Cannot parse value '{boolstring}' as boolean")

FORMAT_PARSERS = {
    'csv': BlocklistParserCSV,
    'json': BlocklistParserJSON,
    'rapidblock.csv': RapidBlockParserCSV,
    'rapidblock.json': RapidBlockParserJSON,
}

# helper function to select the appropriate Parser
def parse_blocklist(
    blockdata,
    format="csv",
    import_fields: list=['domain', 'severity'],
    max_severity: str='suspend'):
    """Parse a blocklist in the given format
    """
    parser = FORMAT_PARSERS[format](import_fields, max_severity)
    log.debug(f"parsing {format} blocklist with import_fields: {import_fields}...")
    return parser.parse_blocklist(blockdata)