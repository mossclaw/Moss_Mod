"""
Tests that JSON files are correct according to schemas.

 Please do not put the *unittest* in the tests/unittest GitHub action.
 It is only for local use.
HOWEVER,
 Please keep the raw python script, so it can be run by the GitHub action.
"""

from itertools import chain

import json
import jsonschema
from pathlib import Path
from referencing import Registry
from referencing.jsonschema import DRAFT7
import unittest

ROOT_DIR = Path(__file__).parent.parent
SCHEMA_DIR = ROOT_DIR / "schemas"
RESOURCES_DIR = ROOT_DIR / "resources"

COMMON_SCHEMA = json.loads((SCHEMA_DIR / "common.schema.json").read_text())
THOUGHT_SCHEMA = json.loads((SCHEMA_DIR / "thought.schema.json").read_text())
PATROL_SCHEMA = json.loads((SCHEMA_DIR / "patrol.schema.json").read_text())
SHORTEVENT_SCHEMA = json.loads((SCHEMA_DIR / "shortevent.schema.json").read_text())

registry = Registry().with_resources(
    [
        ("common.schema.json", DRAFT7.create_resource(COMMON_SCHEMA)),
        ("thought.schema.json", DRAFT7.create_resource(THOUGHT_SCHEMA)),
        ("patrol.schema.json", DRAFT7.create_resource(PATROL_SCHEMA)),
        ("shortevent.schema.json", DRAFT7.create_resource(SHORTEVENT_SCHEMA)),
    ]
)

import logging
logging.disable(logging.WARNING)


def all_thought_files():
    """
    Iterator for Paths for all thought files
    """
    yield from RESOURCES_DIR.glob("lang/*/thoughts/**/*.json")


def all_patrol_files():
    """
    Iterator for Paths for all patrol files
    """
    EXCLUSIONS = [
        "explicit_patrol_art.json",
        "prey_text_replacements.json",
    ]

    yield from (
        file
        for file in RESOURCES_DIR.glob("lang/*/patrols/**/*.json")
        if file.name not in EXCLUSIONS
    )


def all_shortevent_files():
    """
    Iterator for Paths for all shortevent files
    """

    INCLUSION_GLOBS = ["death/*.json", "injury/*.json", "misc/*.json", "new_cat/*.json"]

    yield from chain.from_iterable(
        RESOURCES_DIR.glob("lang/*/events/" + glob) for glob in INCLUSION_GLOBS
    )


def do_test_schema(files, schema):
    for file in files:
        data = json.loads(file.read_text())
        try:
            jsonschema.validate(
                data, schema, cls=jsonschema.Draft7Validator, registry=registry
            )
        except:
            print(file.relative_to(ROOT_DIR))
            raise
    


def test_thoughts_schema():
    """Test that all thought JSONs are correct according to the JSON schema"""
    do_test_schema(all_thought_files(), THOUGHT_SCHEMA)


def test_patrols_schema():
    """Test that all patrol JSONs are correct according to the JSON schema"""
    do_test_schema(all_patrol_files(), PATROL_SCHEMA)


def test_shortevent_schema():
    """Tests that all shortevent JSONs are correct according to the JSON schema"""
    do_test_schema(all_shortevent_files(), SHORTEVENT_SCHEMA)


class TestJsonSchemas(unittest.TestCase):
    """Unittest for local use to test that JSON files
    are correct according to schemas."""

    def test_thoughts_schema(self):
        """Unittest for local use to test that all
        thought JSONs are correct according to the JSON schema."""
        test_thoughts_schema()

    def test_patrols_schema(self):
        """Unittest for local use to test that all
        patrol JSONs are correct according to the JSON schema."""
        test_patrols_schema()

    def test_shortevent_schema(self):
        """Unittest for local use to test that all
        shortevent JSONs are correct according to the JSON schema."""
        test_shortevent_schema()


if __name__ == "__main__":
    test_thoughts_schema()
    test_patrols_schema()
    test_shortevent_schema()
