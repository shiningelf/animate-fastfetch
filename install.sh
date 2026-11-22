#!/usr/bin/env sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target=${1:-"$HOME/.config/fastfetch/animate"}
mkdir -p "$target"
cp -R "$repo_dir/animate/nezuko" "$repo_dir/animate/2b" "$target/"
printf 'Installed character configs to %s\n' "$target"
printf 'Run with: fastfetch --config %s/nezuko/config.jsonc\n' "$target"
printf '     or: fastfetch --config %s/2b/config.jsonc\n' "$target"
