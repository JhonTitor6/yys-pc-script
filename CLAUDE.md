# CLAUDE.md
## 重要说明

- **回答和代码注释必须使用中文**
- **Git 提交信息必须使用中文**

## 项目概述
yys-pc-script 是一个基于事件驱动架构的阴阳师 PC 端自动化脚本。通过图像识别、OCR 和鼠标/键盘控制实现游戏任务自动化，无需游戏窗口处于前台激活状态。

## 环境配置
```bash
# 使用项目指定的 conda 环境
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pip install -r requirements.txt
```

## 核心开发规则
- 所有代码都必须提供类型提示 
- 公共 API 必须包含文档字符串 
- 函数必须简洁明了、篇幅短小

## 测试

### 单元测试（推荐）
测试位于 `yys/test/`，使用 pytest 运行：
```bash
# 运行所有测试
pytest yys/test/

# 只运行御魂模块测试（不需要游戏窗口）
pytest yys/test/test_soul_raid.py -v
```
单元测试使用 Mock 环境，不依赖游戏窗口。

### 测试框架架构

```
yys/test/
├── environment/           # 环境抽象层
│   ├── base.py           # GameEnvironment 抽象基类
│   ├── mock_environment.py  # Mock 测试环境
│   └── windows_environment.py  # Windows 生产环境
├── providers/             # 图片提供者
│   └── file_image_provider.py  # 从文件加载截图
├── recorders/           # 操作记录器
│   ├── action_log.py    # 操作日志容器
│   ├── action_recorder.py  # 操作记录器
│   └── record_replay.py  # 录制-回放工具
└── test_data/           # 测试数据
    └── scenarios/       # 场景截图
```

### Mock 测试示例

```python
from yys.test.environment.mock_environment import MockEnvironment
from yys.test.recorders.action_log import ActionLog

# 创建 Mock 环境
log = ActionLog()
env = MockEnvironment(action_log=log)

# 执行点击操作
env.left_click(100, 200)

# 验证操作记录
log.assert_click_at(100, 200, tolerance=10)
log.assert_click_count(1)
```

### 录制新测试场景

```python
from yys.test.recorders.record_replay import ScenarioRecorder

recorder = ScenarioRecorder()
recorder.start_recording()

# ... 执行操作 ...

# 保存场景
screenshot = env.capture_screen()
recorder.save_scenario("soul_raid/battle_01", screenshot)
```

集成测试需要打开游戏窗口。
