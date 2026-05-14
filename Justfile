config_dir := env_var("HOME") / ".config"
backups_dir := env_var_or_default("XDG_DATA_HOME", env_var("HOME") / ".local" / "share") / "zyn" / "backups"
stow_flags := "--no-folding --ignore=deps\\.txt -t " + config_dir + " -d bundles"

default:
    @just --list

# Symlink the bundle into ~/.config via stow.
install BUNDLE:
    @mkdir -p {{config_dir}}
    stow {{stow_flags}} {{BUNDLE}}

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

# Backup, wipe, and reinstall the bundle from scratch.
fresh-install BUNDLE:
    just backup {{BUNDLE}}
    just clear {{BUNDLE}} true
    just install {{BUNDLE}}

fresh-install-all: (fresh-install "gatzi") (fresh-install "zennij") (fresh-install "gigazyn")

install_all: (install "gatzi") (install "zennij") (install "gigazyn")

uninstall_all: (uninstall "gatzi") (uninstall "zennij") (uninstall "gigazyn")

backup_all: (backup "gatzi") (backup "zennij") (backup "gigazyn")

clear_all: (clear "gatzi") (clear "zennij") (clear "gigazyn")

brew_all: (brew "gatzi") (brew "zennij") (brew "gigazyn")
