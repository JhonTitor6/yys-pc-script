# GUI图片资源替换与持久化技术设计

## 1. Design Decisions

- 复用 `win_util.image.to_project_path()` 作为唯一运行时入口，不新增第二套图片加载器。
- Electron 通过环境变量 `YYS_USER_DATA_DIR` 把 `app.getPath('userData')` 传给后端；开发环境或独立后端未提供该变量时保持现有项目根行为。
- 清单从当前内置安装树动态扫描，不建立需要人工同步的 manifest 或中文别名表。
- 每个资源只保存一个用户覆盖；内置图永远留在安装树，可通过删除覆盖立即恢复。
- API 使用二进制请求体，不引入 `python-multipart`；服务端根据目标资源扩展名解码并重新编码。

## 2. Persistent Layout

```text
<userData>/
└── image-overrides/
    └── yys/
        └── <与内置资源相同的相对路径>
```

- 覆盖根只由 `YYS_USER_DATA_DIR` 派生，客户端不能传入绝对目标路径。
- 不迁移现有 `config/ui_workbench.db`；本任务的重装保留只依赖覆盖文件本身。
- 临时文件与目标覆盖位于同一目录，保证 `os.replace()` 不跨卷。

## 3. Catalog and Path Resolution

### 3.1 Production catalog

在 `win_util.image` 内提供共享枚举/规范化函数，扫描 `PROJECT_ROOT/yys`：

- 只接受 `.bmp`、`.png`，扩展名不区分大小写。
- 任一路径段为 `test`、`tests`、`debug`、`logs`、`example`、`recordings` 时排除。
- 资源 ID 是相对 `PROJECT_ROOT` 的 POSIX 路径，例如 `yys/abyss_shadows/images/boss_label.bmp`。
- 启动或 API 请求时扫描即可；当前规模不足百张，不增加缓存失效机制。

规划时 Git 基线为 97 张；工作树额外存在未提交的 `gained_reward.bmp` 时为 98 张。测试比较“扫描结果与 API 清单”，不断言固定数量。

### 3.2 `to_project_path()` contract

1. 输入是相对文件路径：规范化并确认位于项目根；若对应覆盖是有效文件则返回覆盖，否则返回内置文件。
2. 输入是 `PROJECT_ROOT` 下的绝对文件路径：转回资源 ID 后执行相同覆盖选择，修复 `SceneManager` 目录扫描生成绝对路径后绕过覆盖的问题。
3. 输入是目录：始终返回内置目录，让部分覆盖不会遮蔽其他内置文件。
4. 输入是项目根以外的绝对路径：保持现有原样返回行为。
5. 路径含 `..`、盘符切换或无法归一到允许资源 ID 时，不访问覆盖根。

## 4. Backend Service and API

新增一个窄职责资源服务，由 `ui_backend.app` 注入持久化根：

- `GET /api/image-resources`：返回资源 ID、分组、文件名、格式、尺寸、覆盖状态。
- `GET /api/image-resources/content?resource_id=...&variant=effective|builtin`：返回缩略图/预览来源。
- `PUT /api/image-resources/override?resource_id=...`：读取二进制请求体、校验、重新编码并原子替换。
- `DELETE /api/image-resources/override?resource_id=...`：删除单个覆盖并恢复内置图。

所有端点继续受现有 `YYS_UI_TOKEN` 中间件保护。返回值只暴露资源 ID 和状态，不把服务器绝对路径交给渲染进程。

## 5. Validation and Atomic Write

写入顺序：

1. 资源 ID 必须存在于本次动态清单。
2. 限制请求体大小，使用 Pillow 解码并触发其解压炸弹保护。
3. 拒绝空尺寸、不可解码内容和非 BMP/PNG 输入。
4. 按目标资源扩展名写入同目录唯一临时文件并关闭文件句柄。
5. 从临时文件重新解码，确认尺寸和格式可读。
6. `os.replace(temp, target)`；异常时删除临时文件并保留旧覆盖。

运行中匹配每次重新打开模板文件，因此一次已开始匹配可使用旧文件，后续匹配使用新文件；原子替换保证不会看到半文件。

## 6. GUI

在现有“设置”页增加资源管理区：

- 脚本/公共目录分组和路径搜索。
- 当前生效缩略图、文件名、相对路径、“内置/已覆盖”状态。
- “选择文件替换”“截图并替换”“恢复默认”操作。
- 替换已有覆盖和恢复默认均显示目标缩略图与路径确认；成功后只刷新该项。
- 运行中仍显示相同操作，不调用任何运行控制端点。

## 7. Compatibility and Packaging

- `gui/main.js` 启动后端时追加 `YYS_USER_DATA_DIR`，不改变端口、token、cwd 和 Python 选择逻辑。
- PyInstaller 继续打包内置 `yys/` 资源；覆盖目录不进入构建、不被安装器写入。
- 新安装包删除某个内置资源后，旧覆盖文件留在磁盘但不进入清单、也不能通过 API 访问；可后续单独提供孤立文件清理工具，本任务不做。
- 现有绝对外部图片路径、未覆盖路径、匹配阈值和 `ImageFinder` 调用签名保持不变。

## 8. Risks and Rollback

- 风险：目录与文件混用导致部分覆盖遮蔽内置树。防护：只对存在的文件应用覆盖，目录永远使用内置树。
- 风险：Windows 并发读取时替换失败。防护：关闭临时句柄后 `os.replace()`；失败时保留旧版本并返回错误，不做非原子覆盖回退。
- 回滚：删除 `image-overrides` 中对应文件即可恢复内置图；移除 `YYS_USER_DATA_DIR` 时后端回到现有无覆盖行为。
