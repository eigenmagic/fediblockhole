from fediblockhole.const import BlockSeverity, SeverityLevel

def test_severity_eq():

    s1 = BlockSeverity('suspend')
    s2 = BlockSeverity('suspend')

    assert s1 == s2

    s3 = BlockSeverity('silence')
    s4 = BlockSeverity('silence')

    assert s3 == s4

    s5 = BlockSeverity('noop')
    s6 = BlockSeverity('noop')

    assert s5 == s6

def test_severity_ne():
    s1 = BlockSeverity('noop')
    s2 = BlockSeverity('silence')
    s3 = BlockSeverity('suspend')

    assert s1 != s2
    assert s2 != s3
    assert s1 != s3

def test_severity_lt():
    s1 = BlockSeverity('noop')
    s2 = BlockSeverity('silence')
    s3 = BlockSeverity('suspend')

    assert s1 < s2
    assert s2 < s3
    assert s1 < s3

def test_severity_gt():
    s1 = BlockSeverity('noop')
    s2 = BlockSeverity('silence')
    s3 = BlockSeverity('suspend')

    assert s2 > s1
    assert s3 > s2
    assert s3 > s1

def test_severity_le():
    s1 = BlockSeverity('noop')
    s2 = BlockSeverity('silence')
    s2a = BlockSeverity('silence')
    s3 = BlockSeverity('suspend')

    assert s1 <= s2
    assert s2a <= s2
    assert s2 <= s3
    assert s1 <= s3

def test_severity_ge():
    s1 = BlockSeverity('noop')
    s2 = BlockSeverity('silence')
    s2a = BlockSeverity('silence')
    s3 = BlockSeverity('suspend')

    assert s2 >= s1
    assert s2a >= s1
    assert s3 >= s2
    assert s3 >= s1

