#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod policy;
#[cfg(feature = "smoke-test")]
mod smoke;
mod window_state;

use serde::Serialize;
use std::{
    fs,
    path::{Path, PathBuf},
};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager, State, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct Bootstrap {
    ready: bool,
    api_base: String,
    token: String,
    reason: String,
}

struct Desktop {
    user_data: PathBuf,
    bootstrap: Bootstrap,
}

fn authorize(window: &WebviewWindow) -> Result<(), String> {
    policy::authorize(window.label(), &window.url().map_err(|e| e.to_string())?)
}

#[tauri::command]
fn desktop_bootstrap(window: WebviewWindow, state: State<Desktop>) -> Result<Bootstrap, String> {
    authorize(&window)?;
    Ok(state.bootstrap.clone())
}

#[derive(Clone, Serialize)]
struct WindowState {
    maximized: bool,
}

#[tauri::command]
fn window_action(
    window: WebviewWindow,
    action: policy::WindowAction,
) -> Result<WindowState, String> {
    authorize(&window)?;
    let result = match action {
        policy::WindowAction::Minimize => window.minimize(),
        policy::WindowAction::ToggleMaximize => {
            if window.is_maximized().map_err(|e| e.to_string())? {
                window.unmaximize()
            } else {
                window.maximize()
            }
        }
        policy::WindowAction::Close => window.hide(),
        policy::WindowAction::Drag => window.start_dragging(),
    };
    result.map_err(|e| e.to_string())?;
    let state = WindowState {
        maximized: window.is_maximized().map_err(|e| e.to_string())?,
    };
    window
        .emit_to(
            tauri::EventTarget::webview_window("main"),
            "window-state",
            &state,
        )
        .map_err(|e| e.to_string())?;
    Ok(state)
}

#[tauri::command]
fn is_maximized(window: WebviewWindow) -> Result<bool, String> {
    authorize(&window)?;
    window.is_maximized().map_err(|e| e.to_string())
}

fn show_main(window: &WebviewWindow) -> tauri::Result<()> {
    if window.is_minimized()? {
        window.unminimize()?;
    }
    window.show()?;
    window.set_focus()
}

#[tauri::command]
fn restore_gui_focus(window: WebviewWindow) -> Result<bool, String> {
    authorize(&window)?;
    show_main(&window).map_err(|e| e.to_string())?;
    Ok(true)
}

#[derive(Serialize)]
struct OpenResult {
    opened: bool,
    reason: Option<String>,
}

fn open_directory(target: Result<PathBuf, String>, select: bool) -> OpenResult {
    let result = target.and_then(|path| {
        #[cfg(feature = "smoke-test")]
        {
            let _ = (path, select);
            Ok(())
        }
        #[cfg(not(feature = "smoke-test"))]
        {
            use std::os::windows::process::CommandExt;
            let windows = std::env::var_os("WINDIR").ok_or("缺少 Windows 系统目录")?;
            let mut command =
                std::process::Command::new(PathBuf::from(windows).join("explorer.exe"));
            if select {
                command.arg("/select,");
            }
            command
                .arg(path)
                .creation_flags(0x08000000)
                .spawn()
                .map(|_| ())
                .map_err(|e| e.to_string())
        }
    });
    OpenResult {
        opened: result.is_ok(),
        reason: result.err(),
    }
}

#[tauri::command]
fn open_screenshot_directory(
    window: WebviewWindow,
    state: State<Desktop>,
) -> Result<OpenResult, String> {
    authorize(&window)?;
    Ok(open_directory(
        policy::screenshot_directory(&state.user_data),
        false,
    ))
}

#[tauri::command]
fn open_image_resource_directory(
    window: WebviewWindow,
    state: State<Desktop>,
    resource_id: String,
) -> Result<OpenResult, String> {
    authorize(&window)?;
    Ok(open_directory(
        policy::image_path(&state.user_data, &resource_id),
        true,
    ))
}

fn tray_command(app: &tauri::AppHandle, command: &str) {
    if app.state::<Desktop>().bootstrap.ready && matches!(command, "pause" | "stop") {
        let _ = app.emit_to(
            tauri::EventTarget::webview_window("main"),
            "tray-command",
            command,
        );
    }
}

fn setup_tray(app: &tauri::App) -> tauri::Result<()> {
    let ready = app.state::<Desktop>().bootstrap.ready;
    let show = MenuItem::with_id(app, "show", "显示工作台", true, None::<&str>)?;
    let pause = MenuItem::with_id(app, "pause", "暂停当前脚本", ready, None::<&str>)?;
    let stop = MenuItem::with_id(app, "stop", "停止当前脚本", ready, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let exit = MenuItem::with_id(app, "exit", "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &pause, &stop, &separator, &exit])?;
    TrayIconBuilder::with_id("workbench")
        .icon(tauri::include_image!("../icon.ico"))
        .tooltip("阴阳师脚本工作台")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = show_main(&window);
                }
            }
            "pause" | "stop" => tray_command(app, event.id.as_ref()),
            "exit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if matches!(event, TrayIconEvent::DoubleClick { .. }) {
                if let Some(window) = tray.app_handle().get_webview_window("main") {
                    let _ = show_main(&window);
                }
            }
        })
        .build(app)?;
    Ok(())
}

fn setup_window(app: &tauri::App, user_data: &Path) -> tauri::Result<WebviewWindow> {
    let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
        .title("阴阳师脚本工作台")
        .inner_size(900.0, 650.0)
        .min_inner_size(800.0, 600.0)
        .decorations(false)
        // 当前 Tao 的无边框阴影会在恢复尺寸时额外计入隐藏标题栏高度。
        .shadow(false)
        .resizable(true)
        .visible(false)
        .use_https_scheme(false)
        .data_directory(user_data.join("WebView2"))
        .on_navigation(|url| policy::trusted_url(url))
        .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
        .on_download(|_, _| false)
        .on_page_load(|window, payload| {
            #[cfg(feature = "smoke-test")]
            if matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                smoke::page_loaded(&window);
            }
            #[cfg(not(feature = "smoke-test"))]
            let _ = (window, payload);
        })
        .build()?;
    window_state::restore(&window, user_data);
    let event_window = window.clone();
    let root = user_data.to_owned();
    window.on_window_event(move |event| match event {
        tauri::WindowEvent::CloseRequested { api, .. } => {
            api.prevent_close();
            window_state::save(&event_window, &root, false);
            let _ = event_window.hide();
        }
        tauri::WindowEvent::Moved(_)
        | tauri::WindowEvent::Resized(_)
        | tauri::WindowEvent::ScaleFactorChanged { .. } => {
            window_state::save(&event_window, &root, true);
            if let Ok(maximized) = event_window.is_maximized() {
                let _ = event_window.emit_to(
                    tauri::EventTarget::webview_window("main"),
                    "window-state",
                    WindowState { maximized },
                );
            }
        }
        _ => {}
    });
    window.show()?;
    Ok(window)
}

fn main() {
    let mut context = tauri::generate_context!();
    #[cfg(feature = "smoke-test")]
    let desktop = smoke::prepare(&mut context).expect("隔离烟测准备失败");
    #[cfg(not(feature = "smoke-test"))]
    let desktop = {
        let _ = &mut context;
        Desktop {
            user_data: PathBuf::from(std::env::var_os("APPDATA").expect("缺少 APPDATA"))
                .join("yys-script-manager"),
            bootstrap: Bootstrap {
                ready: false,
                api_base: "http://127.0.0.1:8000".into(),
                token: String::new(),
                reason: "后端尚未接入；当前为桌面宿主阶段。请使用现有 Electron 工作台处理业务。"
                    .into(),
            },
        }
    };
    tauri::Builder::default()
        .manage(desktop)
        .invoke_handler(tauri::generate_handler![
            desktop_bootstrap,
            window_action,
            is_maximized,
            restore_gui_focus,
            open_screenshot_directory,
            open_image_resource_directory
        ])
        .setup(|app| {
            let root = app.state::<Desktop>().user_data.clone();
            fs::create_dir_all(&root)?;
            let window = setup_window(app, &root)?;
            setup_tray(app)?;
            #[cfg(feature = "smoke-test")]
            smoke::run(app, &window)?;
            #[cfg(not(feature = "smoke-test"))]
            let _ = window;
            Ok(())
        })
        .build(context)
        .expect("桌面宿主初始化失败")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Some(window) = app.get_webview_window("main") {
                    window_state::save(&window, &app.state::<Desktop>().user_data, false);
                }
            }
        });
}
