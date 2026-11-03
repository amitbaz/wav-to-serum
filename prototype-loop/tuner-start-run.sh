#!/bin/zsh
# PROTOTYPE, throw away. "Find a start the tuner can finish from".
#   ./run.sh           start, or resume after a kill or reboot: finished work is skipped
#   ./run.sh pause     freeze the run where it is (nothing lost while the Mac stays on)
#   ./run.sh resume    unfreeze it
#   ./run.sh status    what has finished, and whether it is running
#   ./run.sh tmpl      restarts on the POC template's own designs (4 workers); rerun to resume
cd ~/wav-to-serum-work/w
PY=$HOME/wav-to-serum-work/venv/bin/python
SOUNDS=("Bass 1" "Bass 2" "Lead 1" "Lead 4" "Synth 1" "Synth 4")
ARMS=(blocks restarts screen model)
JOBS='routes.py \.|tmpl.py|train.py \.'
case $1 in
  pause|resume)  # the runner and its 8 workers; the shell loop just waits on them
    p=($(pgrep -f $JOBS)); [[ -z $p ]] && { echo "not running"; exit; }
    kill -$([[ $1 = pause ]] && echo STOP || echo CONT) $p $(for i in $p; do pgrep -P $i; done); echo "${1}d" ;;
  tmpl) caffeinate -i -w $$ &
    $PY -W ignore tmpl.py ../old restarts 20000 1 B F E A D C 2>&1 | grep --line-buffered '^{' >> tmpl.log ;;
  status) cut -c1-160 routes.log; [[ -f tmpl.log ]] && cut -c1-160 tmpl.log; [[ -f train.log ]] && tail -3 train.log | cut -c1-200; p=$(pgrep -f $JOBS | head -1)
    [[ -z $p ]] && echo "-- not running" || echo "-- $(ps -o stat= -p $p | grep -q T && echo paused || echo running): $(ps -o command= -p $p | grep -oE '(routes|train)\.py.*' | cut -c1-80)" ;;
  *) caffeinate -i -w $$ &  # no idle sleep while this runs
     for a in $ARMS; do $PY -W ignore routes.py . $a 20000 1 $SOUNDS 2>&1 | grep --line-buffered '^{' >> routes.log; done ;;  # model training dropped: 3x data barely helped
esac
