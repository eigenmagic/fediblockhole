""" Constant objects used by FediBlockHole
"""
from __future__ import annotations
import enum
from typing import NamedTuple, Optional, TypedDict
from dataclasses import dataclass

import logging
log = logging.getLogger('fediblockhole')

class SeverityLevel(enum.IntEnum):
    """How severe should a block be? Higher is more severe.
    """
    NONE = enum.auto()
    SILENCE = enum.auto()
    SUSPEND = enum.auto()

class BlockSeverity(object):
    """A representation of a block severity

    We add some helpful functions rather than using a bare IntEnum
    """

    def __init__(self, severity:str=None):
        self._level = self.str2level(severity)

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, value):
        if isinstance(value, SeverityLevel):
            self._level = value
        elif type(value) == type(''):
            self._level = self.str2level(value)
        else:
            raise ValueError(f"Invalid level value '{value}'")

    def str2level(self, severity:str=None):
        """Convert a string severity level to an internal enum"""

        if severity in [None, '', 'noop']:
            return SeverityLevel.NONE

        elif severity in ['silence']:
            return SeverityLevel.SILENCE
        
        elif severity in ['suspend']:
            return SeverityLevel.SUSPEND

        else:
            raise ValueError(f"Invalid severity value '{severity}'")

    def __repr__(self):
        return f"'{str(self)}'"

    def __str__(self):
        """A string version of the severity level
        """
        levelmap = {
            SeverityLevel.NONE: 'noop',
            SeverityLevel.SILENCE: 'silence',
            SeverityLevel.SUSPEND: 'suspend',
        }
        return levelmap[self.level]

    def __lt__(self, other):
        if self._level < other._level:
            return True

    def __gt__(self, other):
        if self._level > other._level:
            return True

    def __eq__(self, other):
        if other is not None and self._level == other._level:
            return True

    def __le__(self, other):
        if self._level <= other._level:
            return True

    def __ge__(self, other):
        if self._level >= other._level:
            return True
        
class BlockAudit(object):

    fields = [
        'domain',
        'count',
        'percent',
    ]

    all_fields = [
        'domain',
        'count',
        'percent',
        'id'
    ]

    def __init__(self, domain:str,
            count: int=0,
            percent: int=0,
            id: int=None):
        """Initialize the BlockAudit
        """        
        self.domain = domain
        self.count = count
        self.percent = percent
        self.id = id

    def _asdict(self):
        """Return a dict version of this object
        """
        dictval = {
            'domain': self.domain,
            'count': self.count,
            'percent': self.percent,
        }
        if self.id:
            dictval['id'] = self.id

        return dictval

    def __repr__(self):

        return f"<BlockAudit {self._asdict()}>"

    def copy(self):
        """Make a copy of this object and return it
        """
        retval = BlockAudit(**self._asdict())
        return retval

    def update(self, dict):
        """Update my kwargs
        """
        for key in dict:
            setattr(self, key, dict[key])

    def __iter__(self):
        """Be iterable"""
        keys = self.fields

        if getattr(self, 'id', False):
            keys.append('id')

        for k in keys:
            yield k

    def __getitem__(self, k, default=None):
        "Behave like a dict for getting values"
        if k not in self.all_fields:
            raise KeyError(f"Invalid key '{k}'")

        return getattr(self, k, default)

    def get(self, k, default=None):
        return self.__getitem__(k, default)

# class _DomainBlock(NamedTuple):
#     domain: str # FIXME: Use an actual Domain object from somewhere?
#     severity: BlockSeverity = BlockSeverity.SUSPEND
#     public_comment: str = ''
#     private_comment: str = ''
#     reject_media: bool = False
#     reject_reports: bool = False
#     obfuscate: bool = False

class DomainBlock(object):

    fields = [
        'domain',
        'severity',
        'public_comment',
        'private_comment',
        'reject_media',
        'reject_reports',
        'obfuscate',
    ]

    all_fields = [
        'domain',
        'severity',
        'public_comment',
        'private_comment',
        'reject_media',
        'reject_reports',
        'obfuscate',
        'id'
    ]

    def __init__(self, domain:str,
            severity: BlockSeverity=BlockSeverity('suspend'),
            public_comment: str="",
            private_comment: str="",
            reject_media: bool=False,
            reject_reports: bool=False,
            obfuscate: bool=False,
            id: int=None):
        """Initialize the DomainBlock
        """        
        self.domain = domain
        self.severity = severity
        self.public_comment = public_comment
        self.private_comment = private_comment
        self.reject_media = reject_media
        self.reject_reports = reject_reports
        self.obfuscate = obfuscate
        self.id = id

    @property
    def severity(self):
        return self._severity

    @severity.setter
    def severity(self, sev):
        if isinstance(sev, BlockSeverity):
            self._severity = sev
        else:
            self._severity = BlockSeverity(sev)

    def _asdict(self):
        """Return a dict version of this object
        """
        dictval = {
            'domain': self.domain,
            'severity': str(self.severity),
            'public_comment': self.public_comment,
            'private_comment': self.private_comment,
            'reject_media': self.reject_media,
            'reject_reports': self.reject_reports,
            'obfuscate': self.obfuscate,
        }
        if self.id:
            dictval['id'] = self.id

        return dictval

    def compare_fields(self, other, fields=None)->list:
        """Compare two DomainBlocks on specific fields.
        If all the fields are equal, the DomainBlocks are equal.

        @returns: a list of the fields that are different
        """
        if not isinstance(other, DomainBlock):
            raise ValueError(f"Cannot compare DomainBlock to {type(other)}:{other}")

        if fields is None:
            fields = self.fields

        diffs = []
        # Check if all the fields are equal
        for field in self.fields:
            a = getattr(self, field)
            b = getattr(other, field)
            # log.debug(f"Comparing field {field}: '{a}' <> '{b}'")
            if getattr(self, field) != getattr(other, field):
                diffs.append(field)
        return diffs

    def __eq__(self, other):
        diffs = self.compare_fields(other)
        if len(diffs) == 0:
            return True

    def __repr__(self):

        return f"<DomainBlock {self._asdict()}>"

    def copy(self):
        """Make a copy of this object and return it
        """
        retval = DomainBlock(**self._asdict())
        return retval

    def update(self, dict):
        """Update my kwargs
        """
        for key in dict:
            setattr(self, key, dict[key])

    def __iter__(self):
        """Be iterable"""
        keys = self.fields

        if getattr(self, 'id', False):
            keys.append('id')

        for k in keys:
            yield k

    def __getitem__(self, k, default=None):
        "Behave like a dict for getting values"
        if k not in self.all_fields:
            raise KeyError(f"Invalid key '{k}'")

        return getattr(self, k, default)

    def get(self, k, default=None):
        return self.__getitem__(k, default)