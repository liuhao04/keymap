#!/bin/sh
# fn+Esc 一键启停 Karabiner：在「启用」和「停用」两个 profile 间切换。
# profile 名不写死：每次从 karabiner.json 现场读——规则最少的 profile 认作「停用」档，
# 另一个认作「启用」档，所以在 Karabiner 里随意改名不影响本脚本。
# Karabiner 进程与虚拟驱动保持运行；状态看菜单栏 profile 名（show_profile_name_in_menu_bar）。
CLI='/Library/Application Support/org.pqrs/Karabiner-Elements/bin/karabiner_cli'
SELECTOR="$(dirname "$0")/keymap-select-input-source"
# 兼容尚未安装原生切换工具的旧部署。
[ -x "$SELECTOR" ] || SELECTOR=/opt/homebrew/bin/macism

names="$(/usr/bin/python3 - <<'PY'
import json, os
d = json.load(open(os.path.expanduser('~/.config/karabiner/karabiner.json')))
profs = d['profiles']
def weight(p):
    return (len(p.get('complex_modifications', {}).get('rules', []))
            + len(p.get('simple_modifications', []))
            + len(p.get('fn_function_keys', [])))
off = min(profs, key=weight)
on = max(profs, key=weight)
print(off['name'])
print(on['name'])
PY
)"
OFF="$(printf '%s\n' "$names" | sed -n 1p)"
ON="$(printf '%s\n' "$names" | sed -n 2p)"
[ -n "$OFF" ] && [ -n "$ON" ] || exit 1

cur="$("$CLI" --show-current-profile-name)"
if [ "$cur" = "$OFF" ]; then
  "$CLI" --select-profile "$ON" || exit 1
  # 切到启用档时，输入法同步切到 InputStudio。
  "$SELECTOR" com.liuhao.inputmethod.InputStudio.Wubi
else
  "$CLI" --select-profile "$OFF" || exit 1
  # 切到停用档时，输入法同步退回系统自带简体拼音。
  "$SELECTOR" com.apple.inputmethod.SCIM.ITABC
fi
