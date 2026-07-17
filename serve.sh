#!/usr/bin/env bash
set -euo pipefail

# Code Forge 服务管理脚本（开发 / 生产通用）
#
# 用法:
#   ./serve.sh <command> [target] [--prod]
#
# 命令:
#   start    启动服务
#   stop     停止服务
#   restart  重启服务
#   status   查看运行状态
#   logs     查看日志 (tail -f)
#
# 目标:
#   backend   仅后端
#   frontend  仅前端（生产模式跳过，由 nginx 托管）
#   all       全部（默认）
#
# 选项:
#   --prod    生产模式（无 --reload，前端不启动，uv --no-dev）
#
# 示例:
#   ./serve.sh start                     # 开发模式启动全部
#   ./serve.sh start backend --prod      # 生产模式启动后端
#   ./serve.sh restart backend           # 开发模式重启后端
#   ./serve.sh stop all                  # 停止全部

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PID_DIR="$ROOT_DIR/.serve-pids"
LOG_DIR="$ROOT_DIR/.serve-logs"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

BACKEND_PORT=8000
FRONTEND_PORT=5173

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 解析参数 ──────────────────────────────────────────────

ACTION=""
TARGET="all"
PROD=false

for arg in "$@"; do
  case "$arg" in
    start|stop|restart|status|logs) ACTION="$arg" ;;
    backend|frontend|all)           TARGET="$arg" ;;
    --prod)                         PROD=true ;;
    -h|--help)                      ACTION="help" ;;
  esac
done

mkdir -p "$PID_DIR" "$LOG_DIR"

# ── 工具函数 ──────────────────────────────────────────────

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid=$(cat "$pid_file" 2>/dev/null) || return 1
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

get_pid() { cat "$1" 2>/dev/null || echo ""; }

port_in_use() { lsof -iTCP:"$1" -sTCP:LISTEN -P -n 2>/dev/null | grep -q .; }

stop_pid() {
  local pid="$1" name="$2"
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then
    warn "$name 未响应 SIGTERM，发送 SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
    sleep 1
  fi
}

# ── Backend ───────────────────────────────────────────────

start_backend() {
  if is_running "$BACKEND_PID_FILE"; then
    warn "backend 已在运行 (PID $(get_pid "$BACKEND_PID_FILE"))"
    return 0
  fi
  if port_in_use "$BACKEND_PORT"; then
    error "端口 $BACKEND_PORT 被占用"
    return 1
  fi

  local uv_flag="--reload"
  if $PROD; then
    uv_flag=""
    info "生产模式：无 --reload，uv --no-dev"
  else
    info "开发模式：--reload 热加载"
  fi

  info "启动 backend ..."
  (
    cd "$BACKEND_DIR"
    .venv/bin/python -m uvicorn app.main:app \
      --host 0.0.0.0 --port "$BACKEND_PORT" \
      $($PROD || echo --reload) \
      >> "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
  )

  sleep 2
  if is_running "$BACKEND_PID_FILE"; then
    info "backend 已启动 (PID $(get_pid "$BACKEND_PID_FILE")) → :$BACKEND_PORT"
    info "  日志: $BACKEND_LOG"
  else
    error "backend 启动失败"
    tail -20 "$BACKEND_LOG" 2>/dev/null
    return 1
  fi
}

stop_backend() {
  if ! is_running "$BACKEND_PID_FILE"; then
    rm -f "$BACKEND_PID_FILE"
    info "backend 未在运行"
    return 0
  fi
  local pid
  pid=$(get_pid "$BACKEND_PID_FILE")
  info "停止 backend (PID $pid) ..."
  stop_pid "$pid" "backend"
  rm -f "$BACKEND_PID_FILE"
  info "backend 已停止"
}

# ── Frontend ──────────────────────────────────────────────

start_frontend() {
  if $PROD; then
    info "生产模式：前端由 nginx 托管，跳过"
    return 0
  fi
  if is_running "$FRONTEND_PID_FILE"; then
    warn "frontend 已在运行 (PID $(get_pid "$FRONTEND_PID_FILE"))"
    return 0
  fi
  if port_in_use "$FRONTEND_PORT"; then
    error "端口 $FRONTEND_PORT 被占用"
    return 1
  fi

  info "启动 frontend ..."
  (
    cd "$FRONTEND_DIR"
    pnpm dev >> "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
  )

  sleep 2
  if is_running "$FRONTEND_PID_FILE"; then
    info "frontend 已启动 (PID $(get_pid "$FRONTEND_PID_FILE")) → :$FRONTEND_PORT"
    info "  日志: $FRONTEND_LOG"
  else
    error "frontend 启动失败"
    tail -20 "$FRONTEND_LOG" 2>/dev/null
    return 1
  fi
}

stop_frontend() {
  if $PROD; then
    return 0
  fi
  if ! is_running "$FRONTEND_PID_FILE"; then
    rm -f "$FRONTEND_PID_FILE"
    info "frontend 未在运行"
    return 0
  fi
  local pid
  pid=$(get_pid "$FRONTEND_PID_FILE")
  info "停止 frontend (PID $pid) ..."
  stop_pid "$pid" "frontend"
  rm -f "$FRONTEND_PID_FILE"
  info "frontend 已停止"
}

# ── 命令分发 ──────────────────────────────────────────────

usage() {
  cat <<'EOF'
Code Forge 服务管理脚本（开发 / 生产通用）

用法:
  ./serve.sh <command> [target] [--prod]

命令:
  start    启动服务
  stop     停止服务
  restart  重启服务
  status   查看运行状态
  logs     查看日志 (tail -f)

目标:
  backend   仅后端
  frontend  仅前端（生产模式跳过，由 nginx 托管）
  all       全部（默认）

选项:
  --prod    生产模式（无 --reload，前端不启动）

示例:
  ./serve.sh start                     # 开发模式启动全部
  ./serve.sh start backend --prod      # 生产模式启动后端
  ./serve.sh restart backend           # 重启后端
  ./serve.sh stop all                  # 停止全部
  ./serve.sh status                    # 查看状态
  ./serve.sh logs backend              # 跟随后端日志
EOF
}

do_start() {
  case "$TARGET" in
    backend)   start_backend ;;
    frontend)  start_frontend ;;
    all)       start_backend; start_frontend ;;
    *)         error "未知目标: $TARGET"; usage; exit 1 ;;
  esac
}

do_stop() {
  case "$TARGET" in
    backend)   stop_backend ;;
    frontend)  stop_frontend ;;
    all)       stop_frontend; stop_backend ;;
    *)         error "未知目标: $TARGET"; usage; exit 1 ;;
  esac
}

do_restart() {
  case "$TARGET" in
    backend)   stop_backend; start_backend ;;
    frontend)  stop_frontend; start_frontend ;;
    all)       stop_frontend; stop_backend; start_backend; start_frontend ;;
    *)         error "未知目标: $TARGET"; usage; exit 1 ;;
  esac
}

do_status() {
  echo "Code Forge 服务状态"
  echo "─────────────────────────────────────"
  if is_running "$BACKEND_PID_FILE"; then
    echo -e "  backend   ${GREEN}running${NC}  (PID $(get_pid "$BACKEND_PID_FILE"))  :$BACKEND_PORT"
  else
    echo -e "  backend   ${RED}stopped${NC}"
  fi
  if is_running "$FRONTEND_PID_FILE"; then
    echo -e "  frontend  ${GREEN}running${NC}  (PID $(get_pid "$FRONTEND_PID_FILE"))  :$FRONTEND_PORT"
  else
    echo -e "  frontend  ${RED}stopped${NC}"
  fi
  echo
}

do_logs() {
  case "$TARGET" in
    backend)   exec tail -f "$BACKEND_LOG" ;;
    frontend)  exec tail -f "$FRONTEND_LOG" ;;
    all)       exec tail -f "$BACKEND_LOG" "$FRONTEND_LOG" ;;
    *)         error "未知目标: $TARGET"; usage; exit 1 ;;
  esac
}

case "$ACTION" in
  start)   do_start ;;
  stop)    do_stop ;;
  restart) do_restart ;;
  status)  do_status ;;
  logs)    do_logs ;;
  *)       usage; exit 1 ;;
esac
