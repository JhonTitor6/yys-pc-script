use serde::Deserialize;
use std::{
    fs,
    path::{Path, PathBuf},
};

#[derive(Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum WindowAction {
    Minimize,
    ToggleMaximize,
    Close,
    Drag,
}

/// 仅受控首页可以导航或调用宿主。
pub fn trusted_url(url: &tauri::Url) -> bool {
    url.scheme() == "http"
        && url.host_str() == Some("tauri.localhost")
        && url.port().is_none()
        && url.username().is_empty()
        && url.password().is_none()
        && matches!(url.path(), "/" | "/index.html")
        && url.query().is_none()
}

/// 将窗口身份与当前来源同时作为命令边界。
pub fn authorize(label: &str, url: &tauri::Url) -> Result<(), String> {
    if label == "main" && trusted_url(url) {
        Ok(())
    } else {
        Err("拒绝非可信主窗口或来源".into())
    }
}

/// 解析真实路径后检查包含性，拒绝链接逃逸。
pub fn contained(root: &Path, target: &Path) -> Result<PathBuf, String> {
    // 复用 Tauri 已依赖的 Windows 路径规范化，避免把扩展路径前缀交给资源管理器。
    let root = dunce::canonicalize(root).map_err(|_| "允许目录不存在")?;
    let target = dunce::canonicalize(target).map_err(|_| "目标不存在")?;
    if target.starts_with(&root) {
        Ok(target)
    } else {
        Err("目标超出允许目录".into())
    }
}

/// 创建并校验固定截图库目录。
pub fn screenshot_directory(user_data: &Path) -> Result<PathBuf, String> {
    let target = user_data.join("screenshots");
    if !target.exists() {
        fs::create_dir(&target).map_err(|e| e.to_string())?;
    }
    let target = contained(user_data, &target)?;
    if !target.is_dir() {
        return Err("截图路径不是目录".into());
    }
    Ok(target)
}

/// 只解析白名单生产资源对应的现存覆盖文件。
pub fn image_path(user_data: &Path, id: &str) -> Result<PathBuf, String> {
    if id.contains(['\\', ':', '\0'])
        || id
            .split('/')
            .any(|part| part.is_empty() || part == "." || part == "..")
    {
        return Err("invalid-resource".into());
    }
    let known: Vec<String> =
        serde_json::from_str(include_str!("../../build/tauri-image-resources.json"))
            .map_err(|e| e.to_string())?;
    if !known.iter().any(|value| value == id) {
        return Err("invalid-resource".into());
    }
    let root = contained(user_data, &user_data.join("image-overrides"))?;
    let target = contained(&root, &root.join(id))?;
    if !target.is_file() {
        return Err("not-found".into());
    }
    Ok(target)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_trusted_main_and_enum_actions() {
        // 产品契约：AC13/AC14，其他来源、窗口和未知动作都不能调用宿主。
        let good = tauri::Url::parse("http://tauri.localhost/index.html").unwrap();
        assert!(authorize("main", &good).is_ok());
        assert!(authorize("other", &good).is_err());
        for url in [
            "https://tauri.localhost/",
            "http://tauri.localhost.evil/",
            "http://127.0.0.1:8000/",
            "http://tauri.localhost:1234/",
            "http://user@tauri.localhost/",
            "http://tauri.localhost/other.html",
        ] {
            assert!(
                authorize("main", &tauri::Url::parse(url).unwrap()).is_err(),
                "{url}"
            );
        }
        assert!(serde_json::from_str::<WindowAction>("\"execute\"").is_err());
        assert!(serde_json::from_str::<WindowAction>("123").is_err());
    }

    #[test]
    fn paths_require_known_resource_and_real_containment() {
        // 产品契约：AC8/AC9，拒绝同前缀兄弟目录、路径穿越及链接逃逸。
        let base = std::env::temp_dir().join(format!("yys-policy-{}", std::process::id()));
        let root = base.join("data");
        let sibling = base.join("data-other");
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(&sibling).unwrap();
        assert!(contained(&root, &sibling).is_err());
        assert!(screenshot_directory(&root).unwrap().is_dir());
        for id in [
            "../secret.png",
            "yys/../secret.png",
            "C:/secret.png",
            "yys/unknown.png",
            "yys\\secret.png",
        ] {
            assert!(image_path(&root, id).is_err());
        }
        let ids: Vec<String> =
            serde_json::from_str(include_str!("../../build/tauri-image-resources.json")).unwrap();
        let file = root.join("image-overrides").join(&ids[0]);
        fs::create_dir_all(file.parent().unwrap()).unwrap();
        fs::write(&file, b"test").unwrap();
        assert_eq!(
            image_path(&root, &ids[0]).unwrap(),
            dunce::canonicalize(file).unwrap()
        );
        #[cfg(windows)]
        {
            let link = root.join("escape");
            std::os::windows::fs::symlink_dir(&sibling, &link).unwrap();
            assert!(contained(&root, &link).is_err());
            fs::remove_dir(link).unwrap();
        }
        fs::remove_dir_all(&base).unwrap();
    }
}
