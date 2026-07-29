# 录制回放框架与自动结界突破：技术设计

## 1. 设计目标

本设计建立四个相互解耦、可独立验证的能力：

1. 在真实 Windows 游戏窗口上采集画面和人工输入。
2. 将原始采集转换为版本化、可审查的场景回放夹具。
3. 在离线环境中重放结界突破并验证动作与状态转换。
4. 通过有硬性边界的真机观察/试跑完成最后校准。

完整数据流如下：

```text
阴阳师窗口 + 人工输入
  → 伴随录制器
  → recordings/<scenario>/<recording-id>/
  → 关键帧候选与人工确认清单
  → 版本化回放夹具
  → SceneReplayEnvironment
  → RealmRaidScript 离线回归
  → 人工启动的受控真机试跑
```

## 2. 架构边界

### 2.1 Windows 环境抽象

将目前位于 `tests/common/environment/` 的通用环境契约提升到生产包：

```text
win_util/environment/
├── base.py       # GameEnvironment、ActionType、ActionRecord
├── windows.py    # WindowsEnvironment
└── guarded.py    # 观察模式、动作预算、超时和停止原因
```

原测试路径保留兼容导入，避免一次性修改所有调用方。`WinController` 的鼠标、键盘和截图都通过同一个
`GameEnvironment` 注入；修复当前键盘绕过环境抽象的问题，使离线回放和动作预算能够覆盖
`ESC`、`ENTER` 等按键。

### 2.2 录制核心

新增通用录制包：

```text
yys/common/recording/
├── contracts.py      # 唯一的 JSON/JSONL 类型、校验与序列化入口
├── session.py        # 录制生命周期、画面队列、输出目录
├── win32_input.py    # Windows 低层输入监听与客户区坐标归一化
└── fixture_builder.py # 关键帧候选与回放夹具生成
```

命令行只负责参数解析和展示状态：

```text
tools/record_gameplay.py
tools/build_replay_fixture.py
tools/run_guarded_script.py
```

业务脚本不得直接解析原始 JSONL；所有消费者必须调用 `contracts.py` 的解码器。

### 2.3 测试回放

扩展 `SceneReplayEnvironment`，使场景转换完全来自夹具，不再使用
`_DEFAULT_CLICK_REGIONS` 中的狭间暗域硬编码。读取器同时支持：

- 新的 `schema_version: 1` 夹具；
- 现有简单 `{scene: {button_image: next_scene}}` 配置，作为兼容路径。

### 2.4 结界突破业务状态

`RealmRaidScript` 继续使用现有事件驱动基类，但增加显式的每轮状态对象，不再通过
“是否识别到 9 个目标”推断退出三次是否已经执行。

建议的状态数据：

```python
@dataclass
class RealmRaidRoundState:
    generation: int
    victory_count_at_start: int
    quit_three_completed: bool
    attempted_cells: set[tuple[int, int]]
    current_cell: tuple[int, int] | None
```

目标由 `(row, col, point)` 表示，检测结果固定按 `(row, col)` 排序。真实录制显示最后目标结算后
游戏会自动换组；只有胜场数相对本轮起点增加且画面出现“攻略记录 0”时，才递增 `generation`
并重置每轮状态。该双重判据避免首次退出三次期间把初始记录 0 误判为新一轮。

## 3. 录制数据合约

### 3.1 原始目录

```text
recordings/
└── realm_raid/
    └── 20260725T120000Z-<short-id>/
        ├── metadata.json
        ├── events.jsonl
        ├── recording.mp4
        └── frames/
            ├── 000001-before.png
            └── 000001-after.png
```

录制过程中使用 `.partial` 后缀。正常结束后写入最终元数据再原子重命名；异常退出时保留
`.partial` 目录并写明错误，便于恢复证据。

### 3.2 元数据

`metadata.json` 至少包含：

- `schema_version`
- `recording_id`
- `scenario`
- `started_at`、`ended_at`
- `duration_ms`
- `window_title`
- `client_width`、`client_height`
- `fps`、`codec`
- `event_count`、`dropped_frame_count`
- `status`
- `stop_reason`

窗口句柄只在进程内使用，不写入持久化数据。

### 3.3 事件 JSONL

每条事件公共字段：

- `schema_version`
- `seq`
- `elapsed_ms`，来源为单调时钟
- `kind`

鼠标事件附加：

- `action`
- `button`
- `client_x`、`client_y`
- `normalized_x`、`normalized_y`

键盘事件附加：

- `action`
- `key`

约束：

- `seq` 严格递增；
- `elapsed_ms` 不倒退；
- 客户区坐标必须在录制时窗口范围内；
- 不持久化桌面绝对坐标；
- 除全局 `F12` 外，只有目标游戏是前台窗口时才记录键盘事件；
- 未知 `schema_version`、非法坐标和未知事件种类必须在解码边界报错。

## 4. 录制生命周期

生命周期为：

```text
IDLE → ARMED → RECORDING → STOPPING → COMPLETED
                              └──────→ FAILED
```

- `ARMED`：已经找到阴阳师窗口并完成客户区校验，尚未采集。
- `RECORDING`：画面线程和输入监听线程同时运行。
- `STOPPING`：停止接收新事件，排空有限队列并关闭视频。
- `COMPLETED`：元数据和视频均可读取。
- `FAILED`：保留已写证据并记录原因。

首次实现采用固定帧率和有界队列。写盘速度不足时丢弃画面帧并累计
`dropped_frame_count`，不得丢弃输入事件。录制期间窗口客户区尺寸变化时停止录制并提示重新开始，
避免视频尺寸与坐标系不一致。

## 5. Windows 输入与截图

### 5.1 截图

复用 `ScreenCapture` 的 `PrintWindow` 能力，但新增明确的客户区截图入口，统一输出 BGR 帧。
录制器不得截取完整桌面。视频写入前验证：

- 第一帧尺寸与客户区元数据一致；
- `VideoWriter.isOpened()` 为真；
- 每帧尺寸一致。

首选 MP4；如果本机 OpenCV 构建不支持选定编码器，应在开始录制前明确失败，不生成伪成功文件。

### 5.2 输入监听

使用 Windows 低层鼠标/键盘监听，回调只做时间戳、过滤和入队，不执行磁盘 I/O。鼠标事件通过
`ScreenToClient` 转为客户区坐标，只保留落在阴阳师客户区内的操作。`F12` 始终作为停止信号处理，
不作为普通游戏输入回放。

## 6. 夹具合约与生成

新夹具由一个 `fixture.json` 作为唯一入口：

```json
{
  "schema_version": 1,
  "scenario_id": "realm_raid-main-flow",
  "client_size": [1154, 680],
  "initial_scene": "home",
  "scenes": {},
  "transitions": [],
  "expected_actions": []
}
```

其中：

- `scenes` 将稳定场景名映射到经过确认的截图；
- `transitions` 描述源场景、触发动作或按钮、坐标区域与目标场景；
- `expected_actions` 描述动作类型、允许区域、顺序和可选停止原因。

生成过程分两步：

1. 工具按输入事件提取动作前后关键帧并生成候选清单。
2. Agent 或用户修正场景名、裁剪范围和转换，再显式执行生成命令。

工具不得把未经确认的原始帧直接复制到 Git 跟踪目录。

## 7. 结界突破状态机

### 7.1 目标选择

- 固定扫描 3×3 九宫格；
- 目标按上到下、每行左到右排序；
- 已尝试或不可攻击格子不再选择；
- 点击目标后必须等待并确认“进攻”界面，不能在同一截图上重复点击。

### 7.2 每轮退出三次

- 新九宫格创建一个新的 `RealmRaidRoundState`；
- 仅当 `quit_3_times_config` 开启且本轮尚未执行时触发；
- 三轮 `ESC → ENTER → 再次挑战` 都必须分别确认下一画面；
- 任一确认失败立即安全停止，不继续猜测点击；
- 完成后设置 `quit_three_completed=True`；
- 自动换组判据成立或手动刷新确认成功后创建下一轮，允许再次执行。

### 7.3 战斗与结束

保留公共战斗结束处理，同时为结界突破维护明确停止原因：

- `max_battle_count`
- `ticket_not_enough`
- `no_attackable_target`
- `refresh_failed`
- `unknown_scene_limit`
- `action_limit`
- `timeout`
- `emergency_stop`

异常分支没有真实录制时只允许安全停止或测试注入，不能新增未经验证的真机点击。

## 8. 受控真机运行

`GuardedEnvironment` 统一统计鼠标、拖拽和按键逻辑动作。`RunGuard` 使用单调时钟并维护：

- 默认 180 秒超时；
- 默认 30 个输入动作；
- 连续 3 次未知画面；
- `F12` 紧急停止；
- 观察模式下记录拟执行动作但不向游戏发送输入。

真机 CLI 默认必须运行在交互式终端，并要求用户现场输入确认短语。若用户在当前活动任务中明确
授权 Agent “自行调试”，CLI 允许通过 `--confirmation-phrase` 显式传入同一条完整确认短语。
该参数不是跳过确认的 `--yes`：短语必须与当前脚本和模式精确匹配，错误时必须在解析游戏窗口前退出。
两条启动路径使用完全相同的 `RunGuard`、前台捕获、动作预算、超时、未知场景和 `F12` 保险丝，
且一次进程仍只执行一次，不得自动重启。

## 9. 兼容性与迁移

- 保留 `tests.common.environment.*` 的兼容导入。
- 保留 `ScenarioRecorder` 公开 API，内部可逐步委托给新合约。
- 旧版场景转换 JSON 继续可读，新生成内容统一使用 v1。
- 保留现有 `RealmRaidConfig` 字段和默认值。
- 保留用户将 `BATTLE_END_CLICK_SLEEP` 调整为 3 秒的未提交修改。
- 第一阶段不修改桌面前端和 FastAPI 接口。

## 10. 主要取舍

- 采用“候选生成 + 人工确认”，不追求视频到状态机的全自动标注，以换取可验证性。
- 原始数据仅本地保存，减少仓库体积和隐私风险。
- 将环境抽象提升到生产包会增加一次兼容迁移，但能统一键盘、鼠标、截图、观察模式和动作预算。
- 数据驱动回放替换硬编码区域，初始改动较大，但这是后续复用到其他副本的必要边界。

## 11. 回滚策略

- 环境抽象迁移通过兼容导入分阶段落地，可单独回滚而不删除旧测试路径。
- v1 回放读取失败时仍可使用旧转换配置。
- 结界突破状态机改动限定在 `yys/realm_raid/`，出现真机回归时可关闭新配置入口并保留离线夹具。
- 原始录制位于 Git 忽略目录，回滚代码不会删除用户录制；清理由用户显式执行。
