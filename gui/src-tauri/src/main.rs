#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod policy;
#[cfg(feature = "smoke-test")]
mod smoke;
mod window_state;

use serde::Serialize;
use std::{
    fs,
    path::{Path, PathBuf},
    process::Child,
    sync::Mutex,
    time::Duration,
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

/// 启动计划：生产固定 8000；烟测可用独立端口和显式启动命令。
#[derive(Clone)]
struct StartupPlan {
    port: u16,
    launch: Option<backend::Launch>,
    timeout: Duration,
}

struct Desktop {
    user_data: PathBuf,
    bootstrap: Mutex<Bootstrap>,
    backend: Mutex<Option<Child>>,
    plan: StartupPlan,
}

fn authorize(window: &WebviewWindow) -> Result<(), String> {
    policy::authorize(window.label(), &window.url().map_err(|e| e.to_string())?)
}

#[tauri::command]
fn desktop_bootstrap(window: WebviewWindow, state: State<Desktop>) -> Result<Bootstrap, String> {
    authorize(&window)?;
    let bootstrap = state.bootstrap.lock().map_err(|_| "启动状态不可用")?;
    Ok(bootstrap.clone())
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

fn backend_ready(app: &tauri::AppHandle) -> bool {
    app.state::<Desktop>()
        .bootstrap
        .lock()
        .map(|bootstrap| bootstrap.ready)
        .unwrap_or(false)
}

fn tray_command(app: &tauri::AppHandle, command: &str) {
    if backend_ready(app) && matches!(command, "pause" | "stop") {
        let _ = app.emit_to(
            tauri::EventTarget::webview_window("main"),
            "tray-command",
            command,
        );
    }
}

fn setup_tray(app: &tauri::AppHandle) -> tauri::Result<()> {
    let ready = backend_ready(app);
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

fn setup_window(app: &tauri::AppHandle, user_data: &Path) -> tauri::Result<WebviewWindow> {
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

/// 后端就绪后才创建业务主窗口；烟测在窗口创建后接管。
fn open_main(app: &tauri::AppHandle) -> Result<(), String> {
    let root = app.state::<Desktop>().user_data.clone();
    let window = setup_window(app, &root).map_err(|error| error.to_string())?;
    setup_tray(app).map_err(|error| error.to_string())?;
    #[cfg(feature = "smoke-test")]
    smoke::after_window(app, &window).map_err(|error| error.to_string())?;
    #[cfg(not(feature = "smoke-test"))]
    let _ = window;
    Ok(())
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."))
}

fn resolve_launch(app: &tauri::AppHandle) -> Result<backend::Launch, String> {
    if cfg!(debug_assertions) {
        Ok(backend::dev_launch(&repo_root()))
    } else {
        let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
        Ok(backend::packaged_launch(&resources))
    }
}

/// 探测端口、启动受管后端、等待鉴权就绪，全部在后台线程完成。
fn startup(app: &tauri::AppHandle) -> Result<(), String> {
    let desktop = app.state::<Desktop>();
    let plan = desktop.plan.clone();
    // 烟测旧模式：假后端由测试器预先启动，直接开窗。
    if backend_ready(app) {
        let handle = app.clone();
        app.run_on_main_thread(move || {
            if let Err(error) = open_main(&handle) {
                report_failure(&handle, &format!("创建窗口失败：{error}"));
            }
        })
        .map_err(|e| e.to_string())?;
        return Ok(());
    }

    match backend::probe(&backend::generate_token(), plan.port) {
        backend::Probe::Free => {}
        backend::Probe::Protected => {
            return Err(format!(
                "端口 {} 已有受保护的桌面后端在运行，请先退出旧进程",
                plan.port
            ))
        }
        backend::Probe::Healthy => {
            return Err(format!(
                "端口 {} 已有可用的桌面后端在运行，请先退出旧进程",
                plan.port
            ))
        }
        backend::Probe::Occupied => {
            return Err(format!(
                "端口 {} 已被其他进程占用，无法启动桌面后端",
                plan.port
            ))
        }
    }

    let token = backend::generate_token();
    let launch = match plan.launch.clone() {
        Some(launch) => launch,
        None => resolve_launch(app)?,
    };
    let mut child = backend::spawn(&launch, &token, &desktop.user_data)?;
    if let Err(error) = backend::wait_ready(&mut child, &token, plan.port, plan.timeout) {
        backend::stop(&mut child);
        return Err(error);
    }
    {
        let mut bootstrap = desktop.bootstrap.lock().map_err(|_| "启动状态不可用")?;
        *bootstrap = Bootstrap {
            ready: true,
            api_base: format!("http://127.0.0.1:{}", plan.port),
            token,
            reason: String::new(),
        };
    }
    *desktop.backend.lock().map_err(|_| "后端句柄不可用")? = Some(child);

    let handle = app.clone();
    app.run_on_main_thread(move || {
        if let Err(error) = open_main(&handle) {
            report_failure(&handle, &format!("创建窗口失败：{error}"));
        }
    })
    .map_err(|e| e.to_string())
}

fn report_failure(app: &tauri::AppHandle, message: &str) {
    eprintln!("桌面宿主启动失败：{message}");
    #[cfg(feature = "smoke-test")]
    {
        // 烟测用文件记录失败，避免自动化被模态框卡住。
        let root = app.state::<Desktop>().user_data.clone();
        let _ = fs::write(root.join("startup-error.txt"), message);
    }
    #[cfg(not(feature = "smoke-test"))]
    show_message_box("阴阳师脚本工作台", message);
    app.exit(1);
}

#[cfg(not(feature = "smoke-test"))]
fn show_message_box(title: &str, message: &str) {
    use std::os::windows::ffi::OsStrExt;
    fn wide(value: &str) -> Vec<u16> {
        std::ffi::OsStr::new(value)
            .encode_wide()
            .chain(std::iter::once(0))
            .collect()
    }
    #[link(name = "user32")]
    unsafe extern "system" {
        fn MessageBoxW(hwnd: isize, text: *const u16, caption: *const u16, flags: u32) -> i32;
    }
    let text = wide(message);
    let caption = wide(title);
    // MB_OK | MB_ICONERROR | MB_SETFOREGROUND，缺少失败原因也可见。
    unsafe {
        MessageBoxW(0, text.as_ptr(), caption.as_ptr(), 0x0001_0010);
    }
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
            bootstrap: Mutex::new(Bootstrap {
                ready: false,
                api_base: format!("http://127.0.0.1:{}", backend::PORT),
                token: String::new(),
                reason: String::new(),
            }),
            backend: Mutex::new(None),
            plan: StartupPlan {
                port: backend::PORT,
                launch: None,
                timeout: backend::READY_TIMEOUT,
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
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                if let Err(error) = startup(&handle) {
                    report_failure(&handle, &error);
                }
            });
            Ok(())
        })
        .build(context)
        .expect("桌面宿主初始化失败")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Ok(mut guard) = app.state::<Desktop>().backend.lock() {
                    if let Some(mut child) = guard.take() {
                        backend::stop(&mut child);
                    }
                }
                if let Some(window) = app.get_webview_window("main") {
                    window_state::save(&window, &app.state::<Desktop>().user_data, false);
                }
            }
        });
}
