cmake_minimum_required(VERSION 3.20)
project(tinypp VERSION 0.1.0 LANGUAGES C CXX)

if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "The initial backend requires Windows x64")
endif()

set(CMAKE_CXX_STANDARD 98)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
file(READ "${CMAKE_SOURCE_DIR}/tinycc/VERSION" TCC_VERSION)
string(STRIP "${TCC_VERSION}" TCC_VERSION)
file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/generated")
file(WRITE "${CMAKE_BINARY_DIR}/generated/config.h"
    "#define TCC_VERSION \"${TCC_VERSION}\"\n")

# Compile upstream sources in place; generated files stay in the build tree.
add_library(tinypp_tcc SHARED tinycc/libtcc.c)
target_include_directories(tinypp_tcc PRIVATE
    "${CMAKE_BINARY_DIR}/generated")
target_compile_definitions(tinypp_tcc PRIVATE
    TCC_TARGET_PE TCC_TARGET_X86_64 LIBTCC_AS_DLL)
add_custom_command(TARGET tinypp_tcc POST_BUILD
    COMMAND "${CMAKE_COMMAND}" -E copy_directory
        "${CMAKE_SOURCE_DIR}/tinycc/win32/include"
        "$<TARGET_FILE_DIR:tinypp_tcc>/include"
    COMMAND "${CMAKE_COMMAND}" -E copy_directory
        "${CMAKE_SOURCE_DIR}/tinycc/include"
        "$<TARGET_FILE_DIR:tinypp_tcc>/include")
add_executable(tinypp_backend tinycc/tcc.c)
target_include_directories(tinypp_backend PRIVATE
    "${CMAKE_BINARY_DIR}/generated")
target_compile_definitions(tinypp_backend PRIVATE
    TCC_TARGET_PE TCC_TARGET_X86_64 ONE_SOURCE=0)
target_link_libraries(tinypp_backend PRIVATE tinypp_tcc)

add_executable(tinypp
    src/main.cpp src/ast.cpp src/source.cpp src/frontend.cpp
    src/lowering.cpp src/backend.cpp)
target_include_directories(tinypp PRIVATE src tinycc)
target_link_libraries(tinypp PRIVATE tinypp_tcc)
target_compile_definitions(tinypp PRIVATE _CRT_SECURE_NO_WARNINGS)
if(MSVC)
    target_compile_options(tinypp PRIVATE /W4 /WX /EHsc)
endif()

find_package(Python3 3.12 REQUIRED COMPONENTS Interpreter)
add_custom_target(tinypp_runtime ALL
    COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_SOURCE_DIR}/tools/build_runtime.py"
        --backend "$<TARGET_FILE:tinypp_backend>"
        --root "${CMAKE_SOURCE_DIR}"
        --output "${CMAKE_BINARY_DIR}/runtime/$<CONFIG>"
    DEPENDS tinypp_backend
    COMMENT "Build pinned TinyCC runtime in the project build tree")
include(CTest)
if(BUILD_TESTING)
    find_program(PWSH_EXECUTABLE NAMES pwsh REQUIRED)
    string(CONCAT TINYPP_STYLE_COMMAND
        "& './wsp/tools/Test-SourceStyle.ps1' "
        "-RepositoryRoot . -SourcePath "
        "src,tools,tests,CMakeLists.txt,Doxyfile,.github")
    add_test(NAME owned-source-style COMMAND "${PWSH_EXECUTABLE}"
        -NoProfile -Command "${TINYPP_STYLE_COMMAND}")
    set_tests_properties(owned-source-style PROPERTIES
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}")
    string(CONCAT TINYPP_DMC_STYLE_COMMAND
        "& './wsp/tools/Test-SourceStyle.ps1' -RepositoryRoot . "
        "-SourcePath tools -IncludeExtension .d")
    add_test(NAME dmc-adaptation-style COMMAND "${PWSH_EXECUTABLE}"
        -NoProfile -Command "${TINYPP_DMC_STYLE_COMMAND}")
    set_tests_properties(dmc-adaptation-style PROPERTIES
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}")
    add_test(NAME planning COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_SOURCE_DIR}/tools/check-planning.py")
    add_test(NAME semantic-signature-boundary COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_SOURCE_DIR}/tests/test_semantic_signatures.py")
    add_test(NAME semantic-body-boundary COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_SOURCE_DIR}/tests/test_semantic_ir.py")
    add_test(NAME compiler-foundation COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_SOURCE_DIR}/tests/run_foundation.py"
        --compiler "$<TARGET_FILE:tinypp>"
        --backend "$<TARGET_FILE:tinypp_backend>"
        --root "${CMAKE_SOURCE_DIR}"
        --runtime "${CMAKE_BINARY_DIR}/runtime/$<CONFIG>"
        --configuration "$<CONFIG>"
        --output "${CMAKE_BINARY_DIR}/evidence/$<CONFIG>")
endif()
