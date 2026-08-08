#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# uninstall.sh   移除 SEMS systemd 服务（与 install_service.sh 对应）
# 用法：
#   sudo bash ./uninstall.sh [--service-name=sems] [--user-level] [--purge-data]
#         --purge-data: 会一并删除 /var/log/sems 与 /var/lib/sems（默认不删，避免误删日志/健康计数）
# ---------------------------------------------------------------------------
set -euo pipefail

SERVICE_NAME="sems"
USER_LEVEL=0
PURGE=0

while [ $# -ge 1 ]; do
  case "$1" in
    --service-name=*) SERVICE_NAME="${1#--service-name=}" ;;
    --user-level) USER_LEVEL=1 ;;
    --purge-data) PURGE=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$USER_LEVEL" -eq 1 ]; then
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    systemctl --user stop "$SERVICE_NAME" || true
    echo "[OK] stop user-level $SERVICE_NAME"
  fi
  systemctl --user disable "$SERVICE_NAME.service" 2>/dev/null || true
  UNIT="${HOME}/.config/systemd/user/${SERVICE_NAME}.service"
  [ -f "$UNIT" ] && rm -f "$UNIT" && echo "[OK] 删除 $UNIT"
  DROPIN="${UNIT}.d"
  [ -d "$DROPIN" ] && rm -rf "$DROPIN" && echo "[OK] 删除 drop-in: $DROPIN"
  systemctl --user daemon-reload || true
  # 健康检查 cron：卸载时只注释掉，不删整份 crontab
  ( crontab -l 2>/dev/null || true ) | sed -E '/sems_healthcheck\.sh/ s/^/# DISABLED-by-sems-uninstall # /' | crontab - || true
  if [ "$PURGE" -eq 1 ]; then
    rm -rf "${HOME}/.local/state/sems"
    echo "[PURGE] 删除 ~/.local/state/sems"
  fi
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "[ERROR] 需要 root 才能卸载 system service。请 sudo bash ./uninstall.sh 或加 --user-level" >&2
  exit 3
fi

if systemctl is-active --quiet "$SERVICE_NAME"; then
  systemctl stop "$SERVICE_NAME"
  echo "[OK] stop $SERVICE_NAME"
fi
systemctl disable "$SERVICE_NAME.service" 2>/dev/null || true
UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
[ -f "$UNIT" ] && rm -f "$UNIT" && echo "[OK] 删除 $UNIT"
DROPIN="${UNIT}.d"
[ -d "$DROPIN" ] && rm -rf "$DROPIN" && echo "[OK] 删除 drop-in: $DROPIN"
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

# 健康检查 cron：注释行（不破坏管理员其它条目）
( crontab -l -u root 2>/dev/null || true ) | sed -E '/sems_healthcheck\.sh/ s/^/# DISABLED-by-sems-uninstall # /' | crontab -u root - || true

if [ "$PURGE" -eq 1 ]; then
  rm -rf /var/log/sems /var/lib/sems
  echo "[PURGE] 删除 /var/log/sems /var/lib/sems"
fi
echo "===== uninstall 完成 ====="
