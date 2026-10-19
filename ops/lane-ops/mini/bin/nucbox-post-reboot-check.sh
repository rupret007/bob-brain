#!/bin/bash
# nucbox-post-reboot-check.sh: verify NucBox cluster services came back after a reboot and a test job completes.
# Usage: ~/bin/nucbox-post-reboot-check.sh   (exit 0 = all good). Read-only except one test job.
set -uo pipefail
SSH="ssh -i $HOME/.ssh/nuc_ed25519 -p 2222 -o BatchMode=yes -o ConnectTimeout=10 rupret@nuc-wsl"
fail=0
echo "[check] $(date '+%F %T %Z') NucBox post-reboot check"
$SSH 'echo "uptime: $(uptime -p)"; linger=$(loginctl show-user rupret -p Linger 2>/dev/null); echo "$linger"' || { echo "FAIL: ssh unreachable"; exit 2; }
for u in bob-cluster.target bob-nats bob-cluster-worker bob-live; do
  s=$($SSH "XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user is-active $u" 2>/dev/null)
  echo "  $u: ${s:-unknown}"; [ "$s" = active ] || fail=1
done
id="rebootchk-$(date +%Y%m%d%H%M%S)"
echo "[check] submitting test job $id (bob-ops-dashboard cluster unit tests @ pinned 45f4624)"
out=$($SSH "cd ~/work/bob-ops-dashboard && PYTHONPATH=.:\$HOME/.local/share/bob-cluster-py timeout 900 python3 -m cluster.submit --wait --wait-timeout 840 --spec '{\"v\":1,\"id\":\"$id\",\"class\":\"test\",\"repo\":\"rupret007/bob-ops-dashboard\",\"ref\":\"45f462418830058ca91d4e21678dc6300b1c9658\",\"timeout_s\":600,\"load_ceiling\":24,\"cmd\":[\"python3\",\"-m\",\"unittest\",\"discover\",\"-s\",\"cluster/tests\",\"-v\"]}'" 2>&1); rc=$?
echo "$out" | tail -15
if [ $rc -eq 0 ] && echo "$out" | grep -Eq '"(exit_code|rc)": ?0|"status": ?"(ok|success|passed|done)"'; then echo "  test job: PASS"; else echo "  test job: FAIL (rc=$rc)"; fail=1; fi
[ $fail -eq 0 ] && echo "RESULT: ALL GOOD" || echo "RESULT: PROBLEMS FOUND"
exit $fail
