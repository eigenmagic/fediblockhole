""" Utility functions for tests
"""
from fediblockhole import setup_argparse, augment_args

def shim_argparse(testargv: list=[], tomldata: str=None):
    """Helper function to parse test args
    """
    ap = setup_argparse()
    args = ap.parse_args(testargv)
    args = augment_args(args, tomldata)
    return args