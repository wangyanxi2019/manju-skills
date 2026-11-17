#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
target_root="${MANJU_SKILLS_TARGET:-$HOME/.agents/skills}"
backup_root="$target_root/.manju-skills-backups/$(date +%Y%m%d-%H%M%S)-$$"
names=(manju-jb manju-rw manju-dj manju-cj manju-fj manju-h3 manju-shared)

for name in "${names[@]}"; do
  if [ ! -d "$repo_root/$name" ]; then
    echo "Missing Skill folder: $repo_root/$name" >&2
    exit 1
  fi
done

mkdir -p "$target_root"
for name in "${names[@]}"; do
  target="$target_root/$name"
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    mkdir -p "$backup_root"
    mv "$target" "$backup_root/$name"
  fi
  ln -sfn "$repo_root/$name" "$target"
done

echo "Installed six Skills and manju-shared from: $repo_root"
if [ -d "$backup_root" ]; then
  echo "Previous copies backed up to: $backup_root"
fi
python3 "$target_root/manju-shared/resolve_project.py"
