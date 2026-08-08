#!/bin/bash
# ---------------------------------------------------------------------------
# watchdog_user.sh —— 极简用户级看门狗（无 root / 无 systemd 也能用）。
# 场景：受限环境（不能写 systemd、没有 sudo、只读系统目录）。
# 用 cron @reboot 启动；每分钟自己检查 run_server 是否存活 + /health 是否返回 ok；
# 连续失败 N 次 → kill 旧进程 → 拉起新进程。
#
# 用法（只看当前用户，不涉及 root）：
#   1) 首次：  bash ./watchdog_user.sh install --backend-dir=$HOME/sems/backend --port=8000
#              将把脚本自身写进 crontab: @reboot / 每分钟
#   2) 卸载：  bash ./watchdog_user.sh uninstall
#   3) 手动拉：bash ./watchdog_user.sh tick --backend-dir=... --port=8000   (用于调试)
# ---------------------------------------------------------------------------
set -u

MODE="${1:-install}"
BACKEND_DIR=""
PORT="8000"
LOG_DIR=""
MAX_FAIL=3

install() {
  [ -z "$BACKEND_DIR" ] && { echo "--backend-dir= required"; exit 2; }
  BACKEND_DIR="$(cd "$BACKEND_DIR" && pwd)"
  SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
  if [ -z "$LOG_DIR" ]; then LOG_DIR="$BACKEND_DIR/data/logs"; fi
  mkdir -p "$LOG_DIR"

  cat >"${HOME}/.sems_watchdog.conf" <<EOF
BACKEND_DIR=$BACKEND_DIR
PORT=$PORT
LOG_DIR=$LOG_DIR
MAX_FAIL=$MAX_FAIL
EOF
  chmod 600 "${HOME}/.sems_watchdog.conf"

  # 写两份：开机自启 + 每分钟 tick
  (
    crontab -l 2>/dev/null | grep -vE "(^[^#]*sems_watchdog\.sh)" || true
    echo ""
    echo "@reboot /bin/bash $SCRIPT tick --from-cron >> $LOG_DIR/watchdog.log 2>&1"
    echo "* * * * * /bin/bash $SCRIPT tick --from-cron >> $LOG_DIR/watchdog.log 2>&1"
  ) | crontab -

  echo "[OK] 看门狗已写入当前用户 crontab："
  crontab -l | grep sems_watchdog
  echo ""
  echo "配置文件：${HOME}/.sems_watchdog.conf"
  echo "日志：$LOG_DIR/watchdog.log"
  echo "接下来 1 分钟内 watchdog 会第一次 tick，自动拉起 run_server。"
}

uninstall() {
  ( crontab -l 2>/dev/null || true ) | grep -vE "(^[^#]*sems_watchdog\.sh)" | crontab -
  rm -f "${HOME}/.sems_watchdog.conf"
  echo "[OK] 看门狗已从当前用户 crontab 移除，配置文件已删除。"
}

tick() {
  # 读配置
  CONF="${HOME}/.sems_watchdog.conf"
  if [ -r "$CONF" ]; then
    # shellcheck disable=SC1090
    source "$CONF"
  else
    # 参数兜底
    :
  fi
  [ -z "$BACKEND_DIR" ] && { echo "[FAIL] 无 BACKEND_DIR 配置"; exit 2; }
  mkdir -p "$LOG_DIR"
  STATE_FILE="${LOG_DIR}/.watchdog_fail_count"
  PID_FILE="${LOG_DIR}/.watchdog_server.pid"

  log() { echo "[$(date '+%F %T')] $*"; }

  # 1. /health 检查
  alive=0
  if command -v curl >/dev/null 2>&1; then
    B=$(curl -fsS --max-time 6 "http://127.0.0.1:${PORT}/health" 2>/dev/null) && [[ "$B" == *ok* ]] && alive=1
  else
    B=$(python3 -c "import urllib.request as r; print(r.urlopen('http://127.0.0.1:${PORT}/health', timeout=6).read().decode())" 2>/dev/null) && [[ "$B" == *ok* ]] && alive=1
  fi

  if [ "$alive" -eq 1 ]; then
    echo 0 > "$STATE_FILE" 2>/dev/null || true
    exit 0
  fi

  # 2. 失败计数
  prev=0; [ -r "$STATE_FILE" ] && prev=$(cat "$STATE_FILE" 2>/dev/null || echo 0); prev=$((prev+0))
  next=$((prev+1))
  echo "$next" > "$STATE_FILE" 2>/dev/null || true
  log "health FAIL ($next/$MAX_FAIL): body=$B"
  if [ "$next" -lt "$MAX_FAIL" ]; then
    exit 0
  fi

  # 3. 达到阈值：强制清理并拉起
  log "达到连续失败阈值，开始拉起 run_server..."

  # 清理旧进程（精确：含 run_server.py + python -m uvicorn 监听 $PORT）
  if [ -r "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
      log "kill old pid=$OLD_PID (SIGTERM, wait up to 20s)"
      kill -TERM "$OLD_PID" 2>/dev/null || true
      for _ in $(seq 1 20); do
        kill -0 "$OLD_PID" 2>/dev/null || break
        sleep 1
      done
      kill -0 "$OLD_PID" 2>/dev/null && kill -KILL "$OLD_PID" 2>/dev/null || true
    fi
  fi
  # 兜底：端口占用的进程再查一次，杀掉
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
  fi
  sleep 2

  # 拉起新进程：setsid + nohup，避免 cron 退出时被回收
  cd "$BACKEND_DIR" || exit 2
  PY_BIN="python3"
  [ -x "$BACKEND_DIR/.venv/bin/python" ] && PY_BIN="$BACKEND_DIR/.venv/bin/python"
  export SEMS_OPEN_BROWSER=0 PORT="$PORT" HOST="0.0.0.0" SEMS_LOG_DIR="$LOG_DIR"
  nohup setsid "$PY_BIN" "$BACKEND_DIR/run_server.py" >>"$LOG_DIR/watchdog_server.stdout.log" 2>&1 &
  NEW_PID=$!
  echo "$NEW_PID" > "$PID_FILE"
  log "已启动 run_server.py (pid=$NEW_PID)"
  echo 0 > "$STATE_FILE" 2>/dev/null || true
  exit 0
}

# 参数解析：install/uninstall 模式取 --backend-dir 等；tick 只关心 --from-cron(忽略)
shift || true
while [ $# -ge 1 ]; do
  case "$1" in
    --backend-dir=*) BACKEND_DIR="${1#--backend-dir=}" ;;
    --port=*) PORT="${1#--port=}" ;;
    --log-dir=*) LOG_DIR="${1#--log-dir=}" ;;
    --max-fail=*) MAX_FAIL="${1#--max-fail=}" ;;
    --from-cron) : ;;
    *) echo "unknown tick/install arg: $1" >&2; exit 2 ;;
  esac
  shift
done

case "$MODE" in
  install) install ;;
  uninstall) uninstall ;;
  tick) tick ;;
  -h|--help) sed -n '2,15p' "$0" ;;
  *) echo "unknown mode $MODE"; exit 2 ;;
esac
