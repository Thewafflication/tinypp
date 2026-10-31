/** @file frontend.cpp
 * @brief Parse scalar functions without delegating C++ semantics to TinyCC.
 */
#include "frontend.hpp"

#include <climits>
#include <map>
#include <set>
#include <sstream>

namespace tinypp {

/** @brief Own a source diagnostic with the supplied physical location. */
Diagnostic::Diagnostic(const std::string &text, const Location &location)
    : std::runtime_error(text), line(location.line), column(location.column) {}

namespace {

/** @brief A token owns its spelling and physical starting location. */
struct Token : Location {
    std::string text; ///< Exact spelling, or empty for end of source.
};

/** @brief A lexical binding retains type separately from its C spelling. */
struct Binding {
    std::string name; ///< Source identifier.
    std::string symbol; ///< Collision-free local or parameter symbol.
    ScalarType type; ///< Declared C++ scalar type.
    bool reference; ///< Name denotes the scalar through a stored pointer.
    bool constant; ///< Binding denotes a const-qualified scalar object.
    /** @brief Initialize a scalar value binding before declaration analysis. */
    Binding() : type(IntType), reference(false), constant(false) {}
};

/** @brief Bounded recursive-descent scalar parser with location tracking. */
class Parser {
    /** @brief A reversible lexer position for syntactic disambiguation. */
    struct Cursor {
        size_t offset; ///< Next normalized byte.
        unsigned line; ///< Physical line at that byte.
        unsigned column; ///< Physical column at that byte.
        Token token; ///< Current lookahead spelling and start.
    };
    const std::string &source_; ///< Borrowed only for the parse invocation.
    const std::vector<Location> &locations_; ///< Original source coordinates.
    std::string::size_type offset_; ///< Next unread byte.
    unsigned line_; ///< Next byte line.
    unsigned column_; ///< Next byte column.
    unsigned depth_; ///< Current expression nesting depth.
    Token token_; ///< Current lookahead.
    std::vector<Function> declarations_; ///< Functions visible at this point.
    std::vector<Parameter> parameters_; ///< Current function parameter scope.
    std::vector<Binding> bindings_; ///< Active lexical bindings.
    size_t scope_begin_; ///< First binding in the current declaration scope.
    unsigned local_index_; ///< Monotonic unique name counter per function.
    unsigned statement_depth_; ///< Bounded nested statement depth.
    unsigned statement_count_; ///< Bounded statement count per function.
    unsigned loop_depth_; ///< Context for break and continue validation.
    ScalarType return_type_; ///< Current function return conversion target.
    std::string namespace_; ///< Current namespace path including trailing ::.
    unsigned namespace_depth_; ///< Bounded named namespace nesting.
    std::set<std::string> namespaces_; ///< Declared named namespaces.
    std::map<std::string, std::string> aliases_; ///< Canonical alias targets.
    bool c_linkage_; ///< Current language linkage for nested declarations.
    bool linkage_scope_; ///< Whether an explicit linkage block is active.

    /** @brief Save the token cursor without changing semantic state. */
    Cursor cursor() const {
        Cursor result;
        result.offset = offset_;
        result.line = line_;
        result.column = column_;
        result.token = token_;
        return result;
    }

    /** @brief Restore lookahead after a syntax-only trial parse. */
    void restore(const Cursor &saved) {
        offset_ = saved.offset;
        line_ = saved.line;
        column_ = saved.column;
        token_ = saved.token;
    }

    /** @brief Convert a checked decimal index to an owned string. */
    static std::string number(size_t value) {
        std::ostringstream text;
        text << value;
        return text.str();
    }

    /** @brief Consume an identifier, rejecting reserved C++98 spellings. */
    std::string identifier() {
        const std::string keywords =
            " asm auto bool break case catch char class const "
            "const_cast continue default delete do double dynamic_cast "
            "else enum explicit export extern false float for friend "
            "goto if inline int long mutable namespace new operator "
            "private protected public register reinterpret_cast return "
            "short signed sizeof static static_cast struct switch "
            "template this throw true try typedef typeid typename union "
            "unsigned using virtual void volatile wchar_t while and "
            "and_eq bitand bitor compl not not_eq or or_eq xor xor_eq ";
        std::string name = token_.text;
        if (name.size() > 1024) {
            fail("identifier limit exceeded (1024 bytes)");
        }
        if (name.empty() || !letter(name[0]) || name[0] == '_' ||
            name.find("__") != std::string::npos ||
            keywords.find(" " + name + " ") != std::string::npos) {
            fail("expected a supported non-reserved identifier");
        }
        next();
        return name;
    }

    /** @brief Read an optionally rooted qualified expression name. */
    std::string qualified_name() {
        std::string result;
        if (token_.text == "::") { result = "::"; next(); }
        result += identifier();
        while (token_.text == "::") {
            next();
            result += "::" + identifier();
            if (result.size() > 4096) {
                fail("qualified name limit exceeded (4096 bytes)");
            }
        }
        return result;
    }

    /** @brief Encode namespace components without collisions with globals. */
    static std::string encoded_name(const std::string &name) {
        if (name.find("::") == std::string::npos) {
            return "tinypp_fn_" + name;
        }
        std::string result = "tinypp_ns_";
        size_t start = 0;
        for (;;) {
            size_t end = name.find("::", start);
            std::string component = name.substr(start, end - start);
            result += number(component.size()) + "_" + component + "_";
            if (end == std::string::npos) { break; }
            start = end + 2;
        }
        return result;
    }

    /** @brief Compare the parameter types that form a scalar signature. */
    static bool same_parameters(const Function &a, const Function &b) {
        if (a.parameters.size() != b.parameters.size()) { return false; }
        for (size_t i = 0; i < a.parameters.size(); ++i) {
            if (a.parameters[i].type != b.parameters[i].type ||
                a.parameters[i].reference != b.parameters[i].reference) {
                return false;
            }
        }
        return true;
    }

    /** @brief Remove one namespace component from an enclosing prefix. */
    static std::string enclosing(std::string prefix) {
        if (prefix.empty()) { return prefix; }
        prefix.erase(prefix.size() - 2);
        size_t parent = prefix.rfind("::");
        return parent == std::string::npos ? "" : prefix.substr(0, parent + 2);
    }

    /** @brief Resolve one namespace name without recursive alias expansion. */
    std::string namespace_target(const std::string &name) const {
        if (namespaces_.count(name)) { return name; }
        std::map<std::string, std::string>::const_iterator found =
            aliases_.find(name);
        return found == aliases_.end() ? "" : found->second;
    }

    /** @brief Resolve namespace components, stopping at the nearest match. */
    std::string resolve_namespace(const std::string &name) const {
        bool rooted = name.compare(0, 2, "::") == 0;
        size_t start = rooted ? 2 : 0;
        size_t end = name.find("::", start);
        std::string first = name.substr(start, end - start);
        std::string prefix = rooted ? "" : namespace_;
        std::string target;
        for (;;) {
            target = namespace_target(prefix + first);
            if (!target.empty() || prefix.empty()) { break; }
            prefix = enclosing(prefix);
        }
        while (!target.empty() && end != std::string::npos) {
            start = end + 2;
            end = name.find("::", start);
            target += "::";
            target += name.substr(start, end - start);
            target = namespace_target(target);
        }
        return target;
    }

    /** @brief Find the first enclosing namespace with a declaration set. */
    std::string resolve_function(const std::string &name) {
        size_t separator = name.rfind("::");
        if (separator != std::string::npos && separator != 0) {
            std::string target = resolve_namespace(name.substr(0, separator));
            return target.empty() ? "" : target + name.substr(separator);
        }
        if (name.compare(0, 2, "::") == 0) { return name.substr(2); }
        std::string prefix = namespace_;
        for (;;) {
            std::string candidate = prefix + name;
            if (!namespace_target(candidate).empty()) {
                return candidate;
            }
            for (size_t i = 0; i < declarations_.size(); ++i) {
                if (declarations_[i].name == candidate) { return candidate; }
            }
            if (prefix.empty()) { break; }
            prefix = enclosing(prefix);
        }
        return name;
    }

    /** @brief Consume a supported type specifier. */
    ScalarType scalar_type() {
        if (token_.text == "bool") { next(); return BoolType; }
        if (token_.text == "void") { next(); return VoidType; }
        bool integer = false, longer = false, sign = false, unsign = false;
        bool consumed = false;
        while (token_.text == "int" || token_.text == "long" ||
               token_.text == "signed" || token_.text == "unsigned") {
            consumed = true;
            if (token_.text == "int") {
                if (integer) { fail("duplicate int specifier"); }
                integer = true;
            } else if (token_.text == "long") {
                if (longer) { fail("long long is outside strict C++98"); }
                longer = true;
            } else if (token_.text == "signed") {
                if (sign || unsign) { fail("conflicting sign specifiers"); }
                sign = true;
            } else {
                if (sign || unsign) { fail("conflicting sign specifiers"); }
                unsign = true;
            }
            next();
        }
        if (!consumed) { fail("expected supported scalar type"); }
        return unsign ? (longer ? UnsignedLongType : UnsignedType) :
                       (longer ? LongType : IntType);
    }

    /** @brief Read leading/trailing const for a scalar object declaration. */
    ScalarType qualified_scalar(bool &constant) {
        constant = token_.text == "const";
        if (constant) { next(); }
        ScalarType result = scalar_type();
        if (token_.text == "const") {
            if (constant) { fail("duplicate const qualifier"); }
            constant = true;
            next();
        }
        return result;
    }

    /** @brief Normalize an int value converted to bool in the owned AST. */
    Expression convert(Expression value, ScalarType target) {
        if ((value.type == VoidType) != (target == VoidType)) {
            fail("void and value expressions cannot be implicitly converted");
        }
        if (target == BoolType && value.type != BoolType) {
            Expression result;
            result.kind = Expression::Unary;
            result.type = BoolType;
            result.operation = "!!";
            result.height = value.height + 1;
            result.children.push_back(value);
            return result;
        }
        return value;
    }

    /** @brief Rank exact match, bool promotion, then int-to-bool conversion. */
    static int rank(ScalarType from, ScalarType to) {
        return from == to ? 0 : (from == BoolType && to == IntType ? 1 : 2);
    }

    /** @brief Select usual arithmetic type for the Windows 32-bit integers. */
    static ScalarType arithmetic(ScalarType a, ScalarType b) {
        if (a == BoolType) { a = IntType; }
        if (b == BoolType) { b = IntType; }
        if (a == b) { return a; }
        if (a == UnsignedLongType || b == UnsignedLongType) {
            return UnsignedLongType;
        }
        if ((a == LongType && b == UnsignedType) ||
            (b == LongType && a == UnsignedType)) {
            return UnsignedLongType;
        }
        if (a == LongType || b == LongType) { return LongType; }
        return UnsignedType;
    }

    /** @brief Identify type-keyword starts without consuming lookahead. */
    bool type_start() const {
        return token_.text == "int" || token_.text == "bool" ||
            token_.text == "long" || token_.text == "unsigned" ||
            token_.text == "signed" || token_.text == "void";
    }

    /** @brief Build a scalar conversion or exact reference cast. */
    static Expression cast(ScalarType target, bool reference,
                           const Expression &operand, const Location &where) {
        if (operand.type == VoidType && target != VoidType) {
            throw Diagnostic("void cannot be cast to a scalar value", where);
        }
        if (reference && (!is_lvalue(operand) || operand.type != target ||
                          operand.constant)) {
            throw Diagnostic("reference cast requires an exact-type lvalue",
                             where);
        }
        Expression result;
        result.kind = reference ? Expression::ReferenceCast : Expression::Cast;
        result.type = target;
        result.children.push_back(operand);
        result.height = operand.height + 1;
        if (result.height > 128) {
            throw Diagnostic("cast tree limit exceeded (128)", where);
        }
        return result;
    }

    /** @brief Check arity and exact lvalue binding for non-const references. */
    static bool viable(const Function &function,
                       const std::vector<Expression> &arguments) {
        if (function.parameters.size() != arguments.size()) { return false; }
        for (size_t i = 0; i < arguments.size(); ++i) {
            if (arguments[i].type == VoidType) { return false; }
            if (function.parameters[i].reference &&
                (!is_lvalue(arguments[i]) ||
                 function.parameters[i].type != arguments[i].type ||
                 arguments[i].constant)) {
                return false;
            }
        }
        return true;
    }

    /** @brief Test candidate dominance across every argument. */
    static bool better(const Function &a, const Function &b,
                       const std::vector<Expression> &arguments) {
        bool strict = false;
        for (size_t i = 0; i < arguments.size(); ++i) {
            int ar = rank(arguments[i].type, a.parameters[i].type);
            int br = rank(arguments[i].type, b.parameters[i].type);
            if (ar > br) { return false; }
            if (ar < br) { strict = true; }
        }
        return strict;
    }

    /** @brief Bind a call using the currently visible scalar overload set. */
    Expression call(const std::string &name, const Location &location) {
        Expression result;
        result.kind = Expression::Call;
        expect("(");
        if (token_.text != ")") {
            for (;;) {
                if (result.children.size() == 16) {
                    fail("argument limit exceeded (16)");
                }
                result.children.push_back(expression(0));
                if (token_.text != ",") { break; }
                next();
            }
        }
        expect(")");
        std::string resolved = resolve_function(name);
        std::vector<size_t> candidates;
        for (size_t i = 0; i < declarations_.size(); ++i) {
            if (declarations_[i].name == resolved && resolved != "main" &&
                viable(declarations_[i], result.children)) {
                candidates.push_back(i);
            }
        }
        size_t selected = declarations_.size();
        for (size_t i = 0; i < candidates.size(); ++i) {
            bool best = true;
            for (size_t j = 0; j < candidates.size(); ++j) {
                if (i != j && !better(declarations_[candidates[i]],
                    declarations_[candidates[j]], result.children)) {
                    best = false;
                }
            }
            if (best) { selected = candidates[i]; }
        }
        if (selected == declarations_.size()) {
            throw Diagnostic(candidates.empty() ?
                "no matching visible function" : "ambiguous scalar overload",
                location);
        }
        const Function &function = declarations_[selected];
        result.type = function.type;
        result.operation = function.symbol;
        for (size_t i = 0; i < result.children.size(); ++i) {
            result.references.push_back(function.parameters[i].reference);
            if (!function.parameters[i].reference) {
                result.children[i] = convert(result.children[i],
                                             function.parameters[i].type);
            }
            if (result.height <= result.children[i].height) {
                result.height = result.children[i].height + 1;
            }
        }
        return result;
    }

    /** @brief Advance a byte; newline increments the physical line. */
    void advance() {
        ++offset_;
        line_ = locations_[offset_].line;
        column_ = locations_[offset_].column;
    }

    /** @brief Test ASCII identifier-start membership for one byte. */
    static bool letter(char c) {
        return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
    }

    /** @brief Test ASCII decimal-digit membership for one byte. */
    static bool digit(char c) { return c >= '0' && c <= '9'; }

    /** @brief Throw at the current lookahead location; never returns. */
    void fail(const std::string &message) const {
        throw Diagnostic(message, token_);
    }

    /** @brief Read lookahead, skipping whitespace and C++ comments.
     * @throws Diagnostic On unterminated comment or invalid source byte.
     */
    void next() {
        while (offset_ < source_.size()) {
            char c = source_[offset_];
            if (c == ' ' || c == '\t' || c == '\r' || c == '\n' ||
                c == '\v' || c == '\f') {
                advance();
            } else if (source_.compare(offset_, 2, "//") == 0) {
                while (offset_ < source_.size() && source_[offset_] != '\n') {
                    advance();
                }
            } else if (source_.compare(offset_, 2, "/*") == 0) {
                Location start;
                start.line = line_;
                start.column = column_;
                advance();
                advance();
                while (offset_ < source_.size() &&
                       source_.compare(offset_, 2, "*/") != 0) {
                    advance();
                }
                if (offset_ == source_.size()) {
                    throw Diagnostic("unterminated comment", start);
                }
                advance();
                advance();
            } else {
                break;
            }
        }
        token_.line = line_;
        token_.column = column_;
        token_.text.clear();
        if (offset_ == source_.size()) {
            return;
        }
        char c = source_[offset_];
        if (c == '\0' || static_cast<unsigned char>(c) >= 128) {
            fail("unsupported source byte in initial ASCII subset");
        }
        std::string::size_type start = offset_;
        advance();
        if (letter(c) || digit(c)) {
            while (offset_ < source_.size() &&
                   (letter(source_[offset_]) || digit(source_[offset_]))) {
                advance();
            }
        } else if (c == '"') {
            while (offset_ < source_.size() && source_[offset_] != '"') {
                if (source_[offset_] == '\n' || source_[offset_] == '\r') {
                    fail("newline in a string literal");
                }
                if (source_[offset_] == '\\') {
                    advance();
                    if (offset_ == source_.size()) {
                        fail("unterminated string escape");
                    }
                }
                advance();
            }
            if (offset_ == source_.size()) {
                fail("unterminated string literal");
            }
            advance();
        }
        token_.text = source_.substr(start, offset_ - start);
        if (token_.text == "and") { token_.text = "&&"; }
        if (token_.text == "or") { token_.text = "||"; }
        if (token_.text == "not") { token_.text = "!"; }
        if (token_.text == "compl") { token_.text = "~"; }
        if (token_.text == "bitand") { token_.text = "&"; }
        if (token_.text == "bitor") { token_.text = "|"; }
        if (token_.text == "xor") { token_.text = "^"; }
        if (token_.text == "not_eq") { token_.text = "!="; }
        if (token_.text == "and_eq") { token_.text = "&="; }
        if (token_.text == "or_eq") { token_.text = "|="; }
        if (token_.text == "xor_eq") { token_.text = "^="; }
        if (!letter(c) && !digit(c) && offset_ < source_.size()) {
            const char *operators[] = {
                "<<=", ">>=",
                "++", "--", "+=", "-=", "*=", "/=", "%=", "==", "!=",
                "<=", ">=", "&&", "||", "<<", ">>", "->", "::", "&=",
                "|=", "^=", "##", 0
            };
            for (size_t i = 0; operators[i]; ++i) {
                size_t length = std::string(operators[i]).size();
                if (source_.compare(start, length, operators[i]) == 0) {
                    for (size_t n = 1; n < length; ++n) { advance(); }
                    token_.text = source_.substr(start, length);
                    break;
                }
            }
        }
    }

    /** @brief Consume the specified spelling or report a diagnostic. */
    void expect(const std::string &text) {
        if (token_.text != text) {
            fail("expected '" + text + "'");
        }
        next();
    }

    /** @brief Parse bounded unary or parenthesized/literal expression. */
    Expression primary() {
        if (++depth_ > 128) {
            fail("expression nesting limit exceeded (128)");
        }
        Expression result;
        if (token_.text == "static_cast") {
            Location where = token_;
            next();
            expect("<");
            bool constant = false;
            ScalarType target = qualified_scalar(constant);
            bool reference = false;
            if (token_.text == "&") { reference = true; next(); }
            if (constant && reference) {
                fail("const reference cast unsupported");
            }
            expect(">");
            expect("(");
            Expression operand = sequence();
            expect(")");
            result = cast(target, reference, operand, where);
        } else if (type_start()) {
            Location where = token_;
            ScalarType target = token_.text == "bool" ? BoolType :
                (token_.text == "void" ? VoidType :
                 (token_.text == "long" ? LongType :
                  (token_.text == "unsigned" ? UnsignedType : IntType)));
            next();
            expect("(");
            Expression operand;
            if (token_.text != ")") { operand = expression(0); }
            expect(")");
            result = cast(target, false, operand, where);
        } else if (token_.text == "++" || token_.text == "--") {
            result.kind = Expression::Update;
            result.operation = "pre" + token_.text;
            next();
            result.children.push_back(primary());
            if (result.children[0].type == VoidType) {
                fail("unary operator requires a value");
            }
            result.type = result.children[0].type;
            result.height = result.children[0].height + 1;
            if (!is_lvalue(result.children[0]) || result.children[0].constant ||
                (result.type == BoolType && result.operation == "pre--")) {
                fail("invalid prefix update operand");
            }
        } else if (token_.text == "+" || token_.text == "-" ||
            token_.text == "!" || token_.text == "~") {
            result.kind = Expression::Unary;
            result.operation = token_.text;
            result.type = token_.text == "!" ? BoolType : IntType;
            next();
            result.children.push_back(primary());
            if (result.children[0].type == VoidType) {
                fail("unary operator requires a value");
            }
            if (result.operation != "!") {
                result.type = result.children[0].type == BoolType ? IntType :
                    result.children[0].type;
            }
            result.height = result.children[0].height + 1;
        } else if (token_.text == "(") {
            Location where = token_;
            next();
            if (type_start() || token_.text == "const") {
                Cursor saved = cursor();
                bool constant = false;
                ScalarType target = qualified_scalar(constant);
                bool reference = false;
                if (token_.text == "&") { reference = true; next(); }
                if (constant && reference) {
                    fail("const reference cast unsupported");
                }
                if (token_.text == ")") {
                    next();
                    result = cast(target, reference, primary(), where);
                } else {
                    restore(saved);
                    result = sequence();
                    expect(")");
                }
            } else {
                result = sequence();
                expect(")");
            }
        } else if (token_.text == "true" || token_.text == "false") {
            result.kind = Expression::Literal;
            result.type = BoolType;
            result.operation = token_.text == "true" ? "1" : "0";
            next();
        } else if (token_.text == "::" ||
                   (!token_.text.empty() && letter(token_.text[0]))) {
            Location location = token_;
            std::string name = qualified_name();
            bool found = false;
            for (size_t i = bindings_.size(); i > 0; --i) {
                if (bindings_[i - 1].name == name) {
                    result.kind = Expression::Name;
                    result.type = bindings_[i - 1].type;
                    result.constant = bindings_[i - 1].constant;
                    result.operation = bindings_[i - 1].symbol;
                    if (bindings_[i - 1].reference) {
                        result.operation = "(*" + result.operation + ")";
                    }
                    found = true;
                    break;
                }
            }
            if (found && token_.text == "(") {
                throw Diagnostic("scalar variable is not callable", location);
            }
            if (!found) {
                if (token_.text != "(") {
                    throw Diagnostic("undeclared identifier '" + name + "'",
                                     location);
                }
                result = call(name, location);
            }
        } else {
            if (token_.text.empty() || !digit(token_.text[0])) {
                fail("expected an int expression; construct not supported");
            }
            unsigned long value = 0;
            const std::string text = token_.text;
            size_t i = 0;
            unsigned base = 10;
            if (text[0] == '0') { base = 8; }
            if (text.size() > 1 && text[0] == '0' &&
                (text[1] == 'x' || text[1] == 'X')) {
                base = 16;
                i = 2;
            }
            size_t first = i;
            for (; i < text.size(); ++i) {
                char c = text[i];
                unsigned d = digit(c) ? c - '0' :
                    (c >= 'a' && c <= 'f' ? c - 'a' + 10 :
                     (c >= 'A' && c <= 'F' ? c - 'A' + 10 : 99));
                if (d >= base) { break; }
                if (value > (4294967295UL - d) / base) {
                    fail("integer literal exceeds supported 32-bit types");
                }
                value = value * base + d;
            }
            if (i == first) { fail("integer literal requires digits"); }
            bool unsign = false, longer = false;
            for (; i < text.size(); ++i) {
                char c = text[i];
                if ((c == 'u' || c == 'U') && !unsign) { unsign = true; }
                else if ((c == 'l' || c == 'L') && !longer) { longer = true; }
                else { fail("invalid or unsupported integer suffix"); }
            }
            result.kind = Expression::Literal;
            result.type = unsign ? (longer ? UnsignedLongType : UnsignedType) :
                (longer ? (value <= 2147483647UL ? LongType :
                           UnsignedLongType) :
                 (value <= 2147483647UL ? IntType :
                  (base == 10 ? UnsignedLongType : UnsignedType)));
            result.operation = number(value);
            if (result.type == LongType) { result.operation += "L"; }
            if (result.type == UnsignedType) { result.operation += "U"; }
            if (result.type == UnsignedLongType) { result.operation += "UL"; }
            result.height = 1;
            next();
        }
        while (token_.text == "++" || token_.text == "--") {
            if (!is_lvalue(result) || result.constant ||
                (result.type == BoolType && token_.text == "--")) {
                fail("invalid postfix update operand");
            }
            Expression updated;
            updated.kind = Expression::Update;
            updated.operation = "post" + token_.text;
            updated.type = result.type;
            updated.children.push_back(result);
            updated.height = result.height + 1;
            result = updated;
            next();
        }
        --depth_;
        if (result.height > 128) {
            fail("expression tree limit exceeded (128)");
        }
        return result;
    }

    /** @brief Return scalar precedence, or -1 for a non-binary token. */
    static int precedence(const std::string &op) {
        if (op == "||") { return 0; }
        if (op == "&&") { return 1; }
        if (op == "|") { return 2; }
        if (op == "^") { return 3; }
        if (op == "&") { return 4; }
        if (op == "==" || op == "!=") { return 5; }
        if (op == "<" || op == ">" || op == "<=" || op == ">=") {
            return 6;
        }
        if (op == "<<" || op == ">>") { return 7; }
        if (op == "+" || op == "-") { return 8; }
        if (op == "*" || op == "/" || op == "%") { return 9; }
        return -1;
    }

    /** @brief Parse left-associative arithmetic using precedence climbing. */
    Expression expression(int minimum) {
        Expression left = primary();
        while (precedence(token_.text) >= minimum) {
            std::string op = token_.text;
            int level = precedence(op);
            next();
            Expression combined;
            combined.kind = Expression::Binary;
            combined.operation = op;
            combined.type = level == 0 || level == 1 || level == 5 ||
                level == 6 ? BoolType : IntType;
            combined.children.push_back(left);
            combined.children.push_back(expression(level + 1));
            if (left.type == VoidType ||
                combined.children[1].type == VoidType) {
                fail("binary operator requires value operands");
            }
            if (combined.type != BoolType) {
                combined.type = level == 7 ?
                    (left.type == BoolType ? IntType : left.type) :
                    arithmetic(combined.children[0].type,
                               combined.children[1].type);
            }
            unsigned lh = combined.children[0].height;
            unsigned rh = combined.children[1].height;
            combined.height = 1 + (lh > rh ? lh : rh);
            if (combined.height > 128) {
                fail("expression tree limit exceeded (128)");
            }
            left = combined;
        }
        if (minimum == 0 && token_.text == "?") {
            if (left.type == VoidType) {
                fail("conditional test requires a value");
            }
            if (++depth_ > 128) {
                fail("conditional nesting limit exceeded (128)");
            }
            next();
            Expression selected;
            selected.kind = Expression::Conditional;
            selected.children.push_back(left);
            selected.children.push_back(sequence());
            expect(":");
            selected.children.push_back(expression(0));
            if ((selected.children[1].type == VoidType) !=
                (selected.children[2].type == VoidType)) {
                fail("conditional void branches must both have void type");
            }
            selected.type = selected.children[1].type ==
                selected.children[2].type ? selected.children[1].type :
                arithmetic(selected.children[1].type,
                           selected.children[2].type);
            if (is_lvalue(selected.children[1]) &&
                is_lvalue(selected.children[2]) &&
                selected.children[1].type == selected.children[2].type) {
                if (selected.children[1].constant !=
                    selected.children[2].constant) {
                    fail("mixed-const conditional lvalues are unsupported");
                }
                selected.constant = selected.children[1].constant;
            }
            for (size_t i = 0; i < selected.children.size(); ++i) {
                if (selected.height <= selected.children[i].height) {
                    selected.height = selected.children[i].height + 1;
                }
            }
            if (selected.height > 128) {
                fail("conditional tree limit exceeded (128)");
            }
            --depth_;
            left = selected;
        }
        const std::string assignments =
            " = += -= *= /= %= <<= >>= &= |= ^= ";
        if (minimum == 0 && !token_.text.empty() &&
            assignments.find(" " + token_.text + " ") != std::string::npos) {
            if (!is_lvalue(left) || left.constant) {
                fail("assignment requires a scalar lvalue");
            }
            if (++depth_ > 128) {
                fail("assignment nesting limit exceeded (128)");
            }
            Expression assigned;
            assigned.kind = Expression::Assignment;
            assigned.operation = token_.text;
            next();
            assigned.type = left.type;
            assigned.children.push_back(left);
            Expression right = expression(0);
            assigned.children.push_back(assigned.operation == "=" ?
                convert(right, left.type) : right);
            unsigned lh = assigned.children[0].height;
            unsigned rh = assigned.children[1].height;
            assigned.height = 1 + (lh > rh ? lh : rh);
            if (assigned.height > 128) {
                fail("assignment tree limit exceeded (128)");
            }
            --depth_;
            return assigned;
        }
        return left;
    }

    /** @brief Parse comma sequencing without consuming call delimiters. */
    Expression sequence() {
        Expression left = expression(0);
        while (token_.text == ",") {
            next();
            Expression result;
            result.kind = Expression::Comma;
            result.operation = ",";
            result.children.push_back(left);
            result.children.push_back(expression(0));
            result.type = result.children[1].type;
            result.constant = result.children[1].constant;
            unsigned lh = left.height, rh = result.children[1].height;
            result.height = 1 + (lh > rh ? lh : rh);
            if (result.height > 128) {
                fail("comma tree limit exceeded (128)");
            }
            left = result;
        }
        return left;
    }

    /** @brief Parse a block and restore bindings on scope exit. */
    Statement block(bool function_body,
                    size_t restricted = std::string::npos) {
        Statement result;
        size_t previous = scope_begin_;
        size_t saved = bindings_.size();
        scope_begin_ = function_body ? 0 :
            (restricted == std::string::npos ? saved : restricted);
        expect("{");
        while (token_.text != "}") {
            if (token_.text.empty()) { fail("unterminated block"); }
            result.children.push_back(statement());
        }
        expect("}");
        bindings_.resize(saved);
        scope_begin_ = previous;
        return result;
    }

    /** @brief Parse a substatement with its required implicit lexical scope. */
    Statement scoped_statement(size_t restricted = std::string::npos) {
        size_t saved = bindings_.size();
        size_t previous = scope_begin_;
        scope_begin_ = restricted == std::string::npos ? saved : restricted;
        Statement result;
        if (restricted != std::string::npos && token_.text == "{") {
            result = block(false, restricted);
        } else {
            result = statement();
        }
        bindings_.resize(saved);
        scope_begin_ = previous;
        return result;
    }

    /** @brief Read a bounded scalar declarator with optional parentheses. */
    std::string local_name(bool &reference, unsigned depth) {
        if (depth > 128) { fail("declarator nesting limit exceeded (128)"); }
        if (token_.text == "&") {
            if (reference) { fail("reference-to-reference declarator"); }
            reference = true;
            next();
        }
        if (token_.text == "(") {
            next();
            std::string name = local_name(reference, depth + 1);
            expect(")");
            return name;
        }
        return identifier();
    }

    /** @brief Prefer declarations when supported syntax is ambiguous. */
    bool declaration_ahead() {
        Cursor saved = cursor();
        bool constant = false;
        (void)qualified_scalar(constant);
        bool declaration = false;
        try {
            bool reference = false;
            (void)local_name(reference, 0);
            declaration = token_.text == ";" || token_.text == "=" ||
                token_.text == "," || token_.text == "(" ||
                token_.text == "[";
        } catch (const Diagnostic &) {
            // The expression parse still diagnoses malformed syntax.
            declaration = false;
        }
        restore(saved);
        return declaration;
    }

    /** @brief Parse sequential scalar declarators in one lexical scope. */
    Statement local_declaration() {
        Statement group;
        group.kind = Statement::Group;
        bool constant = false;
        ScalarType type = qualified_scalar(constant);
        if (type == VoidType) { fail("void objects cannot be declared"); }
        for (;;) {
            if (local_index_ == 4096 || group.children.size() == 256) {
                fail("local declaration resource limit exceeded");
            }
            Statement result;
            result.kind = Statement::Declaration;
            Binding binding;
            binding.type = type;
            binding.constant = constant;
            binding.name = local_name(binding.reference, 0);
            if (constant && binding.reference) {
                fail("const reference declarations are not yet supported");
            }
            binding.symbol = "tinypp_local_" + number(local_index_++);
            for (size_t i = scope_begin_; i < bindings_.size(); ++i) {
                if (bindings_[i].name == binding.name) {
                    fail("redeclaration in the same lexical scope");
                }
            }
            bindings_.push_back(binding);
            result.symbol = binding.symbol;
            result.type = binding.type;
            result.reference = binding.reference;
            result.constant = binding.constant;
            if (token_.text == "=" || token_.text == "(") {
                bool direct = token_.text == "(";
                next();
                if (direct && token_.text == ")") {
                    fail("block-scope function declarations are not supported");
                }
                result.has_expression = true;
                result.expression = expression(0);
                if (direct) { expect(")"); }
                if (binding.reference) {
                    if (!is_lvalue(result.expression) ||
                        result.expression.constant ||
                        result.expression.type != binding.type) {
                        fail("reference requires an exact-type scalar lvalue");
                    }
                } else {
                    result.expression = convert(result.expression,
                                                binding.type);
                }
            }
            if (binding.reference && !result.has_expression) {
                fail("reference declaration requires an initializer");
            }
            if (constant && !result.has_expression) {
                fail("const scalar declaration requires initialization");
            }
            if (result.expression.height > 128) {
                fail("converted initializer limit exceeded (128)");
            }
            group.children.push_back(result);
            if (token_.text != ",") { break; }
            next();
        }
        expect(";");
        return group;
    }

    /** @brief Parse bounded statements with owned types and lexical scope. */
    Statement statement() {
        if (++statement_depth_ > 128 || ++statement_count_ > 4096) {
            fail("statement resource limit exceeded");
        }
        Statement result;
        if (token_.text == "{") {
            result = block(false);
        } else if (token_.text == "for") {
            next();
            expect("(");
            size_t saved = bindings_.size(), previous = scope_begin_;
            scope_begin_ = saved;
            result.kind = Statement::For;
            if (token_.text == "{" || token_.text == "if" ||
                token_.text == "while" || token_.text == "for" ||
                token_.text == "do" || token_.text == "return" ||
                token_.text == "break" || token_.text == "continue") {
                fail("invalid for-loop initializer statement");
            }
            if (token_.text == ";") {
                Statement empty;
                empty.kind = Statement::Evaluate;
                result.children.push_back(empty);
                next();
            } else {
                result.children.push_back(statement());
            }
            result.expression.operation = "1";
            if (token_.text != ";") { result.expression = sequence(); }
            expect(";");
            if (token_.text != ")") { result.step = sequence(); }
            expect(")");
            ++loop_depth_;
            result.children.push_back(scoped_statement(saved));
            --loop_depth_;
            bindings_.resize(saved);
            scope_begin_ = previous;
        } else if (token_.text == "do") {
            next();
            result.kind = Statement::Do;
            ++loop_depth_;
            result.children.push_back(scoped_statement());
            --loop_depth_;
            expect("while");
            expect("(");
            result.expression = sequence();
            expect(")");
            expect(";");
        } else if (token_.text == "return") {
            next();
            result.kind = Statement::Return;
            if (token_.text != ";") {
                result.has_expression = true;
                result.expression = convert(sequence(), return_type_);
            } else if (return_type_ != VoidType) {
                fail("value-returning function requires a return expression");
            }
            expect(";");
        } else if (token_.text == "if" || token_.text == "while") {
            bool loop = token_.text == "while";
            result.kind = loop ? Statement::While : Statement::If;
            next();
            expect("(");
            result.expression = sequence();
            expect(")");
            if (loop) { ++loop_depth_; }
            result.children.push_back(scoped_statement());
            if (loop) { --loop_depth_; }
            if (!loop && token_.text == "else") {
                next();
                result.children.push_back(scoped_statement());
            }
        } else if (token_.text == "break" || token_.text == "continue") {
            if (!loop_depth_) { fail("loop control outside a loop"); }
            result.kind = token_.text == "break" ? Statement::Break :
                                                     Statement::Continue;
            next();
            expect(";");
        } else if (type_start() || token_.text == "const") {
            if (declaration_ahead()) {
                result = local_declaration();
            } else {
                result.kind = Statement::Evaluate;
                result.expression = sequence();
                expect(";");
            }
        } else if (token_.text == ";") {
            next();
        } else {
            result.kind = Statement::Evaluate;
            result.expression = sequence();
            expect(";");
        }
        if (result.expression.height > 128) {
            fail("converted expression tree limit exceeded (128)");
        }
        if ((result.kind == Statement::If || result.kind == Statement::While ||
             result.kind == Statement::Do || result.kind == Statement::For) &&
            result.expression.type == VoidType) {
            fail("control-flow condition requires a value");
        }
        --statement_depth_;
        return result;
    }

    /** @brief Parse declarations in a bounded namespace context. */
    void declarations(TranslationUnit &result, bool nested) {
        while (!token_.text.empty() && (!nested || token_.text != "}")) {
            bool function_linkage = c_linkage_;
            bool specified_linkage = linkage_scope_;
            bool single_linkage = false;
            if (token_.text == "extern") {
                next();
                if (token_.text != "\"C\"" && token_.text != "\"C++\"") {
                    fail("expected supported language linkage (C or C++)");
                }
                function_linkage = token_.text == "\"C\"";
                specified_linkage = true;
                next();
                if (token_.text == "{") {
                    if (++namespace_depth_ > 32) {
                        fail("declaration scope nesting limit exceeded (32)");
                    }
                    next();
                    bool previous = c_linkage_;
                    bool previous_scope = linkage_scope_;
                    c_linkage_ = function_linkage;
                    linkage_scope_ = true;
                    declarations(result, true);
                    expect("}");
                    c_linkage_ = previous;
                    linkage_scope_ = previous_scope;
                    --namespace_depth_;
                    continue;
                }
                single_linkage = true;
            }
            if (token_.text == "namespace") {
                if (single_linkage) {
                    fail("single linkage specifier requires a function");
                }
                next();
                std::string name = namespace_ + identifier();
                if (name.size() > 4096) {
                    fail("namespace path limit exceeded (4096 bytes)");
                }
                for (size_t i = 0; i < declarations_.size(); ++i) {
                    if (declarations_[i].name == name) {
                        fail("namespace conflicts with a function name");
                    }
                }
                if (token_.text == "=") {
                    next();
                    std::string target = resolve_namespace(qualified_name());
                    if (target.empty()) {
                        fail("namespace alias requires a visible namespace");
                    }
                    if (namespaces_.count(name) ||
                        (aliases_.count(name) && aliases_[name] != target)) {
                        fail("namespace alias conflicts with an existing name");
                    }
                    if (!aliases_.count(name) && aliases_.size() == 256) {
                        fail("namespace alias limit exceeded (256)");
                    }
                    expect(";");
                    aliases_[name] = target;
                    continue;
                }
                if (aliases_.count(name)) {
                    fail("namespace alias cannot be reopened as a namespace");
                }
                if (!namespaces_.count(name) && namespaces_.size() == 256) {
                    fail("named namespace limit exceeded (256)");
                }
                if (++namespace_depth_ > 32) {
                    fail("namespace nesting limit exceeded (32)");
                }
                namespaces_.insert(name);
                expect("{");
                std::string previous = namespace_;
                namespace_ = name + "::";
                declarations(result, true);
                expect("}");
                namespace_ = previous;
                --namespace_depth_;
                continue;
            }
            if (result.functions.size() >= 256) {
                fail("function definition limit exceeded (256)");
            }
            Function function;
            function.c_linkage = function_linkage;
            function.type = scalar_type();
            function.name = namespace_ + identifier();
            if (function.name.size() > 4096) {
                fail("qualified function name limit exceeded (4096 bytes)");
            }
            if (!namespace_target(function.name).empty()) {
                fail("function conflicts with a namespace name");
            }
            expect("(");
            parameters_.clear();
            if (token_.text == "void") {
                next();
            } else if (token_.text != ")") {
                for (;;) {
                    if (parameters_.size() == 16) {
                        fail("parameter limit exceeded (16)");
                    }
                    Parameter parameter;
                    parameter.type = qualified_scalar(parameter.constant);
                    if (parameter.type == VoidType) {
                        fail("void is only valid as a sole parameter marker");
                    }
                    if (token_.text == "&") {
                        parameter.reference = true;
                        next();
                    }
                    if (parameter.constant && parameter.reference) {
                        fail("const reference parameters not yet supported");
                    }
                    if (token_.text != "," && token_.text != ")") {
                        parameter.name = identifier();
                    }
                    for (size_t i = 0; i < parameters_.size(); ++i) {
                        if (!parameter.name.empty() &&
                            parameters_[i].name == parameter.name) {
                            fail("duplicate parameter name");
                        }
                    }
                    parameters_.push_back(parameter);
                    if (token_.text != ",") { break; }
                    next();
                }
            }
            expect(")");
            function.parameters = parameters_;
            for (size_t i = 0; i < declarations_.size(); ++i) {
                const Function &previous = declarations_[i];
                if (previous.name == function.name &&
                    (previous.c_linkage || function.c_linkage)) {
                    if (!same_parameters(previous, function)) {
                        fail("C linkage overloads are not supported");
                    }
                    if (specified_linkage &&
                        previous.c_linkage != function.c_linkage) {
                        fail("conflicting language linkage");
                    }
                    function.c_linkage = previous.c_linkage;
                }
            }
            function.symbol = encoded_name(function.name) + "__";
            if (parameters_.empty()) { function.symbol += "v"; }
            for (size_t i = 0; i < parameters_.size(); ++i) {
                if (parameters_[i].reference) { function.symbol += "R"; }
                const char *codes[] = {"i", "b", "l", "j", "m", "v"};
                function.symbol += codes[parameters_[i].type];
            }
            if (function.c_linkage) {
                size_t qualifier = function.name.rfind("::");
                function.symbol = qualifier == std::string::npos ?
                    function.name : function.name.substr(qualifier + 2);
            }
            if (function.name == "main") {
                if (!parameters_.empty() || function.type != IntType) {
                    fail("supported main must have type int main()");
                }
                function.symbol = "main";
            }
            bool declared = false;
            for (size_t i = 0; i < declarations_.size(); ++i) {
                if (declarations_[i].symbol == function.symbol) {
                    if (declarations_[i].type != function.type ||
                        !same_parameters(declarations_[i], function)) {
                        fail("conflicting function signature");
                    }
                    if (declarations_[i].name == function.name) {
                        declared = true;
                    }
                }
            }
            if (!declared) {
                if (declarations_.size() == 256) {
                    fail("function declaration limit exceeded (256)");
                }
                declarations_.push_back(function);
            }
            if (token_.text == ";") {
                next();
                continue;
            }
            for (size_t i = 0; i < result.functions.size(); ++i) {
                if (result.functions[i].symbol == function.symbol) {
                    fail("duplicate function definition");
                }
            }
            bindings_.clear();
            for (size_t i = 0; i < parameters_.size(); ++i) {
                Binding binding;
                binding.name = parameters_[i].name;
                binding.type = parameters_[i].type;
                binding.reference = parameters_[i].reference;
                binding.constant = parameters_[i].constant;
                binding.symbol = "tinypp_arg_" + number(i);
                bindings_.push_back(binding);
            }
            local_index_ = statement_count_ = loop_depth_ = 0;
            return_type_ = function.type;
            function.body = block(true);
            result.functions.push_back(function);
        }
        if (nested && token_.text.empty()) {
            fail("unterminated namespace");
        }
    }


public:
    /** @brief Borrow source for one parse; initialize first lookahead. */
    explicit Parser(const PreparedSource &source)
        : source_(source.text), locations_(source.locations), offset_(0),
          line_(source.locations[0].line), column_(source.locations[0].column),
          depth_(0),
          scope_begin_(0), local_index_(0), statement_depth_(0),
          statement_count_(0), loop_depth_(0), return_type_(IntType),
          namespace_depth_(0), c_linkage_(false), linkage_scope_(false) {
        next();
    }

    /** @brief Parse a complete unit including reopened named namespaces. */
    TranslationUnit unit() {
        TranslationUnit result;
        declarations(result, false);
        result.declarations = declarations_;
        return result;
    }

};

} // namespace

/** @brief Translate source phases and build a bounded, owned scalar AST. */
TranslationUnit parse(const std::string &source) {
    PreparedSource prepared = prepare_source(source);
    return Parser(prepared).unit();
}

} // namespace tinypp
