config_dir := env_var("HOME") / ".config"
backups_dir := env_var_or_default("XDG_DATA_HOME", env_var("HOME") / ".local" / "share") / "zyn" / "backups"
stow_flags := "--no-folding --ignore=deps\\.txt -t " + config_dir + " -d bundles"

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

# Install upstream tools listed in the bundle's deps.txt via brew.
brew BUNDLE:
    #!/usr/bin/env bash
    set -euo pipefail
    deps="bundles/{{BUNDLE}}/deps.txt"
    if [ ! -f "$deps" ]; then
        echo "{{BUNDLE}}: no deps.txt, skipping"
        exit 0
    fi
    pkgs=$(grep -vE '^(#|$)' "$deps" | tr '\n' ' ')
    if [ -z "$pkgs" ]; then
        echo "{{BUNDLE}}: deps.txt is empty, skipping"
        exit 0
    fi
    brew install $pkgs

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

# Backup, wipe, and reinstall the bundle from scratch.
fresh-install BUNDLE:
    just backup {{BUNDLE}}
    just clear {{BUNDLE}} true
    just install {{BUNDLE}}

fresh-install-all: install-cli (fresh-install "gatzi") (fresh-install "zennij") (fresh-install "gigazyn") (fresh-install "kitty")

install-all: install-cli (install "gatzi") (install "zennij") (install "gigazyn") (install "kitty")

uninstall-all: (uninstall "gatzi") (uninstall "zennij") (uninstall "gigazyn") (uninstall "kitty")

backup-all: (backup "gatzi") (backup "zennij") (backup "gigazyn") (backup "kitty")

clear-all: (clear "gatzi") (clear "zennij") (clear "gigazyn") (clear "kitty")

brew-all: (brew "gatzi") (brew "zennij") (brew "gigazyn") (brew "kitty")
