#!/usr/bin/env bash
# Link .cursor/skills/{name} -> ../../skills/{name} for Cursor auto-discovery.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
src_root="$root/skills"
dst_root="$root/.cursor/skills"
mkdir -p "$dst_root"
names=(
  drama-intake
  drama-series-develop
  0xsline-short-drama
  drama-series-h3-r2v-prompts
)
for n in "${names[@]}"; do
  src="$src_root/$n"
  dst="$dst_root/$n"
  if [[ ! -d "$src" ]]; then
    echo "missing $src" >&2
    continue
  fi
  rm -rf "$dst"
  ln -s "../../skills/$n" "$dst"
  echo "linked $dst -> ../../skills/$n"
done
echo "Cursor skill links ready under .cursor/skills/"
