/** @file backend.cpp
 * @brief Scalar lowering feasibility adapter over pinned libtcc.
 * This adapter owns its TCCState and releases it on every ordinary exit.
 */
#include "frontend.hpp"
#include "libtcc.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <iostream>

namespace tinypp {

/** @brief Emit to a temporary file and publish only into a new destination. */
bool emit_artifact(const std::vector<TranslationUnit> &units,
                   const std::string &output,
                   bool object, const std::string &runtime) {
    if (units.empty() || units.size() > 32 || (object && units.size() != 1)) {
        std::cerr << "tinypp: error: invalid translation-unit count\n";
        return false;
    }
    std::vector<std::string> lowered;
    lowered.reserve(units.size());
    size_t total = 0;
    for (size_t i = 0; i < units.size(); ++i) {
        lowered.push_back(lower_scalar(units[i]));
        total += lowered.back().size();
        if (total > 16777216U) {
            std::cerr << "tinypp: error: lowering exceeds 16 MiB\n";
            return false;
        }
    }
    char absolute[MAX_PATH], temporary[MAX_PATH];
    DWORD length = GetFullPathNameA(output.c_str(), MAX_PATH, absolute, 0);
    if (!length || length >= MAX_PATH) {
        std::cerr << "tinypp: error: output path is unavailable or too long\n";
        return false;
    }
    std::string directory(absolute);
    directory.erase(directory.find_last_of("\\/") + 1);
    if (!GetTempFileNameA(directory.c_str(), "tpp", 0, temporary)) {
        std::cerr << "tinypp: error: cannot create temporary output\n";
        return false;
    }
    TCCState *state = tcc_new();
    if (!state) {
        DeleteFileA(temporary);
        return false;
    }
    if (!runtime.empty()) {
        tcc_set_lib_path(state, runtime.c_str());
    }
    int format = object ? TCC_OUTPUT_OBJ : TCC_OUTPUT_EXE;
    bool success = tcc_set_output_type(state, format) >= 0;
    for (size_t i = 0; success && i < lowered.size(); ++i) {
        success = tcc_compile_string(state, lowered[i].c_str()) >= 0;
    }
    if (success) { success = tcc_output_file(state, temporary) >= 0; }
    tcc_delete(state);
    if (success && !MoveFileExA(temporary, absolute, MOVEFILE_WRITE_THROUGH)) {
        std::cerr << "tinypp: error: output exists or cannot be published\n";
        success = false;
    }
    DeleteFileA(temporary);
    return success;
}

} // namespace tinypp
