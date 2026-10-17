#!/bin/zsh
# Gemini lane v1 (17:35 CT 10/16): direct generateContent (Google billing) via gemini-direct.py.
#  review/critique jobs -> direct review, output to log (no posting)
#  docs jobs on an existing PR -> direct patch; git apply --check; docs-only (*.md, docs/) -> normal commit+push (no force)
#  test-gen jobs -> direct patch saved as q-<job>.gemini.patch, then handed to cursor-agent (CURSOR_MODEL) on NucBox to apply+run tests
#  anything else / any failure -> cursor-agent fallback on NucBox with CURSOR_MODEL
# usage: gemini-lane.sh JOB    (prompt at ~/lane-wt/logs/q-JOB.prompt)
export PATH=/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH
j=$1; L=~/lane-wt/logs; P=$L/q-$j.prompt; G=$L/gemini-direct.py
. $L/lane-route.conf
export GEMINI_DIRECT_MODEL=${GEMINI_CODE_MODEL:-gemini-3.1-pro-preview}; extra=""
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=30 -i $HOME/.ssh/nuc_ed25519 -p 2222 rupret@nuc-wsl"
txt=$(cat $P); lc=${(L)txt}
repo=$(print -r -- $txt | grep -oE 'rupret007/[A-Za-z0-9._-]+' | head -1)
pr=""; [[ $j == *-pr<-> ]] && pr=${j##*-pr}
fallback(){ # $1 = extra prompt file (optional)
  echo "gemini-lane: fallback to cursor-agent ($CURSOR_MODEL) reason=$2"
  { deny=$(awk -F'\t' -v r="$repo" '$1==r{print $2}' $L/gemini-deny-paths.txt | tr '\n' ' '); [[ -n $deny ]] && echo "HARD RULE: do NOT modify these Karen-gated protocol-2 files: $deny"; cat $P; [[ -n $1 && -s $1 ]] && { echo; echo "A Gemini-proposed patch follows. Apply it if correct (git apply), run the repo tests, fix real failures, never weaken tests:"; cat $1; }; } \
    | ${=SSH} "mkdir -p ~/work/results && cat > ~/work/results/q-$j.prompt"
  ${=SSH} "bash -l ~/nuc-tools/lane-supervise.sh run q-$j ${LANE_LEASE_S:-900} -- bash -l ~/nuc-tools/lane-run-q.sh q-$j $CURSOR_MODEL"; }
# lane-ops v3 (B2): fence before any push this script makes on the Mini: the claim lane-lease.sh holds must be live
fence(){ [[ -z ${LANE_CLAIM_FILE:-} ]] && return 0; python3 ${CLAIM_GATE:-$HOME/Documents/bob-overnight-inject/bin/claim-gate.py} check --claim $LANE_CLAIM_FILE --owner $LANE_CLAIM_OWNER >/dev/null 2>&1; }
mode=cursor
[[ -f $L/gemini.pause ]] && { fallback "" "gemini paused: $(tail -1 $L/gemini.pause)"; exit; }
[[ -n $pr ]] && mode=code   # v2 21:55 CT: Gemini codes PR fixes itself; tests run on NucBox (gemini-apply-test.sh)
if [[ -n $pr && ( $lc == *"rewrite the pr body"* || $lc == *"pr body only"* ) && $lc != *"implement"* ]]; then mode=prbody
elif [[ $lc == *"review only"* || $lc == *critique* || $lc == *"hard review"* ]]; then mode=review
elif [[ -n $pr && ( $lc == *readme* || $lc == *docs* ) && $lc != *screenshot* && $lc != *visual* ]]; then mode=docs
elif [[ -n $pr && ( $lc == *"add tests"* || $lc == *test-only* || $lc == *coverage* ) ]]; then mode=tests
fi
echo "gemini-lane $j repo=$repo pr=${pr:-none} mode=$mode $(date)"
# lane-ops v2: PRs from outside authors or forks never reach Gemini or the cursor fallback (public repos; prompt injection)
if [[ -n $pr ]]; then
  who=$(gh pr view $pr -R $repo --json author,isCrossRepository -q '"\(.author.login) \(.isCrossRepository)"' 2>/dev/null)
  [[ " ${LANE_TRUSTED_AUTHORS:-rupret007} " == *" ${who%% *} "* && ${who##* } == false ]] || { echo "BLOCKER untrusted or unknown PR author/fork ($who); not run"; exit 0; }
fi
[[ $mode == cursor ]] && { fallback "" "no PR / visual job"; exit; }
# v6.3 (22:10 CT): clone/checkout/context on the NucBox (gemini-ctx.sh); only the HTTP call runs on the Mini (key stays on the Mini).
print -r -- $txt | grep -oE '[A-Za-z0-9_./-]+\.(ts|tsx|js|mjs|py|sh|json|md)' | ${=SSH} "bash -l ~/nuc-tools/gemini-ctx.sh q-$j $repo $pr" > $L/q-$j.ctx.txt; crc=$?
(( crc == 4 )) && { fallback "" clone-failed; exit; }
(( crc == 5 )) && [[ $mode != review ]] && { fallback "" checkout-failed; exit; }
ctx=($L/q-$j.ctx.txt)
cargs=(); for c in $ctx; do cargs+=(--ctx $c); done
if [[ $mode == review ]]; then
  python3 $G --mode ${GEMINI_REVIEW_MODE:-review} -f $P $cargs --out $L/q-$j.gemini.md; rc=$?
  echo "RESULT gemini-review rc=$rc out=$L/q-$j.gemini.md"; exit 0
fi
if [[ $mode == prbody ]]; then
  gh pr view $pr -R $repo --json body -q .body > $L/q-$j.oldbody.md; ctx2=(--ctx $L/q-$j.oldbody.md $cargs)
  print -r -- "$txt

Write the complete new PR description in GitHub markdown. Output only the body between lines BODY_BEGIN and BODY_END. Never include local filesystem paths, secrets, or HELD/DO NOT MERGE text unless the task says so." > $L/q-$j.bodyprompt
  python3 $G --mode review -f $L/q-$j.bodyprompt $ctx2 --out $L/q-$j.body.raw >/dev/null
  python3 - $L/q-$j.body.raw $L/q-$j.body.md <<'PY2'
import re,sys
t=open(sys.argv[1]).read(); m=re.search(r"BODY_BEGIN\s*\n(.*?)BODY_END",t,re.S)
if not m: sys.exit(3)
b=m.group(1).strip()
if re.search(r"/Users/|/home/\w+|ghp_|sk-|AIza",b): sys.exit(4)
open(sys.argv[2],"w").write(b+"\n")
PY2
  (( $? == 0 )) || { echo "BLOCKER gemini pr-body draft failed/unsafe (see q-$j.body.raw)"; exit 0; }
  gh pr edit $pr -R $repo --body-file $L/q-$j.body.md >/dev/null && echo "RESULT pr-body-updated https://github.com/$repo/pull/$pr (Gemini; needs Karen re-gate)"; exit 0
fi
if [[ $mode == code || $mode == tests || $mode == docs ]]; then
  EF=${GEMINI_EDIT_FORMAT:-edits}   # lane-ops v2: edits (SEARCH/REPLACE) by default; GEMINI_EDIT_FORMAT=patch restores unified diffs
  for try in 1 2; do
    if [[ $EF == edits ]]; then
      python3 $G --mode edits -f $P $cargs ${=extra} > $L/q-$j.gemini.patch || break
      touched=$(grep -E '^FILE:' $L/q-$j.gemini.patch | sed -E 's/^FILE:[[:space:]]*//; s/[[:space:]]*$//; s/`//g')
    else
      python3 $G --mode patch -f $P $cargs ${=extra} > $L/q-$j.gemini.patch || break
      touched=$(grep -E '^(\+\+\+|---) [ab]/' $L/q-$j.gemini.patch | sed -E 's#^(\+\+\+|---) [ab]/##')
    fi
    if print -r -- $touched | while read pf; do [[ -n $pf ]] && grep -qxF "$repo	$pf" $L/gemini-deny-paths.txt && { echo "$pf"; break; }; done | grep -q .; then echo "BLOCKER patch touches Karen-gated protocol-2 file (gemini-deny-paths.txt); not applied, no fallback"; exit 0; fi
    if [[ -n ${GEMINI_DENY_RE:-} ]] && print -r -- $touched | grep -qE "$GEMINI_DENY_RE"; then echo "BLOCKER patch touches denied path ($GEMINI_DENY_RE)"; exit 0; fi
    ${=SSH} "mkdir -p ~/work/results && cat > ~/work/results/q-$j.gemini.patch" < $L/q-$j.gemini.patch
    # v3 (B3): GAT runs supervised on the NucBox, so a lost lease stops it before its push (lane-hooks/pre-push fences too)
    ${=SSH} "bash -l ~/nuc-tools/lane-supervise.sh run q-$j ${LANE_LEASE_S:-900} -- bash -l ~/nuc-tools/gemini-apply-test.sh q-$j $repo $pr push $EF" > $L/q-$j.gat.$try.log 2>&1; grc=$?
    (( grc == 143 )) && { echo "BLOCKER gemini GAT stopped (lease lost); no fallback"; exit 0; }
    cat $L/q-$j.gat.$try.log
    (( grc == 0 )) && { echo "RESULT gemini-code pr=https://github.com/$repo/pull/$pr $(grep '^GAT pushed' $L/q-$j.gat.$try.log) model=$GEMINI_CODE_MODEL"; exit 0; }
    (( grc == 4 || grc == 5 )) && break
    tail -150 $L/q-$j.gat.$try.log > $L/q-$j.fail.txt; print -r -- "--- previous patch ---" >> $L/q-$j.fail.txt; cat $L/q-$j.gemini.patch >> $L/q-$j.fail.txt
    extra="--ctx $L/q-$j.fail.txt"
  done
  fallback $L/q-$j.gemini.patch "gemini code tries failed"; exit
fi
python3 $G --mode patch -f $P $cargs > $L/q-$j.gemini.patch; rc=$?
if (( rc != 0 )) || ! git apply --check $L/q-$j.gemini.patch 2>$L/q-$j.gemini.apply.err; then
  fallback $L/q-$j.gemini.patch "patch rc=$rc or apply --check failed"; exit; fi
files=(${(f)"$(git apply --numstat $L/q-$j.gemini.patch | awk '{print $3}')"})
if [[ $mode == docs ]] && ! print -l $files | grep -vqE '(\.md$|^docs/)'; then
  fence || { echo "BLOCKER lease lost before docs push; not pushed"; exit 0; }
  git apply $L/q-$j.gemini.patch && git add -A && git commit -qm "docs: Gemini lane update for PR #$pr ($j)" && git push -q origin HEAD \
    && echo "RESULT branch=$(git rev-parse --abbrev-ref HEAD) pr=https://github.com/$repo/pull/$pr head=$(git rev-parse HEAD) tests=docs-only (no code touched)" && exit 0
  fallback $L/q-$j.gemini.patch "docs push failed"; exit
fi
fallback $L/q-$j.gemini.patch "tests/code patch needs a test run"
