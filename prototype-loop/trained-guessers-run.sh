#!/bin/zsh
# PROTOTYPE, throw away. "Can trained guessers pick a structure the tuner can finish from?"
#   ./guess-run.sh STAGE    start a stage, or resume it after a kill or reboot: finished work is skipped
#                           STAGE: bound | data (50,000 renders, then the ear and the learning curve) | choose [N]
#   ./guess-run.sh pause    freeze the run where it is (nothing lost while the Mac stays on)
#   ./guess-run.sh resume   unfreeze it
#   ./guess-run.sh status   what has finished, and whether it is running
cd ~/wav-to-serum-work/w
PY=$HOME/wav-to-serum-work/venv/bin/python
export OUT=guess
JOBS='(bank|guess|choose)\.py'
case $1 in
  pause|resume)
    p=($(pgrep -f $JOBS)); [[ -z $p ]] && { echo "not running"; exit; }
    kill -$([[ $1 = pause ]] && echo STOP || echo CONT) $p $(for i in $p; do pgrep -P $i; done); echo "${1}d" ;;
  status) [[ -f guess.log ]] && cut -c1-200 guess.log; p=$(pgrep -f $JOBS | head -1)
    [[ -z $p ]] && echo "-- not running" || echo "-- $(ps -o stat= -p $p | grep -q T && echo paused || echo running): $(ps -o command= -p $p | grep -oE '(bank|guess|choose)\.py.*' | cut -c1-80)" ;;
  bound) caffeinate -i -w $$ &
     $PY -W ignore bank.py bound 20000 "Bass 1" "Bass 2" "Lead 1" "Lead 4" "Synth 1" "Synth 4" 2>&1 | grep --line-buffered '^{' >> guess.log ;;
  data) caffeinate -i -w $$ &
     $PY -W ignore guess.py data 50000 2>&1 | grep --line-buffered "^{" >> guess.log
     $PY -W ignore guess.py ear 5000 10000 25000 50000 2>&1 | grep --line-buffered "^{" >> guess.log ;;
  choose) caffeinate -i -w $$ &
     N=${2:-50000}
     $PY -W ignore choose.py guesses $N 2>&1 | grep --line-buffered "^{" >> guess.log
     for way in build; do  # match is out: the bound failed (Bass 1 4.40, Bass 2 3.74) $PY -W ignore choose.py tune $way 20000 $N 2>&1 | grep --line-buffered "^{" >> guess.log; done ;;
  *) echo "unknown stage $1"; exit 1 ;;
esac
