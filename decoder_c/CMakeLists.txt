cmake_minimum_required(VERSION 3.14)
project(mixi_decoder C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Library
add_library(mixi_decoder STATIC src/mixi_decoder.c)
target_include_directories(mixi_decoder PUBLIC include)
target_link_libraries(mixi_decoder PRIVATE m)

# Tests
add_executable(test_decoder test/test_decoder.c)
target_link_libraries(test_decoder PRIVATE mixi_decoder m)

enable_testing()
add_test(NAME decoder_tests COMMAND test_decoder)

# Install
install(TARGETS mixi_decoder
        ARCHIVE DESTINATION lib)
install(FILES include/mixi_decoder.h
        DESTINATION include)
