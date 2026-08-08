#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install.sh   安装 SEMS 为 systemd 服务（开机自启 + 崩溃自重启 + 看门狗）
#
# 用法（需 root；没 root 时加 --user-level 走用户级 systemd + loginctl linger）：
#   sudo bash ./install.sh --backend-dir=/opt/sems/backend --user=sems --group=sems
#   sudo bash ./install.sh --backend-dir=/opt/sems/backend --port=8000 --with-healthcheck-cron
#
#   # 无 root：用户级 systemd（需宿主机装 systemd --user 可用）
#   bash ./install.sh --user-level --backend-dir=$HOME/sems/backend --port=8000
# ---------------------------------------------------------------------------
set -euo pipefail

BACKEND_DIR=""
USER_NAME="sems"
GROUP_NAME="sems"
PORT="8000"
HOST="0.0.0.0"
SERVICE_NAME="sems"
USER_LEVEL=0
WITH_HC_CRON=0

usage() {
  sed -n '2,15p' "$0"
  echo
  echo "Options:"
  echo "  --backend-dir=PATH      绝对路径，必需（指向 backend 目录，含 .venv/.env/data）"
  echo "  --user=NAME             运行用户（默认 sems；user-level 默认是当前 \$USER）"
  echo "  --group=NAME            运行组（默认 sems）"
  echo "  --port=NUM              后端端口（默认 8000）"
  echo "  --host=ADDR             监听地址（默认 0.0.0.0）"
  echo "  --service-name=NAME     systemd unit 名，默认 sems"
  echo "  --with-healthcheck-cron 追加 root crontab 健康检查（连续失败3次→重启）"
  echo "  --user-level            装到 ~/.config/systemd/user/；开机自启需要 loginctl enable-linger"
  echo "  -h/--help               本帮助"
}

while [ $# -ge 1 ]; do
  case "$1" in
    --backend-dir=*) BACKEND_DIR="${1#--backend-dir=}" ;;
    --user=*) USER_NAME="${1#--user=}" ;;
    --group=*) GROUP_NAME="${1#--group=}" ;;
    --port=*) PORT="${1#--port=}" ;;
    --host=*) HOST="${1#--host=}" ;;
    --service-name=*) SERVICE_NAME="${1#--service-name=}" ;;
    --with-healthcheck-cron) WITH_HC_CRON=1 ;;
    --user-level) USER_LEVEL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -z "$BACKEND_DIR" ]; then
  echo "[ERROR] 必须指定 --backend-dir=/path/to/backend（绝对路径）" >&2
  exit 2
fi
BACKEND_DIR="$(cd "$BACKEND_DIR" && pwd)"
if [ ! -f "$BACKEND_DIR/run_server.py" ]; then
  echo "[ERROR] $BACKEND_DIR 下没有 run_server.py；--backend-dir 应指向 backend 根目录" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------- 选部署方式 ----------
if [ "$USER_LEVEL" -eq 1 ]; then
  if [ "$(id -u)" -eq 0 ]; then
    echo "[WARN] --user-level 不建议配合 sudo/root。请用目标部署用户直接执行本脚本。"
  fi
  if [ "$USER_NAME" = "sems" ] && [ "$GROUP_NAME" = "sems" ]; then
    USER_NAME="$USER"
    GROUP_NAME="$(id -g -n)"
  fi
  UNIT_DIR="${HOME}/.config/systemd/user"
  UNIT_PATH="${UNIT_DIR}/${SERVICE_NAME}.service"
  LOG_DIR="${HOME}/.local/state/sems/logs"
  STATE_DIR="${HOME}/.local/state/sems/lib"
  mkdir -p "$UNIT_DIR" "$LOG_DIR" "$STATE_DIR"
else
  if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] system 级安装需要 root。请 sudo bash ./install.sh ...  或用 --user-level" >&2
    exit 3
  fi
  UNIT_DIR="/etc/systemd/system"
  UNIT_PATH="${UNIT_DIR}/${SERVICE_NAME}.service"
  LOG_DIR="/var/log/sems"
  STATE_DIR="/var/lib/sems"
  # 创建运行用户（如不存在）
  if ! id "$USER_NAME" >/dev/null 2>&1; then
    useradd -r -s /usr/sbin/nologin -U -d "$BACKEND_DIR" "$USER_NAME"
    echo "[OK] 新建系统用户 $USER_NAME:$GROUP_NAME"
  fi
  mkdir -p "$LOG_DIR" "$STATE_DIR"
  # data/.env / scripts 目录授权给运行用户
  chown -R "$USER_NAME:$GROUP_NAME" "$BACKEND_DIR/data" 2>/dev/null || true
  chown -R "$USER_NAME:$GROUP_NAME" "$BACKEND_DIR/scripts" 2>/dev/null || true
  [ -f "$BACKEND_DIR/.env" ] && chown "$USER_NAME:$GROUP_NAME" "$BACKEND_DIR/.env" 2>/dev/null || true
  chown -R "$USER_NAME:$GROUP_NAME" "$LOG_DIR" "$STATE_DIR"
  # .venv 仅读权限（保证 python 能运行即可）
  if [ -d "$BACKEND_DIR/.venv" ]; then
    chmod -R a+rX "$BACKEND_DIR/.venv" 2>/dev/null || true
  fi
fi

# 选 python 路径
PYTHON_BIN="/usr/bin/python3"
if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
fi
echo "[INFO] Python: $PYTHON_BIN"
echo "[INFO] Backend: $BACKEND_DIR"
echo "[INFO] Unit target: $UNIT_PATH"

# ---------- 生成 unit ----------
# 把模板中的占位符替换为实际值
SRC_UNIT="$SCRIPT_DIR/sems.service"
if [ ! -f "$SRC_UNIT" ]; then
  echo "[ERROR] 找不到模板 $SRC_UNIT" >&2; exit 4
fi

sed_script=(
  -e "s|User=sems|User=${USER_NAME}|g"
  -e "s|Group=sems|Group=${GROUP_NAME}|g"
  -e "s|WorkingDirectory=/opt/sems/backend|WorkingDirectory=${BACKEND_DIR}|g"
  -e "s|/opt/sems/backend/.venv/bin|${PYTHON_BIN%/python}|g"
  -e "s|SEMS_LOG_DIR=/var/log/sems|SEMS_LOG_DIR=${LOG_DIR}|g"
  -e "s|ReadWritePaths=/opt/sems/backend/data|ReadWritePaths=${BACKEND_DIR}/data ${BACKEND_DIR}/.env ${LOG_DIR}|g"
  -e "s|ReadWritePaths=/opt/sems/backend/scripts /opt/sems/backend|ReadWritePaths=${BACKEND_DIR}/scripts ${BACKEND_DIR}|g"
)

# 注意：user-level 系统级沙箱能力不完全一致，降级更安全的配置
if [ "$USER_LEVEL" -eq 1 ]; then
  # ProtectSystem / PrivateDevices / ProtectKernel* 在 user-level 经常受限，退化为更宽松设置
  sed_script+=(
    -e 's|^ProtectSystem=strict$|ProtectSystem=false|'
    -e 's|^PrivateDevices=false$|PrivateDevices=false|'
    -e 's|^ProtectKernelTunables=true$|#ProtectKernelTunables=true|'
    -e 's|^ProtectKernelModules=true$|#ProtectKernelModules=true|'
    -e 's|^ProtectControlGroups=true$|#ProtectControlGroups=true|'
    -e 's|^RestrictSUIDSGID=true$|#RestrictSUIDSGID=true|'
    -e 's|^RestrictNamespaces=true$|#RestrictNamespaces=true|'
    -e 's|^LockPersonality=true$|#LockPersonality=true|'
    -e 's|^RestrictRealtime=true$|#RestrictRealtime=true|'
    -e 's|^NoNewPrivileges=true$|NoNewPrivileges=false|'
    -e 's|^SystemCallArchitectures=native$|#SystemCallArchitectures=native|'
    -e 's|^RemoveIPC=true$|RemoveIPC=false|'
    -e "s|WantedBy=multi-user.target|WantedBy=default.target|"
  )
fi

sed "${sed_script[@]}" "$SRC_UNIT" > "$UNIT_PATH"
# 再替换一次 ExecStart 路径（sed 顺序问题）
sed -i "s|ExecStart=/opt/sems/backend/.venv/bin/python /opt/sems/backend/run_server.py|ExecStart=${PYTHON_BIN} ${BACKEND_DIR}/run_server.py|" "$UNIT_PATH"

echo "[OK] unit 已写入：$UNIT_PATH"

# 环境变量：端口/host：通过 drop-in 写入（不要污染 .env）
DROPIN_DIR="${UNIT_PATH}.d"
mkdir -p "$DROPIN_DIR"
cat >"${DROPIN_DIR}/10-port-host.conf" <<EOF
[Service]
Environment=PORT=${PORT}
Environment=HOST=${HOST}
EOF
echo "[OK] drop-in 端口/主机配置已写入 ${DROPIN_DIR}/10-port-host.conf"

# ---------- 让 systemd 识别并 enable + start ----------
if [ "$USER_LEVEL" -eq 1 ]; then
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  if [ ! -d "$XDG_RUNTIME_DIR" ]; then
    echo "[WARN] 没有 \$XDG_RUNTIME_DIR，systemd --user 可能不可用。建议："
    echo "         loginctl enable-linger $USER_NAME"
    echo "         export XDG_RUNTIME_DIR=/run/user/\$(id -u)"
  fi
  systemctl --user daemon-reload
  systemctl --user enable "${SERVICE_NAME}.service" || true
  echo ""
  echo "[NEXT] 启动服务（前台/手动）：systemctl --user start ${SERVICE_NAME}.service"
  echo "[NEXT] 查看日志：        journalctl --user -u ${SERVICE_NAME}.service -f"
  echo "[NEXT] 开机自启："
  echo "       sudo loginctl enable-linger $USER_NAME   （否则用户登出后服务会停）"
  echo "       systemctl --user is-enabled ${SERVICE_NAME}.service   → 应该显示 enabled"
else
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}.service" || true
  echo ""
  echo "[OK] 自启已 enable。现在启动："
  echo "       sudo systemctl start ${SERVICE_NAME}.service"
  echo "[OK] 立即查看运行状态："
  echo "       sudo systemctl status ${SERVICE_NAME}.service"
  echo "       sudo journalctl -u ${SERVICE_NAME}.service -f --since today"
  echo "       sudo cat ${LOG_DIR}/sems.log  ${LOG_DIR}/sems.error.log"
  echo "       curl -fsS http://127.0.0.1:${PORT}/health"
fi

# ---------- 可选：健康检查 crontab（连续失败 3 次自动重启） ----------
if [ "$WITH_HC_CRON" -eq 1 ]; then
  HC_SCRIPT="$SCRIPT_DIR/sems_healthcheck.sh"
  chmod +x "$HC_SCRIPT" 2>/dev/null || true
  CRON_LINE="*/2 * * * * $HC_SCRIPT --url=http://127.0.0.1:${PORT}/health --restart-after=3 >> ${LOG_DIR}/healthcheck.log 2>&1"
  if [ "$USER_LEVEL" -eq 1 ]; then
    ( crontab -l 2>/dev/null || true; echo "$CRON_LINE" ) | crontab -
    echo "[OK] user-level crontab 已追加健康检查（每 2 分钟）"
  else
    ( crontab -l -u root 2>/dev/null || true; echo "$CRON_LINE" ) | crontab -u root -
    echo "[OK] root crontab 已追加健康检查（每 2 分钟，连续失败 3 次 systemctl restart $SERVICE_NAME）"
  fi
fi

echo ""
echo "===== install 完成 ====="
