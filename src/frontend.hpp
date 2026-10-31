/** @file frontend.hpp
 * @brief Owned scalar front end and typed lowering contract.
 * The AST owns all strings and children. No external template engine or
 * standard-library implementation is provided by this component.
 */
#ifndef TINYPP_FRONTEND_HPP
#define TINYPP_FRONTEND_HPP

#include <stdexcept>
#include <string>
#include <vector>

namespace tinypp {

/** @brief Initial target scalar types; bool values normalize to zero/one. */
// C++98 cannot select an enum's underlying type.
// NOLINTNEXTLINE(performance-enum-size)
enum ScalarType { IntType, BoolType, LongType, UnsignedType, UnsignedLongType,
                  VoidType };

/** @brief One-based byte location; grouped to prevent swapped coordinates. */
struct Location {
    unsigned line; ///< Physical source line.
    unsigned column; ///< Physical byte column.
    /** @brief Construct the start of a source file. */
    Location() : line(1), column(1) {}
};

/** @brief Translation-phase text with an original location for every byte. */
struct PreparedSource {
    std::string text; ///< ASCII text after newline/trigraph/splice processing.
    std::vector<Location> locations; ///< One per byte plus the physical EOF.
};

/** @brief Apply initial source translation phases while retaining locations.
 * @param source Original bytes, at most 1 MiB; LF or CRLF physical lines.
 * @return Owned translated text and byte-to-physical-source location map.
 * @throws Diagnostic For unsupported bytes, standalone CR or source limit.
 * @note Supplies a final logical newline when the input lacks one.
 */
PreparedSource prepare_source(const std::string &source);

/** @brief Source failure with a one-based byte-oriented location. */
struct Diagnostic : std::runtime_error {
    unsigned line; ///< One-based physical source line.
    unsigned column; ///< One-based byte column.
    /** @brief Construct an owned diagnostic; does not retain input pointers.
     * @param text Human-readable reason.
     * @param location One-based source coordinates; copied by value.
     */
    Diagnostic(const std::string &text, const Location &location);
};

/** @brief Owned scalar expression retaining type and lvalue semantics. */
struct Expression {
    /** @brief Scalar expression forms retained before backend lowering. */
    // C++98 cannot select an enum's underlying type.
    // NOLINTNEXTLINE(performance-enum-size)
    enum Kind { Literal, Name, Call, Unary, Binary, Conditional, Assignment,
                Update, Comma, Cast, ReferenceCast };
    Kind kind; ///< Discriminant for this node.
    ScalarType type; ///< Semantic type after overload/conversion analysis.
    bool constant; ///< Lvalue denotes a const-qualified scalar object.
    std::string operation; ///< Validated operator or decimal literal.
    std::vector<Expression> children; ///< Owned operand nodes.
    std::vector<bool> references; ///< Reference-passing mode for call operands.
    unsigned height; ///< Maximum recursive AST depth, bounded by the parser.
    /** @brief Initialize a valid zero literal before semantic construction. */
    Expression() : kind(Literal), type(IntType), constant(false),
                   operation("0"), height(1) {}
};

/** @brief Typed function parameter with explicit value/reference passing. */
struct Parameter {
    std::string name; ///< Source name, unique within its parameter scope.
    ScalarType type; ///< Declared target type.
    bool reference; ///< Non-const lvalue reference carried as a target pointer.
    bool constant; ///< Top-level const on a value parameter, ignored in its ID.
    /** @brief Initialize an int value parameter before parsing. */
    Parameter() : type(IntType), reference(false), constant(false) {}
};

/** @brief Scoped scalar statement; children own nested control-flow bodies. */
struct Statement {
    /** @brief Statement forms supported by the scalar milestone. */
    // C++98 cannot select an enum's underlying type.
    // NOLINTNEXTLINE(performance-enum-size)
    enum Kind { Block, Return, Declaration, Evaluate, If, While, For, Do,
                Break, Continue, Group };
    Kind kind; ///< Determines active expression and children.
    ScalarType type; ///< Declared local type when this is a declaration.
    Expression expression; ///< Return, initializer, condition or effect.
    Expression step; ///< For-loop iteration expression, or a zero literal.
    std::vector<Statement> children; ///< Ordered nested statements.
    std::string symbol; ///< Unique lowered local name for a declaration.
    bool has_expression; ///< Whether a declaration/return has an expression.
    bool reference; ///< Whether the declared local is a reference alias.
    bool constant; ///< Whether this local value is immutable after init.
    /** @brief Initialize an empty block with no effects. */
    Statement() : kind(Block), type(IntType), has_expression(false),
                  reference(false), constant(false) {}
};

/** @brief Typed scalar function declaration or definition. */
struct Function {
    std::string name; ///< Validated, non-reserved source identifier.
    std::string symbol; ///< Provisional scalar ABI symbol.
    ScalarType type; ///< Declared return type.
    bool c_linkage; ///< Whether the unmangled C external symbol is selected.
    std::vector<Parameter> parameters; ///< Owned ordered parameter list.
    Statement body; ///< Owned function body and local control flow.
};

/** @brief Owned translation unit; no borrowed source storage. */
struct TranslationUnit {
    std::vector<Function> declarations; ///< Visible scalar function signatures.
    std::vector<Function> functions; ///< Definition order.
};

/** @brief Classify the value category of a validated scalar expression.
 * @param expression Owned AST from parse; no references are retained.
 * @return True for lvalues, including const lvalues; false for scalar values.
 * @note Constness and modifiability are separate from the value category.
 */
bool is_lvalue(const Expression &expression);

/** @brief Parse and validate the documented scalar subset.
 * @param source Complete source bytes; embedded NUL is rejected.
 * @return Owned typed translation unit.
 * @throws Diagnostic On invalid or unsupported syntax, or resource limit.
 * @throws std::bad_alloc On allocation failure; no persistent side effects.
 */
TranslationUnit parse(const std::string &source);

/** @brief Lower a validated scalar unit through the experimental C adapter.
 * @param unit AST produced by parse; caller retains ownership.
 * @return Owned generated C, never the original unvalidated source.
 * @throws std::bad_alloc On allocation failure.
 */
std::string lower_scalar(const TranslationUnit &unit);

/** @brief Emit an artifact using the pinned TinyCC target implementation.
 * @param units Independently validated owned translation units.
 * @param output Destination object path; caller owns output publication.
 * @param object True for an ELF object, false for a Windows PE executable.
 * @param runtime Runtime support directory, mandatory for executables.
 * @return True on success; diagnostic text goes to stderr on failure.
 * @note Single-threaded: upstream libtcc uses global compilation state.
 */
bool emit_artifact(const std::vector<TranslationUnit> &units,
                   const std::string &output,
                   bool object, const std::string &runtime);

} // namespace tinypp
#endif
