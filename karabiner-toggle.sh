#!/bin/sh
# fn+Esc 只切换 profile；输入法统一由原生监听器按 profile 变化处理。
exec "$(dirname "$0")/keymap-input-source" --toggle
