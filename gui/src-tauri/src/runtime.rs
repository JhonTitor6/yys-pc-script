//! WebView2 Runtime 检测；缺失时给出官方安装入口并允许重试。

use std::process::Command;

/// 两个可能的注册位置：机器级 32 位视图与当前用户。
const RUNTIME_KEYS: [&str; 2] = [
    r"HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    r"HKCU\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
];

const DOWNLOAD_URL: &str = "https://go.microsoft.com/fwlink/p/?LinkId=2124703";
const MB_RETRYCANCEL: u32 = 0x0000_0005;
const MB_ICONERROR: u32 = 0x0000_0010;
const MB_TOPMOST: u32 = 0x0004_0000;
const IDRETRY: i32 = 4;

/// 已安装的 Runtime 版本；未安装或读取失败返回 None。
pub fn installed_version() -> Option<String> {
    // 仅调试构建可用：模拟 Runtime 缺失，便于验证提示与重试流程。
    if cfg!(debug_assertions) && std::env::var_os("YYS_FORCE_NO_RUNTIME").is_some() {
        return None;
    }
    RUNTIME_KEYS.iter().find_map(|key| query_version(key))
}

fn query_version(key: &str) -> Option<String> {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let output = Command::new("reg")
            .args(["query", key, "/v", "pv"])
            .creation_flags(0x0800_0000)
            .output()
            .ok()?;
        if !output.status.success() {
            return None;
        }
        parse_version(&String::from_utf8_lossy(&output.stdout))
    }
    #[cfg(not(windows))]
    {
        let _ = key;
        None
    }
}

/// 从 reg query 输出里取版本号：`pv    REG_SZ    155.0.4283.62`。
fn parse_version(text: &str) -> Option<String> {
    text.lines().find_map(|line| {
        let value = line.split_whitespace().last()?;
        let first = value.chars().next()?;
        (first.is_ascii_digit() && value.contains('.')).then(|| value.to_owned())
    })
}

/// 启动前确认 Runtime 可用；缺失时提示安装，用户重试则重新检测。
pub fn ensure_available() -> Result<(), String> {
    if installed_version().is_some() {
        return Ok(());
    }
    #[cfg(feature = "smoke-test")]
    {
        return Err("缺少 WebView2 Runtime（烟测环境不弹窗）".into());
    }
    #[cfg(not(feature = "smoke-test"))]
    {
        loop {
            let choice = show_missing_dialog();
            if choice == IDRETRY {
                if installed_version().is_some() {
                    return Ok(());
                }
                continue;
            }
            // 用户已在缺失提示里选择取消，调用方不要再弹第二个错误框。
            return Err(String::new());
        }
    }
}

#[cfg(not(feature = "smoke-test"))]
fn show_missing_dialog() -> i32 {
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
    let text = wide(&format!(
        "未检测到 Microsoft Edge WebView2 Runtime，工作台无法启动。\n\n请从以下地址安装后点击“重试”：\n{DOWNLOAD_URL}"
    ));
    let caption = wide("阴阳师脚本工作台");
    unsafe {
        MessageBoxW(
            0,
            text.as_ptr(),
            caption.as_ptr(),
            MB_RETRYCANCEL | MB_ICONERROR | MB_TOPMOST,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_version_from_reg_query_output() {
        // 产品契约：AC15，版本号必须从 reg query 的实际输出里取。
        let sample = "\r\nHKEY_LOCAL_MACHINE\\SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}\r\n    pv    REG_SZ    155.0.4283.62\r\n\r\n";
        assert_eq!(parse_version(sample).as_deref(), Some("155.0.4283.62"));
        assert_eq!(parse_version(""), None);
        assert_eq!(parse_version("没有版本号"), None);
    }
}
