config_dir := env_var("HOME") / ".config"
backups_dir := env_var_or_default("XDG_DATA_HOME", env_var("HOME") / ".local" / "share") / "zyn" / "backups"
stow_flags := "--no-folding --ignore=deps\\.txt --ignore=post-install\\.sh -t " + config_dir + " -d bundles"

default:
    @just --list

# Symlink the bundle into ~/.config via stow, then run its post-install hook if present.
install BUNDLE:
    @mkdir -p {{config_dir}}
    stow {{stow_flags}} {{BUNDLE}}
    @just post-install {{BUNDLE}}

# Run the bundle's post-install.sh hook if present and executable.
post-install BUNDLE:
    #!/usr/bin/env bash
    set -euo pipefail
    hook="bundles/{{BUNDLE}}/post-install.sh"
    if [ -x "$hook" ]; then
        echo "{{BUNDLE}}: running post-install hook"
        "$hook"
    fi

# Remove the symlinks stow owns. Leaves any pre-existing user files alone.
uninstall BUNDLE:
    stow {{stow_flags}} -D {{BUNDLE}}

# Snapshot all ~/.config dirs the bundle touches into a timestamped tarball.
backup BUNDLE:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{backups_dir}}
    dirs=""
    for d in bundles/{{BUNDLE}}/*/; do
        name=$(basename "$d")
        if [ -d "{{config_dir}}/$name" ]; then
            dirs+="$name"$'\n'
        fi
    done
    if [ -z "$dirs" ]; then
        echo "{{BUNDLE}}: nothing at install footprint, skipping"
        exit 0
    fi
    ts=$(date +%Y%m%d-%H%M%S)
    archive="{{backups_dir}}/{{BUNDLE}}-$ts.tar.gz"
    printf '%s' "$dirs" | tar -czf "$archive" -C "{{config_dir}}" -T -
    echo "{{BUNDLE}}: backed up to $archive"

# Wipe all ~/.config dirs the bundle touches. Backs up first unless no-backup=true.
clear BUNDLE no-backup="false":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "{{no-backup}}" != "true" ]; then
        just backup {{BUNDLE}}
    fi
    for d in bundles/{{BUNDLE}}/*/; do
        name=$(basename "$d")
        target="{{config_dir}}/$name"
        if [ -e "$target" ] || [ -L "$target" ]; then
            rm -rf "$target"
        fi
    done

# Install upstream tools listed in the bundle's deps.<manager> (or deps.txt fallback)
# via the first detected package manager (pacman > apt > dnf > brew).
pkg BUNDLE:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v pacman &>/dev/null; then
        manager=pacman
        install_cmd="sudo pacman -S --needed --noconfirm"
    elif command -v apt-get &>/dev/null; then
        manager=apt
        install_cmd="sudo apt-get install -y"
    elif command -v dnf &>/dev/null; then
        manager=dnf
        install_cmd="sudo dnf install -y"
    elif command -v brew &>/dev/null; then
        manager=brew
        install_cmd="brew install"
    else
        echo "{{BUNDLE}}: no supported package manager found (pacman, apt, dnf, brew)" >&2
        exit 1
    fi
    override="bundles/{{BUNDLE}}/deps.$manager"
    canonical="bundles/{{BUNDLE}}/deps.txt"
    if [ -f "$override" ]; then
        deps="$override"
    elif [ -f "$canonical" ]; then
        deps="$canonical"
    else
        echo "{{BUNDLE}}: no deps file, skipping"
        exit 0
    fi
    pkgs=$(grep -vE '^(#|$)' "$deps" | tr '\n' ' ')
    if [ -z "$pkgs" ]; then
        echo "{{BUNDLE}}: $(basename "$deps") is empty, skipping"
        exit 0
    fi
    echo "{{BUNDLE}}: installing via $manager from $(basename "$deps"): $pkgs"
    $install_cmd $pkgs

# Install zyn from GitHub via uv tool.
install-cli:
    #!/usr/bin/env bash
    if ! command -v uv &>/dev/null; then
        echo "uv is required: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    uv tool install git+https://github.com/keyvanm/zyn

# Install zyn from the local source tree as an editable uv tool.
install-cli-dev:
    uv tool install --editable .

# Install zyn-probe (rust session probe) from GitHub via cargo.
install-probe:
    #!/usr/bin/env bash
    if ! command -v cargo &>/dev/null; then
        echo "cargo is required: https://rustup.rs"
        exit 1
    fi
    cargo install --git https://github.com/keyvanm/zyn zyn-probe

# Install zyn-probe from the local source tree.
install-probe-dev:
    cargo install --path zyn-probe

# Backup, wipe, and reinstall the bundle from scratch.
fresh-install BUNDLE:
    just backup {{BUNDLE}}
    just clear {{BUNDLE}} true
    just install {{BUNDLE}}

install-all: install-cli install-probe (install "gatzi") (install "zennij") (install "gigazyn") (install "kitty")

fresh-install-all: install-cli install-probe (fresh-install "gatzi") (fresh-install "zennij") (fresh-install "gigazyn") (fresh-install "kitty")

uninstall-all: (uninstall "gatzi") (uninstall "zennij") (uninstall "gigazyn") (uninstall "kitty")

backup-all: (backup "gatzi") (backup "zennij") (backup "gigazyn") (backup "kitty")

clear-all: (clear "gatzi") (clear "zennij") (clear "gigazyn") (clear "kitty")

pkg-all: (pkg "gatzi") (pkg "zennij") (pkg "gigazyn") (pkg "kitty")