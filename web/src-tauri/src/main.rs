#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::path::PathBuf;

use base64::Engine;
use serde_json::Value;

fn safe_name(s: &str) -> String {
    s.chars().filter(|c| !"\\/:*?\"<>|".contains(*c)).collect()
}

/// 找 projects/：先看环境变量，再看 exe 旁边，最后往上找仓库根（开发时用）
fn projects_root() -> PathBuf {
    if let Ok(p) = std::env::var("FLOWBOX_PROJECTS") {
        return PathBuf::from(p);
    }
    let exe = std::env::current_exe().unwrap_or_else(|_| PathBuf::from("."));
    let dir = exe.parent().map(|p| p.to_path_buf()).unwrap_or_default();

    let beside = dir.join("projects");
    if beside.is_dir() {
        return beside;
    }
    let mut cur = dir.clone();
    for _ in 0..6 {
        match cur.parent() {
            Some(p) => cur = p.to_path_buf(),
            None => break,
        }
        let cand = cur.join("projects");
        if cand.is_dir() && cur.join("canvas_demo.py").exists() {
            return cand;
        }
    }
    beside
}

#[tauri::command]
fn list_projects() -> Vec<String> {
    let root = projects_root();
    let mut out = Vec::new();
    if let Ok(rd) = fs::read_dir(&root) {
        for e in rd.flatten() {
            let p = e.path();
            if p.is_dir() && p.join("flow.json").exists() {
                if let Some(n) = p.file_name().and_then(|s| s.to_str()) {
                    out.push(n.to_string());
                }
            }
        }
    }
    out.sort();
    out
}

#[tauri::command]
fn load_flow(project: String) -> Result<Value, String> {
    let p = projects_root().join(safe_name(&project)).join("flow.json");
    let raw = fs::read_to_string(&p).map_err(|e| format!("{}: {}", p.display(), e))?;
    serde_json::from_str(&raw).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_flow(project: String, doc: Value) -> Result<(), String> {
    let dir = projects_root().join(safe_name(&project));
    fs::create_dir_all(dir.join("files")).map_err(|e| e.to_string())?;
    fs::create_dir_all(dir.join("snapshots")).map_err(|e| e.to_string())?;
    let raw = serde_json::to_string_pretty(&doc).map_err(|e| e.to_string())?;
    let tmp = dir.join("flow.tmp");
    fs::write(&tmp, raw).map_err(|e| e.to_string())?;
    fs::rename(&tmp, dir.join("flow.json")).map_err(|e| e.to_string())?;
    Ok(())
}

/// 附件 / 截图读成 data URL，前端直接当 img src 用
#[tauri::command]
fn file_data_url(project: String, path: String) -> Result<String, String> {
    let base = projects_root().join(safe_name(&project));
    let target = base.join(path.replace('/', "\\"));
    let canon = target.canonicalize().map_err(|e| e.to_string())?;
    let base_canon = base.canonicalize().map_err(|e| e.to_string())?;
    if !canon.starts_with(&base_canon) {
        return Err("路径越界".into());
    }
    let raw = fs::read(&canon).map_err(|e| e.to_string())?;
    let mime = match canon
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_lowercase()
        .as_str()
    {
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "webp" => "image/webp",
        "bmp" => "image/bmp",
        "svg" => "image/svg+xml",
        _ => "application/octet-stream",
    };
    Ok(format!(
        "data:{};base64,{}",
        mime,
        base64::engine::general_purpose::STANDARD.encode(raw)
    ))
}

#[tauri::command]
fn save_asset(project: String, node_id: String, name: String, data: String) -> Result<String, String> {
    let dir = projects_root()
        .join(safe_name(&project))
        .join("files")
        .join(safe_name(&node_id));
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let raw = base64::engine::general_purpose::STANDARD
        .decode(data)
        .map_err(|e| e.to_string())?;
    let mut base = safe_name(&name);
    if base.is_empty() {
        base = "file".to_string();
    }
    let (stem, ext) = match base.rfind('.') {
        Some(i) if i > 0 => (base[..i].to_string(), base[i..].to_string()),
        _ => (base.clone(), String::new()),
    };
    let mut file = base.clone();
    let mut i = 1;
    while dir.join(&file).exists() {
        file = format!("{}_{}{}", stem, i, ext);
        i += 1;
    }
    fs::write(dir.join(&file), raw).map_err(|e| e.to_string())?;
    Ok(format!("files/{}/{}", safe_name(&node_id), file))
}

#[tauri::command]
fn create_project(name: String, doc: Value) -> Result<(), String> {
    let dir = projects_root().join(safe_name(&name));
    fs::create_dir_all(dir.join("files")).map_err(|e| e.to_string())?;
    fs::create_dir_all(dir.join("snapshots")).map_err(|e| e.to_string())?;
    let raw = serde_json::to_string_pretty(&doc).map_err(|e| e.to_string())?;
    fs::write(dir.join("flow.json"), raw).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn write_export(project: String, file_name: String, content: String) -> Result<String, String> {
    let dir = projects_root().join(safe_name(&project));
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = dir.join(safe_name(&file_name));
    fs::write(&path, content).map_err(|e| e.to_string())?;
    Ok(path.to_string_lossy().to_string())
}

#[tauri::command]
fn open_path(path: String) -> Result<(), String> {
    std::process::Command::new("cmd")
        .args(["/c", "start", "", &path])
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn open_asset(project: String, path: String) -> Result<(), String> {
    let p = projects_root()
        .join(safe_name(&project))
        .join(path.replace('/', "\\"));
    std::process::Command::new("cmd")
        .args(["/c", "start", "", &p.to_string_lossy()])
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    std::process::Command::new("cmd")
        .args(["/c", "start", "", &url])
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            list_projects,
            load_flow,
            save_flow,
            file_data_url,
            save_asset,
            create_project,
            write_export,
            open_path,
            open_asset,
            open_url
        ])
        .run(tauri::generate_context!())
        .expect("流程盒子启动失败");
}
