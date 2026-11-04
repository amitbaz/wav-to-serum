#!/bin/zsh
# PROTOTYPE, throw away. "Can we pick a sound's structure from the audio?"
#   ./pick-run.sh          start, or resume after a kill or reboot: finished work is skipped
#   ./pick-run.sh pause    freeze the run where it is (nothing lost while the Mac stays on)
#   ./pick-run.sh resume   unfreeze it
#   ./pick-run.sh status   what has finished, and whether it is running
cd ~/wav-to-serum-work/w
PY=$HOME/wav-to-serum-work/venv/bin/python
JOBS='pick.py \.\./old'
case $1 in
  pause|resume)
    p=($(pgrep -f $JOBS)); [[ -z $p ]] && { echo "not running"; exit; }
    kill -$([[ $1 = pause ]] && echo STOP || echo CONT) $p $(for i in $p; do pgrep -P $i; done); echo "${1}d" ;;
  status) [[ -f pick.log ]] && cut -c1-180 pick.log; p=$(pgrep -f $JOBS | head -1)
    [[ -z $p ]] && echo "-- not running" || echo "-- $(ps -o stat= -p $p | grep -q T && echo paused || echo running): $(ps -o command= -p $p | grep -oE 'pick\.py.*' | cut -c1-80)" ;;
  *) caffeinate -i -w $$ &  # no idle sleep while this runs
     $PY -W ignore pick.py ../old factory 20000 3 "Bass 1" "Bass 2" "Lead 1" "Lead 4" "Synth 1" "Synth 4" 2>&1 | grep --line-buffered '^{' >> pick.log
     for part in none tables filter mods fx voices; do
       $PY -W ignore pick.py ../old swap:$part 10000 "Bass 1" "Bass 2" "Lead 4" "Synth 4" 2>&1 | grep --line-buffered '^{' >> pick.log
     done ;;
esac
