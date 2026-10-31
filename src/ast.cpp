/** @file ast.cpp
 * @brief Shared semantic queries for the owned scalar representation.
 * Parser and lowering use the same category rules instead of inferring them
 * independently from the target C representation.
 */
#include "frontend.hpp"

namespace tinypp {

/** @brief Classify an owned scalar node according to its semantic form. */
bool is_lvalue(const Expression &expression) {
    switch (expression.kind) {
    case Expression::Name:
    case Expression::Assignment:
    case Expression::ReferenceCast:
        return true;
    case Expression::Update:
        return expression.operation.compare(0, 3, "pre") == 0;
    case Expression::Comma:
        return is_lvalue(expression.children[1]);
    case Expression::Conditional:
        return expression.children[1].type == expression.children[2].type &&
            expression.children[1].constant ==
                expression.children[2].constant &&
            is_lvalue(expression.children[1]) &&
            is_lvalue(expression.children[2]);
    default:
        return false;
    }
}

} // namespace tinypp
