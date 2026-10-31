/** @file main.cpp
 * @brief Strict scalar-subset driver; unsupported C++ never falls through.
 */
#include "frontend.hpp"

#include <cstdio>
#include <fstream>
#include <iostream>

/** @brief Validate arguments, parse an owned source, and emit its object.
 * @param argc Argument count including executable name.
 * @param argv OS-provided argument vector; borrowed for this invocation.
 * @return Zero on successful translation; nonzero for every failure.
 * @note Writes the requested output only after successful front-end analysis.
 */
static int run_driver(int argc, char **argv) {
    std::string input, output, runtime;
    std::vector<std::string> inputs;
    bool compile = false;
    for (int i = 1; i < argc; ++i) {
        std::string argument(argv[i]);
        if (argument == "--version") {
            std::cout << "tinypp 0.1.0 experimental scalar C++98 subset\n";
            return 0;
        } else if (argument == "--help") {
            std::cout << "usage: tinypp -std=c++98 -c input.cpp -o output.o\n"
                      << "       tinypp --runtime DIR input.cpp... -o app.exe\n"
                      << "Subset: scalar functions, overloads and control "
                      << "flow.\nExisting output files are preserved.\n";
            return 0;
        } else if (argument == "-std=c++98") {
            continue;
        } else if (argument == "-c") {
            compile = true;
        } else if (argument == "-o" && i + 1 < argc) {
            output = argv[++i];
        } else if (argument == "--runtime" && i + 1 < argc) {
            runtime = argv[++i];
        } else if (!argument.empty() && argument[0] == '-') {
            std::cerr << "tinypp: error: unsupported option " << argument
                      << "\n";
            return 2;
        } else {
            if (inputs.size() == 32) {
                std::cerr << "tinypp: error: source file limit exceeded (32)\n";
                return 2;
            }
            inputs.push_back(argument);
        }
    }
    if (inputs.empty() || output.empty() || (!compile && runtime.empty()) ||
        (compile && inputs.size() != 1)) {
        std::cerr << "tinypp: error: specify source, distinct -o output and "
                  << "either -c or --runtime DIR\n";
        return 2;
    }
    for (size_t i = 0; i < inputs.size(); ++i) {
        if (inputs[i] == output) {
            std::cerr << "tinypp: error: output must differ from each source\n";
            return 2;
        }
    }
    try {
        std::vector<tinypp::TranslationUnit> units;
        units.reserve(inputs.size());
        size_t total = 0, declarations = 0;
        for (size_t i = 0; i < inputs.size(); ++i) {
            input = inputs[i];
            std::ifstream stream(input.c_str(), std::ios::binary);
            if (!stream) {
                std::cerr << "tinypp: error: cannot open " << input << "\n";
                return 1;
            }
            std::string source;
            char bytes[4096];
            while (stream.read(bytes, sizeof bytes) || stream.gcount()) {
                source.append(bytes, static_cast<size_t>(stream.gcount()));
                if (source.size() > 1048576U) {
                    throw tinypp::Diagnostic("source exceeds 1 MiB",
                                             tinypp::Location());
                }
            }
            if (!stream.eof()) {
                throw std::runtime_error("source read failed");
            }
            total += source.size();
            if (total > 16777216U) {
                throw std::runtime_error("aggregate sources exceed 16 MiB");
            }
            units.push_back(tinypp::parse(source));
            declarations += units.back().declarations.size();
            if (declarations > 1024) {
                throw std::runtime_error("aggregate signature limit (1024)");
            }
        }
        return tinypp::emit_artifact(units, output, compile, runtime) ? 0 : 1;
    } catch (const tinypp::Diagnostic &error) {
        std::cerr << input << ":" << error.line << ":" << error.column
                  << ": error: " << error.what() << "\n";
    } catch (const std::exception &error) {
        std::cerr << "tinypp: error: " << error.what() << "\n";
    }
    return 1;
}

/** @brief Contain all C++ exceptions, including argument allocation failures.
 * @param argc OS-provided argument count.
 * @param argv Borrowed OS argument strings.
 * @return Driver status, or one if an unexpected exception escaped it.
 */
int main(int argc, char **argv) {
    try {
        return run_driver(argc, argv);
    } catch (...) {
        // Best-effort diagnostic; the failure exit is already unconditional.
        (void)std::fputs("tinypp: error: driver resource failure\n", stderr);
        return 1;
    }
}
