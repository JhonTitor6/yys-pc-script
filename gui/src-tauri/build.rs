fn main() {
    // 构建前置条件：Node 在 PATH 上，且 gui/node_modules 已安装（裁剪器由 staging 复制）。
    let status = std::process::Command::new("node")
        .arg("../../scripts/stage-tauri.cjs")
        .status()
        .expect("需要 Node 执行静态资源 staging");
    assert!(status.success(), "静态资源 staging 失败");
    for path in [
        "../index.html",
        "../renderer.js",
        "../styles.css",
        "../desktop-bridge.js",
        "../icon.ico",
        "../../scripts/stage-tauri.cjs",
        "../../yys",
    ] {
        println!("cargo:rerun-if-changed={path}");
    }
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "desktop_bootstrap",
            "window_action",
            "is_maximized",
            "restore_gui_focus",
            "open_screenshot_directory",
            "open_image_resource_directory",
        ]),
    ))
    .expect("Tauri 权限或资源构建失败");
}
