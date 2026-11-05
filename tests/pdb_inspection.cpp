/** @file pdb_inspection.cpp
 * @brief Optional DIA fixture for a named function and its source lines.
 * Build with the host DIA SDK and diaguids/ole32/oleaut32/advapi32 libraries.
 * Arguments: DIA DLL, PDB, optional exact function name (default: answer).
 * This fixture does not qualify stepping, aggregate fields or a debugger.
 */
#include <windows.h>
#include <dia2.h>
#include <diacreate.h>
#include <stdio.h>

/** @brief Own one COM reference without registration or shared ownership. */
template<class Interface> class ComReference {
    Interface *value_; ///< Acquired reference, or null before acquisition.
    ComReference(const ComReference &); ///< Copying would duplicate ownership.
    ComReference &operator=(const ComReference &); ///< Copying is disabled.
public:
    /** @brief Start without a reference. */
    ComReference() : value_(0) {}
    /** @brief Release a reference on every exit path. */
    ~ComReference() { if (value_) { value_->Release(); } }
    /** @brief Address for one COM output operation on an empty owner. */
    Interface **output() { return &value_; }
    /** @brief Borrow the acquired interface. */
    Interface *get() const { return value_; }
    /** @brief Access the acquired interface without transferring ownership. */
    Interface *operator->() const { return value_; }
};

/** @brief Own a BSTR returned by DIA. */
class DiaString {
    BSTR value_; ///< Owned string, or null before acquisition.
    DiaString(const DiaString &); ///< Copying is disabled.
    DiaString &operator=(const DiaString &); ///< Copying is disabled.
public:
    /** @brief Start with an empty output value. */
    DiaString() : value_(0) {}
    /** @brief Release the string, including on an inspection failure. */
    ~DiaString() { SysFreeString(value_); }
    /** @brief Address for one DIA string output operation. */
    BSTR *output() { return &value_; }
    /** @brief Borrow a printable string without transferring ownership. */
    const wchar_t *get() const { return value_ ? value_ : L""; }
};

/** @brief Balance COM initialization on all successful initialization paths. */
class Apartment {
    HRESULT result_; ///< Initialization result, including S_FALSE.
public:
    /** @brief Initialize this inspection thread. */
    Apartment() : result_(CoInitialize(0)) {}
    /** @brief Release exactly the acquired initialization reference. */
    ~Apartment() { if (SUCCEEDED(result_)) { CoUninitialize(); } }
    /** @brief Whether COM is available for this process. */
    bool ready() const { return SUCCEEDED(result_); }
};

/** @brief Print source lines for a borrowed function/session pair. */
static unsigned inspect_lines(IDiaSession *session, IDiaSymbol *function) {
    DWORD rva = 0;
    ULONGLONG length = 0;
    DiaString name;
    if (FAILED(function->get_name(name.output())) ||
        FAILED(function->get_relativeVirtualAddress(&rva)) ||
        FAILED(function->get_length(&length)) || !length ||
        length > 0xffffffffUL) { return 0; }
    wprintf(L"function %ls rva %08lX\n", name.get(), rva);
    ComReference<IDiaEnumLineNumbers> lines;
    if (FAILED(session->findLinesByRVA(rva, static_cast<DWORD>(length),
                                     lines.output())) || !lines.get()) {
        return 0;
    }
    unsigned count = 0;
    for (;;) {
        ULONG fetched = 0;
        ComReference<IDiaLineNumber> line;
        if (lines->Next(1, line.output(), &fetched) != S_OK || !fetched) {
            break;
        }
        DWORD number = 0;
        ComReference<IDiaSourceFile> source;
        DiaString filename;
        if (SUCCEEDED(line->get_lineNumber(&number)) && number &&
            SUCCEEDED(line->get_sourceFile(source.output())) && source.get() &&
            SUCCEEDED(source->get_fileName(filename.output())) &&
            *filename.get()) {
            wprintf(L"line %lu file %ls\n", number, filename.get());
            ++count;
        }
    }
    return count;
}

/** @brief Inspect a local PDB through an explicitly supplied DIA DLL. */
int wmain(int argc, wchar_t **argv) {
    if (argc != 3 && argc != 4) {
        fprintf(stderr, "usage: inspect-pdb DIA-DLL PDB [FUNCTION]\n");
        return 2;
    }
    Apartment apartment;
    if (!apartment.ready()) { return 3; }
    ComReference<IDiaDataSource> data;
    HRESULT result = NoRegCoCreate(argv[1], CLSID_DiaSource,
        IID_IDiaDataSource, reinterpret_cast<void **>(data.output()));
    if (FAILED(result) || !data.get()) { return 4; }
    if (FAILED(data->loadDataFromPdb(argv[2]))) { return 5; }
    ComReference<IDiaSession> session;
    if (FAILED(data->openSession(session.output())) || !session.get()) {
        return 6;
    }
    ComReference<IDiaSymbol> global;
    if (FAILED(session->get_globalScope(global.output())) || !global.get()) {
        return 7;
    }
    ComReference<IDiaEnumSymbols> functions;
    const wchar_t *name = argc == 4 ? argv[3] : L"answer";
    if (FAILED(global->findChildren(SymTagFunction, name, nsCaseSensitive,
                                   functions.output())) || !functions.get()) {
        return 8;
    }
    unsigned count = 0;
    for (;;) {
        ULONG fetched = 0;
        ComReference<IDiaSymbol> function;
        if (functions->Next(1, function.output(), &fetched) != S_OK ||
            !fetched) { break; }
        count += inspect_lines(session.get(), function.get());
    }
    printf("matching source line records: %u\n", count);
    return count ? 0 : 9;
}
