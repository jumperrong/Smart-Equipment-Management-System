#!/bin/bash
# ---------------------------------------------------------------------------
# sems_healthcheck.sh
# 系统级健康检查脚本：curl /health + HTTP 200/ok 判断；
# 可选：失败达到 N 次 → 重启 sems systemd 服务（需要 ExecStart 中有写入权限，或由 root 的 crontab 调用）。
#
# 用法：
#   ./sems_healthcheck.sh                       # 只检查，退出码 0=OK 非 0=NG
#   ./sems_healthcheck.sh --restart-after=3     # 连续失败 3 次后尝试 systemctl restart sems
#   ./sems_healthcheck.sh --url=http://192.168.1.50:8000/health
#
# crontab（root，每 2 分钟检查，连续失败 3 次重启）：
#   */2 * * * * /opt/sems/backend/scripts/sems_healthcheck.sh --restart-after=3 >> /var/log/sems_health.log 2>&1
# ---------------------------------------------------------------------------
set -u

URL="http://127.0.0.1:8000/health"
RESTART_AFTER=0
STATE_DIR="/var/lib/sems"
STATE_FILE="${STATE_DIR}/healthcheck_fail_count"

while [ $# -ge 1 ]; do
  case "$1" in
    --url=*) URL="${1#--url=}" ;;
    --restart-after=*) RESTART_AFTER="${1#--restart-after=}" ;;
    -h|--help)
      sed -n '2,20p' "$0"; exit 0 ;;
    *)
      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$STATE_DIR" 2>/dev/null || true

log() { echo "[$(date '+%F %T')] $*"; }

do_restart_if_needed() {
  local fail=$1
  # fail < 阈值不重启
  if [ "$RESTART_AFTER" -le 0 ] || [ "$fail" -lt "$RESTART_AFTER" ]; then
    return 0
  fi
  log "[WARN] 连续失败 ${fail} 次 ≥ ${RESTART_AFTER}，尝试重启 systemd 服务 sems..."
  if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet sems 2>/dev/null; then
      systemctl restart sems 2>/dev/null && log "[OK] systemctl restart sems 已提交"
    else
      log "[INFO] sems service 当前未 active，改执行 start"
      systemctl start sems 2>/dev/null && log "[OK] systemctl start sems 已提交"
    fi
  else
    log "[WARN] 没有 systemctl，尝试 supervisorctl（如有）/ 手动重启提示"
    command -v supervisorctl >/dev/null 2>&1 && supervisorctl restart sems 2>/dev/null || true
  fi
  # 重启后清零计数（下一轮再记）
  echo 0 > "$STATE_FILE" 2>/dev/null || true
}

# 实际检查
BODY=""
CODE=0
if command -v curl >/dev/null 2>&1; then
  BODY=$(curl -fsS --max-time 8 "$URL" 2>/dev/null) && CODE=0 || CODE=$?
else
  BODY=$(python3 -c "import urllib.request as r; print(r.urlopen('$URL', timeout=8).read().decode()[:200])" 2>/dev/null) && CODE=0 || CODE=$?
fi

OK=0
if [ $CODE -eq 0 ] && [ -n "$BODY" ] && echo "$BODY" | grep -qi "ok"; then
  OK=1
fi

if [ $OK -eq 1 ]; then
  echo 0 > "$STATE_FILE" 2>/dev/null || true
  log "[OK] health=OK body=${BODY//[$'\r\n']/}"
  exit 0
fi

# 失败：累加计数
prev=0
if [ -r "$STATE_FILE" ]; then prev=$(cat "$STATE_FILE" 2>/dev/null || echo 0); fi
prev=$((prev + 0))
next=$((prev + 1))
echo "$next" > "$STATE_FILE" 2>/dev/null || true
log "[FAIL] health=NG (连续失败 $next 次, curl/exit=$CODE, body=$BODY)"
do_restart_if_needed "$next"
exit 1
