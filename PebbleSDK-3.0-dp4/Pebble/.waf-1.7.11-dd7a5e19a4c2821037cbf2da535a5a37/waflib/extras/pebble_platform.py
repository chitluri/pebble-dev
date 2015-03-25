#! /usr/bin/env python
# encoding: utf-8
# WARNING! Do not edit! http://waf.googlecode.com/git/docs/wafbook/single.html#_obtaining_the_waf_file

basalt_platform={"NAME":"basalt","MAX_APP_BINARY_SIZE":0x10000,"MAX_APP_MEMORY_SIZE":0x10000,"MAX_WORKER_MEMORY_SIZE":0x2800,"DEFINES":["PBL_PLATFORM_BASALT","PBL_COLOR"],"BUILD_DIR":"basalt","PBW_BIN_DIR":"basalt"}
aplite_platform={"NAME":"aplite","MAX_APP_BINARY_SIZE":0x10000,"MAX_APP_MEMORY_SIZE":0x6000,"MAX_WORKER_MEMORY_SIZE":0x2800,"DEFINES":["PBL_PLATFORM_APLITE","PBL_BW"],"BUILD_DIR":"aplite","PBW_BIN_DIR":""}
pebble_platforms={"basalt":basalt_platform,"aplite":aplite_platform,}
