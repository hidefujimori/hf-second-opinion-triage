#!/usr/bin/env bash
# Publish a GitHub release for this repository.
#   tools/release.sh 0.12.0            -> tag v0.12.0-beta, notes docs/release-notes/v0.12.0-beta.md
#   tools/release.sh 0.12.0 --dry-run  -> only check
# Needs: git, gh (GitHub CLI, signed in: gh auth login), shasum.
# Steps: check -> git push -> tag -> gh release create (pre-release) with the .spl attached.
set -euo pipefail

V="${1:?usage: tools/release.sh <version> [--dry-run]}"
DRY="${2:-}"
TAG="v${V}-beta"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
NOTES="docs/release-notes/${TAG}.md"
SPL="app/_packages/second_opinion_triage-${V}.spl"
APPCONF="app/second_opinion_triage/default/app.conf"

die() { echo "ERROR: $*" >&2; exit 1; }

command -v gh >/dev/null || die "gh is not installed (brew install gh, then gh auth login)"
gh auth status >/dev/null 2>&1 || die "gh is not signed in (gh auth login)"
[ -f "$NOTES" ] || die "missing $NOTES"
[ -f "$SPL" ] || die "missing $SPL"
grep -q "^version = ${V}$" "$APPCONF" || die "$APPCONF is not version $V"
[ -z "$(git status --porcelain)" ] || die "uncommitted changes; commit first"
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || die "not on main"

SHA="$(shasum -a 256 "$SPL" | awk '{print $1}')"
grep -q "$SHA" "$NOTES" || die "SHA-256 of $SPL ($SHA) is not in $NOTES"
TITLE="$(head -1 "$NOTES" | sed 's/^# *//')"

git fetch --tags -q origin
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then die "tag $TAG already exists"; fi

echo "Release : $TAG"
echo "Title   : $TITLE"
echo "Package : $SPL ($SHA)"
echo "Commit  : $(git log --oneline -1)"
echo "To push : $(git rev-list --count origin/main..HEAD) commit(s)"
[ "$DRY" = "--dry-run" ] && { echo "dry run: nothing published"; exit 0; }

read -r -p "Publish? [y/N] " ok
[ "$ok" = "y" ] || [ "$ok" = "Y" ] || { echo "cancelled"; exit 1; }

git push origin main
git tag -a "$TAG" -m "$TITLE"
git push origin "$TAG"
gh release create "$TAG" "$SPL" --prerelease --verify-tag --title "$TITLE" --notes-file "$NOTES"
echo "Done: $(gh release view "$TAG" --json url -q .url)"
