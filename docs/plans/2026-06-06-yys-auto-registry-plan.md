# YYS 自动注册功能实现计划

> 颗粒度对齐：7/7 分支已闭合；本计划是 grill-me 阶段产出，落地阶段按此执行。

| 项 | 值 |
|----|-----|
| 日期 | 2026-06-06 |
| 范围 | `YYSBaseScript` 子脚本自动注册到 GUI，支持配置面 |
| 目标 | 干掉 `config/ui_config.json` 手写 4 项 → 16+ 脚本全量自动暴露 |
| 风险等级 | 中（改 4 个文件、12 处字段引用、6 个回归测试点） |

---

## 1. 顶层设计（架构三层）

```
┌──────────────────────────────────────────────────────────────┐
│  ① Python 元数据层（D-2 内部表示）                              │
│  ────────────────────────────                                 │
│  TypedDict + Annotated[..., ConfigMeta(...)]                  │
│  ConfigMeta 字段:                                            │
│    default, min_value, max_value, options:[{value,label}],   │
│    label, group, help, hot_reloadable                        │
│  → IDE 可见、类型安全、单一事实源                              │
└──────────────────────────────────────────────────────────────┘
                              │ 扫描器反射读取
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  ② 翻译层（registry.py）                                       │
│  ────────────────────────────                                 │
│  字段名映射（D-2 内部 → wire format）:                         │
│    (内部已是 GUI 命名，无需翻译 — 因拍 B 档)                   │
│  输出 wire format:                                            │
│    [{script_id, display_name, category, description,         │
│      config_schema:[{key,label,field_type,min_value,         │
│                     max_value,options,default,               │
│                     hot_reloadable,help,group}],             │
│      default_config:{...}}]                                 │
└──────────────────────────────────────────────────────────────┘
                              │ FastAPI 端点
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  ③ GUI 渲染层（renderer.js，**字段名与 D-2 对齐**）             │
│  ────────────────────────────                                 │
│  GET /api/scripts → 渲染脚本列表 + 表单                       │
│  PATCH /api/scripts/{id}/config → 落盘 + 按 hot_reloadable    │
│                                   决定是否注入当前 run          │
│  POST /api/runs/start → 启动脚本（携带 config dict）          │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 7 个分支决策汇总（grill-me 沉淀）

| # | 分支 | 决策 | 拒绝项 |
|---|------|------|--------|
| 1 | 颗粒度 | **B**（Metadata 级） | A 名字级（配置面太薄）/ C 完全动态（过度设计） |
| 2 | schema 形式 | **D-2**（TypedDict + Annotated） | C 显式 dict（用户纠正了预判）/ D-1 双声明（割裂） |
| 3 | 发现机制 | **A** importlib 自动扫 + **A1** ABCMeta 抽象 | B 显式清单（违背"自动"）/ C entry_points（过度）/ D 装饰器（隐式） |
| 4 | 配置入口 | **A** 构造注入 `__init__(name, config=None, env=None)` | B setter 散装（多校验点）/ C 全局 bus（多实例冲突）/ D 混合（双 API） |
| 5 | 持久化 | **C** `config/script_registry.json` 单一文件 | A 沿用 ui_config.json（无 script_name 层）/ B 拆分（16 文件）/ D sqlite（过度） |
| 6 | GUI↔后端协议 | **B** 改前端对齐 D-2 | A 翻译层（用户拍改前端）/ C 改 D-2 背离 Python 习惯 |
| 7 | 热重载 | **B** 部分字段热重载 + **B2** 默默落盘当前 run 忽略 | A 全部冷重载（弱体验）/ C 全部热重载（竞态 3.25）/ D 弹提示（多状态机） |

---

## 3. 文件改动清单

| # | 文件 | 动作 | 关键改动 |
|---|------|------|----------|
| 1 | `yys/common/script_meta.py` | **新建** | `ConfigMeta` dataclass + `ScriptMeta` dataclass（display_name, category, config_schema, default_config, hot_reloadable_set） |
| 2 | `yys/common/event_script_base.py` | **改** | `class YYSBaseScript(EventBaseScript, metaclass=ABCMeta)` + `@abstractmethod on_run` + 新 `__init__(self, script_name, config=None, env=None)` 签名 + `_apply_config(config: dict)` 单一入口 + `_register_hot_reload_listeners()` 钩子 |
| 3 | `yys/common/registry.py` | **新建** | `Registry` 单例类：`__init__` 调用 `importlib` 扫 `yys/` 子包找 `YYSBaseScript` 非抽象子类；`list_scripts()` 输出 wire format；`get(script_id)` 返回类；`apply_config_to_running(script_id, key, value)` 按 `hot_reloadable` 决定 |
| 4 | `ui_backend/main.py` | **新建端点** | `GET /api/scripts` → 调 `Registry.list_scripts()`；`PATCH /api/scripts/{script_id}/config` → 落盘到 `config/script_registry.json` + 调 `Registry.apply_config_to_running()`；`POST /api/runs/start` → 接收 `{script_id, config}` dict，调 `script_cls(script_name, config=config)` |
| 5 | `config/script_registry.json` | **新建** | 初始为空 `{}`，首次 `GET /api/scripts` 自动写入所有脚本的 `default_config` |
| 6 | `config/ui_config.json` | **归档** | 重命名为 `config/ui_config.json.bak` 备份，4 个 task 的 max_battle_count 一次性迁入新文件 |
| 7 | `gui/renderer.js` | **改 12 处** | 见 §4 字段名映射表，**全文保持 `field_type`/`min_value`/`max_value` 命名**（已是 D-2 命名） |

> 注：因拍 B 档，**字段名实际已是 GUI 现有命名**，`renderer.js` 改动只涉及**让 `config_schema` 字段值来自 D-2 元数据**（之前是从某个 dict 写死），不需要改 `field_type` 这种 key 名 —— **实际改动面比 12 处小**，落到代码时用 Grep 确认具体行数。

---

## 4. 字段名映射表（D-2 内部 ↔ wire format ↔ GUI 渲染）

| D-2 内部（ConfigMeta 字段） | wire format（HTTP JSON） | GUI 渲染（renderer.js:139-163 现有代码） |
|------|------|------|
| `default` | `default` | `defaults[key] ?? field.default ?? ''`（renderer.js:141） |
| `min_value` | `min_value` | `field.min_value`（renderer.js:160） |
| `max_value` | `max_value` | `field.max_value`（renderer.js:161） |
| `options: [{value, label}]` | `options: [{value, label}]` | `field.options`（renderer.js:146） |
| `label` | `label` | `field.label`（renderer.js:142） |
| `field_type` | `field_type` | `field.field_type`（renderer.js:145/154/159） |
| `hot_reloadable` | `hot_reloadable` | **新增**（PATCH 响应里返回是否已生效） |
| `help` | `help` | **新增**（表单 tooltip） |
| `group` | `group` | **新增**（表单分组） |

**结论：因 B 档，wire format 与 GUI 渲染命名 1:1，零翻译 —— 翻译层只是数据形状拼装。**

---

## 5. 实施步骤（5 步 + 每步 verify 钩子）

### Step 1 · 建元数据 + 抽象基类
**改动**：
- 新建 `yys/common/script_meta.py`：定义 `ConfigMeta` + `ScriptMeta` dataclass
- 改 `yys/common/event_script_base.py`：
  - `class YYSBaseScript(EventBaseScript, metaclass=ABCMeta)`
  - `@abstractmethod def on_run(self): ...`
  - `__init__(self, script_name, config=None, env=None)` + 调 `_apply_config(config)`
  - 新 `_apply_config(config: dict)` 方法：按 `SCRIPT_META.config_schema` 校验 + 注入实例属性

**verify 钩子**：
```bash
pytest tests/common/ yys/*/test_*.py -v
# 预期：40 passed, 3 failed（pre-existing），无新增失败
python -c "from yys.common.event_script_base import YYSBaseScript; YYSBaseScript('test', None)"
# 预期：TypeError（不能实例化抽象类）—— 证明 ABCMeta 生效
```

### Step 2 · 一个示例脚本先跑通（**冰山起点**）
**改动**：
- 选 `yys/soul_raid/soul_raid_script.py` 作为 P0
- 加 `SCRIPT_META = ScriptMeta(display_name="御魂", category="日常", config_schema=SoulRaidConfig, default_config={...})`
- 用 D-2 形式声明 `SoulRaidConfig`（TypedDict + Annotated）

**verify 钩子**：
```bash
python -c "
from yys.common.registry import Registry
r = Registry()
scripts = r.list_scripts()
assert any(s['script_id'] == 'soul_raid' for s in scripts), 'soul_raid 未注册'
print('OK:', [s['script_id'] for s in scripts])
"
# 预期：输出含 'soul_raid'，证明扫描器工作
```

### Step 3 · 桥接 SCRIPT_META 到现有 registry（owner 调整后范围）

> **Plan 错位说明（owner 拉通 2026-06-06）**：写 plan 时未 Read 现有 `ui_backend/` 架构，**实际 80% 已实现**。Step 3 真实工作从"新建"转为"扩展"。

**改动**：
1. **`yys/soul_raid/soul_raid_script.py`**：加 `get_config_schema()` 类方法（从 `SCRIPT_META` 反射 `Annotated[..., ConfigMeta(...)]`）
2. **`ui_backend/scripts/registry.py`**：改 `_schema_items_for` 总是先尝试 `_schema_from_class` 反射（不只 custom entries）
3. **`ui_backend/runs/manager.py`**：改 `start()` 用 `script_class(script_id, config=...)` 构造注入（**不**用 setter 散装调）
4. **单测**：`tests/ui_backend/test_script_registry.py` + `tests/ui_backend/test_run_manager.py`（≥ 6 case）
5. **端到端 verify**：启动 web_server + curl + 启动脚本

**持久化**：保留 SQLite (`config/ui_workbench.db`) + `ScriptUserConfigRepository`，**不**用 plan 写的 `config/script_registry.json`（已超越）

**Spec Gap（Step 3 实施时 owner 拉通发现）**：
- soul_raid `__init__(self, env=None, config=None)` **缺 `script_name` 第一位置参数**，与 `YYSBaseScript.__init__(script_name, config, env)` 签名不兼容
- `RunManager.start` 调 `script_class(request.script_id, config=...)` 时 `request.script_id` 作为第一位置参数 → soul_raid 把它当 `env`（字符串）→ `self._env.find_window("阴阳师")` 抛 `AttributeError: 'str' object has no attribute 'find_window'`
- **子任务自测用 mock 替身**（`_ScriptWithConfig`）**未暴露**真实端到端 bug
- **owner 教训**：所有"自动注册/构造注入"类 verify hook **必须**真实 import + 真实实例化（不 mock），否则冰山下炸

**fix 决策**：soul_raid `__init__` 签名改为 `(self, script_name: str = "soul_raid", env=None, config=None)`，**与 base 一致**。`super().__init__(script_name, env=env, config=config)`。

**verify 钩子**：
```bash
# 启动 web_server
python -m ui_backend.main &
sleep 3
curl -s http://127.0.0.1:8000/api/scripts | python -m json.tool
# 预期：返回 JSON 数组，至少含 soul_raid，且 config_schema 字段非空（min_value/max_value/options 来自 SCRIPT_META 反射）
curl -s -X PATCH http://127.0.0.1:8000/api/scripts/soul_raid/config \
  -H "Content-Type: application/json" \
  -d '{"max_battle_count": 50}' | python -m json.tool
# 预期：返回 {"status": "ok"}（SQLite 落盘到 script_user_configs 表）
# 启动脚本：构造注入 config 路径
python -c "
from ui_backend.scripts.registry import ScriptRegistry
from ui_backend.scripts.default_registry import DEFAULT_SCRIPT_ENTRIES
r = ScriptRegistry(entries=DEFAULT_SCRIPT_ENTRIES)
cls = r.load_class('soul_raid')
# 注：5 个走老路径的子类（douji/omoikane/yuling/loop_challenge/script_main）仍走老路径
# 仅 soul_raid 走新构造注入（已加 get_config_schema 类方法 + __init__ 透传 config）
script = cls('soul_raid', config={'max_battle_count': 200, 'accept_wq_type': 1, 'loop_interval': 7})
print(f'max_battle_count={script.max_battle_count} (预期 200)')
"
# 预期：max_battle_count=200

# 真实端到端（不 mock）— 修签名后必须能启动
python -c "
from fastapi.testclient import TestClient
from ui_backend.app import create_app
app = create_app(db_path='config/test.db')
client = TestClient(app)
resp = client.post('/api/runs/start', json={'script_id': 'soul_raid', 'config': {'max_battle_count': 5}})
assert resp.status_code == 200, resp.text
print('真实 soul_raid 启动 PASS:', resp.json())
"
```

### Step 4 · GUI 端 wire 起来
**改动**：
- `gui/renderer.js`：`init()` 已有的 `apiGet('/api/scripts')` 现在能拿到完整 schema（之前是空的，**因为后端端点未实现**）
- PATCH 流程已在 `renderer.js:190-194`，但需**新增「热重载结果」toast/log 提示**（B2 决策：默默落盘 + 文案提示）

**verify 钩子**：
- 启动 Electron：`cd gui && npm start`
- 肉眼验证：脚本列表出现所有 16+ 个脚本；点开表单字段齐全
- 改 `max_battle_count` 点保存 → log 区出现「配置已保存」或「已生效」文案
- GUI 健康探针：`main.js:65-72` 已要求至少 `soul_raid` 出现 → 启动后 tray icon 不报 unhealthy

### Step 5 · 一次性迁移 + 16 脚本全量迁移
**改动**：
- 写 `tools/migrate_ui_config.py`（一次性）：读 `config/ui_config.json`（4 项）→ 按 task name 模糊匹配 `display_name` → 写入 `config/script_registry.json`
- 16 个脚本逐个加 `SCRIPT_META` + `XxxConfig` TypedDict（**P7 子任务并行**，可分批）

**verify 钩子**：
```bash
python -c "
import json
with open('config/script_registry.json') as f: reg = json.load(f)
print('注册的脚本数:', len(reg.get('scripts', {})))
"
# 预期：16（与 yys/ 子包数一致）
# 冷启动：杀掉 Python，重启 → 验证 config 从文件读出来，所有脚本 default 生效
```

---

## 6. 回归测试清单（6 个必过点）

| # | 覆盖点 | 来源 | 验证方式 |
|---|--------|------|----------|
| 1 | `init()` 拿 scripts 不为空 | renderer.js:897 | 启动 Electron，log 不出现 ERROR |
| 2 | `renderField` 三种 widget 渲染 | renderer.js:139-163 | 肉眼 + 截图对比 3 个不同 field_type |
| 3 | `startScript` PATCH + POST 串联 | renderer.js:175-197 | 改字段 → 保存 → 当前 run 区出现「已运行」 |
| 4 | `saveWorkflow` 工作流保存 | renderer.js:207-275 | 新建编排 → 选脚本 → 步骤字段被填入 |
| 5 | Modal dirty 检测 | renderer.js:785-810 | 改字段 → 关闭 → 弹「有未保存修改」 |
| 6 | WebSocket 实时更新 | renderer.js:665-687 | 启动脚本 → log 区持续出现新条目 |

---

## 7. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|:---:|------|
| `renderer.js` 字段名漏改一处 | 中 | **Grep 兜底**：`grep -n "field\.widget\|field\.min[^_]\|field\.max[^_]" gui/renderer.js` 必须 0 结果 |
| ABCMeta 改完导致 16 个子类没实现 `on_run` 而炸 | 中 | **子类先 grep**：`grep -L "def on_run" yys/*/[a-z]*_script.py` 必须为空 |
| importlib 扫不到某个脚本 | 低 | **日志断言**：registry 启动时 `len(list_scripts()) == 16`，不等就抛异常（fail-fast） |
| `config/script_registry.json` 损坏 | 低 | 落盘前 `json.load` 校验 + 备份到 `.bak` |
| 热重载竞态 | 低 | B 档只对 `_cur_battle_count >= self._max_battle_count` 这种**下一轮才读**的字段生效，**脚本内已有 sleep 兜底**（`event_script_base.py:280`） |

---

## 8. 验收标准（DoD）

- [ ] 16 个脚本全部出现在 GUI 列表，**无需修改 `config/*.json`**
- [ ] 新建 `yys/foo/foo_script.py` 继承 `YYSBaseScript` + 声明 `SCRIPT_META` → **重启后端即出现在 GUI**（端到端验证）
- [ ] 改 `max_battle_count` → PATCH → 落盘 → 当前 run 立即读到新值（hot_reloadable=true）
- [ ] 改 `loop_interval` → PATCH → 落盘 → 当前 run 忽略（B2 决策）→ 下次启动读新值
- [ ] 6 个回归测试点全过
- [ ] `config/ui_config.json.bak` 备份存在
- [ ] `docs/specs/2026-06-06-yys-auto-registry-design.md` 同步产出（**设计规格单独存档**）

---

## 9. 不在本次范围（冰山外）

- ❌ 抽象基类方法 `on_run` 之外的方法（`before_iteration`/`after_iteration`）不参与 schema
- ❌ 编排（workflow）的 schema 不变（workflow 已有自己的 schema，不依赖 script registry）
- ❌ 跨窗口 / 多实例 / 远程调用场景（**当前架构单实例**，未来再拉通）
- ❌ i18n / 多语言（display_name 中文 OK，未来再抽 i18n key）
- ❌ WebSocket 推送 schema 变更（**当前 GUI 启动拉一次即可**，B 档拍冷重载额外字段）

---

## 10. 后续行动（落地阶段）

| 步骤 | 触发 | 产物 |
|------|------|------|
| 1. 写 `docs/specs/2026-06-06-yys-auto-registry-design.md` | 本 plan 通过 | 设计规格存档 |
| 2. 拆 P7 子任务 | 设计 spec 通过 | TaskCreate 任务清单 |
| 3. P7-1：Step 1 + Step 2（基类 + 示例） | 任务派发 | PR #1 |
| 4. P7-2：Step 3（registry + 端点） | 独立 PR | PR #2 |
| 5. P7-3：Step 4 + Step 5（GUI wire + 16 脚本迁移） | 独立 PR | PR #3 |
| 6. 回归测试 + DoD 自检 | 三个 PR merge 后 | 验收报告 |
