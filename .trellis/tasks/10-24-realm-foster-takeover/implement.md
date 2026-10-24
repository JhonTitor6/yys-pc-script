# 寄养试点执行计划

## 规划关口

- [x] 对齐目标，整理现有素材、原产品契约和接管矩阵。
- [x] 用户确认 D1 自动安全回退重选，已更新父子 PRD。
- [x] 目视复查 realm、friend_realm、growth、confirm、success，记录槽位语义和取消按钮遮挡问题。
- [x] 核验归属特征及取消/返回动作的完整前后帧；优先本地原始录制，缺失部分再补录。
- [x] 明确跨区和中途确认素材缺口，不用合成测试声称真实覆盖。
- [x] 本轮 PRD 收敛：F/B/FA 映射保留，Q1 已归入 D1；证据缺口与产品决策分开。
- [x] 素材核验完成后再次收敛设计并供用户审阅（结论见 design.md「2026-10-24 素材核验结论」）。
- [x] 用户要求实施，已 start；用户 2026-10-24 决定先补录制再改生产代码。
- [x] 产出补录清单 `recording-checklist.md` 与测试骨架 `yys/realm_foster/test_takeover_contract.py`（1 条启用，4 条待启用）。
- [x] 完成三段录制（成功 / 取消 / 跨区）并校验尺寸与事件；关键帧清单 `keyframes-2026-10-24.md`。

## 当前状态（2026-10-24）

录制关已过，可以开始改 `realm_foster_script.py`：先补好友结界主页标记与取消控件模板，再实现
`_classify` 与 D1 逐级恢复（好友育成页 → 好友结界主页 → 本人结界主页 → 本人育成页 → 列表）。
新寄养成功的「确定后」终态仍缺帧，先用旧 `success.png` 作正样本。

## 实施记录（2026-10-24）

- [x] 取消按钮模板从 c02 确认框帧裁切入库：`yys/realm_foster/images/cancel_button.png`（115×66），来源登记在 `tests/fixtures/realm_foster/sources.json`。
- [x] 新增脱敏夹具 `tests/fixtures/realm_foster/confirm_live.png`（只裁确认框主体，不含好友结界名）。
- [x] `realm_foster_script.py`：新增 `_classify` / `_takeover` / `_open_home_menu` / `_cancel_confirm` / `_open_list` / `_foster` / `_wait_stable`，重写 `_return_home`；删除「必须从庭院启动」的限制。
- [x] 测试：`yys/realm_foster` 38 passed（含本地真实关键帧用例，缺 recordings 时自动跳过）；`ruff check`、`py_compile`、`git diff --check` 通过。
- [ ] `tests/ui_backend` 回归未运行：沙箱拒绝 pytest 临时目录（23 个 setup 错误，与本次改动无关）。
- [x] 本人育成页（已寄养）实机通过：`fostered` → `already_fostering` → 返回庭院，零寄养确认。
- [x] 阴阳寮主页实机通过：`guild` → 结界 → 式神育成 → 已寄养 → 返回庭院。
- [ ] 确认框取消与回退实机未验。
- [ ] 新寄养成功终态实机未验（等寄养结束后补录）。

### 实施顺序核对

1. 场景分类与交叉负样本测试 —— 完成（`test_classifies_each_supported_start_scene`、`test_own_growth_page_owns_foster_open_marker`）。
2. 替换 home 前置限制，建立观察 → 目标判断 → 单步执行闭环 —— 完成（`_takeover`）。
3. 迁移扫描进度，保持 B1–B4 —— 扫描逻辑未改动，原回归通过。
4. 按 D1 实现已验证局部恢复 —— 完成（`_cancel_confirm` + 有界逐级返回）。
5. 补全终态及重复帧、跳页、暂停/停止/观察测试 —— 部分完成（终态与未知页用例已有，暂停/停止沿用原 `_click` 覆盖）。
6. 验证与审阅 —— 代码侧完成，实机待安排。

## 实施顺序（未执行）

1. 场景分类与交叉负样本测试，注释标注 FA1/FA2 产品契约。
2. 替换 home 前置限制，建立观察、目标判断、单步执行闭环。
3. 迁移扫描进度，保持 B1–B4 并加入依据失效规则。
4. 按 D1 实现已验证局部恢复，确认最多发送一次。
5. 补全终态及重复帧、跳页、暂停/停止/观察测试。
6. 验证与审阅；实机另行安排，不自动提交或归档。

## 验证命令

使用项目解释器，测试不查找或控制真实窗口：

    & 'D:/ProgramData/anaconda3/envs/win_macro/python.exe' -m pytest yys/realm_foster/test_realm_foster.py -q
    & 'D:/ProgramData/anaconda3/envs/win_macro/python.exe' -m pytest tests/ui_backend/test_run_manager.py tests/ui_backend/test_script_registry.py -q
    git diff --check

公共入口/场景/阵容确有修改才追加 tests/common/test_entry_runtime.py、test_scene_manager.py、test_lineup.py。

## 文件范围与回退

预期修改 yys/realm_foster/realm_foster_script.py 及 test_realm_foster.py；有证据需要时补最小脱敏模板、夹具及来源。
保留已有寄养/OCR/阵容未提交改动。实施前复查 status/diff，不使用整文件恢复。

## 当前验证边界

仅规划；上述业务测试未运行，新场景分类、恢复与实机接管未验证，不能宣称实现就绪。