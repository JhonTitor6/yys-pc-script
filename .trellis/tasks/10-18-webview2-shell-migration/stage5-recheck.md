# 阶段 5 修复、重打包与复验

日期：2026-10-19，Asia/Shanghai。基线：`af92eeea9cddfda7dbdbbc561840fab394f7b093`。

## 结论

F1/F2/F3 已修复，已重新生成 NSIS 与单文件便携包，本轮本机可执行复验通过。D1 按用户明确决定更新契约：HTTP 未知 Origin 不额外拒绝，仍必须通过 token 鉴权，不返回 CORS 允许头；WebSocket 校验不变。

**阶段 5 保持部分验证，不宣称完整发布矩阵通过。** 用户明确 Win10 和混合 DPI 暂不验；整机真实 Runtime 缺失仍无独立测试环境。物理拔屏、旧 Electron 原位升级/回退、全部托盘操作与完整裁剪 UI 等原报告未覆盖项不因此自动转为通过。

未提交、未推送、未归档。未修改并行的 OCR/controller/daily_collect 等业务代码；发行物使用隔离源码快照，未把这些未提交业务修改混入新包。

## 修复与回归

| 问题 | 修复 | 复验 |
|---|---|---|
| F1 迁移可能覆盖并发目标 | 每次创建独立同目录副本；SQLite backup/quick_check 后关闭连接；`os.link` 原子、不覆盖发布；finally 只清理本次副本 | 两迁移者竞争时胜者保留、后者抛出 FileExistsError；副本路径不同；损坏源不留下目标或打开的副本 |
| F2 便携缓存读到旧/不完整载荷 | 取消载荷缓存，每次完整解到独立 `$PLUGINSDIR/runtime`；ExecWait 后切离 cwd，交 NSIS 清理 | 最小 NSIS 回归验证同版本更新、不同 cwd 和重复启动；真实完整单文件包两次运行使用不同目录，退出后均清理，永久库保留 |
| F3 日志记录 token | Uvicorn 两个输出 handler 均加入脱敏过滤器；保留访问日志参数结构 | 单测覆盖 AccessFormatter、WS 直接消息、元组和字典；真实新后端检查 `access_log_contains_token=false` |
| D1 HTTP Origin | 不改请求处理逻辑；更新 AC21、项目约定和回归断言 | 正确 token + 未知 Origin 返回 200，无 CORS 允许头；缺失/错误 token 403；错误 WS Origin 403 |

迁移目标卷不支持硬链接时明确失败，不降级为覆盖；永久 AppData 在本机 NTFS 上通过。便携版每次启动增加一次完整解压，旧的版本化缓存保持原样，不自动删除用户磁盘上的历史目录。

## 重建与产物

隔离重建目录：`build/tauri-stage5/rebuild-20261019-223031`。

- 由 `git archive HEAD` 创建可追溯源码副本；ZIP comment 记录完整基线提交。
- 只覆盖本轮生产文件：`ui_backend/main.py`、`ui_backend/storage/workbench_db.py`、`scripts/portable.nsi`、`scripts/build_portable.ps1`；不叠加工作树中的 OCR 或日常业务修改。
- 复用已安装的 gui/node_modules、Rust 构建缓存与专用 headless 打包环境；OCR 模型复制到隔离源码，未下载或重装依赖。
- 执行隔离副本中的 `scripts/build_release.ps1 -SkipOcrDownload`，构建退出码 0。
- 旧包保存在重建目录的 `previous-packages/`。新便携包验证输入已复制回原有 `dist-electron` 路径。
- 最终 `portable.nsi` 首行说明在构建后改为准确的独立解压描述，仅注释有差异，不影响发行逻辑。

| 产物 | 字节数 | SHA-256 |
|---|---:|---|
| `gui/src-tauri/target/release/bundle/nsis/阴阳师脚本工作台_1.0.0_x64-setup.exe` | 80,340,052 | `7dba194a0488e69d0a4f83a4b439e9c0f69e50cfaa1f613ec68e157c6d47671c` |
| `dist-electron/阴阳师脚本工作台-1.0.0-portable.exe` | 80,257,552 | `bbd2352e977fa9d5558774d05952b7e2d52833a39011782e74a93cb3d90e2ea9` |

两包均严格小于 100,000,000 bytes。旧包、新包及生产覆盖文件哈希见 `build/tauri-stage5/rebuild-manifest.json`。

## 本轮检查

| 检查 | 结果 |
|---|---|
| 后端全量回归 | 136 通过，140 条既有 FastAPI 生命周期弃用警告 |
| Rust 单测 | 10/10 通过；保留两条既有未使用项警告 |
| JS 桥接/配置/后端检测 | 三组通过 |
| Ruff / cargo fmt / diff whitespace | 本轮相关文件通过 |
| 便携 NSIS 最小回归 | 同版本新载荷、重复启动、独立临时目录、完整资源、退出清理和数据哨兵全部通过 |
| 当前 WebView2 烟测 | 22 项页面检查、非授权窗口和原生尺寸通过；额外执行双屏移动矩阵 |
| 真实新后端 | 脚本 15 项、图片资源 178 项；鉴权/CORS/WS/图片替换预览恢复通过；日志 token 检查为 false |
| 真实发行宿主 | 新建隔离 APPDATA 数据库，其他 cwd 可运行；强杀后真实后端回收 |
| 真实 NSIS 新包 | 含空格的指定路径静默安装 0，安装版后端启动成功，快捷方式创建；卸载 0，目录/快捷方式/卸载键移除，隔离业务库与真实业务库保留 |
| 真实完整 portable | 两次独立解压，均连接真实后端；强杀宿主后 wrapper 退出，载荷清理，永久库保留；重复运行使用不同 cwd |

安装器的 InstallLocation 注册表值带引号，比较时按 NSIS 约定去除外层引号；初次测试器把引号当成路径内容导致断言失败，修正比较后继续完成同一次安装的启动与卸载，未将此测试器问题记成产品缺陷。

## 原生页面观察

通过 Computer Use 只操作本次创建的隔离便携版窗口，未运行任何游戏业务：

1. 首次启动为浅色、导航展开，显示“已连接”，无当前任务。
2. 切到深色、折叠导航；真实标题栏拖动后窗口移动。
3. 设置页显示真实图片资源；点击“永久截图库 / 打开目录”后，Explorer 打开隔离 APPDATA 的 `yys-script-manager/screenshots`。
4. 重启实际便携包后，仍为深色、导航折叠，显示“已连接”。
5. 关闭按钮点击后宿主和后端仍存活；列表 API 对隐藏窗口的枚举语义不足以单独证明隐藏状态，因此不将此项扩大描述为全部托盘实机验收通过。

Explorer 验证窗口随后关闭；本次创建的宿主/后端已回收，8000 端口释放。真实永久业务库、窗口文件及开发库前后哈希一致。

## 显示与 Runtime 的验证边界

### 已实测

- 两块真实显示器，均为 100% 缩放：
  - DISPLAY1：工作区 `(2560, 192)` / `1920×1032`。
  - DISPLAY2：工作区 `(0, 0)` / `2560×1392`。
- 隔离窗口分别移动到两屏，实际缩放均 1.0，逻辑客户区均 900×650，位置落在对应工作区。
- 为测试进程设置 `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` 指向空目录，真实 WebView2 初始化返回“找不到 Runtime”，宿主退出码 1，无业务页报告，后端回收。

### 未实测或用户延后

- Win10 22H2：用户明确“win10先不验”。
- 混合 DPI：用户明确保持系统设置、暂不验；没有修改显示缩放。
- 物理拔除显示器：未做；原离屏恢复测试不能替代物理拔屏。
- 整机真实 Runtime 缺失、在线安装后重试、离线、安装取消/失败：没有独立环境。本机 Hyper-V 无虚拟机、无可用 Windows Sandbox，未卸载或重注册共享 Runtime。
- 空浏览器目录的实际初始化失败，不等于整机未安装 Runtime；不把二者混记为通过。

## AC 状态更新

保留 `stage5-report.md` 的逐项审计作为初次结果。本轮仅更新有新证据的项：

- AC7：主题与导航折叠的真实便携版重启持久化已补齐。
- AC8：真实 Explorer 打开隔离截图库已补齐。
- AC10：真实标题栏拖动已补齐；尺寸、边缘缩放命中等沿用当前烟测证据。
- AC11：新增真实双屏 100% 移动证据；混合 DPI / 物理拔屏仍未验。
- AC15：新增真实初始化失败证据；整机缺失矩阵仍未验。
- AC17：新包指定含空格路径安装/启动/卸载已补齐；旧 Electron 原位升级仍未验。
- AC18：新包实际字节数通过。
- AC21：按用户确认的新契约通过本机 API/WS/CORS/图片检查；完整裁剪 UI 仍按原报告边界。
- AC23：F2 已关闭，真实完整包两次独立载荷、退出清理与永久库保留通过；非管理员独立账户和完整版本升级矩阵未做。
- AC25：F1 已关闭，并发发布不覆盖及异常副本清理回归通过。
- 日志设计约束：F3 已关闭，真实新后端日志检查通过。

其余 AC 不因本次修复自动改变判定；尤其 AC19/28 的实际 Electron 回退仍需补证。

## 本地证据

- `build/tauri-stage5/portable-regression.json`。
- `build/tauri-stage5/packaged-results.json`（新包运行目录 `packaged-223727`）。
- `build/tauri-stage5/native-portable-results.json`（实际包目录 `native-portable-223822`，两次载荷均已清理）。
- `build/tauri-stage5/nsis-install-results.json`（安装/卸载目录 `nsis-install-224313`）。
- `build/tauri-stage5/runtime-initialization-results.json`。
- `build/tauri-smoke/20261019-223231-712793/display-matrix.json`。
- `build/tauri-stage5/rebuild-manifest.json`、重建目录 `build.log` 与 `source.zip`。

这些在忽略的 build 下，清理前需要保留；未把用户数据或发行 EXE 加入 Git。

实现依据：[NSIS 临时目录退出清理与 cwd 限制](https://nsis.sourceforge.io/Docs/Chapter4.html)、[WebView2 的进程级浏览器目录覆盖](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/webview2-idl)。
