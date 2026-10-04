# PlayAtlas Godot 静态验证记录

验证日期：2026-10-04（Asia/Shanghai）  
验证范围：`playatlas_core/` 中的 Godot 项目文件、场景引用、导出配置模板。  
验证方式：文本/JSON 路径检查与人工静态审阅；当前工作区没有 Godot 编辑器、Godot CLI、Windows 主机或 Android 设备。

## 已完成的静态检查

| 检查项 | 结果 | 证据 |
|---|---|---|
| `project.godot` 存在 | 已检查 | `project.godot` |
| 主场景路径存在 | 已检查 | `run/main_scene=res://ui/CoreShell.tscn`，文件存在 |
| 主场景外部脚本存在 | 已检查 | `res://scripts/ui/core_shell.gd`，文件存在 |
| 9 个 autoload 脚本路径存在 | 已检查 | `project.godot` 中的全部 `res://scripts/core/*.gd` 均可定位 |
| `GameRegistry` 目录路径存在 | 已检查 | `res://data/games/GAME_CATALOG.json`，JSON 可读取 |
| 目录条目结构 | 已检查 | 36 个条目，ID 唯一；当前状态字段均为 `in_development` |
| `CoreShell.tscn` 外部资源 | 已检查 | `ExtResource("1_shell")` 指向现有脚本 |
| 导出配置模板 | 已添加 | Windows x86_64 与 Android arm64 模板，无密钥 |
| 第三方/收费服务依赖 | 未发现 | 静态扫描未发现 API key、token 或远程游戏服务配置 |

## 不能由本次静态检查证明的项目

以下项目保持“未测试/待验证”，不能写成通过：

- GDScript 是否能在目标 Godot 4.7.x 编辑器中无错误解析；本环境没有 Godot
  二进制，无法运行 `--headless --path . --editor --quit`。
- 主场景启动、窗口缩放、DPI、音频总线和实际输入映射。
- Windows `.exe` 导出、启动、真实交互、性能或截图。
- Android SDK/JDK 配置、APK 导出、安装、触屏、系统返回、切后台与恢复。
- 六款样板的 Godot 画面、教程、结算、存档恢复与音效闭环。
- 36 款游戏的真实可玩数量；目录元数据不等于实现。

## 静态审阅发现的集成缺口

这些不是“导出通过”结论，而是源码层可直接看到、需要后续接线的事项：

1. `GameRegistry.register_module()` 有接口，但当前 Godot 脚本中没有发现任何
   `register_module()` 调用。因而 `AppCore.open_game()` 在没有外部注册工厂时会
   返回失败；目录按钮目前只发出 `game_selected` 信号，没有连接到打开游戏的
   场景路由。
2. `InputService` 会创建语义动作名，但 `project.godot` 没有默认键盘/手柄事件；
   目标项目需要在输入层或项目设置中补齐可验证的默认映射。
3. `AudioService` 依赖名为 `SFX` 的音频总线，但项目配置中尚未声明该总线；
   需要在目标 Godot 版本中补齐总线并进行听感测试。
4. `PackageManager` 已有路径穿越和体积限制检查，但升级覆盖、备份/回滚与
   未知第三方脚本隔离仍需在真实安装流程中验收。

## 导出模板使用说明

`export_presets.cfg` 只提供可在 Godot 编辑器中继续校准的配置模板：

- Windows：`builds/PlayAtlas-Windows.exe`，x86_64，未启用代码签名。
- Android：`builds/PlayAtlas-Android.apk`，arm64-v8a，离线权限关闭；发布签名
  密钥留空，不应把密钥写入仓库。
- 由于没有安装导出模板、Android SDK/JDK 和目标设备，本文件不代表已经生成
  `.exe` 或 `.apk`。第一次导出前必须在 Godot 的 Export 窗口确认选项并由目标
  机器执行真实构建。

## 建议的下一步验证命令

在安装了与项目兼容的 Godot 4.x 的机器上执行：

```text
godot --headless --path playatlas_core --editor --quit
godot --headless --path playatlas_core --export-release "Windows Desktop" builds/PlayAtlas-Windows.exe
godot --headless --path playatlas_core --export-debug "Android (template)" builds/PlayAtlas-Android.apk
```

上述命令仅是验证入口；在没有对应导出模板、SDK、JDK 或签名设置时应保留真实
错误，不得把配置文件存在误报为构建成功。
