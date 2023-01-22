""" Test merging of comments
"""
import pytest

from fediblockhole import merge_comments

def test_merge_blank_comments():
    
    oldcomment = ''
    newcomment = ''

    merged_comment = merge_comments(oldcomment, newcomment)

    assert merged_comment == ''

def test_merge_None_comments():
    
    oldcomment = None
    newcomment = None

    merged_comment = merge_comments(oldcomment, newcomment)

    assert merged_comment == ''

def test_merge_oldstr_newNone():
    
    oldcomment = 'fred, bibble'
    newcomment = None

    merged_comment = merge_comments(oldcomment, newcomment)

    assert merged_comment == 'fred, bibble'

def test_merge_oldempty_newcomment():
    
    oldcomment = ''
    newcomment = 'fred, bibble'

    merged_comment = merge_comments(oldcomment, newcomment)

    assert merged_comment == 'fred, bibble'

def test_merge_oldNone_newcomment():
    
    oldcomment = None
    newcomment = 'fred, bibble'

    merged_comment = merge_comments(oldcomment, newcomment)

    assert merged_comment == 'fred, bibble'

def test_merge_two_different():
    
    oldcomment = 'happy, medium, spinning'
    newcomment = 'fred, bibble'

    merged_comment = merge_comments(oldcomment, newcomment)

    assert merged_comment == 'happy, medium, spinning, fred, bibble'

def test_merge_overlaps():
    
    oldcomment = 'happy, medium, spinning'
    newcomment = 'fred, medium, bibble, spinning'

    merged_comment = merge_comments(oldcomment, newcomment)

    assert merged_comment == 'happy, medium, spinning, fred, bibble'