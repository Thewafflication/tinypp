"""Exercise failure controls at the experimental DMC process boundary."""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from semantic_signatures import load_signatures  # noqa: E402


class SignatureBoundary(unittest.TestCase):
    """Reject incompatible or malformed data before semantic consumption."""

    def setUp(self):
        """Create a scalar signature independently of the producer."""
        self.scalar = {"kind": "int", "const": False,
                       "volatile": False, "bytes": 4}
        self.record = {
            "schema": "tinypp.semantic-signature.v1", "target": "windows-x64",
            "abi": "dmc-experimental-v1", "function_kind": "function",
            "linkage": "c++", "path_hex": ["4e", "66"],
            "const_member": False, "volatile_member": False,
            "variadic": False, "result": copy.deepcopy(self.scalar),
            "parameters": [],
        }

    def encoded(self):
        """Encode an independently constructed protocol message."""
        return (json.dumps(self.record) + "\n").encode("utf-8")

    def reject(self, text):
        """Require a specific rejection, rather than any parser exception."""
        with self.assertRaisesRegex(ValueError, text):
            load_signatures(self.encoded(), "windows-x64")

    def test_owned_scalar_and_cv_reference(self):
        """Valid nested qualifiers are retained without producer pointers."""
        self.record["parameters"] = [{
            "kind": "lvalue-reference", "const": False, "volatile": False,
            "to": dict(self.scalar, const=True),
        }]
        result = load_signatures(self.encoded(), "windows-x64")
        self.record["parameters"].clear()
        self.assertTrue(result[0]["parameters"][0]["to"]["const"])

    def test_schema(self):
        self.record["schema"] = "tinypp.semantic-signature.v2"
        self.reject("Unsupported signature protocol")

    def test_target(self):
        self.record["target"] = "windows-x86"
        self.reject("Signature target mismatch")

    def test_abi(self):
        self.record["abi"] = "msvc"
        self.reject("Unsupported signature protocol or ABI")

    def test_unknown_field(self):
        self.record["pointer"] = 1234
        self.reject("Signature field mismatch")

    def test_duplicate_key(self):
        data = self.encoded().replace(b'"schema":', b'"schema":0,"schema":')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            load_signatures(data, "windows-x64")

    def test_truncation(self):
        with self.assertRaisesRegex(ValueError, "Truncated signature stream"):
            load_signatures(self.encoded().rstrip(), "windows-x64")

    def test_duplicate_record(self):
        with self.assertRaisesRegex(ValueError, "Repeated signature record"):
            load_signatures(self.encoded() * 2, "windows-x64")

    def test_boolean_number(self):
        self.record["variadic"] = 0
        self.reject("Expected a JSON boolean")

    def test_identifier_encoding(self):
        self.record["path_hex"] = ["abc"]
        self.reject("Invalid identifier byte encoding")

    def test_identifier_nul(self):
        self.record["path_hex"] = ["6600"]
        self.reject("Invalid identifier byte encoding")

    def test_unknown_type(self):
        self.record["result"] = {"kind": "unsupported", "raw_type": 999}
        self.reject("Unsupported signature type")

    def test_nonstring_kind(self):
        self.record["result"] = {"kind": []}
        self.reject("Unsupported signature type")

    def test_wrong_scalar_width(self):
        self.record["result"]["bytes"] = 8
        self.reject("Unexpected target scalar width")

    def test_incomplete_record(self):
        self.record["result"] = {"kind": "record", "const": False,
            "volatile": False, "path_hex": ["50"], "bytes": 0, "alignment": 0}
        self.reject("Invalid or incomplete record layout")

    def test_constructor_result(self):
        self.record["function_kind"] = "constructor"
        self.reject("Constructor/destructor has a result type")

    def test_void_parameter(self):
        self.record["parameters"] = [dict(self.scalar, kind="void", bytes=0)]
        self.reject("Void is not a value parameter")

    def test_nested_type_limit(self):
        value = self.scalar
        for unused in range(32):
            value = {"kind": "pointer", "const": False,
                     "volatile": False, "to": value}
        self.record["result"] = value
        self.reject("excessively nested signature type")


if __name__ == "__main__":
    unittest.main()
