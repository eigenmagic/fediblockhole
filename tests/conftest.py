import os
import sys

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))


def load_data(datafile):
    """Load test data from a fixture datafile"""
    with open(os.path.join(os.path.dirname(__file__), "fixtures", datafile)) as fp:
        return fp.read()


@pytest.fixture
def data_mastodon_json():
    return load_data("data-mastodon.json")


@pytest.fixture
def data_rapidblock_json():
    return load_data("data-rapidblock.json")


@pytest.fixture
def data_suspends_01():
    return load_data("data-suspends-01.csv")


@pytest.fixture
def data_silences_01():
    return load_data("data-silences-01.csv")


@pytest.fixture
def data_noop_01():
    return load_data("data-noop-01.csv")
