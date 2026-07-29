# 录制回放框架与自动结界突破：实施计划

## 1. 实施顺序

### 阶段 A：环境抽象与合约

- [x] 将 `GameEnvironment`、`ActionType`、`ActionRecord` 提升到 `win_util/environment/`。
- [x] 将 `WindowsEnvironment` 提升到生产包，修正客户区截图和坐标语义。
- [x] 保留 `tests/common/environment/` 兼容导入。
- [x] 让 `KeyboardController` 与 `WinController` 支持环境注入，确保按键能够被回放和动作预算捕获。
- [x] 为鼠标、键盘、截图和旧导入路径添加单元测试。

验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ -v
```

### 阶段 B：伴随录制器

- [x] 新增版本化录制合约及严格解码器。
- [x] 新增客户区截图、固定帧率视频写入和有界帧队列。
- [x] 新增 Windows 输入监听、前台窗口过滤和客户区坐标转换。
- [x] 实现 `.partial` 生命周期、异常元数据、掉帧统计和窗口尺寸变化停止。
- [x] 实现 `record`、`inspect`、`clean` 命令。
- [x] 将 `recordings/` 加入 `.gitignore`。
- [x] 测试 JSONL 往返、非法版本、非法坐标、事件顺序、异常关闭和单次清理边界。

验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_recording_contracts.py tests/common/test_recording_session.py -v
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/record_gameplay.py --help
```

手工门禁：

- [x] 找不到阴阳师窗口时明确失败且不创建伪完成录制。
- [x] 视频编码器不可用时在录制前失败。
- [x] `F12` 能终止录制并生成可读取的元数据。
- [x] 窗口移动不改变客户区坐标，窗口尺寸变化会停止录制。

### 阶段 C：夹具生成与数据驱动回放

- [x] 定义 v1 `fixture.json` 类型和单一解码入口。
- [x] 实现按动作时间提取前后关键帧与候选转换。
- [x] 实现人工确认清单输入，不自动写入 Git 跟踪目录。
- [x] 移除 `SceneReplayEnvironment` 的狭间暗域硬编码区域，改为读取夹具。
- [x] 增加旧转换 JSON 兼容适配器。
- [x] 为新旧夹具、非法转换、坐标边界和动作断言添加测试。

验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_replay_environment.py tests/common/test_fixture_builder.py yys/abyss_shadows/test_abyss_shadows_scene_replay.py -v
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/build_replay_fixture.py --help
```

### 阶段 D：结界突破状态机

- [x] 新增带类型提示的目标格与每轮状态类型。
- [x] 将 3×3 检测结果稳定排序并跳过已尝试格。
- [x] 将退出三次从“目标数量等于 9”改成显式每轮状态。
- [x] 为退出三轮的每一步加入画面确认和失败停止。
- [x] 刷新成功后创建新一轮；刷新失败时停止。
- [x] 处理券不足、战斗失败、未知场景和最大次数停止原因。
- [x] 保留配置兼容与 3 秒战斗结束等待。
- [x] 新增 `yys/realm_raid/test_realm_raid_flow.py`。

验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest yys/realm_raid/test_realm_raid_flow.py tests/common/test_event_script_base.py tests/common/test_scene_transition_entry.py -v
```

### 阶段 E：受控真机调试

- [x] 新增 `RunGuard` 和 `GuardedEnvironment`。
- [x] 观察模式记录拟执行动作但不发送输入。
- [x] 实现 180 秒、30 动作、连续 3 次未知画面和 `F12` 停止。
- [x] 真机 CLI 默认要求交互式终端和现场确认短语；用户明确授权 Agent 自行调试时，
  允许通过精确的 `--confirmation-phrase` 启动同等保护的单次运行。
- [x] 为每一种停止原因添加确定性测试。

验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_guarded_environment.py tests/common/test_run_guard.py -v
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/run_guarded_script.py --help
```

### 阶段 F：真实录制与校准

- [x] 用户录制主流程：庭院进入、每轮退出三次、至少两个正常目标。
- [x] 用户录制组末流程：最后目标结算、自动换组、新九宫格。
- [x] Agent 生成候选关键帧与转换清单。
- [x] 用户确认可进入 Git 的最小脱敏测试资产。
- [x] 使用真实夹具完成入口、主流程、每轮退出三次和自动换组回归。
- [x] 运行观察模式，确认只记录计划动作、不发送输入且不自动重启。
- [x] 完成一次用户手动启动或用户明确授权 Agent 启动的受控真机试跑。
- [x] 罕见异常在后续遇到时补录，不阻塞主流程交付。

## 2. 全量质量门禁

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ yys/*/test_*.py -v
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ruff check win_util yys tests tools
```

额外检查：

- [x] 所有新增和修改函数包含类型提示。
- [x] 公共 API 有中文注释或文档字符串。
- [x] JSONL/夹具只通过共享解码器读取。
- [x] 测试不依赖真实游戏窗口。
- [x] 原始录制未被 Git 跟踪。
- [x] 不覆盖现有 `BATTLE_END_CLICK_SLEEP = 3` 修改。
- [x] 不修改与本任务无关的用户文件。

当前验证记录（2026-07-25）：

- 本任务新增/修改文件 Ruff 检查通过。
- 环境注入、录制、回放、结界突破、受控运行和 CLI 共 88 个定向测试通过。
- 三个 CLI 的 `--help` 均可正常运行，未触发真实窗口操作。
- 仓库级 Ruff 仍有 28 个既有问题；仓库级 pytest 为 172 通过、53 失败、3 错误。
  失败主要来自旧测试的全局模块 Mock 污染、无效御魂 PNG 素材和既有 OCR/配置测试，
  不在本任务中修改。

录制诊断与修复记录（2026-07-26）：

- 两次 `realm_raid_main` 录制均由 `F12` 正常完成，分别记录 18 与 8 个客户区鼠标事件。
- MSMF 写入的视频可读取，但视频和动作关键帧均为纯白；`PrintWindow` 对游戏窗口返回成功
  不代表成功捕获了硬件加速画面，因此这两次录制不得生成 Git 夹具。
- 录制器现在会在终端确认后自动恢复并激活游戏窗口，仅在录制路径使用桌面前台客户区采集；
  普通后台自动化仍保留原 `PrintWindow` 模式。
- 首帧为空或标准差低于 `1.0` 时，在视频写入器和输入监听器启动前立即失败并保留错误元数据，
  避免再次完成整段无效录制。
- 修复后的 3.9 秒冒烟录制 `20260726T122738Z-d0f39920` 已通过真实画面验收：
  1136×640 视频可读，首帧标准差为 `53.59`，目视确认为未被终端遮挡的游戏客户区。
- 本次修复 Ruff 通过；录制、回放、环境迁移、受控运行、结界突破和狭间暗域共
  67 个定向测试通过。

正式录制接入记录（2026-07-28）：

- 主流程录制 `20260728T144645Z-a7712611`：119516 ms、1136×640、38 个事件，
  覆盖庭院入口、首次退出三次和至少两个正常目标。
- 组末录制 `20260728T144916Z-a483b704`：22750 ms、1136×640、9 个事件。
  实际游戏在最后目标结算后自动出现新九宫格，没有人工“刷新确认”步骤。
- 已生成并人工检查 12 张最小脱敏场景图；账号栏、聊天、玩家昵称和个人统计区域均已遮盖，
  原始录制继续保留在 Git 忽略目录。
- 正式回放驱动生产 `SceneManager` 从庭院进入结界突破，并校准三个已漂移的真实入口模板。
- 新增“攻略记录 0”模板和“新增胜场 + 记录归零”的自动换组判据，避免首次退出三次期间误判。
- 录制构建器、结界状态机和正式回放共 24 个定向测试通过；本任务环境、录制、回放、
  安全控制和结界突破完整定向测试共 82 个通过。
- 本任务新增和修改的 Python 文件 Ruff 全部通过；`git diff --check` 通过。
- 仓库级 pytest 为 181 通过、60 失败、3 错误；仓库级 Ruff 保持 28 个既有问题。
  失败仍集中于旧测试全局 Mock 污染、无效御魂 PNG、OCR/配置兼容和既有静态问题，
  未修改这些任务外文件。
- 观察模式真机验证运行 16.094 秒，识别九宫格 9 个目标并记录 9 个计划动作；
  `consecutive_unknown=0`、`battle_count=0`、`auto_restart=false`。最终
  `no_attackable_target` 是观察模式不发送点击、画面不切换后遍历完九格的预期停止结果。
- 首次受控执行运行 34.657 秒并完成首次退出三次，11 个动作未超预算且未自动重启；
  随后在真实战斗画面连续 3 次未知而安全停止。根因是结界脚本未注册战斗进行中事件，
  且旧公共 `battling.bmp` 无法匹配当前界面。
- 已从脱敏正式帧生成结界专用“结界加成”战斗标记，注册无输入回调并增加生产事件循环回归测试；
  不通过调高 `unknown_limit` 弱化保险丝。
- 第二次受控执行在跳过退三次后成功完成目标选择和进攻点击，2 个动作未超预算且未自动重启；
  但在 8.641 秒的加载/入场动画中连续 3 次未知而安全停止，尚未进入稳定战斗标记。
- 已为 `RunGuard` 增加动作限定的一次性未知宽限，并在进攻或成功完成退三次后设置 12 秒。
  任意已知事件会立即结束宽限，总超时、动作上限和 F12 始终生效；全局未知阈值仍为 3。
- 第三次受控执行继续成功完成目标选择和进攻点击，8.156 秒内执行 2 个动作且未自动重启；
  但快照中的 `unknown_grace_remaining_seconds=0.0`，随后仍因连续 3 次未知安全停止。
- 根因是事件回调先开启宽限，事件循环在回调返回后又为同一个进攻事件调用
  `note_iteration(True)`，把刚开启的宽限误当成“后续已恢复识别”而立即取消。
- `RunGuard` 现在区分开启宽限的当前事件回执与之后的新识别事件：前者保留宽限，后者才结束；
  已增加保险丝单元测试、真实事件循环时序测试和结界进攻回调测试。
- 第四次受控执行运行 15.297 秒，仍只执行目标选择和进攻 2 个动作；12 秒宽限完整生效后才累计
  3 次未知并安全停止，证明同轮宽限时序修复有效，但稳定战斗标记仍未命中。
- 停机后的前台游戏画面显示目标 `[1,0]` 已被击破、攻略记录增长到 4，确认业务点击和战斗结果
  正确，剩余问题仅是战斗进行中识别。
- 对 119.5 秒正式录制视频以每秒 2 帧测量模板覆盖率：旧“结界加成”面板每段战斗只命中
  约 1.5–5 秒；左下角“自动”控件覆盖完整战斗区间，非战斗片段最高相似度为 `0.371`。
- 已将生产 `realm_raid_battling.bmp` 替换为脱敏正式帧中的持久“自动”控件，并把搜索范围改为
  左下角；真实战斗正向回归和真实战后总结负向回归均通过。
- 本轮修复后，录制、回放、安全控制和结界突破完整定向测试共 88 个通过；相关 Ruff 和
  `git diff --check` 通过。
- 第五次受控执行运行 17.875 秒，仍只执行目标选择和进攻 2 个动作；完整宽限后连续 3 次未知
  安全停止，持久“自动”模板在实机战斗阶段依然完全未命中。
- 停机后游戏停在胜利奖励“点击屏幕继续”画面，确认目标 `[1,1]` 已打赢，但脚本因战斗中提前
  停机而没有处理结算，进一步把故障限定到战斗阶段截图链路。
- 在当前静态胜利奖励画面，前台状态下的 `PrintWindow` 与桌面客户区截图平均像素差为 `1.516`；
  结合此前战斗录制中 `PrintWindow` 纯白、前台捕获正常的直接证据，说明捕获有效性取决于
  “截图后端 × 渲染阶段”，不能由静态画面推断硬件加速战斗阶段。
- 交互式受控 `--execute` 现在显式使用 `capture_mode="foreground"`，确认后自动恢复并激活游戏，
  等待 0.5 秒再开始识别；观察模式和普通后台脚本继续使用 `PrintWindow`，不抢占窗口焦点。
- 新增执行/观察两条 CLI 回归，分别断言捕获模式和激活次数；完整任务定向测试增至 90 个，
  相关 Ruff 和 `git diff --check` 通过。

自主实机闭环与最终校准记录（2026-07-29）：

- 用户明确要求 Agent “自行调试”后，受控 CLI 新增 `--confirmation-phrase`：
  非交互调用仍需完整匹配 `RUN realm_raid`，缺失短语返回 2，错误短语返回 1，
  两者均在解析游戏窗口前退出；默认交互式确认路径保持不变。
- 第一轮 Agent 授权执行运行 18.547 秒、2 个动作。前台截图让持久“自动”模板在完整战斗阶段
  连续命中，证明硬件加速截图根因已修复；战斗结束后到胜利模板出现前仍有约 1.4 秒过渡，
  连续 3 帧未知因此安全停止。
- `RealmRaidScript._on_battling` 现在只刷新 5 秒结算尾部宽限，不发送任何输入。
  宽限随持久战斗标记刷新，标记消失后覆盖确定性的结算动画；胜利或奖励事件出现后立即结束。
  总超时、动作预算、未知阈值和 `F12` 始终有效。
- 第二轮 Agent 授权执行运行 27.203 秒、4 个动作，`consecutive_unknown=0`；
  依次命中战斗标记、`battle_end.bmp` 和 `battle_end_1.bmp`，最终
  `battle_count=1`、`victory_count=1`、`stop_reason=max_battle_count`，
  `auto_restart=false`，完成结界突破单场真实闭环。
- 新增找不到游戏窗口时不创建录制目录，以及客户区尺寸变化时停止采集的直接回归。
  任务范围环境、录制、回放、安全控制和结界突破测试增至 95 个，全部通过；
  本次修改文件 Ruff 与 `git diff --check` 通过。
- 狭间暗域复用同一 `SceneReplayEnvironment` 的 11 个独立回放测试通过，证明通用回放层
  不依赖结界突破业务。
- 仓库级递归 pytest 为 186 通过、66 失败、3 错误；失败仍来自既有全局模块 Mock 污染、
  损坏图片、OCR/配置兼容和旧测试初始化问题。仓库级 Ruff 仍为既有 28 项，
  本任务未扩大这些基线问题。

## 3. 风险文件与回滚点

| 范围 | 风险 | 回滚点 |
|---|---|---|
| `win_util/environment/`、`WinController` | 影响所有脚本的输入注入 | 先保留旧导入与构造签名，每个阶段单独测试 |
| `SceneReplayEnvironment` | 可能破坏狭间暗域旧回放 | 先加入兼容适配器，再移除硬编码 |
| `RealmRaidScript` | 真机状态误判会产生错误点击 | 离线夹具先通过，观察模式后才允许受控试跑 |
| Windows 输入监听 | 回调阻塞或记录无关输入 | 回调只入队，严格窗口过滤，`F12` 优先停止 |
| 视频写入 | 编码器/帧尺寸不兼容 | 开始前探测，失败即停止并保留错误元数据 |

## 4. 规划后的执行单元

实施按以下依赖顺序推进：

1. 通用环境抽象与伴随录制器。
2. 夹具生成与数据驱动回放。
3. 结界突破状态机与受控真机调试。
4. 用户真实录制、Agent 校准与最终全量验证。

每个执行单元完成后运行其局部测试；只有前三个单元通过后才进入真实录制。
