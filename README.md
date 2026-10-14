# keymap

在任意 Mac 上一键部署我的 Karabiner 键盘映射。

## 用法（在对方 Mac 的 Terminal 里）

```sh
# 完整安装：装 Karabiner-Elements + 注入我的 profile（合并，不覆盖机主配置）
bash <(curl -fsSL https://raw.githubusercontent.com/liuhao04/keymap/main/setup.sh)

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

`fn+Esc` 切到启用档（`on`）时自动切换到 InputStudio，切到停用档（`off`）时
切回系统简体拼音；输入法联动使用 macOS 原生输入源 API，需要已安装、启用对应输入法。
安装时用 Xcode Command Line Tools 编译小型切换工具，运行时不依赖 `macism`。
完整安装还会启用菜单栏切换监听：手动选择 `on` 同样会切到 InputStudio。
仅在进入启用档时切换一次，此后手动选择其他输入法不会被改回；登录后也会自动启动监听。

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

- `setup.sh` — 部署/还原入口（install / lite / lite-off / restore）
- `profiles.json` — 我的 Karabiner profile（`__TOGGLE__` 为占位符，安装时按目标机器改写）
- `lite.json` — hidutil UserKeyMapping（由 simple_modifications 生成）
- `karabiner-toggle.sh` — fn+Esc 启停脚本（profile 名免疫，按规则数识别启停档）
- `karabiner-input-source.py` — 菜单栏 profile 变化监听及用户级 LaunchAgent 安装/移除
- `select-input-source.swift` — 原生输入源切换工具（安装时编译）
- `push.sh` — 从本机配置重新生成上述两个 json 并推送
