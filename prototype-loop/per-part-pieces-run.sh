#!/bin/zsh
# PROTOTYPE, throw away. "Can per-part pieces pick a structure and a start the tuner can finish from?"
#   ./parts-run.sh          whole (6 sounds, 20,000 renders), then worth (6 pieces x 4 sounds, 10,000); rerun resumes, finished work is skipped
#   ./parts-run.sh pause    freeze the run where it is (nothing lost while the Mac stays on)
#   ./parts-run.sh resume   unfreeze it
#   ./parts-run.sh status   what has finished, and whether it is running
cd ~/wav-to-serum-work/w
PY=$HOME/wav-to-serum-work/venv/bin/python
JOBS='parts\.py (whole|worth)'
case $1 in
  pause|resume)
    p=($(pgrep -f $JOBS)); [[ -z $p ]] && { echo "not running"; exit; }
    kill -$([[ $1 = pause ]] && echo STOP || echo CONT) $p $(for i in $p; do pgrep -P $i; done); echo "${1}d" ;;
  status) [[ -f parts/tune.log ]] && cut -c1-200 parts/tune.log | grep -v screen; p=$(pgrep -f $JOBS | head -1)
    [[ -z $p ]] && echo "-- not running" || echo "-- $(ps -o stat= -p $p | grep -q T && echo paused || echo running): $(ps -o command= -p $p | grep -oE 'parts\.py.*' | cut -c1-80)" ;;
  *) caffeinate -i -w $$ &
     $PY -W ignore parts.py whole 20000 "Bass 1" "Bass 2" "Lead 4" "Synth 4" "Lead 1" "Synth 1" 2>&1 | grep --line-buffered '^{' >> parts/tune.log
     for pc in tables movement voices filter fx envelope; do
       $PY -W ignore parts.py worth $pc 10000 "Bass 1" "Bass 2" "Lead 4" "Synth 4" 2>&1 | grep --line-buffered '^{' >> parts/tune.log
     done ;;
esac
