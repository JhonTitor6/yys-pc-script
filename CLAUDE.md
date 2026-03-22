# CLAUDE.md
## 重要说明

- **回答和代码注释必须使用中文**
- **Git 提交信息必须使用中文**

## 文档路径规范

- **项目文档**: `docs/` — 架构、API、设计规格（可被他人阅读）
- **实现计划**: `docs/plans/` — YYYY-MM-DD-<feature>-plan.md
- **设计规格**: `docs/specs/` — YYYY-MM-DD-<feature>-design.md
- **Claude 记忆**: `.claude/memory/` — MEMORY.md 索引 + 主题文件
- **Brainstorming 临时文件**: `.superpowers/` — 会话用，完成后清理

## 项目概述
yys-pc-script 是一个基于事件驱动架构的阴阳师 PC 端自动化脚本。通过图像识别、OCR 和鼠标/键盘控制实现游戏任务自动化，无需游戏窗口处于前台激活状态。

## 环境配置
```bash
# 使用项目指定的 conda 环境
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pip install -r requirements.txt
```

## 核心开发规则
- 所有代码都必须提供类型提示 
- 公共 API 必须包含注释
- 函数必须简洁明了、篇幅短小

## 测试

### 单元测试（推荐）
测试位于各业务模块和 `tests/` 目录下，使用 pytest 运行：
```bash
# 运行所有测试
pytest tests/ yys/*/test_*.py -v

# 只运行御魂模块测试（不需要游戏窗口）
pytest yys/soul_raid/test_soul_raid.py -v

# 运行公共模块测试
pytest tests/common/ -v
```
单元测试使用 Mock 环境，不依赖游戏窗口。

### 测试框架架构

```
tests/                          # 测试基础设施
├── conftest.py               # pytest 配置和 fixtures
├── common/                   # 公共测试基础设施
│   ├── environment/         # 环境抽象层
│   │   ├── base.py         # GameEnvironment 抽象基类
│   │   ├── mock_environment.py  # Mock 测试环境
│   │   └── windows_environment.py  # Windows 生产环境
│   ├── providers/           # 图片提供者
│   │   └── file_image_provider.py  # 从文件加载截图
│   ├── recorders/           # 操作记录器
│   │   ├── action_log.py    # 操作日志容器
│   │   ├── action_recorder.py  # 操作记录器
│   │   └── record_replay.py  # 录制-回放工具
│   ├── images/             # 测试用图片
│   └── test_*.py           # 公共模块测试
│
yys/                          # 业务模块
├── soul_raid/
│   ├── test_soul_raid.py   # 御魂模块测试
│   └── images/test/        # 御魂测试用图片
└── rifts_shadows/
    └── test_rifts_shadows_flow.py  # 狭间暗域测试
```

### Mock 测试示例

```python
from tests.common.environment.mock_environment import MockEnvironment
from tests.common.recorders.action_log import ActionLog

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
from tests.common.recorders.record_replay import ScenarioRecorder

recorder = ScenarioRecorder()
recorder.start_recording()

# ... 执行操作 ...

# 保存场景
screenshot = env.capture_screen()
recorder.save_scenario("soul_raid/battle_01", screenshot)
```

集成测试需要打开游戏窗口。
