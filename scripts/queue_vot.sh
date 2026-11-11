#!/bin/zsh
# Value-of-time runs with continuous batching (independent one-question calls decoded side by side;
# each call has its own context, nothing is shared). Optional arg: a pid to wait for first.
# Log: runs/queue.log
set -u
cd "$(dirname "$0")/.."
UV="${UV:-uv}"
WAIT_PID="${1:-0}"
BS=${BS:-8}
LOG=runs/queue.log
mkdir -p runs

# Run a stage until every cell is done; a crash (e.g. Metal OOM) just resumes from completed cells.
run_stage() {
  local id=$1; shift
  for attempt in $(seq 1 200); do
    caffeinate -i $UV run --extra mlx python -m value_of_time.run "$@" --engine mlx --batch-size $BS \
      --run-id $id >> $LOG 2>&1 && return 0
    echo "$(date '+%F %T') $id crashed (attempt $attempt); resuming in 30s" >> $LOG
    sleep 30
  done
  return 1
}
if [ "$WAIT_PID" != "0" ]; then
  echo "$(date '+%F %T') waiting on pid $WAIT_PID" >> $LOG
  while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 60; done
fi
echo "$(date '+%F %T') start s1_single (batch $BS)" >> $LOG

# Stage 1: no memories + each memory alone, 5 reps.
run_stage s1_single --stages baseline single --reps 5 || { echo "s1 failed" >> $LOG; exit 1; }
$UV run python -m value_of_time.analyze runs/s1_single >> $LOG 2>&1
echo "$(date '+%F %T') s1 done; start s2_combos" >> $LOG

# Stage 2: pairs, one-at-a-time ladders, all nine; 2 reps.
run_stage s2_combos --stages pairs ladder full --reps 2 || { echo "s2 failed" >> $LOG; exit 1; }
$UV run python -m value_of_time.analyze runs/s2_combos >> $LOG 2>&1
echo "$(date '+%F %T') queue finished" >> $LOG
