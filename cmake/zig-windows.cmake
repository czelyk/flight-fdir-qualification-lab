# Optional Windows CMake driver, using a public existing Zig installation.
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES ZIG_EXECUTABLE)
if(NOT ZIG_EXECUTABLE)
  message(FATAL_ERROR "Set ZIG_EXECUTABLE to zig.exe")
endif()
set(CMAKE_C_COMPILER "${ZIG_EXECUTABLE}" CACHE FILEPATH "C driver")
set(CMAKE_C_COMPILER_ARG1 cc CACHE STRING "Zig C driver")
set(CMAKE_AR "${ZIG_EXECUTABLE}" CACHE FILEPATH "Zig archiver")
