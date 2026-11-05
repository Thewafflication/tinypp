"""Validate copied semantic signatures; never treat them as executable IR.

The experimental DMC worker retains its own pointers and allocation state.
Only bounded, versioned values cross this boundary. Unknown forms fail closed.
"""

import argparse
import json
import re
from pathlib import Path


def unique_object(pairs):
    """Reject repeated JSON keys rather than accepting the last occurrence."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def exact_fields(record, fields):
    """Reject incomplete and unknown protocol records."""
    if not isinstance(record, dict) or set(record) != set(fields):
        raise ValueError("Signature field mismatch")


def check_path(value):
    """Validate compiler identifier bytes without guessing their encoding."""
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        raise ValueError("Invalid symbol path")
    for component in value:
        if (not isinstance(component, str) or not 2 <= len(component) <= 1024
                or len(component) % 2 or
                not re.fullmatch(r"[0-9a-f]+", component) or
                b"\0" in bytes.fromhex(component)):
            raise ValueError("Invalid identifier byte encoding")


def check_boolean(value):
    """Keep JSON booleans distinct from numeric zero and one."""
    if type(value) is not bool:
        raise ValueError("Expected a JSON boolean")


def check_type(value, depth=0):
    """Validate supported C++98 type identities and explicit layout values."""
    if depth >= 32 or not isinstance(value, dict):
        raise ValueError("Invalid or excessively nested signature type")
    kind = value.get("kind")
    if not isinstance(kind, str):
        raise ValueError("Unsupported signature type")
    fields = {"kind", "const", "volatile"}
    if kind in ("pointer", "lvalue-reference"):
        exact_fields(value, fields | {"to"})
        check_type(value["to"], depth + 1)
    elif kind == "record":
        exact_fields(value, fields | {"path_hex", "bytes", "alignment"})
        check_path(value["path_hex"])
        size, alignment = value["bytes"], value["alignment"]
        if (type(size) is not int or not 1 <= size <= 0xffffffff or
                type(alignment) is not int or not 1 <= alignment <= 65536 or
                alignment & (alignment - 1) or size % alignment):
            raise ValueError("Invalid or incomplete record layout")
    else:
        widths = {
            "void": {0}, "bool": {1}, "char": {1}, "signed-char": {1},
            "unsigned-char": {1}, "short": {2}, "unsigned-short": {2},
            "int": {4}, "unsigned-int": {4}, "long": {4},
            "unsigned-long": {4}, "float": {4}, "double": {8},
            "long-double": {8, 10, 16}, "wchar-t": {2},
        }
        if kind not in widths:
            raise ValueError("Unsupported signature type")
        exact_fields(value, fields | {"bytes"})
        if (type(value["bytes"]) is not int or
                value["bytes"] not in widths[kind]):
            raise ValueError("Unexpected target scalar width")
    check_boolean(value["const"])
    check_boolean(value["volatile"])
    if kind in ("pointer", "lvalue-reference"):
        if value["to"]["kind"] == "lvalue-reference":
            raise ValueError("Pointer/reference to reference is invalid")
    if kind == "lvalue-reference" and (
            value["to"]["kind"] == "void" or value["const"] or
            value["volatile"]):
        raise ValueError("Invalid reference type")


def load_signatures(data, expected_target):
    """Read a complete worker stream into owned Python values or reject it."""
    if expected_target not in {"windows-x86", "windows-x64"}:
        raise ValueError("Unsupported signature target")
    if not isinstance(data, bytes) or not 1 <= len(data) <= 4 * 1024 * 1024:
        raise ValueError("Invalid signature stream size")
    if not data.endswith(b"\n"):
        raise ValueError("Truncated signature stream")
    lines = data.splitlines()
    if not 1 <= len(lines) <= 4096:
        raise ValueError("Invalid signature record count")
    result, seen = [], set()
    for line in lines:
        if not line or len(line) > 65536:
            raise ValueError("Invalid signature line size")
        try:
            record = json.loads(line, object_pairs_hook=unique_object)
        except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
            raise ValueError("Invalid signature JSON") from error
        exact_fields(record, {
            "schema", "target", "abi", "function_kind", "linkage",
            "path_hex", "const_member", "volatile_member", "variadic",
            "result", "parameters",
        })
        if (record["schema"] != "tinypp.semantic-signature.v1" or
                record["abi"] != "dmc-experimental-v1"):
            raise ValueError("Unsupported signature protocol or ABI")
        if record["target"] != expected_target:
            raise ValueError("Signature target mismatch")
        if record["linkage"] not in ("c", "c++"):
            raise ValueError("Unsupported language linkage")
        category = record["function_kind"]
        if category not in ("function", "constructor", "destructor"):
            raise ValueError("Unsupported function kind")
        check_path(record["path_hex"])
        for field in ("const_member", "volatile_member", "variadic"):
            check_boolean(record[field])
        if category == "function":
            check_type(record["result"])
        elif record["result"] is not None:
            raise ValueError("Constructor/destructor has a result type")
        parameters = record["parameters"]
        if not isinstance(parameters, list) or len(parameters) > 256:
            raise ValueError("Invalid signature parameter count")
        for parameter in parameters:
            check_type(parameter)
            if parameter["kind"] == "void":
                raise ValueError("Void is not a value parameter")
        key = json.dumps(record, sort_keys=True)
        if key in seen:
            raise ValueError("Repeated signature record")
        seen.add(key)
        result.append(record)
    return result


def read_signatures(path, expected_target):
    """Bound file reads before decoding an untrusted worker response."""
    with path.open("rb") as stream:
        data = stream.read(4 * 1024 * 1024 + 1)
    return load_signatures(data, expected_target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stream", type=Path)
    parser.add_argument("--target", required=True)
    options = parser.parse_args()
    signatures = read_signatures(options.stream, options.target)
    print(f"Validated {len(signatures)} experimental signatures; no IR claim")
