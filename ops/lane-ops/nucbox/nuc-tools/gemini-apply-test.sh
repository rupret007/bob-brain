#!/bin/bash
# gemini-apply-test.sh JOB REPO PR [push] [edits|patch]   (lane-ops v2: edits = SEARCH/REPLACE blocks via apply-edits.py)  (21:55 CT 10/16) — applies ~/work/results/JOB.gemini.patch on PR branch, runs tests; push only if "push" and tests pass.
J=$1; R=$2; PR=$3; PUSH=$4; FMT=${5:-patch}; P=~/work/results/$J.gemini.patch; W=~/work/gem-$J
. ~/.nvm/nvm.sh >/dev/null 2>&1; [ -f ~/nuc-tools/pw-env.sh ] && . ~/nuc-tools/pw-env.sh
while [ "$(cut -d' ' -f1 /proc/loadavg | cut -d. -f1)" -ge 11 ]; do sleep 30; done
# lane-ops v3 (capacity): one cached bare clone per repo + a worktree per job (was rm -rf + a fresh --depth 80 clone)
BR=$(gh pr view $PR -R $R --json headRefName -q .headRefName 2>/dev/null); [ -n "$BR" ] || { echo "GAT checkout-failed (no head branch for PR #$PR)"; exit 4; }
bash ~/nuc-tools/nuc-repo-cache.sh $R $W $PR >/dev/null; crc=$?
(( crc == 0 )) || { echo "GAT clone-failed (cache rc=$crc)"; exit 4; }
cd $W || { echo "GAT checkout-failed"; exit 4; }
# lane-ops v2: SEARCH/REPLACE edits are applied to the checkout first, then turned into the diff every later check reads
if [ "$FMT" = edits ]; then
  python3 ~/nuc-tools/apply-edits.py ~/work/results/$J.gemini.patch --root . || { echo "GAT apply-check-failed (edits)"; exit 3; }
  git add -N . && git diff > /tmp/gat-$J.diff && git reset -q && git checkout -q -- . && git clean -fdq && P=/tmp/gat-$J.diff
  [ -s "$P" ] || { echo "GAT refuses: edits produced no change"; exit 3; }
fi
# lane-ops v2: refuse patches that weaken tests/CI before anything touches the tree (fail closed if the policy is missing)
python3 ~/nuc-tools/gat-policy.py $P || { echo "GAT refuses: policy (see lines above)"; exit 3; }
# never loosen tests: no deleted lines in test files (v3 B6: same test-path rule as gat-policy; the old `$3 ~ /test/`
# also refused paths like src/latest.ts)
if git apply --numstat $P | awk '$2>0 && $3 ~ /(^|\/)(tests?|specs?|__tests__|e2e)\/|(^|\/)test_[^\/]*\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$/{bad=1} END{exit !bad}'; then echo "GAT refuses: patch deletes lines in test files"; exit 3; fi
# lane-ops v2: tolerant apply ladder (LLM diffs often have whitespace/context drift); tests still gate the push
AOPT=; AOK=
for o in "" "--ignore-whitespace" "--ignore-whitespace -C1"; do
  if git apply --recount $o --check $P 2>/tmp/gat-$J.apply; then AOPT="$o"; AOK=1; break; fi
done
[ -n "$AOK" ] || { cat /tmp/gat-$J.apply; echo "GAT apply-check-failed"; exit 3; }
echo "GAT apply opts: ${AOPT:-none}"
git apply --recount $AOPT $P || exit 3
rc=0
if [ -f package.json ]; then
  if [ -f pnpm-lock.yaml ]; then corepack pnpm install --frozen-lockfile >/tmp/gat-$J.inst 2>&1; T="corepack pnpm test"; else npm ci --no-audit --no-fund >/tmp/gat-$J.inst 2>&1 || npm install --no-audit --no-fund >/tmp/gat-$J.inst 2>&1; T="npm test --silent"; fi
  grep -q '"test"' package.json || T="npx tsc --noEmit"
elif [ -e pytest.ini ] || [ -e pyproject.toml ] || [ -e setup.cfg ] || [ -d tests ]; then T="python3 -m pytest -q"; else T=""; fi
# lane-ops v2: no test command means no evidence; never push untested (old code always picked pytest via an ls|head bug)
[ -z "$T" ] && { echo "GAT refuses: no test command found"; exit 1; }
echo "GAT test cmd: $T"
# lane-ops v3: at most NUC_TEST_SLOTS (3) test runs at once on the NucBox, separate from the LLM lane slots
CI=1 bash ~/nuc-tools/nuc-test-slot.sh nice -n 10 timeout 1500 bash -c "$T" > /tmp/gat-$J.test 2>&1; rc=$?
tail -120 /tmp/gat-$J.test
echo "GAT tests rc=$rc"
[ $rc -ne 0 ] && exit 1
if [ "$PUSH" = push ]; then
  # v3 B2 fence: never push after this lane lost its lease (lane-supervise stop / stale heartbeat)
  if [ -n "${LANE_NAME:-}" ]; then bash ~/nuc-tools/lane-supervise.sh ok "$LANE_NAME" || { echo "GAT push-fenced (lease lost)"; exit 5; }; fi
  git add -A && git commit -qm "Gemini lane: $J (tests pass: $T)" && git push -q origin "HEAD:refs/heads/$BR" || { echo "GAT push-failed"; exit 5; }
  echo "GAT pushed $BR $(git rev-parse HEAD)"
fi
exit 0
