#!/bin/bash
# 在自己的 Mac 上改完 Karabiner 配置后运行本脚本：
# 从本机 karabiner.json 重新生成 profiles.json / lite.json 并推送到 GitHub。
# 环境变量（仅测试用）：KEYMAP_SRC_CONFIG 覆盖源配置路径；KEYMAP_NO_GIT=1 只生成不提交。
set -euo pipefail
cd "$(dirname "$0")"

SRC="${KEYMAP_SRC_CONFIG:-$HOME/.config/karabiner/karabiner.json}"
[ -f "$SRC" ] || { echo "找不到源配置: $SRC" >&2; exit 1; }

SRC="$SRC" python3 - <<'PY'
import json, os, re, sys

src = os.environ['SRC']
d = json.load(open(src))
profiles = d['profiles']

# shell_command 里指向 karabiner-toggle.sh 的绝对路径换成占位符，安装时按对方机器改写
def scrub(obj):
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, str) and obj.endswith('/karabiner-toggle.sh'):
        return '__TOGGLE__'
    return obj

profiles = scrub(profiles)

out = json.dumps(profiles, ensure_ascii=False, indent=2)
# PII 门：占位后不允许残留任何用户路径/用户名
for bad in ('/Users/', os.path.expanduser('~').split('/')[-1]):
    if bad in out:
        sys.exit(f'PII 检查失败：profiles.json 含 {bad!r}，中止')
open('profiles.json', 'w').write(out + '\n')

# lite.json：把规则最多的 profile 的 simple_modifications 转成 hidutil UserKeyMapping
USAGE = {  # HID keyboard/keypad page (0x07)
    'a':0x04,'b':0x05,'c':0x06,'d':0x07,'e':0x08,'f':0x09,'g':0x0A,'h':0x0B,
    'i':0x0C,'j':0x0D,'k':0x0E,'l':0x0F,'m':0x10,'n':0x11,'o':0x12,'p':0x13,
    'q':0x14,'r':0x15,'s':0x16,'t':0x17,'u':0x18,'v':0x19,'w':0x1A,'x':0x1B,
    'y':0x1C,'z':0x1D,
    'return_or_enter':0x28,'escape':0x29,'delete_or_backspace':0x2A,'tab':0x2B,
    'spacebar':0x2C,'hyphen':0x2D,'equal_sign':0x2E,'open_bracket':0x2F,
    'close_bracket':0x30,'backslash':0x31,'semicolon':0x33,'quote':0x34,
    'grave_accent_and_tilde':0x35,'comma':0x36,'period':0x37,'slash':0x38,
    'caps_lock':0x39,
}
BASE = 0x700000000
main = max(json.load(open(src))['profiles'],
           key=lambda p: len(p.get('complex_modifications', {}).get('rules', [])))
mapping, skipped = [], []
for sm in main.get('simple_modifications', []):
    f = sm.get('from', {}).get('key_code')
    tos = sm.get('to', [])
    t = tos[0].get('key_code') if len(tos) == 1 else None
    if f in USAGE and t in USAGE:
        mapping.append({'HIDKeyboardModifierMappingSrc': BASE + USAGE[f],
                        'HIDKeyboardModifierMappingDst': BASE + USAGE[t]})
    else:
        skipped.append(sm)
open('lite.json', 'w').write(json.dumps(mapping, indent=2) + '\n')
print(f'profiles.json: {len(profiles)} 个 profile；lite.json: {len(mapping)} 条映射', end='')
print(f'（跳过 {len(skipped)} 条无法转换）' if skipped else '')
PY

if [ "${KEYMAP_NO_GIT:-0}" = "1" ]; then
  echo '(KEYMAP_NO_GIT=1，跳过 git 提交)'
  exit 0
fi

if git diff --quiet -- profiles.json lite.json 2>/dev/null && \
   git ls-files --error-unmatch profiles.json >/dev/null 2>&1; then
  echo '配置无变化，无需推送'
else
  git add profiles.json lite.json
  git commit -m "sync keymap $(date +%Y-%m-%d)"
  git push
  echo '已推送最新配置'
fi
