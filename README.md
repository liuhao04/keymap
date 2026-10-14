# keymap

在任意 Mac 上一键部署我的 Karabiner 键盘映射。

## 用法（在对方 Mac 的 Terminal 里）

```sh
# 完整安装：装 Karabiner-Elements + 注入我的 profile（合并，不覆盖机主配置）
bash <(curl -fsSL https://raw.githubusercontent.com/liuhao04/keymap/main/setup.sh)

# 只做安装前检查，不修改配置、不安装或重启后台项
bash <(curl -fsSL https://raw.githubusercontent.com/liuhao04/keymap/main/setup.sh) check

# 用完还原：移除我的 profile，恢复机主原配置
bash <(curl -fsSL https://raw.githubusercontent.com/liuhao04/keymap/main/setup.sh) restore

# 轻量模式：只借用十分钟时用。零安装零权限，hidutil 直接生效，注销/重启自动失效。
# 只包含简单键位互换（退格/反斜杠/括号/标点组），复杂规则（Caps-Hyper 等）不生效。
# 注意：已在跑 Karabiner 的机器不要叠加 lite。
bash <(curl -fsSL https://raw.githubusercontent.com/liuhao04/keymap/main/setup.sh) lite
bash <(curl -fsSL https://raw.githubusercontent.com/liuhao04/keymap/main/setup.sh) lite-off
```

完整安装需要对方机器的管理员密码（装驱动），且有两步 GUI 授权必须手动点
（系统扩展批准、输入监控），脚本结束时会打印清单。

完整安装会先检查 macOS、当前图形登录会话、Xcode Command Line Tools、Python 3.8+、
现有配置及写入权限，再实际编译并通过系统 API 检查 InputStudio 和系统简体拼音均已启用。
所需资源也会提前下载；这些检查全部通过后才安装 Karabiner、写入配置和启用后台项。
缺少条件会给出提示并退出，保留现有配置和后台程序。输入法检查不会切换当前输入法。

请先安装 InputStudio，并在系统设置的输入法列表中添加 InputStudio 和简体拼音；
此脚本不会安装或启用输入法。缺少编译工具时先执行 `xcode-select --install`，完成后重试。
整条命令请以已登录用户执行，不要加 `sudo`；需要管理员权限的驱动安装会单独请求。
安装会新增 `keymap-input-source` 后台项，macOS 可能显示“App 后台活动”通知，请允许其运行。

`check` 模式只下载/缓存资源并临时编译检查，不安装 Karabiner、不改写配置、不新增或重启后台项。
下载缓存保存在 `~/Library/Caches/keymap`，再次运行时会向服务器检查资源是否更新。

`fn+Esc` 和菜单栏切换 profile 使用同一套双向联动：

- 进入 `on` → InputStudio。
- 进入 `off` → 系统简体拼音。

原生 Swift 程序用系统文件事件监听 profile 变化，通过 macOS 输入源 API 切换输入法，
由用户级 LaunchAgent 随登录启动。空闲时不轮询，运行时不依赖 Python、`macism` 或 Homebrew。
安装时需要 Xcode Command Line Tools 和 Python 3，并已安装、启用对应输入法。
每次进入 profile 只切换一次，此后手动选择其他输入法不会被改回；其他 profile 不受影响。
启动监听时也会按当前 profile 同步一次。

`select_input_source` 只能作为按键规则动作，不能单独覆盖菜单栏切换。
因此 `fn+Esc` 只负责切换 profile，输入法切换统一交给监听器，避免两条路径重复执行。

本机已有 profile、只需安装或更新监听时，在仓库目录执行：

```sh
/usr/bin/python3 karabiner-input-source.py install
# 移除监听（不改动 profile）
/usr/bin/python3 karabiner-input-source.py uninstall
```

## 更新配置（在自己的 Mac 上）

改完本机 Karabiner 配置后，在本仓库目录运行：

```sh
./push.sh
```

会从 `~/.config/karabiner/karabiner.json` 重新生成 `profiles.json`（完整 profile，
含 fn+Esc 一键启停）和 `lite.json`（hidutil 简单映射），并推送。

## 文件

- `setup.sh` — 检查、部署/还原入口（check / install / lite / lite-off / restore）
- `profiles.json` — 我的 Karabiner profile（`__TOGGLE__` 为占位符，安装时按目标机器改写）
- `lite.json` — hidutil UserKeyMapping（由 simple_modifications 生成）
- `karabiner-toggle.sh` — fn+Esc 入口（调用原生程序切换 profile）
- `karabiner-input-source.swift` — 原生 profile 监听、输入源切换及 profile 切换程序
- `karabiner-input-source.py` — 编译、安装/移除用户级 LaunchAgent，仅安装时使用
- `test-input-source.swift` — 双向联动、改名与其他 profile 隔离的回归测试
- `test-setup.py` — 安装前检查失败不修改配置、重复安装后还原的离线回归测试
- `push.sh` — 从本机配置重新生成上述两个 json 并推送
