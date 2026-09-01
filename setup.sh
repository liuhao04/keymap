#!/bin/bash
# 在任意 Mac 上一键部署我的键盘映射。
#
#   完整安装（装 Karabiner + 注入我的 profile）：
#     bash <(curl -fsSL https://raw.githubusercontent.com/liuhao04/keymap/main/setup.sh)
#   轻量模式（不装任何东西，hidutil 直接生效，注销/重启自动失效）：
#     bash <(curl -fsSL .../setup.sh) lite
#   撤销轻量模式：       ... lite-off
#   还原（移除我的 profile，恢复机主原配置）： ... restore
#
# 设计要点：
#   - 合并而非覆盖：机主已有的 Karabiner profile 原样保留，只追加我的，restore 可完整退场
#   - 改动 karabiner.json 前必做时间戳备份
# 测试用环境变量：KEYMAP_CONFIG_DIR / KEYMAP_BIN_DIR / KEYMAP_SKIP_APP=1
set -euo pipefail

RAW="https://raw.githubusercontent.com/liuhao04/keymap/main"
CFG_DIR="${KEYMAP_CONFIG_DIR:-$HOME/.config/karabiner}"
CFG="$CFG_DIR/karabiner.json"
STATE="$CFG_DIR/.keymap-state.json"
BIN_DIR="${KEYMAP_BIN_DIR:-$HOME/.local/bin}"
TOGGLE="$BIN_DIR/karabiner-toggle.sh"
MODE="${1:-install}"

# 取资源：同目录有（本地 checkout / 离线包）就用本地，否则从 GitHub 拉
fetch() { # $1=文件名 → 输出本地路径
  local here; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
  if [ -n "$here" ] && [ -f "$here/$1" ]; then echo "$here/$1"; return; fi
  local tmp; tmp="$(mktemp)"
  curl -fsSL "$RAW/$1" -o "$tmp" || { echo "下载 $1 失败" >&2; exit 1; }
  echo "$tmp"
}

case "$MODE" in
lite)
  echo "应用轻量映射（hidutil，注销/重启自动失效；已装 Karabiner 的机器请勿叠加使用）..."
  /usr/bin/hidutil property --set "{\"UserKeyMapping\": $(cat "$(fetch lite.json)")}" >/dev/null
  echo "已生效。撤销：重新运行并加参数 lite-off，或注销/重启"
  exit 0 ;;
lite-off)
  /usr/bin/hidutil property --set '{"UserKeyMapping":[]}' >/dev/null
  echo "轻量映射已清除"
  exit 0 ;;
restore)
  [ -f "$STATE" ] || { echo "没有找到安装记录（$STATE），无需还原" >&2; exit 1; }
  cp "$CFG" "$CFG.bak-$(date +%Y%m%d-%H%M%S)"
  CFG="$CFG" STATE="$STATE" python3 - <<'PY'
import json, os
cfg, state_p = os.environ['CFG'], os.environ['STATE']
d = json.load(open(cfg))
st = json.load(open(state_p))
d['profiles'] = [p for p in d['profiles'] if p['name'] not in st['installed']]
if not d['profiles']:
    d['profiles'] = [{'name': 'Default profile', 'selected': True}]
else:
    names = [p['name'] for p in d['profiles']]
    want = st.get('previous_selected')
    target = want if want in names else names[0]
    for p in d['profiles']:
        p['selected'] = (p['name'] == target)
json.dump(d, open(cfg, 'w'), ensure_ascii=False, indent=4)
os.remove(state_p)
print('已移除 profile:', ', '.join(st['installed']))
PY
  rm -f "$TOGGLE"
  echo "已还原机主配置。如需彻底卸载 Karabiner：打开其设置界面 → Misc → Uninstall"
  exit 0 ;;
install) ;;
*) echo "用法: setup.sh [install|lite|lite-off|restore]" >&2; exit 1 ;;
esac

# ---------- install ----------
if [ "${KEYMAP_SKIP_APP:-0}" != "1" ]; then
  [ "$(uname)" = "Darwin" ] || { echo "只支持 macOS" >&2; exit 1; }
  if [ ! -d "/Applications/Karabiner-Elements.app" ]; then
    echo "安装 Karabiner-Elements（需要管理员密码）..."
    if command -v brew >/dev/null 2>&1; then
      brew install --cask karabiner-elements
    else
      DMG_URL="$(curl -fsSL https://api.github.com/repos/pqrs-org/Karabiner-Elements/releases/latest \
        | /usr/bin/python3 -c 'import json,sys; print(next(a["browser_download_url"] for a in json.load(sys.stdin)["assets"] if a["name"].endswith(".dmg")))')"
      TMPDMG="$(mktemp -d)/karabiner.dmg"
      curl -fL "$DMG_URL" -o "$TMPDMG"
      MNT="$(hdiutil attach -nobrowse "$TMPDMG" | awk -F'\t' 'END{print $NF}')"
      sudo installer -pkg "$MNT"/*.pkg -target /
      hdiutil detach "$MNT" >/dev/null
    fi
  else
    echo "Karabiner-Elements 已安装，跳过"
  fi
fi

mkdir -p "$CFG_DIR" "$BIN_DIR"
[ -f "$CFG" ] && cp "$CFG" "$CFG.bak-$(date +%Y%m%d-%H%M%S)"

install -m 755 "$(fetch karabiner-toggle.sh)" "$TOGGLE"

CFG="$CFG" STATE="$STATE" TOGGLE="$TOGGLE" PROFILES="$(fetch profiles.json)" python3 - <<'PY'
import json, os
cfg, state_p = os.environ['CFG'], os.environ['STATE']
incoming = json.load(open(os.environ['PROFILES']))

def fill(obj):
    if isinstance(obj, dict): return {k: fill(v) for k, v in obj.items()}
    if isinstance(obj, list): return [fill(x) for x in obj]
    if obj == '__TOGGLE__': return os.environ['TOGGLE']
    return obj

incoming = fill(incoming)
names = [p['name'] for p in incoming]
d = json.load(open(cfg)) if os.path.exists(cfg) else {'profiles': []}

prev = next((p['name'] for p in d['profiles']
             if p.get('selected') and p['name'] not in names), None)
d['profiles'] = [p for p in d['profiles'] if p['name'] not in names] + incoming

def weight(p):
    return (len(p.get('complex_modifications', {}).get('rules', []))
            + len(p.get('simple_modifications', [])))
main = max(incoming, key=weight)['name']
for p in d['profiles']:
    p['selected'] = (p['name'] == main)
d.setdefault('global', {})['show_profile_name_in_menu_bar'] = True

json.dump(d, open(cfg, 'w'), ensure_ascii=False, indent=4)
st = {'installed': names, 'previous_selected': prev}
json.dump(st, open(state_p, 'w'), ensure_ascii=False)
print(f'已注入 profile: {", ".join(names)}（选中 {main}）'
      + (f'；机主原 profile {prev} 已保留' if prev else ''))
PY

if [ "${KEYMAP_SKIP_APP:-0}" != "1" ]; then
  open -a Karabiner-Elements || true
  cat <<'EOF'

还差两步手动授权（macOS 强制，脚本无法代点）：
  1. 系统设置 → 隐私与安全性 → 允许 Karabiner 的系统扩展（首次安装会弹提示）
  2. 系统设置 → 隐私与安全性 → 输入监控 → 勾选 karabiner_grabber
完成后键位立即生效。fn+Esc 一键启停；用完这台 Mac 请运行本脚本加参数 restore 还原。
EOF
fi
