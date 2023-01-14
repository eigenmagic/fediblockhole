"""Test the DomainBlock structure
"""
import pytest

from fediblockhole.const import DomainBlock, BlockSeverity, SeverityLevel

def test_blocksev_blankstring():
    a = BlockSeverity('')
    assert a.level == SeverityLevel.NONE

def test_blocksev_string_noop():
    a = BlockSeverity('noop')
    assert a.level == SeverityLevel.NONE

def test_blocksev_none():
    a = BlockSeverity(None)
    assert a.level == SeverityLevel.NONE

def test_empty_domainblock_fails():
    with pytest.raises(TypeError):
        a = DomainBlock()

def test_default_suspend():
    a = DomainBlock('example.org')
    assert a.domain == 'example.org'
    assert a.severity.level == SeverityLevel.SUSPEND

def test_severity_suspend():
    a = DomainBlock('example.org', 'suspend')
    assert a.domain == 'example.org'
    assert a.severity.level == SeverityLevel.SUSPEND

def test_severity_silence():
    a = DomainBlock('example.org', 'silence')
    assert a.domain == 'example.org'
    assert a.severity.level == SeverityLevel.SILENCE

def test_severity_noop_string():
    a = DomainBlock('example.org', 'noop')
    assert a.domain == 'example.org'
    assert a.severity.level == SeverityLevel.NONE

def test_severity_none():
    a = DomainBlock('example.org', None)
    assert a.domain == 'example.org'
    assert a.severity.level == SeverityLevel.NONE

def test_compare_equal_blocks():

    a = DomainBlock('example1.org', 'suspend')
    b = DomainBlock('example1.org', 'suspend')

    assert a == b

def test_compare_diff_domains():

    a = DomainBlock('example1.org', 'suspend')
    b = DomainBlock('example2.org', 'suspend')

    assert a != b

def test_compare_diff_sevs():

    a = DomainBlock('example1.org', 'suspend')
    b = DomainBlock('example1.org', 'silence')

    assert a != b

def test_compare_diff_sevs_2():

    a = DomainBlock('example1.org', 'suspend')
    b = DomainBlock('example1.org', 'noop')

    assert a != b
