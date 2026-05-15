use std::env;
use std::os::unix::fs::FileTypeExt;
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};

use clap::Parser;
use md5::{Digest, Md5};

#[derive(Parser)]
#[command(about = "Exit 0 if a live zyn session exists for PATH (walks up parents), 1 otherwise")]
struct Args {
    path: PathBuf,

    #[arg(long, default_value = "mux", help = "Scope dims: comma list of mux,wm — or 'all'/'none'")]
    scope: String,
}

fn sockets_dir() -> PathBuf {
    env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/tmp"))
        .join("zyn")
}

fn detect_multiplexer() -> Option<String> {
    if let Ok(name) = env::var("ZELLIJ_SESSION_NAME") {
        return Some(format!("zellij:{name}"));
    }
    if env::var_os("TMUX").is_some() {
        let out = Command::new("tmux")
            .args(["display-message", "-p", "#S"])
            .output()
            .ok()?;
        if !out.status.success() {
            return None;
        }
        let name = String::from_utf8(out.stdout).ok()?.trim().to_string();
        return Some(format!("tmux:{name}"));
    }
    None
}

fn scope_components(scope: &str) -> Vec<String> {
    let dims: Vec<&str> = match scope.trim() {
        "" | "none" => return vec![],
        "all" => vec!["mux", "wm"],
        s => s.split(',').map(str::trim).filter(|p| !p.is_empty()).collect(),
    };
    let mut out = Vec::new();
    if dims.contains(&"mux") {
        if let Some(m) = detect_multiplexer() {
            out.push(format!("mux:{m}"));
        }
    }
    // wm detection: add hyprland/sway later when needed
    out
}

fn socket_for(root: &Path, scope: &[String]) -> PathBuf {
    let abs = root.canonicalize().unwrap_or_else(|_| root.to_path_buf());
    let mut parts = vec![abs.to_string_lossy().into_owned()];
    parts.extend_from_slice(scope);
    let mut hasher = Md5::new();
    hasher.update(parts.join("|").as_bytes());
    sockets_dir().join(format!("{}.sock", hex::encode(hasher.finalize())))
}

fn is_live_socket(path: &Path) -> bool {
    let Ok(meta) = std::fs::symlink_metadata(path) else {
        return false;
    };
    meta.file_type().is_socket() && UnixStream::connect(path).is_ok()
}

fn has_session(start: &Path, scope: &[String]) -> bool {
    let dir = if start.is_dir() {
        start.to_path_buf()
    } else {
        start.parent().map(Path::to_path_buf).unwrap_or_default()
    };
    dir.ancestors()
        .any(|ancestor| is_live_socket(&socket_for(ancestor, scope)))
}

fn main() -> ExitCode {
    let args = Args::parse();
    let scope = scope_components(&args.scope);
    if has_session(&args.path, &scope) {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}
