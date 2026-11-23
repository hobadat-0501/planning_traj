#!/usr/bin/env bash
# Chạy CARLA KHÔNG giao diện + batch, tự dựng lại server nếu chết. Dùng khi chạy hàng loạt, tiết kiệm VRAM.
#
#   bash av_conformal/scripts/run_headless.sh --exp B0_shared
#   bash av_conformal/scripts/run_headless.sh --exp B0_shared --seeds 0-4 --out av_conformal/data/raw/B0_pilot
#
# Tùy chọn: --mode nullrhi|offscreen (mặc định nullrhi, tự chuyển sang offscreen nếu server không lên được)
#           --carla-dir DIR  --port 2000  --tm-port 8000  --keep-server (không tắt server khi xong)
# Chạy ngầm, sống sót khi đóng terminal:
#   nohup bash av_conformal/scripts/run_headless.sh --exp B0_shared > b0_shared.log 2>&1 &
set -u

EXP=""; SEEDS=""; OUT=""; MODE="nullrhi"; CARLA_DIR=""; PORT=2000; TM_PORT=8000; KEEP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --exp) EXP="$2"; shift 2;;
    --seeds) SEEDS="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    --mode) MODE="$2"; shift 2;;
    --carla-dir) CARLA_DIR="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --tm-port) TM_PORT="$2"; shift 2;;
    --keep-server) KEEP=1; shift;;
    *) echo "tham số lạ: $1"; exit 2;;
  esac
done
[ -n "$EXP" ] || { echo "thiếu --exp"; exit 2; }
OUT="${OUT:-av_conformal/data/raw/$EXP}"
if [ -z "$CARLA_DIR" ]; then
  sh_path=$(find ~ -maxdepth 4 -name CarlaUE4.sh 2>/dev/null | head -1)
  [ -n "$sh_path" ] || { echo "không tìm thấy CarlaUE4.sh, dùng --carla-dir"; exit 2; }
  CARLA_DIR=$(dirname "$sh_path")
fi
LOGDIR="av_conformal/data/logs"; mkdir -p "$LOGDIR" "$OUT"
SLOG="$LOGDIR/carla_server_$PORT.log"
SERVER_PID=""
STARTED_BY_US=0

log() { echo "[$(date +%H:%M:%S)] $*"; }

server_alive() { pgrep -f "CarlaUE4.*-carla-rpc-port=$PORT" > /dev/null; }   # khớp cả CarlaUE4.sh lẫn tiến trình chính

kill_server() {
  pkill -f "CarlaUE4.sh.*-carla-rpc-port=$PORT" 2>/dev/null
  pkill -f "CarlaUE4-Linux-Shipping.*-carla-rpc-port=$PORT" 2>/dev/null
  sleep 3
}

start_server() {
  local flags
  case "$MODE" in
    nullrhi)   flags="-nullrhi -nosound -quality-level=Low";;
    offscreen) flags="-RenderOffScreen -nosound -quality-level=Low";;
    *) echo "mode lạ: $MODE"; exit 2;;
  esac
  log "khởi động CARLA ($MODE) cổng $PORT, log: $SLOG"
  kill_server
  ( cd "$CARLA_DIR" && setsid nohup ./CarlaUE4.sh $flags -carla-rpc-port=$PORT > "$OLDPWD/$SLOG" 2>&1 & )
  STARTED_BY_US=1
}

wait_ready() {   # tối đa ~180 s
  local i
  sleep 10   # ân hạn: tiến trình chính sinh ra chậm sau CarlaUE4.sh
  for i in $(seq 1 34); do
    server_alive || { log "server đã thoát khi khởi động; log:"; tail -5 "$SLOG"; return 1; }
    if python - <<EOF 2>/dev/null
import carla
c = carla.Client("localhost", $PORT); c.set_timeout(5)
c.get_server_version()
EOF
    then log "server sẵn sàng"; return 0; fi
    sleep 5
  done
  log "server không sẵn sàng sau 180 s"; return 1
}

cleanup() {
  if [ "$KEEP" -eq 0 ] && [ "$STARTED_BY_US" -eq 1 ]; then log "tắt server"; kill_server; fi
}
trap cleanup EXIT

BATCH_ARGS="--exp $EXP --backend carla --host localhost --port $PORT --tm-port $TM_PORT --out $OUT"
[ -n "$SEEDS" ] && BATCH_ARGS="$BATCH_ARGS --seeds $SEEDS"

start_fail=0; err_rounds=0
for round in $(seq 1 60); do
  if ! server_alive; then
    start_server
    if ! wait_ready; then
      start_fail=$((start_fail + 1))
      if [ "$start_fail" -ge 2 ] && [ "$MODE" = "nullrhi" ]; then
        log "nullrhi không chạy được, chuyển sang offscreen"; MODE="offscreen"; start_fail=0
      elif [ "$start_fail" -ge 3 ]; then
        log "server không lên được; xem $SLOG"; exit 1
      fi
      kill_server; continue
    fi
    start_fail=0
  fi
  log "vòng $round: chạy batch"
  python -m av_conformal.scripts.batch $BATCH_ARGS | tee -a "$LOGDIR/batch_$EXP.log"
  rc=${PIPESTATUS[0]}
  last=$(tail -1 "$LOGDIR/batch_$EXP.log")
  if [ "$rc" -eq 0 ]; then
    if echo "$last" | grep -q '"errors": 0'; then log "xong: $last"; exit 0; fi
    err_rounds=$((err_rounds + 1))
    log "còn lượt lỗi ($last), thử lại lần $err_rounds/3"
    [ "$err_rounds" -ge 3 ] && { log "dừng: lượt lỗi vẫn còn sau 3 lần thử lại"; exit 1; }
  else
    log "batch thoát mã $rc (thường do CARLA abort); thử lại sau 20 s"
  fi
  server_alive || log "server không còn chạy, sẽ dựng lại"
  sleep 20
done
log "hết số vòng thử lại"; exit 1
