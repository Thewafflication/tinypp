"""Failure controls for the typed CFG boundary, independent of DMC output."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from semantic_ir import (check_body, check_function, check_function_contract,
                         function_key, lower_units)  # noqa: E402


class BodyBoundary(unittest.TestCase):
    """Reject malformed or unsupported IR before code emission."""

    def setUp(self):
        """Create an independent int answer() body with no worker pointers."""
        self.integer = {"kind": "int", "const": False,
                        "volatile": False, "bytes": 4}
        self.record = {
            "schema": "tinypp.function-ir.v2", "target": "windows-x64",
            "abi": "dmc-experimental-v1", "emission": "semantic-only",
            "function": {"path_hex": [b"answer".hex()], "linkage": "c",
                "function_kind": "function", "const_member": False,
                "volatile_member": False, "variadic": False,
                "internal": False, "result": copy.deepcopy(self.integer),
                "parameters": [], "receiver": None,
                "lowered_result": copy.deepcopy(self.integer)},
            "variables": [], "blocks": [{"id": 0, "exit": "return-value",
                "successors": [], "expression": {"op": "literal",
                "type": copy.deepcopy(self.integer), "value": "42"}}],
        }

    def reject(self, message):
        """Require the intended failure rather than any exception."""
        with self.assertRaisesRegex(ValueError, message):
            check_body(self.record, "windows-x64")

    def test_dead_implicit_return(self):
        """Only reachable returns must supply a nonvoid result."""
        self.record["blocks"].append({"id": 1, "exit": "return",
                                      "successors": [], "expression": None})
        output = lower_units([[self.record]])[0]
        self.assertNotIn("b1:", output)
        self.assertIn("return ", output)

    def test_reachable_missing_result(self):
        """Reject a reachable fallthrough instead of manufacturing a value."""
        self.record["blocks"][0].update(exit="return", expression=None)
        self.reject("reachable return does not match")

    def test_implicit_main_result(self):
        """Falling off standard int main returns zero, not an invented value."""
        self.record["function"]["path_hex"] = [b"main".hex()]
        self.record["blocks"][0].update(exit="return", expression=None)
        output = lower_units([[self.record]])[0]
        self.assertIn("return 0;", output)

    def test_dangling_successor(self):
        """Never lower a jump to an unknown block."""
        self.record["blocks"][0].update(exit="goto", successors=[9])
        self.reject("Invalid IR block exit or successor")

    def test_block_identity(self):
        """Reject noncanonical or repeated block numbers."""
        self.record["blocks"][0]["id"] = True
        self.reject("ordered and unique")

    def test_unknown_operation(self):
        """An opcode is not a raw target-language escape hatch."""
        self.record["blocks"][0]["expression"]["op"] = "raw-c"
        self.reject("Unsupported IR operation")

    def test_unknown_variable(self):
        """All operand bindings must be local to this function."""
        self.record["blocks"][0]["expression"] = {
            "op": "variable", "type": self.integer, "id": 7, "offset": 0}
        self.reject("Unknown IR variable")

    def test_invalid_assignment(self):
        """A literal cannot acquire writable storage through the protocol."""
        value = copy.deepcopy(self.record["blocks"][0]["expression"])
        self.record["blocks"][0]["expression"] = {
            "op": "assign", "type": self.integer, "args": [value, value]}
        self.reject("requires an lvalue")

    def test_parameter_storage(self):
        """Definition storage and explicit parameter types must agree."""
        self.record["function"]["parameters"] = [self.integer]
        self.reject("parameter storage does not match")

    def test_unsupported_type(self):
        """Signature support does not silently enable floating body lowering."""
        self.record["function"]["result"] = dict(
            self.integer, kind="float", bytes=4)
        self.record["function"]["lowered_result"] = copy.deepcopy(
            self.record["function"]["result"])
        self.reject("Unsupported IR type profile")

    def test_wrong_target(self):
        """A valid target label cannot enable an unqualified emitter."""
        with self.assertRaisesRegex(ValueError, "Unsupported IR emission"):
            lower_units([[self.record]], "windows-x86")

    def test_native_observation_stream(self):
        """Require successful semantic-only mode rather than leftover IR."""
        self.record["emission"] = "legacy-observation"
        self.reject("IR protocol, target or ABI mismatch")

    def test_return_type(self):
        """Reject a pointer result paired with an integer-returning body."""
        self.record["function"]["result"] = {
            "kind": "pointer", "const": False, "volatile": False,
            "to": self.integer}
        self.record["function"]["lowered_result"] = copy.deepcopy(
            self.record["function"]["result"])
        self.reject("IR return expression type mismatch")

    def test_void_branch(self):
        """A side-effect-only expression cannot become a branch condition."""
        node = self.record["blocks"][0]["expression"]
        self.record["blocks"][0].update(exit="branch", successors=[0, 0],
            expression={"op": "discard", "type": dict(self.integer,
                kind="void", bytes=0), "args": [node]})
        self.reject("IR branch condition is void")

    def test_identity_domains(self):
        """Internal functions are unit-local; external functions are shared."""
        value = self.record["function"]
        self.assertEqual(function_key(value, 0), function_key(value, 1))
        value["internal"] = True
        self.assertNotEqual(function_key(value, 0), function_key(value, 1))

    def test_opaque_names(self):
        """Opaque compiler identifiers cannot inject target C text."""
        other = copy.deepcopy(self.record)
        payload = 'x); int injected(void){return 0;} /*'
        other["function"]["path_hex"] = [payload.encode().hex()]
        output = lower_units([[self.record, other]])[0]
        self.assertNotIn(payload, output)
        self.assertNotIn("injected", output)

    def test_unknown_field(self):
        """Reject protocol extensions until they have defined semantics."""
        self.record["raw_c"] = "return 42;"
        self.reject("field mismatch")

    def test_duplicate_definition(self):
        """Do not pick one of conflicting cross-unit bodies."""
        with self.assertRaisesRegex(ValueError, "Duplicate IR function"):
            lower_units([[self.record], [copy.deepcopy(self.record)]])

    def test_constant_range(self):
        """Check target integer bounds before spelling a C literal."""
        self.record["blocks"][0]["expression"]["value"] = "2147483648"
        self.reject("constant out of range")

    def object_function(self, category="constructor"):
        """Describe a logical class member independently of worker output."""
        owner = {"kind": "record", "path_hex": ["47"], "bytes": 8,
                 "alignment": 8, "const": False, "volatile": False}
        receiver = {"kind": "pointer", "const": False, "volatile": False,
                    "to": owner}
        function = copy.deepcopy(self.record["function"])
        function.update(path_hex=["47", "3f30"], linkage="c++",
            function_kind=category, result=None, receiver=receiver,
            lowered_result=copy.deepcopy(receiver))
        if category == "destructor":
            function.update(path_hex=["47", "3f31"],
                            lowered_result=copy.deepcopy(self.integer))
        return function

    def test_constructor_contract(self):
        """Constructors expose a lowered pointer without a logical result."""
        function = self.object_function()
        check_function_contract(function, "windows-x64")
        self.assertIsNone(function["result"])
        check_function(function, "windows-x64")

    def test_destructor_contract(self):
        """DMC's legacy int placeholder does not create a logical result."""
        check_function_contract(self.object_function("destructor"),
                                "windows-x64")

    def test_constructor_receiver_required(self):
        """An implicit receiver cannot disappear during protocol conversion."""
        function = self.object_function()
        function["receiver"] = None
        with self.assertRaisesRegex(ValueError, "constructor result contract"):
            check_function_contract(function, "windows-x64")

    def test_constructor_lowered_result(self):
        """A constructor cannot return an unrelated scalar through the ABI."""
        function = self.object_function()
        function["lowered_result"] = self.integer
        with self.assertRaisesRegex(ValueError, "constructor result contract"):
            check_function_contract(function, "windows-x64")

    def test_destructor_lowered_result(self):
        """A destructor's logical null cannot hide arbitrary lowered types."""
        function = self.object_function("destructor")
        function["lowered_result"] = function["receiver"]
        with self.assertRaisesRegex(ValueError, "destructor result contract"):
            check_function_contract(function, "windows-x64")

    def test_destructor_parameters(self):
        """Destructor parameters exclude the receiver and must be empty."""
        function = self.object_function("destructor")
        function["parameters"] = [self.integer]
        with self.assertRaisesRegex(ValueError, "destructor result contract"):
            check_function_contract(function, "windows-x64")

    def test_receiver_owner(self):
        """Receiver identity must name the owning class of the member."""
        function = self.object_function()
        function["receiver"]["to"]["path_hex"] = ["48"]
        with self.assertRaisesRegex(ValueError, "Invalid IR receiver"):
            check_function_contract(function, "windows-x64")

    def test_member_qualification(self):
        """Member cv belongs on the receiver pointee and must agree."""
        function = self.object_function()
        function.update(function_kind="function", result=self.integer,
                        lowered_result=self.integer, const_member=True)
        function["receiver"]["to"]["const"] = True
        check_function_contract(function, "windows-x64")
        function["receiver"]["to"]["const"] = False
        with self.assertRaisesRegex(ValueError, "Invalid IR receiver"):
            check_function_contract(function, "windows-x64")

    def test_logical_lowered_result_mismatch(self):
        """Normal scalar functions retain their logical result convention."""
        self.record["function"]["lowered_result"] = dict(
            self.integer, kind="unsigned-int")
        self.reject("logical and lowered result mismatch")

    def test_member_overload_identity(self):
        """Member cv overloads have distinct identities without ABI details."""
        function = self.object_function()
        function.update(path_hex=["47", "72656164"], function_kind="function",
                        result=self.integer, lowered_result=self.integer)
        first = function_key(function, 0)
        function["const_member"] = True
        function["receiver"]["to"]["const"] = True
        check_function_contract(function, "windows-x64")
        self.assertNotEqual(first, function_key(function, 0))

    def test_receiver_linkage(self):
        """A member receiver requires the C++ language linkage domain."""
        function = self.object_function()
        function["linkage"] = "c"
        with self.assertRaisesRegex(ValueError, "Invalid IR receiver"):
            check_function_contract(function, "windows-x64")

    def test_missing_receiver_metadata(self):
        """V2 functions cannot omit the explicit receiver convention."""
        del self.record["function"]["receiver"]
        self.reject("Missing IR receiver or lowered result")

    def test_v1_rejected(self):
        """Old body records cannot be reinterpreted as receiver-aware IR."""
        self.record["schema"] = "tinypp.function-ir.v1"
        self.reject("IR protocol, target or ABI mismatch")

    def test_scalar_call_receiver(self):
        """A free-function call cannot smuggle a receiver expression."""
        self.record["blocks"][0]["expression"] = {
            "op": "call", "type": self.integer, "args": [],
            "function": copy.deepcopy(self.record["function"]),
            "receiver": {"op": "literal", "type": self.integer,
                         "value": "0"}}
        self.reject("IR call receiver mismatch")

    def field_body(self):
        """Build an independent member reading the second scalar field."""
        body = copy.deepcopy(self.record)
        function = self.object_function()
        function.update(path_hex=["47", "72656164"], function_kind="function",
                        result=self.integer, lowered_result=self.integer)
        body["function"] = function
        body["variables"] = [{"id": 0, "storage": "parameter",
                              "type": function["receiver"]}]
        body["blocks"][0]["expression"] = {"op": "indirect",
            "type": self.integer, "args": [{"op": "field-address",
                "type": {"kind": "pointer", "const": False,
                         "volatile": False, "to": self.integer}, "offset": 4,
                "args": [{"op": "variable", "type": function["receiver"],
                          "id": 0, "offset": 0}]}]}
        return body

    def test_field_address(self):
        """A bounded, aligned byte field access has a valid typed identity."""
        check_body(self.field_body(), "windows-x64")

    def test_field_overrun(self):
        """The complete field span must fit within the owning record."""
        self.record = self.field_body()
        self.record["blocks"][0]["expression"]["args"][0]["offset"] = 8
        self.reject("field address exceeds layout or alignment")

    def test_field_negative_offset(self):
        """A field cannot precede its owning object."""
        self.record = self.field_body()
        self.record["blocks"][0]["expression"]["args"][0]["offset"] = -4
        self.reject("field address exceeds layout or alignment")

    def test_field_alignment(self):
        """A byte offset is not sufficient evidence of aligned storage."""
        self.record = self.field_body()
        self.record["blocks"][0]["expression"]["args"][0]["offset"] = 2
        self.reject("field address exceeds layout or alignment")

    def test_field_qualification(self):
        """Field addressing must preserve the base's cv qualification."""
        self.record = self.field_body()
        self.record["function"]["const_member"] = True
        self.record["function"]["receiver"]["to"]["const"] = True
        self.reject("field address drops qualification")

    def test_record_layout_conflict(self):
        """One type identity cannot acquire different layouts across units."""
        first = self.field_body()
        second = copy.deepcopy(first)
        second["function"]["path_hex"][-1] = b"other".hex()
        second["function"]["receiver"]["to"]["bytes"] = 16
        with self.assertRaisesRegex(ValueError, "Conflicting IR record layout"):
            lower_units([[self.record, first], [second]])

    def test_record_storage_bound(self):
        """Valid wire sizes still obey the narrower emitter storage bound."""
        self.record = self.field_body()
        self.record["function"]["receiver"]["to"]["bytes"] = 2 * 1024 * 1024
        self.reject("record storage limits")

    def test_record_value_result(self):
        """Storage support does not silently implement class value ABI."""
        owner = self.object_function()["receiver"]["to"]
        self.record["function"].update(result=owner, lowered_result=owner)
        self.reject("Unsupported IR record value result")

    def test_destructor_result_consumption(self):
        """DMC's int placeholder must never become an observable C++ value."""
        function = self.object_function("destructor")
        self.record["variables"] = [{"id": 0, "storage": "local",
                                    "type": function["receiver"]["to"]}]
        self.record["blocks"][0]["expression"] = {
            "op": "call", "type": self.integer, "function": function,
            "receiver": {"op": "variable-address", "id": 0, "offset": 0,
                         "type": function["receiver"]}, "args": []}
        self.reject("Destructor result cannot be consumed")

    def test_record_binding_type(self):
        """A class storage ID cannot be reinterpreted as a scalar variable."""
        self.record["variables"] = [{"id": 0, "storage": "local",
            "type": self.object_function()["receiver"]["to"]}]
        self.record["blocks"][0]["expression"] = {"op": "variable",
            "id": 0, "offset": 0, "type": self.integer}
        self.reject("IR variable type mismatch")


if __name__ == "__main__":
    unittest.main()
