#!/bin/bash
# gemini-apply-test.sh JOB REPO PR [push]  (21:55 CT 10/16) — applies ~/work/results/JOB.gemini.patch on PR branch, runs tests; push only if "push" and tests pass.
J=$1; R=$2; PR=$3; PUSH=$4; P=~/work/results/$J.gemini.patch; W=~/work/gem-$J
. ~/.nvm/nvm.sh >/dev/null 2>&1; [ -f ~/nuc-tools/pw-env.sh ] && . ~/nuc-tools/pw-env.sh
while [ "$(cut -d' ' -f1 /proc/loadavg | cut -d. -f1)" -ge 11 ]; do sleep 30; done
rm -rf $W; gh repo clone $R $W -- --depth 80 --no-single-branch -q || { echo "GAT clone-failed"; exit 4; }
cd $W && gh pr checkout $PR >/dev/null 2>&1 || { echo "GAT checkout-failed"; exit 4; }
git apply --recount --check $P 2>&1 || { echo "GAT apply-check-failed"; exit 3; }
# never loosen tests: no deleted lines in test files
if git apply --numstat $P | awk '$3 ~ /(test|spec|__tests__)/ && $2>0{bad=1} END{exit !bad}'; then echo "GAT refuses: patch deletes lines in test files"; exit 3; fi
git apply --recount $P || exit 3
rc=0
if [ -f package.json ]; then
  if [ -f pnpm-lock.yaml ]; then corepack pnpm install --frozen-lockfile >/tmp/gat-$J.inst 2>&1; T="corepack pnpm test"; else npm ci --no-audit --no-fund >/tmp/gat-$J.inst 2>&1 || npm install --no-audit --no-fund >/tmp/gat-$J.inst 2>&1; T="npm test --silent"; fi
  grep -q '"test"' package.json || T="npx tsc --noEmit"
elif ls pytest.ini pyproject.toml setup.cfg tests 2>/dev/null | head -1 >/dev/null; then T="python3 -m pytest -q"; else T="true"; fi
echo "GAT test cmd: $T"
CI=1 nice -n 10 timeout 1500 bash -c "$T" > /tmp/gat-$J.test 2>&1; rc=$?
tail -120 /tmp/gat-$J.test
echo "GAT tests rc=$rc"
[ $rc -ne 0 ] && exit 1
if [ "$PUSH" = push ]; then
  git add -A && git commit -qm "Gemini lane: $J (tests pass: $T)" && git push -q origin HEAD || { echo "GAT push-failed"; exit 5; }
  echo "GAT pushed $(git rev-parse --abbrev-ref HEAD) $(git rev-parse HEAD)"
fi
exit 0
