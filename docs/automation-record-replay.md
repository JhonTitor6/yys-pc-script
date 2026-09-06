# 游戏流程录制、回放与受保护运行

## 这套工具解决什么问题

单独的视频只能让 AI 看懂大致流程，无法可靠还原点击坐标、按键时序和窗口客户区位置。本项目的“伴随录制器”会同时保存：

- 游戏客户区视频；
- 客户区相对坐标的鼠标和键盘事件；
- 每个事件前后的关键帧；
- 窗口尺寸、时间戳、停止原因等元数据。

录制器支持竖向鼠标滚轮：`action: "wheel"` 的 `wheel_delta` 保存原始有符号增量（正数向上、负数向下，普通一格通常为 120），坐标表示滚动发生时鼠标所在的客户区位置。只记录前台游戏客户区内的非注入滚轮。新录制使用 v2，读取工具继续兼容 v1；候选清单保留滚动量，当前场景回放夹具尚不支持执行滚轮。

阵容流程可用 `record --scenario lineup_switch` 采集：从入口开始，分别演示分组与阵容列表的滚动、选中目标以及切换成功画面，按 F12 结束。录制时保持窗口尺寸不变，滚动后稍停以获得清晰文字。

原始录制默认写入 `recordings/`，该目录已被 Git 忽略。只有经过人工检查并挑选出的最小回放夹具才应提交到仓库。

当前已经完成通用录制/回放基础设施，以及结界突破的固定顺序状态机。狭间暗域、御魂、御灵、探索可以先使用同一个录制器采集流程，后续再逐个补齐各自状态机。狭间暗域 Home 入口已接入脱敏回放夹具，覆盖横向拖拽、动态入口找图、纵向拖拽和狭间暗域卡片找图。

## 1. 录制结界突破

使用项目指定环境，在交互式终端运行：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/record_gameplay.py record --scenario realm_raid
```

工具找到窗口后会等待 Enter。切换到游戏并按 Enter 开始，录制过程中按 F12 停止。

建议先录两段：

1. 从庭院开始，进入探索、结界突破，完成首次退三次，并至少挑战两个目标。
2. 从当前九宫格最后一个可挑战目标开始，打完后刷新，直到看到下一轮九宫格。

录制期间不要改变游戏客户区尺寸。若尺寸变化，录制器会停止并保留失败原因。

检查录制是否完整：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/record_gameplay.py inspect recordings/realm_raid/<录制编号>
```

## 2. 生成人工确认清单

先从录制事件生成候选清单：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/build_replay_fixture.py candidates recordings/realm_raid/<录制编号> --output recordings/realm_raid/<录制编号>/candidates.json
```

逐项查看 `frames/*-before.png` 和 `frames/*-after.png`，只保留能证明状态转换的事件。确认文件格式如下：

```json
{
  "scenario_id": "realm_raid_basic",
  "initial_scene": "home",
  "transitions": [
    {
      "event_seq": 1,
      "from_scene": "home",
      "to_scene": "exploration",
      "action": "left_click",
      "region": [100, 100, 140, 140]
    }
  ]
}
```

`region` 必须来自实际录制及人工确认，不要根据视频猜坐标。

拖拽转换额外填写 `end_region`，分别约束拖拽起点和终点：

```json
{
  "from_scene": "home",
  "to_scene": "home_panned",
  "action": "drag",
  "region": [553, 304, 577, 328],
  "end_region": [928, 304, 952, 328]
}
```

## 3. 生成最小回放夹具

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/build_replay_fixture.py build recordings/realm_raid/<录制编号> recordings/realm_raid/<录制编号>/confirmation.json tests/fixtures/realm_raid/basic
```

工具只复制确认事件的关键帧，并生成 `fixture.json`。确认不含账号、聊天或其他隐私画面后，才可把这个最小目录加入 Git。

狭间暗域 Home 入口的脱敏夹具位于 `tests/fixtures/abyss_shadows/home_entry/`，可单独验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest yys/abyss_shadows/test_abyss_shadows_scene_replay.py::TestAbyssShadowsSceneReplay::test_home_entry_replays_recorded_drag_and_dynamic_templates -v
```

离线验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_replay_environment.py yys/realm_raid/test_realm_raid_flow.py -v
```

## 4. 先用观察模式验证

观察模式不会向游戏发送输入，只记录脚本原本准备执行的动作。先把游戏手动停在结界突破相关画面，然后运行：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/run_guarded_script.py realm_raid
```

按提示输入：

```text
OBSERVE realm_raid
```

默认保险丝：

- 最长运行 180 秒；
- 最多计划 30 个逻辑动作；
- 连续 3 帧无法识别即停止；
- F12 随时紧急停止；
- 结束后绝不自动重启。

## 5. 人工启动一次真实执行

确认观察结果合理后，显式增加 `--execute`：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/run_guarded_script.py realm_raid --execute --max-battles 9
```

按提示输入：

```text
RUN realm_raid
```

执行模式可从庭院开始，也可直接从结界突破页面开始。脚本会按从左到右、从上到下选择目标；每个新九宫格仅执行一次退三次，刷新确认且识别到新目标后才开始下一轮。

券不足、再次挑战按钮缺失、刷新失败、动作超限、超时、连续未知画面或 F12 都会停止本次运行。若本次不需要退三次，可增加 `--skip-quit-three`。

## 6. 录制其他副本

同一个录制器可直接换场景标识：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/record_gameplay.py record --scenario abyss_shadows
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/record_gameplay.py record --scenario soul_raid
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/record_gameplay.py record --scenario spirit_guardian
D:/ProgramData/anaconda3/envs/win_macro/python.exe tools/record_gameplay.py record --scenario exploration
```

每个副本至少录制正常主流程、一次刷新或循环边界，以及之后遇到的稀有失败画面。录制数据可以帮助 AI 编写和离线调试状态机，但启用真实执行前仍需为该副本接入相同的保险丝入口并通过回放测试。
