# GUI资源、截图与狭间配置增强集成计划

## Parent Workflow

1. 不启动父任务实现；按顺序分别评审并启动资源、截图、狭间配置子任务。
2. 资源子任务通过质量门后，再启动依赖其 API 的截图子任务。
3. 狭间配置子任务可独立实施，但三个子任务完成前父任务不得归档。
4. 子任务全部完成后执行跨功能开发/打包/重装验收。
5. 对照父 PRD AC1-AC5 记录证据，再归档父任务。

## Integrated Validation

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_image_resource_overrides.py tests/common/test_event_screenshot_trigger.py tests/ui_backend/test_image_resources_api.py tests/ui_backend/test_screenshot_api.py tests/ui_backend/test_run_manager.py tests/ui_backend/test_run_observability.py tests/ui_backend/test_script_registry.py tests/ui_backend/test_app_api.py yys/abyss_shadows/test_abyss_shadows_flow.py -v
node --check gui/main.js
node --check gui/preload.js
node --check gui/renderer.js
node tests/gui/test_backend_detection.js
node tests/gui/test_renderer_config.js
git diff --check
```

真实产物：

```powershell
& '.\scripts\build_release.ps1' -Target nsis -SkipOcrDownload
```

- 启动打包后端并请求 `/api/scripts`、`/api/image-resources`、`/api/screenshots`。
- 完成一次空闲截图、一次运行缓存截图、一次裁剪替换和一次恢复默认。
- 覆盖安装新包后再次验证覆盖与截图库。

## Scope Guard

- 父任务不拥有生产文件，不创建额外协调层。
- 保留所有无关脏文件；提交只包含已启动子任务的明确文件。
- 离线单元测试不能替代真实游戏前台截图、运行中无扰动和安装包重装证据。
