# GUI图片资源替换与持久化实施计划

## Order

1. 在 `win_util/image.py` 增加持久化根解析、生产资源扫描、资源 ID 规范化，并让 `to_project_path()` 支持相对文件和项目内绝对文件覆盖；先补路径/目录/SceneManager 回归测试。
2. 增加后端资源服务和只接受清单资源 ID 的 API，完成二进制校验、目标格式重编码、同目录临时文件和原子替换。
3. 在 `gui/main.js` 传入 `YYS_USER_DATA_DIR`，保持现有 token、cwd 和打包后端探测契约；扩展 main 模块测试的 Electron stub。
4. 在 `gui/index.html`、`gui/renderer.js`、`gui/styles.css` 的设置页实现分组、搜索、缩略图、状态、文件替换和恢复默认。
5. 为截图子任务保留资源条目入口和复用函数，不在本子任务实现裁剪器。
6. 验证开发模式与真实打包模式均读取同一 `userData` 覆盖，且未提交的现有图片不被任务修改或提交。

## Expected Files

- `win_util/image.py`
- `ui_backend/app.py`
- `ui_backend/image_resources.py`（单个窄服务；若实现可直接保持在现有模块且更短，则不新建）
- `gui/main.js`
- `gui/index.html`
- `gui/renderer.js`
- `gui/styles.css`
- `tests/common/test_image_resource_overrides.py`
- `tests/ui_backend/test_image_resources_api.py`
- `tests/gui/test_backend_detection.js`

## Validation

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_image_resource_overrides.py tests/common/test_scene_manager.py tests/ui_backend/test_image_resources_api.py -v
node --check gui/main.js
node --check gui/renderer.js
node tests/gui/test_backend_detection.js
node tests/gui/test_renderer_config.js
git diff --check
```

手工/打包验收：

- 在源码模式替换普通事件图和 `SceneManager` 场景图，确认两类后续匹配都读取覆盖。
- 运行脚本时替换一次，确认 run 快照、焦点和输入记录不变。
- 构建 NSIS，替换图片后使用同应用 ID 的新安装包重新安装，确认覆盖仍生效。

## Risk and Rollback Points

- 修改 `to_project_path()` 影响所有模板调用；必须先跑路径、场景与至少一个业务模块回归。
- 不删除或改写内置资源；任何失败通过删除单个覆盖回滚。
- 不把 `yys/common_challenge/images/gained_reward.bmp` 或其他无关脏文件纳入任务提交。
