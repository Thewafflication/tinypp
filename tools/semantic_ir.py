"""Validate experimental typed CFG bodies and lower them to owned target C.

Source code and DMC object files never enter this emitter. Its vocabulary is
explicit and bounded; unsupported language/runtime operations are rejected.
"""

import hashlib
import json
import re
from pathlib import Path

from semantic_signatures import (check_type, exact_fields, load_signatures,
                                 unique_object)

SCALARS = {"bool": "_Bool", "int": "int", "unsigned-int": "unsigned int",
           "long": "long", "unsigned-long": "unsigned long", "void": "void"}
BINARY = {
    "add": "+", "subtract": "-", "multiply": "*", "divide": "/",
    "remainder": "%", "shift-left": "<<", "shift-right": ">>",
    "bit-and": "&", "bit-or": "|", "bit-xor": "^",
    "logical-and": "&&", "logical-or": "||", "less-equal": "<=",
    "greater": ">", "less": "<", "greater-equal": ">=", "equal": "==",
    "not-equal": "!=", "comma": ",",
}
ASSIGN = {"assign": "=", "add-assign": "+=", "subtract-assign": "-=",
          "multiply-assign": "*=", "divide-assign": "/=",
          "remainder-assign": "%="}
UNARY = {"logical-not": "!", "booleanize": "!!", "bit-not": "~",
         "negate": "-", "positive": "+", "discard": "(void)"}


def profile_type(value, depth=0):
    """Restrict the handoff to implemented carriers after schema validation."""
    if depth == 32:
        raise ValueError("IR type depth exceeded")
    kind = value["kind"]
    if kind in ("pointer", "lvalue-reference"):
        profile_type(value["to"], depth + 1)
    elif kind == "record":
        if value["bytes"] > 1024 * 1024 or value["alignment"] > 16:
            raise ValueError("Unsupported IR record storage limits")
    elif kind not in SCALARS:
        raise ValueError("Unsupported IR type profile")


def carrier(value, storage=False):
    """Choose fixed target spellings; no input text becomes C source."""
    kind = value["kind"]
    if kind in ("pointer", "lvalue-reference"):
        text = carrier(value["to"]) + " *"
    elif kind == "record":
        text = "struct " + record_name(value)
    else:
        text = SCALARS[kind]
    if value["volatile"]:
        text += " volatile"
    if value["const"] and not storage:
        text += " const"
    return text


def record_name(value):
    """Generate an opaque record carrier name from its complete layout."""
    return "tinypp_record_" + hashlib.sha256(json.dumps(value_type(value),
        sort_keys=True).encode()).hexdigest()


def emitted_result(function):
    """Normalize DMC's destructor placeholder to a side-effect-only result."""
    if function["function_kind"] == "destructor":
        return {"kind": "void", "bytes": 0, "const": False, "volatile": False}
    return function["lowered_result"]


def bound_parameters(function):
    """Use one receiver-first convention for owned definitions and calls."""
    return ([function["receiver"]] if function["receiver"] is not None else
            []) + function["parameters"]


def type_layout(value, target):
    """Return byte size/alignment for the bounded Windows object profile."""
    if value["kind"] in ("pointer", "lvalue-reference"):
        width = 8 if target == "windows-x64" else 4
        return width, width
    if value["kind"] == "record":
        return value["bytes"], value["alignment"]
    return value["bytes"], value["bytes"]


def value_type(value):
    """Remove only top-level cv for value and prototype comparisons."""
    return dict(value, const=False, volatile=False)


def compatible(source, destination):
    """Check the implemented value conversions, including ref carriers."""
    left, right = source["kind"], destination["kind"]
    if left in SCALARS and right in SCALARS:
        return (left == "void") == (right == "void")
    pointers = {"pointer", "lvalue-reference"}
    if left in pointers and right == "bool":
        return True
    return (left in pointers and right in pointers and
            value_type(source["to"]) == value_type(destination["to"]) and
            (not source["to"]["const"] or destination["to"]["const"]) and
            (not source["to"]["volatile"] or destination["to"]["volatile"]))


def check_function_contract(value, target):
    """Validate logical signatures and explicit worker call conventions."""
    if not isinstance(value, dict) or type(value.get("internal")) is not bool:
        raise ValueError("Invalid IR function identity")
    if "receiver" not in value or "lowered_result" not in value:
        raise ValueError("Missing IR receiver or lowered result")
    signature = {key: item for key, item in value.items()
                 if key not in ("internal", "receiver", "lowered_result")}
    signature.update(schema="tinypp.semantic-signature.v1", target=target,
                     abi="dmc-experimental-v1")
    load_signatures((json.dumps(signature) + "\n").encode(), target)
    receiver = value["receiver"]
    if receiver is not None:
        check_type(receiver)
        if (value["linkage"] != "c++" or
                receiver["kind"] != "pointer" or receiver["const"] or
                receiver["volatile"] or receiver["to"]["kind"] != "record" or
                receiver["to"]["path_hex"] != value["path_hex"][:-1] or
                receiver["to"]["const"] != value["const_member"] or
                receiver["to"]["volatile"] != value["volatile_member"]):
            raise ValueError("Invalid IR receiver contract")
    elif value["const_member"] or value["volatile_member"]:
        raise ValueError("Member qualification requires an IR receiver")
    check_type(value["lowered_result"])
    category = value["function_kind"]
    if category == "constructor":
        if (receiver is None or value["const_member"] or
                value["volatile_member"] or
                value["lowered_result"] != receiver):
            raise ValueError("Invalid IR constructor result contract")
    elif category == "destructor":
        if (receiver is None or value["parameters"] or value["variadic"] or
                value["const_member"] or value["volatile_member"] or
                value["lowered_result"] != {"kind": "int", "bytes": 4,
                    "const": False, "volatile": False}):
            raise ValueError("Invalid IR destructor result contract")
    elif value_type(value["lowered_result"]) != value_type(value["result"]):
        raise ValueError("IR logical and lowered result mismatch")


def check_function(value, target):
    """Keep structural object support separate from emission capabilities."""
    check_function_contract(value, target)
    if value["variadic"]:
        raise ValueError("Unsupported IR function convention")
    profile_type(value["lowered_result"])
    if value["receiver"] is not None:
        profile_type(value["receiver"])
    if value["lowered_result"]["kind"] == "record":
        raise ValueError("Unsupported IR record value result")
    for parameter in value["parameters"]:
        profile_type(parameter)
        if parameter["kind"] == "record":
            raise ValueError("Unsupported IR record value parameter")


def function_key(value, unit):
    """Keep C linkage unique and C++ overloads distinct across units."""
    path = value["path_hex"] if value["linkage"] == "c++" else \
        value["path_hex"][-1:]
    identity = {"path": path, "linkage": value["linkage"]}
    if value["linkage"] == "c++":
        identity["parameters"] = [value_type(t) for t in value["parameters"]]
        if value["receiver"] is not None:
            identity["member_cv"] = [value["const_member"],
                                     value["volatile_member"]]
        identity["category"] = value["function_kind"]
    if value["internal"]:
        identity["unit"] = unit
    return json.dumps(identity, sort_keys=True)


def function_name(key):
    """Generate a collision-resistant C identifier from opaque identity data."""
    return "tinypp_ir_" + hashlib.sha256(key.encode()).hexdigest()


def check_body(record, target):
    """Validate CFG shape, bindings and supported expressions before output."""
    exact_fields(record, {"schema", "target", "abi", "emission", "function",
                          "variables", "blocks"})
    if (record["schema"] != "tinypp.function-ir.v2" or
            record["target"] != target or
            record["abi"] != "dmc-experimental-v1" or
            record["emission"] != "semantic-only"):
        raise ValueError("IR protocol, target or ABI mismatch")
    check_function(record["function"], target)
    variables, parameters = {}, []
    if (not isinstance(record["variables"], list) or
            len(record["variables"]) > 1024):
        raise ValueError("IR variable limit exceeded")
    for item in record["variables"]:
        exact_fields(item, {"id", "storage", "type"})
        identifier = item["id"]
        if (type(identifier) is not int or not 0 <= identifier < 1024 or
                identifier in variables or
                item["storage"] not in ("parameter", "local")):
            raise ValueError("Invalid IR variable identity or storage")
        check_type(item["type"])
        profile_type(item["type"])
        if item["type"]["kind"] == "void":
            raise ValueError("Void IR variable")
        variables[identifier] = item
        if item["storage"] == "parameter":
            parameters.append(value_type(item["type"]))
    if parameters != [value_type(t) for t in
                      bound_parameters(record["function"])]:
        raise ValueError("IR parameter storage does not match signature")
    blocks = record["blocks"]
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 512:
        raise ValueError("Invalid IR block count")
    calls, count = [], [0]

    def expression(node, depth=0, discarded=False, storage=False):
        """Check all nodes, including unreachable code, without evaluation."""
        count[0] += 1
        if depth >= 64 or count[0] > 4096 or not isinstance(node, dict):
            raise ValueError("IR expression limit or shape violation")
        operation = node.get("op")
        if not isinstance(operation, str):
            raise ValueError("Unsupported IR operation")
        fields = {"op", "type"}
        check_type(node.get("type"))
        profile_type(node["type"])
        if node["type"]["kind"] == "record" and not storage:
            raise ValueError("Unsupported IR record value expression")
        if operation == "literal":
            exact_fields(node, fields | {"value"})
            text = node["value"]
            kind = node["type"]["kind"]
            if kind == "pointer" and text == "0":
                return
            if (kind not in SCALARS or kind == "void" or
                    not isinstance(text, str) or len(text) > 11 or
                    not re.fullmatch(r"0|-?[1-9][0-9]*", text)):
                raise ValueError("Invalid IR integer constant")
            lower, upper = (0, 0xffffffff) if "unsigned" in kind else (
                -0x80000000, 0x7fffffff)
            if kind == "bool":
                lower, upper = 0, 1
            if not lower <= int(text) <= upper:
                raise ValueError("IR integer constant out of range")
        elif operation in ("variable", "variable-address"):
            exact_fields(node, fields | {"id", "offset"})
            if (type(node["id"]) is not int or node["id"] not in variables or
                    type(node["offset"]) is not int or node["offset"] != 0):
                raise ValueError("Unknown IR variable or unsupported offset")
            declared = variables[node["id"]]["type"]
            expected = ({"kind": "pointer", "const": False,
                         "volatile": False, "to": declared}
                        if operation == "variable-address" else declared)
            if not (compatible(expected, node["type"]) or
                    value_type(expected) == value_type(node["type"])):
                raise ValueError("IR variable type mismatch")
        elif operation == "field-address":
            exact_fields(node, fields | {"offset", "args"})
            if not isinstance(node["args"], list) or len(node["args"]) != 1:
                raise ValueError("IR field address arity mismatch")
        elif operation == "call":
            exact_fields(node, fields | {"function", "receiver", "args"})
            check_function(node["function"], target)
            receiver = node["function"]["receiver"]
            if (receiver is None) != (node["receiver"] is None):
                raise ValueError("IR call receiver mismatch")
            if receiver is not None:
                expression(node["receiver"], depth + 1)
                if not compatible(node["receiver"]["type"], receiver):
                    raise ValueError("IR call receiver type mismatch")
            if not compatible(node["function"]["lowered_result"], node["type"]):
                raise ValueError("IR call result mismatch")
            if node["function"]["function_kind"] == "destructor" and \
                    not discarded:
                raise ValueError("Destructor result cannot be consumed")
            calls.append(node["function"])
            if (not isinstance(node.get("args"), list) or
                    len(node["args"]) != len(node["function"]["parameters"])):
                raise ValueError("IR call argument count mismatch")
        else:
            arity = 3 if operation == "conditional" else 2 if operation in (
                set(BINARY) | set(ASSIGN) | {"post-add", "post-subtract"}) \
                else 1 if operation in set(UNARY) | {"indirect", "address"} \
                else 0
            if not arity:
                raise ValueError("Unsupported IR operation")
            exact_fields(node, fields | {"args"})
            if not isinstance(node["args"], list) or len(node["args"]) != arity:
                raise ValueError("IR operation arity mismatch")
        if "args" in node:
            if not isinstance(node["args"], list) or len(node["args"]) > 256:
                raise ValueError("Invalid IR argument list")
            for index, child in enumerate(node["args"]):
                child_discard = (operation == "discard" or
                    operation == "comma" and (index == 0 or discarded) or
                    operation == "conditional" and index > 0 and discarded)
                expression(child, depth + 1, child_discard,
                           operation == "address")
        if operation == "field-address":
            base, result = node["args"][0]["type"], node["type"]
            offset = node["offset"]
            if (base["kind"] != "pointer" or
                    base["to"]["kind"] != "record" or
                    result["kind"] != "pointer" or
                    result["to"]["kind"] == "void" or
                    type(offset) is not int):
                raise ValueError("Invalid IR field address types")
            size, alignment = type_layout(result["to"], target)
            if (not 0 <= offset <= base["to"]["bytes"] - size or
                    offset % alignment or
                    base["to"]["alignment"] < alignment):
                raise ValueError("IR field address exceeds layout or alignment")
            if any(base["to"][cv] and not result["to"][cv]
                   for cv in ("const", "volatile")):
                raise ValueError("IR field address drops qualification")
        if operation == "call" and any(not compatible(arg["type"], parameter)
                for arg, parameter in zip(node["args"],
                                          node["function"]["parameters"])):
            raise ValueError("IR call argument type mismatch")
        if operation in set(ASSIGN) | {"post-add", "post-subtract", "address"}:
            if not is_lvalue(node["args"][0]):
                raise ValueError("IR operation requires an lvalue")
        integer_ops = (set(BINARY) - {"comma", "logical-and", "logical-or"}
                       | set(ASSIGN) - {"assign"}
                       | {"post-add", "post-subtract", "negate", "positive",
                          "bit-not"})
        if operation in integer_ops and any(
                item["type"]["kind"] not in SCALARS or
                item["type"]["kind"] == "void" for item in node["args"]):
            raise ValueError("Unsupported noninteger IR operation")
        if operation == "indirect":
            pointer = node["args"][0]["type"]
            if (pointer["kind"] not in ("pointer", "lvalue-reference") or
                    pointer["to"]["kind"] == "void" or
                    pointer["to"] != node["type"]):
                raise ValueError("Invalid typed IR indirection")

    for index, block in enumerate(blocks):
        exact_fields(block, {"id", "exit", "successors", "expression"})
        if type(block["id"]) is not int or block["id"] != index:
            raise ValueError("IR block identifiers must be ordered and unique")
        exits = {"goto": 1, "branch": 2, "return": 0, "return-value": 0}
        successors = block["successors"]
        if (not isinstance(block["exit"], str) or block["exit"] not in exits or
                not isinstance(successors, list) or
                len(successors) != exits[block["exit"]] or any(
                    type(item) is not int or not 0 <= item < len(blocks)
                    for item in successors)):
            raise ValueError("Invalid IR block exit or successor")
        if block["expression"] is not None:
            expression(block["expression"], discarded=block["exit"] in
                       ("goto", "return"))
        elif block["exit"] in ("branch", "return-value"):
            raise ValueError("IR exit requires an expression")
    pending, reachable = [0], set()
    while pending:
        index = pending.pop()
        if index not in reachable:
            reachable.add(index)
            pending.extend(blocks[index]["successors"])
    result = emitted_result(record["function"])
    void = result["kind"] == "void"
    for index in reachable:
        exit_kind = blocks[index]["exit"]
        node = blocks[index]["expression"]
        implicit_main = record["function"]["path_hex"] == [b"main".hex()] and \
            result["kind"] == "int"
        if exit_kind == "return" and not void and not implicit_main:
            raise ValueError("IR reachable return does not match result type")
        if exit_kind == "return-value" and not compatible(node["type"], result):
            raise ValueError("IR return expression type mismatch")
        if exit_kind == "branch" and node["type"]["kind"] == "void":
            raise ValueError("IR branch condition is void")
    return variables, reachable, calls


def is_lvalue(node):
    """Recognize identities retained by the supported scalar profile."""
    if node["op"] in ("variable", "indirect") or node["op"] in ASSIGN:
        return True
    if node["op"] == "comma":
        return is_lvalue(node["args"][1])
    if node["op"] == "conditional":
        return all(is_lvalue(item) for item in node["args"][1:])
    return False


def read_bodies(path, target):
    """Bound worker input before parsing and validate every complete record."""
    with Path(path).open("rb") as stream:
        data = stream.read(8 * 1024 * 1024 + 1)
    if not 1 <= len(data) <= 8 * 1024 * 1024 or not data.endswith(b"\n"):
        raise ValueError("IR stream size or truncation failure")
    lines = data.splitlines()
    if not 1 <= len(lines) <= 256:
        raise ValueError("IR function limit exceeded")
    result = []
    for line in lines:
        if not line or len(line) > 1024 * 1024:
            raise ValueError("IR line size exceeded")
        try:
            record = json.loads(line, object_pairs_hook=unique_object)
        except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
            raise ValueError("Invalid IR JSON") from error
        check_body(record, target)
        result.append(record)
    return result


def lower_units(units, target="windows-x64"):
    """Produce target C solely from validated IR; reject unresolved bodies."""
    if target != "windows-x64" or not 1 <= len(units) <= 32:
        raise ValueError("Unsupported IR emission target or unit count")
    definitions, information, declarations, layouts = {}, {}, {}, {}
    for unit, records in enumerate(units):
        for record in records:
            information[id(record)] = check_body(record, target)
            pending = [record]
            while pending:
                item = pending.pop()
                if isinstance(item, list):
                    pending.extend(item)
                elif isinstance(item, dict):
                    if item.get("kind") == "record":
                        identity = tuple(item["path_hex"])
                        layout = value_type(item)
                        if identity in layouts and layouts[identity] != layout:
                            raise ValueError("Conflicting IR record layout")
                        layouts[identity] = layout
                        if len(layouts) > 256:
                            raise ValueError("IR record layout limit exceeded")
                    pending.extend(item.values())
            function = record["function"]
            key = function_key(function, unit)
            if key in definitions:
                raise ValueError("Duplicate IR function definition")
            definitions[key] = (unit, record)
            declarations[key] = function
    for unit, records in enumerate(units):
        for record in records:
            for function in information[id(record)][2]:
                key = function_key(function, unit)
                if key not in definitions:
                    raise ValueError("Unresolved IR function body")
                actual = declarations[key]
                if (actual["function_kind"] != function["function_kind"] or
                        actual["receiver"] != function["receiver"] or
                        value_type(actual["lowered_result"]) !=
                        value_type(function["lowered_result"]) or
                        [value_type(t) for t in actual["parameters"]] !=
                        [value_type(t) for t in function["parameters"]]):
                    raise ValueError("Cross-unit IR function type mismatch")
    def entries_named(name):
        """Prefer a standard zero-argument main over the probe entry."""
        return [key for key, (_, record) in definitions.items()
                if record["function"]["path_hex"] == [name.encode().hex()] and
                not record["function"]["parameters"] and
                record["function"]["result"]["kind"] == "int"]
    entries = entries_named("main") or entries_named("answer")
    if len(entries) != 1:
        raise ValueError("IR program requires int main() or int answer()")

    def prototype(key, function, parameters=None):
        """Build declarations from fixed carriers and validated identities."""
        args = parameters if parameters is not None else [carrier(t, True)
            for t in bound_parameters(function)]
        return (("static " if function["internal"] else "") +
                carrier(emitted_result(function)) + " " + function_name(key) +
                "(" + (",".join(args) or "void") + ")")

    outputs = []
    for unit, records in enumerate(units):
        text = ["/* Owned typed CFG lowering; no source text passthrough. */"]
        for layout in layouts.values():
            name = record_name(layout)
            text.append("struct " + name + "{unsigned char bytes[" +
                str(layout["bytes"]) + "];} __attribute__((aligned(" +
                str(layout["alignment"]) + ")));")
            text.append("typedef char " + name + "_check[(sizeof(struct " +
                name + ")==" + str(layout["bytes"]) + " && __alignof__(struct "
                + name + ")==" + str(layout["alignment"]) + ")?1:-1];")
        for key, function in declarations.items():
            if not function["internal"] or definitions[key][0] == unit:
                text.append(prototype(key, function) + ";")
        for record in records:
            variables, reachable, unused_calls = information[id(record)]
            function = record["function"]
            parameters = [carrier(v["type"], True) + " v" + str(v["id"])
                for v in variables.values() if v["storage"] == "parameter"]
            text.append(prototype(function_key(function, unit), function,
                                  parameters) + "{")
            for identifier, variable in variables.items():
                if variable["storage"] == "local":
                    text.append(carrier(variable["type"], True) +
                                " v" + str(identifier) + ";")

            def address(node):
                """Retain C++ assignment/comma lvalue identity in target C."""
                operation, args = node["op"], node.get("args", [])
                if operation == "variable":
                    return "&v" + str(node["id"])
                if operation == "indirect":
                    return render(args[0])
                if operation == "comma":
                    return "(" + discard(args[0]) + "," + address(args[1]) + ")"
                if operation == "conditional":
                    return "(" + render(args[0]) + "?" + address(args[1]) + \
                        ":" + address(args[2]) + ")"
                if operation in ASSIGN:
                    return "({" + carrier(args[0]["type"], True) + \
                        " *p=" + address(args[0]) + ";*p" + \
                        ASSIGN[operation] + \
                        render(args[1]) + ";p;})"
                raise ValueError("Unsupported IR lvalue")

            def discard(node):
                """Do not fetch discarded nonvolatile scalar lvalues."""
                if is_lvalue(node) and not node["type"]["volatile"]:
                    return "((void)(" + address(node) + "))"
                return render(node)

            def render(node):
                """Render only checked operation tags and generated names."""
                operation, args = node["op"], node.get("args", [])
                result = carrier(node["type"])
                if operation == "literal":
                    value = node["value"] + ("U" if "unsigned" in
                                             node["type"]["kind"] else "")
                elif operation == "variable":
                    value = "v" + str(node["id"])
                elif operation == "variable-address":
                    value = "&v" + str(node["id"])
                elif operation == "call":
                    key = function_key(node["function"], unit)
                    arguments = ([node["receiver"]] if
                                 node["receiver"] is not None else []) + args
                    value = function_name(key) + "(" + ",".join(
                        render(arg) for arg in arguments) + ")"
                    if node["function"]["function_kind"] == "destructor":
                        value = "(" + value + ",0)"
                elif operation == "field-address":
                    value = "(unsigned char *)(" + render(args[0]) + ")+" + \
                        str(node["offset"])
                elif operation == "address":
                    value = address(args[0])
                elif operation == "indirect":
                    value = "*(" + render(args[0]) + ")"
                elif operation == "conditional":
                    value = render(args[0]) + "?" + render(args[1]) + ":" + \
                        render(args[2])
                elif operation == "comma":
                    value = discard(args[0]) + "," + render(args[1])
                elif operation in ASSIGN:
                    value = "*(" + address(node) + ")"
                elif operation in ("post-add", "post-subtract"):
                    op = "+=" if operation == "post-add" else "-="
                    value = "({" + carrier(args[0]["type"], True) + \
                        " *p=" + address(args[0]) + ";" + result + \
                        " old=*p;*p" + op + render(args[1]) + ";old;})"
                elif operation in UNARY:
                    value = UNARY[operation] + "(" + render(args[0]) + ")"
                else:
                    value = render(args[0]) + BINARY[operation] + \
                        render(args[1])
                return "((" + result + ")(" + value + "))"

            for index in sorted(reachable):
                block = record["blocks"][index]
                text.append("b" + str(index) + ":;")
                node, exit_kind = block["expression"], block["exit"]
                successors = block["successors"]
                if exit_kind == "branch":
                    text.append("if(" + render(node) + ")goto b" +
                        str(successors[0]) + ";else goto b" +
                        str(successors[1]) + ";")
                elif exit_kind == "return-value":
                    if emitted_result(function)["kind"] == "void":
                        text.append("(void)(" + render(node) + ");return;")
                    else:
                        text.append("return " + render(node) + ";")
                else:
                    if node is not None:
                        text.append("(void)(" + discard(node) + ");")
                    if exit_kind == "return":
                        implicit_main = function["path_hex"] == [b"main".hex()]
                        text.append("return 0;" if implicit_main else "return;")
                    else:
                        text.append("goto b" + str(successors[0]) + ";")
            text.append("}")
        if unit == definitions[entries[0]][0]:
            text.append("int main(void){return " + function_name(entries[0]) +
                        "();}")
        outputs.append("\n".join(text) + "\n")
    if sum(len(text) for text in outputs) > 16 * 1024 * 1024:
        raise ValueError("IR lowering size exceeded")
    return outputs
