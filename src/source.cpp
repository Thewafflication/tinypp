/** @file source.cpp
 * @brief Translate source characters and splice lines before tokenization.
 * Location maps retain physical positions even when lines/tokens are joined.
 */
#include "frontend.hpp"

namespace tinypp {

/** @brief Translate source characters, line endings and logical lines. */
PreparedSource prepare_source(const std::string &source) {
    if (source.size() > 1048576U) {
        throw Diagnostic("source size limit exceeded (1 MiB)", Location());
    }
    PreparedSource phase_one;
    phase_one.text.reserve(source.size() + 1);
    phase_one.locations.reserve(source.size() + 2);
    Location location;
    const std::string endings = "=/'()!<>-";
    const std::string replacements = "#\\^[]|{}~";
    for (size_t i = 0; i < source.size();) {
        char value = source[i];
        if (value == '\0' || static_cast<unsigned char>(value) >= 128) {
            throw Diagnostic("unsupported source byte", location);
        }
        Location original = location;
        size_t width = 1;
        if (source.compare(i, 2, "??") == 0 && i + 2 < source.size()) {
            size_t index = endings.find(source[i + 2]);
            if (index != std::string::npos) {
                value = replacements[index];
                width = 3;
            }
        }
        if (value == '\r') {
            if (i + 1 == source.size() || source[i + 1] != '\n') {
                throw Diagnostic("standalone CR is not supported", location);
            }
            value = '\n';
            width = 2;
        }
        phase_one.text += value;
        phase_one.locations.push_back(original);
        if (value == '\n') {
            ++location.line;
            location.column = 1;
        } else {
            location.column += static_cast<unsigned>(width);
        }
        i += width;
    }
    if (!phase_one.text.empty() && phase_one.text[phase_one.text.size()-1]
        != '\n') {
        phase_one.text += '\n';
        phase_one.locations.push_back(location);
    }
    phase_one.locations.push_back(location);

    PreparedSource result;
    result.text.reserve(phase_one.text.size());
    result.locations.reserve(phase_one.locations.size());
    for (size_t i = 0; i < phase_one.text.size(); ++i) {
        if (phase_one.text[i] == '\\' && i + 1 < phase_one.text.size() &&
            phase_one.text[i + 1] == '\n') {
            ++i;
            continue;
        }
        result.text += phase_one.text[i];
        result.locations.push_back(phase_one.locations[i]);
    }
    result.locations.push_back(location);
    return result;
}

} // namespace tinypp
