#!/usr/bin/env bash
# Sync GitHub repository "About" (description, homepage, topics) from .github/repository-metadata.json
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
META="${ROOT}/.github/repository-metadata.json"
OWNER_REPO="${GITHUB_REPOSITORY:-AmanBadola01/Linkwise-Graph}"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  if [[ -n "${SECRET_GITHUB_A7AA0BAEFEBD45B68BDC42374E5F00A9:-}" ]]; then
    GITHUB_TOKEN="$SECRET_GITHUB_A7AA0BAEFEBD45B68BDC42374E5F00A9"
  else
    echo "Set GITHUB_TOKEN (PAT with Administration: Read and write on this repo)." >&2
    exit 1
  fi
fi

PATCH_BODY="$(python3 - "${META}" <<'PY'
import json, sys
from pathlib import Path
m = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps({"description": m["description"], "homepage": m["homepage"]}))
PY
)"

TOPICS_JSON="$(python3 - "${META}" <<'PY'
import json, sys
from pathlib import Path
m = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps({"names": m["topics"]}))
PY
)"

API="https://api.github.com/repos/${OWNER_REPO}"

patch_resp="$(curl -sS -w "\n%{http_code}" -X PATCH \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "${API}" \
  -d "${PATCH_BODY}")"
patch_code="${patch_resp##*$'\n'}"
if [[ "$patch_code" != "200" ]]; then
  echo "PATCH repository failed (HTTP ${patch_code})." >&2
  echo "${patch_resp%$'\n'*}" >&2
  echo "Grant the token Administration: Read and write (fine-grained) or repo (classic)." >&2
  exit 1
fi

topics_resp="$(curl -sS -w "\n%{http_code}" -X PUT \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.mercy-preview+json" \
  "${API}/topics" \
  -d "${TOPICS_JSON}")"
topics_code="${topics_resp##*$'\n'}"
if [[ "$topics_code" != "200" ]]; then
  echo "PUT topics failed (HTTP ${topics_code})." >&2
  echo "${topics_resp%$'\n'*}" >&2
  exit 1
fi

echo "GitHub About updated for ${OWNER_REPO}."
python3 - "${META}" <<'PY'
import json, sys
from pathlib import Path
m = json.loads(Path(sys.argv[1]).read_text())
print(f"  description: {m['description']}")
print(f"  homepage:    {m['homepage']}")
PY