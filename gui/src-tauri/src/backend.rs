//! 后端进程的端口探测、启动与鉴权就绪等待。

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

/// 生产固定端口，不随配置漂移。
pub const PORT: u16 = 8000;
const HOST: &str = "127.0.0.1";
/// 等待后端鉴权健康的最长时间。
pub const READY_TIMEOUT: Duration = Duration::from_secs(30);
const POLL_INTERVAL: Duration = Duration::from_millis(500);

#[derive(Clone, Debug, PartialEq)]
pub enum Probe {
    /// 端口空闲，可以启动本宿主管理的后端。
    Free,
    /// 已有本产品后端且使用当前 token 应答。
    Healthy,
    /// 已有受保护的桌面后端（token 不匹配）。
    Protected,
    /// 其他进程占用端口。
    Occupied,
}

#[derive(Clone)]
pub struct Launch {
    pub program: PathBuf,
    pub args: Vec<String>,
    pub cwd: PathBuf,
}

/// 生成每次启动唯一的 32 字节十六进制 token。
pub fn generate_token() -> String {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("系统随机源不可用");
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn address(port: u16) -> SocketAddr {
    SocketAddr::from(([127, 0, 0, 1], port))
}

/// 探测端口状态；只有能读到本产品 /api/scripts 才算健康。
pub fn probe(token: &str, port: u16) -> Probe {
    if TcpStream::connect_timeout(&address(port), Duration::from_millis(600)).is_err() {
        return Probe::Free;
    }
    match request_scripts(token, port) {
        Some((200, body)) if looks_like_scripts(&body) => Probe::Healthy,
        Some((403, _)) => Probe::Protected,
        _ => Probe::Occupied,
    }
}

fn request_scripts(token: &str, port: u16) -> Option<(u16, String)> {
    let mut stream = TcpStream::connect_timeout(&address(port), Duration::from_millis(800)).ok()?;
    stream
        .set_write_timeout(Some(Duration::from_secs(2)))
        .ok()?;
    stream.set_read_timeout(Some(Duration::from_secs(3))).ok()?;
    let request = format!(
        "GET /api/scripts HTTP/1.1\r\nHost: {HOST}:{port}\r\nX-YYS-UI-Token: {token}\r\nConnection: close\r\n\r\n"
    );
    stream.write_all(request.as_bytes()).ok()?;
    let mut raw = String::new();
    stream.read_to_string(&mut raw).ok()?;
    let (head, body) = raw.split_once("\r\n\r\n")?;
    let status = head
        .lines()
        .next()?
        .split_whitespace()
        .nth(1)?
        .parse()
        .ok()?;
    Some((status, body.to_owned()))
}

fn looks_like_scripts(body: &str) -> bool {
    let Ok(items) = serde_json::from_str::<serde_json::Value>(body) else {
        return false;
    };
    let Some(array) = items.as_array() else {
        return false;
    };
    // 与旧宿主一致：只有真的是工作台脚本列表才认作健康，避免误判同端口其他服务。
    array.iter().any(|item| {
        item.as_str() == Some("soul_raid")
            || item.get("script_id").and_then(|id| id.as_str()) == Some("soul_raid")
            || item.get("id").and_then(|id| id.as_str()) == Some("soul_raid")
    })
}

/// 受管后端：宿主异常结束时由 Job Object 回收子进程。
pub struct Managed {
    child: Child,
    job: Option<job::Job>,
}

impl Managed {
    /// 供就绪轮询检查退出状态。
    pub fn child(&mut self) -> &mut Child {
        &mut self.child
    }

    /// 主动终止本宿主创建的后端，最多等待 5 秒。
    pub fn stop(&mut self) {
        let _ = self.child.kill();
        let deadline = Instant::now() + Duration::from_secs(5);
        while Instant::now() < deadline {
            if matches!(self.child.try_wait(), Ok(Some(_))) {
                return;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        // 仍未退出时交给 Job Object：Managed 释放句柄会终止剩余进程。
        eprintln!("后端未在 5 秒内退出，交由 Job Object 回收");
    }
}

/// 后端日志位置；启动失败时可从这里看到具体原因。
pub fn log_path(user_data: &Path) -> PathBuf {
    user_data.join("logs").join("backend.log")
}

/// 启动受管后端；页面永远拿不到这条启动路径。
pub fn spawn(launch: &Launch, token: &str, user_data: &Path) -> Result<Managed, String> {
    let log_file = {
        let path = log_path(user_data);
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .ok()
    };
    let (stdout, stderr) = match log_file {
        Some(file) => (
            Stdio::from(file.try_clone().map_err(|e| e.to_string())?),
            Stdio::from(file),
        ),
        None => (Stdio::null(), Stdio::null()),
    };
    let child = Command::new(&launch.program)
        .args(&launch.args)
        .current_dir(&launch.cwd)
        .env("YYS_UI_TOKEN", token)
        .env("YYS_USER_DATA_DIR", user_data)
        .env("PYTHONIOENCODING", "utf-8")
        // 数据库固定落在永久用户目录，不再依赖 cwd 相对定位。
        .env(
            "YYS_WORKBENCH_DB_PATH",
            user_data.join("config").join("ui_workbench.db"),
        )
        .stdin(Stdio::null())
        .stdout(stdout)
        .stderr(stderr)
        .spawn()
        .map_err(|error| format!("启动后端失败：{error}"))?;
    // Job 创建失败不影响正常退出路径，只是少了宿主崩溃时的兜底回收。
    let job = job::Job::create(&child);
    Ok(Managed { child, job })
}

#[cfg(windows)]
mod job {
    use std::ffi::c_void;
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;

    const KILL_ON_JOB_CLOSE: u32 = 0x2000;
    const EXTENDED_LIMIT_INFORMATION: u32 = 9;

    #[repr(C)]
    #[derive(Default)]
    struct IoCounters {
        read_operations: u64,
        write_operations: u64,
        other_operations: u64,
        read_bytes: u64,
        write_bytes: u64,
        other_bytes: u64,
    }

    #[repr(C)]
    #[derive(Default)]
    struct BasicLimits {
        per_process_user_time: i64,
        per_job_user_time: i64,
        limit_flags: u32,
        minimum_working_set: usize,
        maximum_working_set: usize,
        active_process_limit: u32,
        affinity: usize,
        priority_class: u32,
        scheduling_class: u32,
    }

    #[repr(C)]
    #[derive(Default)]
    struct ExtendedLimits {
        basic: BasicLimits,
        io: IoCounters,
        process_memory_limit: usize,
        job_memory_limit: usize,
        peak_process_memory: usize,
        peak_job_memory: usize,
    }

    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn CreateJobObjectW(attributes: *mut c_void, name: *const u16) -> *mut c_void;
        fn SetInformationJobObject(
            job: *mut c_void,
            class: u32,
            information: *mut c_void,
            length: u32,
        ) -> i32;
        fn AssignProcessToJobObject(job: *mut c_void, process: *mut c_void) -> i32;
        fn CloseHandle(handle: *mut c_void) -> i32;
    }

    /// 只包含本次后端的 Job Object；句柄关闭（含宿主被强杀）时内核终止子进程。
    pub struct Job(*mut c_void);

    impl Job {
        pub fn create(child: &Child) -> Option<Self> {
            unsafe {
                let job = CreateJobObjectW(std::ptr::null_mut(), std::ptr::null());
                if job.is_null() {
                    return None;
                }
                let mut limits = ExtendedLimits::default();
                limits.basic.limit_flags = KILL_ON_JOB_CLOSE;
                let length = std::mem::size_of::<ExtendedLimits>() as u32;
                if SetInformationJobObject(
                    job,
                    EXTENDED_LIMIT_INFORMATION,
                    &mut limits as *mut _ as *mut c_void,
                    length,
                ) == 0
                {
                    CloseHandle(job);
                    return None;
                }
                if AssignProcessToJobObject(job, child.as_raw_handle() as *mut c_void) == 0 {
                    CloseHandle(job);
                    return None;
                }
                Some(Job(job))
            }
        }
    }

    // 句柄只在宿主进程内使用，跨线程只用于回收。
    unsafe impl Send for Job {}
    unsafe impl Sync for Job {}

    impl Drop for Job {
        fn drop(&mut self) {
            unsafe {
                CloseHandle(self.0);
            }
        }
    }
}

#[cfg(not(windows))]
mod job {
    use std::process::Child;
    pub struct Job;
    impl Job {
        pub fn create(_child: &Child) -> Option<Self> {
            None
        }
    }
}

/// 轮询鉴权健康接口，30 秒上限；后端提前退出立即失败。
pub fn wait_ready(
    child: &mut Child,
    token: &str,
    port: u16,
    timeout: Duration,
) -> Result<(), String> {
    let started = Instant::now();
    loop {
        match probe(token, port) {
            Probe::Healthy => return Ok(()),
            Probe::Protected => {
                return Err(format!(
                    "端口 {port} 已有受保护的桌面后端在运行，请先退出旧进程"
                ))
            }
            Probe::Free | Probe::Occupied => {}
        }
        if let Ok(Some(status)) = child.try_wait() {
            return Err(format!("后端在就绪前退出（{status}）"));
        }
        if started.elapsed() > timeout {
            return Err(format!("等待后端就绪超时（{} 秒）", timeout.as_secs()));
        }
        std::thread::sleep(POLL_INTERVAL);
    }
}

/// 终止本宿主启动的后端；不触碰其他进程。
pub fn stop(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

/// 开发模式：沿用旧宿主的 Python 解析顺序，cwd 为项目根。
pub fn dev_launch(repo_root: &Path) -> Launch {
    let program = std::env::var_os("YYS_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("D:/ProgramData/anaconda3/envs/win_macro/python.exe"));
    Launch {
        program,
        args: vec!["-m".into(), "ui_backend.main".into()],
        cwd: repo_root.to_owned(),
    }
}

/// 打包模式：资源目录下的完整 PyInstaller onedir，cwd 为 exe 同目录。
pub fn packaged_launch(resource_dir: &Path) -> Launch {
    let program = resource_dir.join("backend").join("yys-backend.exe");
    let cwd = program
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| resource_dir.to_owned());
    Launch {
        program,
        args: Vec::new(),
        cwd,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    /// 起一个只应答固定响应的假后端，返回端口。
    fn fake_backend(status: u16, body: &'static str) -> u16 {
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        std::thread::spawn(move || {
            for stream in listener.incoming().take(8) {
                let Ok(mut stream) = stream else { continue };
                let mut buffer = [0u8; 1024];
                let _ = stream.read(&mut buffer);
                let response = format!(
                    "HTTP/1.1 {status} X\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                    body.len()
                );
                let _ = stream.write_all(response.as_bytes());
            }
        });
        port
    }

    #[test]
    fn probe_distinguishes_health_protection_and_free_ports() {
        // 产品契约：AC1/AC2，只有本产品脚本列表算健康，403 视为受保护后端。
        let healthy = fake_backend(200, r#"[{"script_id":"soul_raid"}]"#);
        assert_eq!(probe("token", healthy), Probe::Healthy);
        let protected = fake_backend(403, r#"{"detail":"UI token 无效"}"#);
        assert_eq!(probe("token", protected), Probe::Protected);
        let other = fake_backend(200, r#"{"hello":"world"}"#);
        assert_eq!(probe("token", other), Probe::Occupied);
        let free = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let free_port = free.local_addr().unwrap().port();
        drop(free);
        assert_eq!(probe("token", free_port), Probe::Free);
    }

    #[test]
    fn wait_ready_reports_early_exit() {
        // 产品契约：AC4，后端提前退出不能假装就绪。
        let free = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let port = free.local_addr().unwrap().port();
        drop(free);
        let mut child = Command::new("cmd")
            .args(["/C", "exit", "3"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .unwrap();
        let error = wait_ready(&mut child, "token", port, Duration::from_secs(5)).unwrap_err();
        assert!(error.contains("退出"), "{error}");
    }

    #[test]
    fn wait_ready_times_out_when_backend_never_answers() {
        // 产品契约：AC4，端口上只有不响应的进程时必须超时失败，不能假就绪。
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        std::thread::spawn(move || {
            for stream in listener.incoming() {
                drop(stream);
            }
        });
        let mut child = Command::new("cmd")
            .args(["/C", "ping", "-n", "6", "127.0.0.1"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .unwrap();
        let started = Instant::now();
        let error = wait_ready(&mut child, "token", port, Duration::from_millis(800)).unwrap_err();
        assert!(error.contains("超时"), "{error}");
        assert!(started.elapsed() < Duration::from_secs(5));
        let _ = child.kill();
        let _ = child.wait();
    }

    #[test]
    fn launch_resolution_matches_legacy_layout() {
        // 产品契约：AC3，开发/打包两种 cwd 与旧宿主一致。
        let dev = dev_launch(Path::new("F:/repo"));
        assert_eq!(dev.cwd, PathBuf::from("F:/repo"));
        assert_eq!(
            dev.args,
            vec!["-m".to_string(), "ui_backend.main".to_string()]
        );
        let packaged = packaged_launch(Path::new("C:/app/resources"));
        assert_eq!(
            packaged.program,
            PathBuf::from("C:/app/resources/backend/yys-backend.exe")
        );
        assert_eq!(packaged.cwd, PathBuf::from("C:/app/resources/backend"));
    }

    #[test]
    fn token_is_32_bytes_of_hex() {
        let token = generate_token();
        assert_eq!(token.len(), 64);
        assert!(token.chars().all(|c| c.is_ascii_hexdigit()));
    }
}
