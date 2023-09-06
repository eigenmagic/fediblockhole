"""Parse various blocklist data formats
"""
from __future__ import annotations
import csv
import json
from typing import Iterable
from dataclasses import dataclass, field

from .const import DomainBlock, BlockSeverity, BlockAudit

import logging
log = logging.getLogger('fediblockhole')

@dataclass
class Blocklist:
    """ A Blocklist object

    A Blocklist is a list of DomainBlocks from an origin
    """
    origin: str = None
    blocks: dict[str, DomainBlock] = field(default_factory=dict)

    def __len__(self):
        return len(self.blocks)

    def __class_getitem__(cls, item):
        return dict[str, DomainBlock]

    def __getitem__(self, item):
        return self.blocks[item]

    def __iter__(self):
        return self.blocks.__iter__()

    def items(self):
        return self.blocks.items()

    def values(self):
        return self.blocks.values()

@dataclass   
class BlockAuditList:
    """ A BlockAuditlist object

    A BlockAuditlist is a list of BlockAudits from an origin
    """
    origin: str = None
    blocks: dict[str, BlockAudit] = field(default_factory=dict)

    def __len__(self):
        return len(self.blocks)

    def __class_getitem__(cls, item):
        return dict[str, BlockAudit]

    def __getitem__(self, item):
        return self.blocks[item]

    def __iter__(self):
        return self.blocks.__iter__()

    def items(self):
        return self.blocks.items()

    def values(self):
        return self.blocks.values()

class BlocklistParser(object):
    """
    Base class for parsing blocklists
    """
    do_preparse = False

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

    def parse_blocklist(self, blockdata, origin:str=None) -> Blocklist:
        """Parse an iterable of blocklist items
        @param blocklist: An Iterable of blocklist items
        @returns: A dict of DomainBlocks, keyed by domain
        """
        if self.do_preparse:
            blockdata = self.preparse(blockdata)

        parsed_list = Blocklist(origin)
        for blockitem in blockdata:
            block = self.parse_item(blockitem)
            parsed_list.blocks[block.domain] = block
        return parsed_list
    
    def parse_item(self, blockitem) -> DomainBlock:
        """Parse an individual block item

        @param blockitem: an individual block to be parsed
        @param import_fields: fields of a block we will import
        """
        raise NotImplementedError

class BlocklistParserJSON(BlocklistParser):
    """Parse a JSON formatted blocklist"""
    do_preparse = True

    def preparse(self, blockdata) -> Iterable:
        """Parse the blockdata as JSON if needed"""
        if type(blockdata) == type(''):
            return json.loads(blockdata)
        return blockdata

    def parse_item(self, blockitem: dict) -> DomainBlock:
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

class BlocklistParserMastodonAPIPublic(BlocklistParserJSON):
    """The public blocklist API is slightly different to the admin one"""
    
    def parse_item(self, blockitem: dict) -> DomainBlock:
        # Remove fields we don't want to import
        origitem = blockitem.copy()
        for key in origitem:
            # The Mastodon public API uses the 'public' field
            # to mean 'public_comment' because what even is consistency?
            if key == 'comment':
                key = 'public_comment'
                blockitem['public_comment'] = blockitem['comment']
                del blockitem['comment']
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
    do_preparse = True

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

class BlocklistParserMastodonCSV(BlocklistParserCSV):
    """ Parse Mastodon CSV formatted blocklists

    The Mastodon v4.1.x domain block CSV export prefixes its
    field names with a '#' character because… reasons?
    """
    do_preparse = True

    def parse_item(self, blockitem: dict) -> DomainBlock:
        """Build a new blockitem dict with new un-#ed keys
        """
        newdict = {}
        for key in blockitem:
            newkey = key.lstrip('#')
            newdict[newkey] = blockitem[key]

        return super().parse_item(newdict)

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
    'mastodon_csv': BlocklistParserMastodonCSV,
    'json': BlocklistParserJSON,
    'mastodon_api_public': BlocklistParserMastodonAPIPublic,
    'rapidblock.csv': RapidBlockParserCSV,
    'rapidblock.json': RapidBlockParserJSON,
}

# helper function to select the appropriate Parser
def parse_blocklist(
    blockdata,
    origin,
    format="csv",
    import_fields: list=['domain', 'severity'],
    max_severity: str='suspend'):
    """Parse a blocklist in the given format
    """
    log.debug(f"parsing {format} blocklist with import_fields: {import_fields}...")

    parser = FORMAT_PARSERS[format](import_fields, max_severity)
    return parser.parse_blocklist(blockdata, origin)