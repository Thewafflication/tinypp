/** @file lowering.cpp
 * @brief Lower the owned typed scalar AST through the experimental C adapter.
 * Source text is never forwarded here. The caller supplies a validated AST;
 * generated target-C temporaries retain lvalue identity and side effects.
 */
#include "frontend.hpp"

#include <sstream>

namespace tinypp {
namespace {

/** @brief Map semantic types to the Windows target's scalar carriers. */
const char *carrier_type(ScalarType type) {
    switch (type) {
    case IntType: case BoolType: return "int";
    case LongType: return "long";
    case UnsignedType: return "unsigned int";
    case UnsignedLongType: return "unsigned long";
    case VoidType: return "void";
    }
    throw std::runtime_error("invalid scalar type reached lowering");
}

/** @brief Lower a validated scalar expression without duplicating effects. */
std::string lower_expression(const Expression &expression);

/** @brief Evaluate effects without fetching a discarded scalar lvalue. */
std::string lower_discarded(const Expression &expression);

/** @brief Lower the identity of a semantically validated scalar lvalue. */
std::string lower_address(const Expression &expression) {
    if (expression.kind == Expression::ReferenceCast) {
        return lower_address(expression.children[0]);
    }
    if (expression.kind == Expression::Comma) {
        return "(" + lower_discarded(expression.children[0]) + ", " +
            lower_address(expression.children[1]) + ")";
    }
    if (expression.kind == Expression::Name) {
        return "&(" + expression.operation + ")";
    }
    if (expression.kind == Expression::Assignment) {
        // A local target-C temporary preserves lvalue identity and effects.
        std::string right = lower_expression(expression.children[1]);
        if (expression.operation != "=") {
            std::string operation = expression.operation.substr(
                0, expression.operation.size() - 1);
            right = "(*tinypp_address " + operation + " " + right + ")";
            if (expression.type == BoolType) { right = "!!" + right; }
        }
        return "({" + std::string(carrier_type(expression.type)) +
            " *tinypp_address=" +
            lower_address(expression.children[0]) + ";*tinypp_address=" +
            right + ";tinypp_address;})";
    }
    if (expression.kind == Expression::Update &&
        expression.operation.compare(0, 3, "pre") == 0) {
        std::string effect = expression.type == BoolType ?
            "*tinypp_address=1;" :
            expression.operation.substr(3) + "*tinypp_address;";
        return "({" + std::string(carrier_type(expression.type)) +
            " *tinypp_address=" + lower_address(expression.children[0]) +
            ";" + effect + "tinypp_address;})";
    }
    if (expression.kind == Expression::Conditional) {
        return "(" + lower_expression(expression.children[0]) + " ? " +
            lower_address(expression.children[1]) + " : " +
            lower_address(expression.children[2]) + ")";
    }
    throw std::runtime_error("non-lvalue reached reference lowering");
}

/** @brief Generate effect-preserving C for an owned scalar expression. */
std::string lower_expression(const Expression &expression) {
    if (expression.kind == Expression::Comma) {
        return "(" + lower_discarded(expression.children[0]) + ", " +
            lower_expression(expression.children[1]) + ")";
    }
    if (expression.kind == Expression::ReferenceCast) {
        return "(*" + lower_address(expression) + ")";
    }
    if (expression.kind == Expression::Cast) {
        if (expression.type == VoidType) {
            return lower_discarded(expression.children[0]);
        }
        std::string operand = lower_expression(expression.children[0]);
        if (expression.type == BoolType) { return "!!(" + operand + ")"; }
        return "((" + std::string(carrier_type(expression.type)) + ")(" +
            operand + "))";
    }
    if (expression.kind == Expression::Update) {
        if (expression.operation.compare(0, 3, "pre") == 0) {
            return "(*" + lower_address(expression) + ")";
        }
        std::string type = carrier_type(expression.type);
        std::string effect = expression.type == BoolType ?
            "*tinypp_address=1;" :
            expression.operation.substr(4) + "*tinypp_address;";
        return "({" + type + " *tinypp_address=" +
            lower_address(expression.children[0]) + ";" + type +
            " tinypp_previous=*tinypp_address;" + effect +
            "tinypp_previous;})";
    }
    if (expression.kind == Expression::Assignment) {
        return "(*" + lower_address(expression) + ")";
    }
    if (expression.kind == Expression::Conditional) {
        return "(" + lower_expression(expression.children[0]) + " ? " +
            lower_expression(expression.children[1]) + " : " +
            lower_expression(expression.children[2]) + ")";
    }
    if (expression.kind == Expression::Literal ||
        expression.kind == Expression::Name) {
        return expression.operation;
    }
    if (expression.kind == Expression::Call) {
        std::string result = expression.operation + "(";
        for (size_t i = 0; i < expression.children.size(); ++i) {
            if (i) { result += ", "; }
            result += expression.references[i] ?
                lower_address(expression.children[i]) :
                lower_expression(expression.children[i]);
        }
        return result + ")";
    }
    if (expression.kind == Expression::Unary) {
        return "(" + expression.operation +
            lower_expression(expression.children[0]) + ")";
    }
    return "(" + lower_expression(expression.children[0]) + " " +
        expression.operation + " " + lower_expression(expression.children[1])
        + ")";
}

/** @brief Preserve effects when discarding a scalar expression. */
std::string lower_discarded(const Expression &expression) {
    return "((void)(" + (is_lvalue(expression) ? lower_address(expression) :
                        lower_expression(expression)) + "))";
}

/** @brief Lower lexical statements while preserving branch/loop structure. */
std::string lower_statement(const Statement &statement) {
    std::string result;
    switch (statement.kind) {
    case Statement::Group:
        for (size_t i = 0; i < statement.children.size(); ++i) {
            result += lower_statement(statement.children[i]);
        }
        return result;
    case Statement::Block:
        result = "{\n";
        for (size_t i = 0; i < statement.children.size(); ++i) {
            result += lower_statement(statement.children[i]);
        }
        return result + "}\n";
    case Statement::Return:
        if (!statement.has_expression) { return "return;\n"; }
        if (statement.expression.type == VoidType) {
            return "{\n" + lower_discarded(statement.expression) +
                ";return;\n}\n";
        }
        return "return " + lower_expression(statement.expression) + ";\n";
    case Statement::Declaration:
        result = std::string(statement.constant ? "const " : "") +
            carrier_type(statement.type) + " " +
            (statement.reference ? "*" : "") +
            statement.symbol;
        if (statement.has_expression) {
            result += " = " + (statement.reference ?
                lower_address(statement.expression) :
                lower_expression(statement.expression));
        }
        return result + ";\n";
    case Statement::Evaluate:
        return lower_discarded(statement.expression) + ";\n";
    case Statement::Break:
        return "break;\n";
    case Statement::Continue:
        return "continue;\n";
    case Statement::If:
        result = "if (" + lower_expression(statement.expression) + ") {\n";
        result += lower_statement(statement.children[0]) + "}\n";
        if (statement.children.size() == 2) {
            result += "else {\n" + lower_statement(statement.children[1]) +
                "}\n";
        }
        return result;
    case Statement::While:
        return "while (" + lower_expression(statement.expression) + ") {\n" +
            lower_statement(statement.children[0]) + "}\n";
    case Statement::For:
        return "{\n" + lower_statement(statement.children[0]) +
            "for (;" + lower_expression(statement.expression) + "; " +
            lower_discarded(statement.step) + ") {\n" +
            lower_statement(statement.children[1]) + "}\n}\n";
    case Statement::Do:
        return "do {\n" + lower_statement(statement.children[0]) +
            "} while (" + lower_expression(statement.expression) + ");\n";
    }
    throw std::runtime_error("invalid statement in lowering interface");
}

} // namespace

/** @brief Lower owned scalar definitions using provisional ABI symbols. */
std::string lower_scalar(const TranslationUnit &unit) {
    std::ostringstream output;
    for (size_t i = 0; i < unit.declarations.size(); ++i) {
        const Function &function = unit.declarations[i];
        output << carrier_type(function.type) << " " << function.symbol << "(";
        if (function.parameters.empty()) { output << "void"; }
        for (size_t j = 0; j < function.parameters.size(); ++j) {
            if (j) { output << ", "; }
            if (function.parameters[j].constant) { output << "const "; }
            output << carrier_type(function.parameters[j].type);
            if (function.parameters[j].reference) { output << " *"; }
        }
        output << ");\n";
    }
    for (size_t i = 0; i < unit.functions.size(); ++i) {
        const Function &function = unit.functions[i];
        output << carrier_type(function.type) << " " << function.symbol << "(";
        if (function.parameters.empty()) { output << "void"; }
        for (size_t j = 0; j < function.parameters.size(); ++j) {
            if (j) { output << ", "; }
            if (function.parameters[j].constant) { output << "const "; }
            output << carrier_type(function.parameters[j].type) << " ";
            if (function.parameters[j].reference) { output << "*"; }
            output << "tinypp_arg_" << j;
        }
        output << ") {\n" << lower_statement(function.body);
        if (function.name == "main") { output << "return 0;\n"; }
        output << "}\n";
    }
    return output.str();
}

} // namespace tinypp
