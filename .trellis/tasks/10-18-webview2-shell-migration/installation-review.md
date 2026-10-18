# 安装后检查与规划更新

日期：2026-10-18。安装会话：01a14ee9-f61e-7d82-bc25-b5f819aa2bf3，GPT-6 Luna / max。

## 结论

工具链安装验收通过，用户随后明确确认迁移策略，阶段 0 的工具和策略门槛均已通过。尚未执行实际迁移，也不据此在本会话启动阶段 1。本会话只检查证据、运行只读版本查询和更新任务文档，没有开发产品代码、重复构建探针或修改安装环境。

安装原始报告保留在 install-report.md，下面区分本会话直接复核结果与安装会话的构建验证。

## 本会话直接复核

| 项目 | 检查结果 |
|---|---|
| Rust | 绝对路径调用 rustc +1.99.1 --version --verbose，返回 1.99.1、host x86_64-pc-windows-msvc、LLVM 23.1.1。 |
| Cargo / Rustup | Cargo 1.99.1；1.99.1-x86_64-pc-windows-msvc 为 active/default。 |
| CLI | build/tauri-tools/node_modules/.bin/tauri.cmd --version 返回 tauri-cli 2.12.2；安装包清单版本也为 2.12.2。 |
| VS / SDK | vswhere 以 Windows10SDK.19041 组件查询到原 VS 2019 16.11.36422.26；SDK 10.0.19041.0 的 Windows.h、user32.lib、ucrt.lib、rc.exe 均存在，原 MSVC 14.29.30133 编译器路径仍存在。 |
| 依赖锁定 | build/tauri-deps-probe/Cargo.lock 中 tauri=2.12.3、tauri-build=2.7.2；共 407 个 package（含探针根包，即 406 个依赖）。 |
| 探针工件 | windows_link_probe.exe 为 126,464 bytes；目标目录中有 libtauri-c3ed2ae729bf80a0.rmeta（4,462,298 bytes），与安装会话成功记录一致。未在本会话运行这些工件。 |
| 数据保护 | 三份数据库快照的 SHA-256 均与原 manifest 一致，安装未更改这些快照。 |
| 忽略范围 | CLI 的 package-lock 与依赖探针 Cargo.lock 都被现有 build/ Git 忽略规则覆盖。 |
| 正式工程 | gui/src-tauri/Cargo.toml 和正式 Cargo.lock 均不存在；安装不能被记录为产品集成已完成。 |

安装会话记录：独立 Rust user32.lib 链接成功，隔离 tauri 2.12.3 / tauri-build 2.7.2 的 cargo check --target x86_64-pc-windows-msvc --locked 成功。原报告、精确版本清单、探针执行脚本及编译工件相符；本会话没有再次执行这些构建，不把 cargo check 当成正式宿主可运行或最终包验证通过。

## 环境注意点

- 当前 Codex 进程继承的 PATH 尚找不到 rustc，但用户级 PATH 已包含 C:/Users/56440/.cargo/bin；绝对路径调用已经验证可用。这属于旧进程环境未刷新，不是 Rust 安装失败。
- 后续可重开终端/应用以读取新环境，也可使用已验证的绝对工具路径；本会话不自动重启 Codex或系统。
- Node CLI 当前位于 build/tauri-tools；它是项目范围的安装准备环境，不是 gui/package.json 已集成的开发命令。正式工程和锁文件创建仍属于后续代码开发范围。
- NSIS 缓存复用、实际 portable 封装、Windows 10/11 产品矩阵及两个最终包 <100,000,000 bytes 都没有因安装完成而得到验证。
- 本会话未安装额外依赖、未操作 8000 端口、未启动/停止工作台或游戏、未暂存/提交代码。

## 已确认的迁移策略

用户于 2026-10-18 回复“是”，已确认下述策略；当前记录为规划决定，本会话不执行数据迁移或产品代码开发：

1. 业务库以用户当前使用的 portable 数据为已选迁移源，正式迁移前重新做一致性快照；不能直接把 20:00:08 的旧快照当作最新数据。
2. 首次将选定业务库复制导入旧 userData/config/ui_workbench.db 的永久位置，原库和安装版/开发版快照分别保留，不自动合并。目标已存在时不覆盖，转为明确冲突处理。
3. 后端资源 cwd 保留，未来单独提供绝对数据库路径输入；create_app 的显式 db_path 参数仍优先，无该配置时保持旧路径回退，不改变 api_token 或 user_data_dir 参数的职责。正式接口未实现。
4. 截图、图片覆盖、窗口状态仍保留原永久 userData 路径。
5. 用户确认首次 Tauri 启动仅主题和导航折叠恢复既有 UI 默认值，其后继续正常持久化；不引入 LevelDB 解析依赖，不清空旧 profile，不重置其他数据。
6. portable 程序载荷和缓存清理与这些永久数据分开；旧数据库位于临时目录的事实不能作为继续把新数据库放临时目录的理由。

统一迁移策略已获用户确认：当前 portable 业务库无损复制到永久目录，其他两库保留但不合并，首次主题/导航折叠恢复默认。阶段 0 两项策略门槛勾选通过；产品中的迁移执行与验收并未完成。

## 状态与下一步

- installation_thread：completed_verified。
- toolchain_gate：passed。
- phase0_gate：passed。
- current_stage：0；Trellis 总任务保持 in_progress。
- 本会话继续只检查、规划。即使迁移策略确认，也不在本会话自动进入产品代码开发。
