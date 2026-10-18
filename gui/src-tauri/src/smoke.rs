// 仅显式 smoke-test 构建存在；生产构建没有端口覆盖和烟测注入入口。
use super::*;
use serde::Deserialize;
use std::time::Duration;

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Config {
    api_base: String,
    token: String,
}

/// 校验独立测试目录和端口，仅替换烟测构建的启动信息。
pub fn prepare(
    context: &mut tauri::Context<tauri::Wry>,
) -> Result<Desktop, Box<dyn std::error::Error>> {
    eprintln!("YYS_TAURI_STAGE1_SMOKE_ONLY");
    let base = dunce::canonicalize(Path::new(env!("CARGO_MANIFEST_DIR")).join("../../build"))?;
    let root =
        PathBuf::from(std::env::var_os("YYS_TAURI_SMOKE_ROOT").ok_or("必须指定隔离烟测目录")?);
    let root = policy::contained(&base, &root)?;
    if root == base {
        return Err("不能直接使用 build 根目录".into());
    }
    let config: Config = serde_json::from_slice(&fs::read(root.join("config.json"))?)?;
    let url = tauri::Url::parse(&config.api_base)?;
    if url.scheme() != "http"
        || url.host_str() != Some("127.0.0.1")
        || url.port().is_none_or(|p| p == 8000 || p == 0)
        || url.path() != "/"
        || url.query().is_some()
        || !url.username().is_empty()
        || config.token.len() < 32
    {
        return Err("隔离后端只能使用独立 loopback 端口".into());
    }
    let csp = context
        .config()
        .app
        .security
        .csp
        .as_ref()
        .ok_or("必须启用 CSP")?
        .to_string();
    context.config_mut().app.security.csp = Some(tauri::utils::config::Csp::Policy(
        csp.replace("http://127.0.0.1:8000", &config.api_base)
            .replace(
                "ws://127.0.0.1:8000",
                &config.api_base.replace("http:", "ws:"),
            ),
    ));
    Ok(Desktop {
        user_data: root,
        bootstrap: Bootstrap {
            ready: true,
            api_base: config.api_base,
            token: config.token,
            reason: String::new(),
        },
    })
}

/// 在真实页面完成加载后执行受编译特性约束的验收脚本。
pub fn page_loaded(window: &WebviewWindow) {
    let bootstrap = &window.state::<Desktop>().bootstrap;
    let prefix = format!(
        "window.smokeEndpoint = {}; window.smokeToken = {};",
        serde_json::to_string(&bootstrap.api_base).unwrap(),
        serde_json::to_string(&bootstrap.token).unwrap()
    );
    let script = if window.label() == "main" {
        include_str!("../../../tests/gui/tauri-smoke.js")
    } else {
        r#"
        (async () => {
          let denied = false;
          try { await window.__TAURI__.core.invoke('desktop_bootstrap'); } catch { denied = true; }
          await fetch(smokeEndpoint + '/smoke/other', { method: 'POST', headers: {'X-YYS-UI-Token': smokeToken}, body: JSON.stringify({denied}) });
        })();
    "#
    };
    let _ = window.eval(format!("{prefix}\n{script}"));
}

/// 创建无权限对照窗口，收到报告后退出本次宿主。
pub fn run(app: &tauri::App, window: &WebviewWindow) -> tauri::Result<()> {
    let root = app.state::<Desktop>().user_data.clone();
    let size = window
        .inner_size()?
        .to_logical::<f64>(window.scale_factor()?);
    let position = window.outer_position()?;
    let visible = window.available_monitors()?.iter().any(|monitor| {
        let area = monitor.work_area();
        position.x >= area.position.x
            && position.y >= area.position.y
            && position.x < area.position.x + area.size.width as i32
            && position.y < area.position.y + area.size.height as i32
    });
    let (minimum, resize_left) = inspect_native(window)?;
    fs::write(root.join("native.json"), serde_json::to_vec(&serde_json::json!({"width":size.width,"height":size.height,"decorated":window.is_decorated()?,"resizable":window.is_resizable()?,"visible_on_screen":visible,"minimum":minimum,"resize_left":resize_left})).unwrap()).unwrap();
    WebviewWindowBuilder::new(app, "untrusted", WebviewUrl::App("index.html".into()))
        .visible(false)
        .use_https_scheme(false)
        .data_directory(root.join("WebView2"))
        .on_page_load(|window, payload| {
            if matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                page_loaded(&window);
            }
        })
        .build()?;
    let handle = app.handle().clone();
    std::thread::spawn(move || {
        for _ in 0..300 {
            std::thread::sleep(Duration::from_millis(200));
            let trigger = root.join("tray-request");
            if trigger.exists() {
                let _ = fs::remove_file(trigger);
                tray_command(&handle, "pause");
                tray_command(&handle, "stop");
            }
            if root.join("report.json").exists() && root.join("other.json").exists() {
                handle.exit(0);
                return;
            }
        }
        handle.exit(1);
    });
    Ok(())
}

fn inspect_native(window: &WebviewWindow) -> tauri::Result<((f64, f64), bool)> {
    #[repr(C)]
    #[derive(Default)]
    struct Point {
        x: i32,
        y: i32,
    }
    #[repr(C)]
    #[derive(Default)]
    struct MinMax {
        reserved: Point,
        max_size: Point,
        max_position: Point,
        min_track: Point,
        max_track: Point,
    }
    #[link(name = "user32")]
    unsafe extern "system" {
        fn SendMessageW(hwnd: isize, message: u32, wparam: usize, lparam: isize) -> isize;
    }
    let hwnd = window.hwnd()?.0 as isize;
    let mut bounds = MinMax::default();
    let position = window.outer_position()?;
    let size = window.outer_size()?;
    let x = position.x + 1;
    let y = position.y + size.height as i32 / 2;
    let point = ((y as u32 & 0xffff) << 16 | (x as u32 & 0xffff)) as isize;
    // 仅向本次创建的窗口查询最小尺寸与边缘命中，不发送鼠标或游戏输入。
    let hit = unsafe {
        SendMessageW(hwnd, 0x0024, 0, &mut bounds as *mut MinMax as isize);
        SendMessageW(hwnd, 0x0084, 0, point)
    };
    let scale = window.scale_factor()?;
    Ok((
        (
            bounds.min_track.x as f64 / scale,
            bounds.min_track.y as f64 / scale,
        ),
        hit == 10,
    ))
}
