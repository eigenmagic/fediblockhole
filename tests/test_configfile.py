"""Test the config file is loading parameters correctly
"""

from textwrap import dedent

from util import shim_argparse

from fediblockhole import augment_args, setup_argparse


def test_parse_tomldata():
    tomldata = """
# Test TOML config for FediBlockHole

blocklist_instance_sources = []

blocklist_url_sources = []

save_intermediate = true

import_fields = ['public_comment']
"""
    ap = setup_argparse()
    args = ap.parse_args([])
    args = augment_args(args, tomldata)

    assert args.blocklist_instance_sources == []
    assert args.blocklist_url_sources == []
    assert args.save_intermediate is True
    assert args.import_fields == ["public_comment"]


def test_set_mergeplan_max():
    tomldata = """mergeplan = 'max'
    """
    args = shim_argparse([], tomldata)

    assert args.mergeplan == "max"


def test_set_mergeplan_min():
    tomldata = """mergeplan = 'min'
    """
    args = shim_argparse([], tomldata)

    assert args.mergeplan == "min"


def test_set_allowlists():
    tomldata = """# Comment on config
allowlist_url_sources = [ { url='file:///path/to/allowlist', format='csv'} ]
"""
    args = shim_argparse([], tomldata)

    assert args.mergeplan == "max"
    assert args.allowlist_url_sources == [
        {
            "url": "file:///path/to/allowlist",
            "format": "csv",
        }
    ]


def test_set_merge_thresold_default():
    tomldata = """
"""
    args = shim_argparse([], tomldata)

    assert args.mergeplan == "max"
    assert args.merge_threshold_type == "count"


def test_set_merge_thresold_count():
    tomldata = """# Add a merge threshold
merge_threshold_type = 'count'
merge_threshold = 2
"""
    args = shim_argparse([], tomldata)

    assert args.mergeplan == "max"
    assert args.merge_threshold_type == "count"
    assert args.merge_threshold == 2


def test_set_merge_thresold_pct():
    tomldata = """# Add a merge threshold
merge_threshold_type = 'pct'
merge_threshold = 35
"""
    args = shim_argparse([], tomldata)

    assert args.mergeplan == "max"
    assert args.merge_threshold_type == "pct"
    assert args.merge_threshold == 35


def test_destination_token_from_environment(monkeypatch):
    tomldata = dedent(
        """\
    blocklist_instance_destinations = [
      { domain='example.com', token='raw-token'},
      { domain='example2.com', token_env_var='TOKEN_ENV_VAR' },
      { domain='env-token.com' },
      { domain='www.env-token.com' },
    ]
    """
    )

    monkeypatch.setenv("TOKEN_ENV_VAR", "env-token")
    monkeypatch.setenv("ENV-TOKEN_COM_TOKEN", "env-token")
    monkeypatch.setenv("WWW_ENV-TOKEN_COM_TOKEN", "www-env-token")

    args = shim_argparse([], tomldata)

    assert args.blocklist_instance_destinations[0]["token"] == "raw-token"
    assert args.blocklist_instance_destinations[1]["token"] == "env-token"
    assert args.blocklist_instance_destinations[2]["token"] == "env-token"
    assert args.blocklist_instance_destinations[3]["token"] == "www-env-token"


def test_instance_sources_token_from_environment(monkeypatch):
    tomldata = dedent(
        """\
    blocklist_instance_sources = [
      { domain='example.com', token='raw-token'},
      { domain='example2.com', token_env_var='TOKEN_ENV_VAR' },
      { domain='env-token.com' },
      { domain='www.env-token.com' },
    ]
    """
    )

    monkeypatch.setenv("TOKEN_ENV_VAR", "env-token")
    monkeypatch.setenv("ENV-TOKEN_COM_TOKEN", "env-token")
    monkeypatch.setenv("WWW_ENV-TOKEN_COM_TOKEN", "www-env-token")

    args = shim_argparse([], tomldata)

    assert args.blocklist_instance_sources[0]["token"] == "raw-token"
    assert args.blocklist_instance_sources[1]["token"] == "env-token"
    assert args.blocklist_instance_sources[2]["token"] == "env-token"
    assert args.blocklist_instance_sources[3]["token"] == "www-env-token"
