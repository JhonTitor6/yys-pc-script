use serde::{Deserialize, Serialize};
use std::{
    fs,
    path::Path,
    sync::Mutex,
    time::{Duration, Instant},
};
use tauri::{Monitor, PhysicalPosition, PhysicalSize, WebviewWindow};

/// 连续移动/缩放时合并写盘的最小间隔。
const SAVE_INTERVAL: Duration = Duration::from_millis(250);

/// 最近一次成功写入时间；只用于节流，不参与恢复。
static LAST_SAVE: Mutex<Option<Instant>> = Mutex::new(None);

#[derive(Clone, Copy, Deserialize, Serialize)]
pub struct Bounds {
    pub width: f64,
    pub height: f64,
    pub x: f64,
    pub y: f64,
}

fn contains(screen: &Bounds, saved: &Bounds) -> bool {
    saved.x >= screen.x
        && saved.y >= screen.y
        && saved.x < screen.x + screen.width
        && saved.y < screen.y + screen.height
}

fn fit(saved: Bounds, screens: &[Bounds], index: usize) -> Option<Bounds> {
    let screen = screens.get(index)?;
    let valid = [saved.width, saved.height, saved.x, saved.y]
        .iter()
        .all(|v| v.is_finite())
        && saved.width >= 800.0
        && saved.height >= 600.0;
    if !valid {
        return None;
    }
    let width = saved.width.min(screen.width).max(800.0);
    let height = saved.height.min(screen.height).max(600.0);
    Some(Bounds {
        width,
        height,
        x: saved
            .x
            .max(screen.x)
            .min(screen.x + (screen.width - width).max(0.0)),
        y: saved
            .y
            .max(screen.y)
            .min(screen.y + (screen.height - height).max(0.0)),
    })
}

/// 找到主显示器在列表中的下标；显示器顺序本身没有“主屏在前”的保证。
fn primary_index(window: &WebviewWindow, monitors: &[Monitor]) -> Option<usize> {
    let primary = window.primary_monitor().ok().flatten()?;
    monitors.iter().position(|monitor| {
        monitor.position() == primary.position() && monitor.size() == primary.size()
    })
}

/// 兼容旧窗口文件，并将位置恢复到当前显示器工作区。
pub fn restore(window: &WebviewWindow, root: &Path) {
    let restored = (|| {
        let data = fs::read(root.join("window-state.json")).ok()?;
        let saved = serde_json::from_slice::<Bounds>(&data).ok()?;
        let monitors = window.available_monitors().ok()?;
        let screens = monitors
            .iter()
            .map(|monitor| {
                let area = monitor.work_area();
                let scale = monitor.scale_factor();
                let position = area.position.to_logical::<f64>(scale);
                let size = area.size.to_logical::<f64>(scale);
                Bounds {
                    x: position.x,
                    y: position.y,
                    width: size.width,
                    height: size.height,
                }
            })
            .collect::<Vec<_>>();
        // 旧文件可能来自已拔除的显示器：优先回到主屏，而不是显示器列表里的任意一块。
        let index = screens
            .iter()
            .position(|screen| contains(screen, &saved))
            .or_else(|| primary_index(window, &monitors))
            .unwrap_or(0);
        let bounds = fit(saved, &screens, index)?;
        Some((bounds, monitors.get(index)?.scale_factor()))
    })();
    if let Some((bounds, scale)) = restored {
        // 按目标屏幕缩放转换，不能用新窗口所在屏幕的 DPI 解释另一块屏幕的位置。
        let _ = window.set_position(PhysicalPosition::new(
            (bounds.x * scale).round() as i32,
            (bounds.y * scale).round() as i32,
        ));
        let _ = window.set_size(PhysicalSize::new(
            (bounds.width * scale).round() as u32,
            (bounds.height * scale).round() as u32,
        ));
    } else {
        let _ = window.center();
    }
}

/// 仅持久化正常窗口边界，最大化与最小化不覆盖原值。
pub fn save(window: &WebviewWindow, root: &Path, throttle: bool) {
    if throttle && recently_saved() {
        // ponytail: 只做时间节流、不做尾随补写；最后 250ms 内的变化依赖关闭/退出时的强制写入，
        // 宿主被强杀时可能丢失最后几次尺寸。需要更强保证时再加后台尾随 debounce 线程。
        return;
    }
    let result = (|| -> Result<(), Box<dyn std::error::Error>> {
        if window.is_minimized()? || window.is_maximized()? || window.is_fullscreen()? {
            return Ok(());
        }
        let scale = window.scale_factor()?;
        let position = window.outer_position()?.to_logical::<f64>(scale);
        let size = window.inner_size()?.to_logical::<f64>(scale);
        if size.width < 800.0 || size.height < 600.0 {
            return Ok(());
        }
        let bounds = Bounds {
            width: size.width,
            height: size.height,
            x: position.x,
            y: position.y,
        };
        let target = root.join("window-state.json");
        if target.exists() {
            super::policy::contained(root, &target)?;
        }
        fs::write(target, serde_json::to_vec_pretty(&bounds)?)?;
        Ok(())
    })();
    match result {
        Ok(()) => mark_saved(),
        Err(error) => eprintln!("保存窗口状态失败：{error}"),
    }
}

fn recently_saved() -> bool {
    LAST_SAVE
        .lock()
        .is_ok_and(|guard| guard.is_some_and(|last| last.elapsed() < SAVE_INTERVAL))
}

fn mark_saved() {
    if let Ok(mut guard) = LAST_SAVE.lock() {
        *guard = Some(Instant::now());
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn legacy_bounds_remain_visible_after_monitor_removal() {
        // 产品契约：AC10/AC11，旧文件兼容；拔除显示器后恢复到可见工作区。
        let saved: Bounds =
            serde_json::from_str(r#"{"width":1316,"height":692,"x":3001,"y":406}"#).unwrap();
        let screen = Bounds {
            x: 0.0,
            y: 0.0,
            width: 1280.0,
            height: 720.0,
        };
        let got = fit(saved, &[screen], 0).unwrap();
        assert_eq!(
            (got.x, got.y, got.width, got.height),
            (0.0, 28.0, 1280.0, 692.0)
        );
        let negative = Bounds {
            x: -1920.0,
            width: 1920.0,
            ..screen
        };
        let saved = Bounds {
            x: -1800.0,
            y: 10.0,
            width: 900.0,
            height: 650.0,
        };
        assert_eq!(fit(saved, &[screen, negative], 1).unwrap().x, -1800.0);
        // 不可见的位置回退到主屏下标，不落到列表里的其他屏幕。
        assert_eq!(fit(saved, &[screen, negative], 0).unwrap().x, 0.0);
        assert!(fit(saved, &[screen], 2).is_none());
        assert!(fit(
            Bounds {
                width: f64::NAN,
                ..saved
            },
            &[screen],
            0
        )
        .is_none());
    }

    #[test]
    fn repeated_window_events_are_throttled() {
        // 产品契约：AC11，拖动/缩放不应每个事件都同步写盘。
        assert!(!recently_saved());
        mark_saved();
        assert!(recently_saved());
        std::thread::sleep(SAVE_INTERVAL + Duration::from_millis(50));
        assert!(!recently_saved());
    }
}
