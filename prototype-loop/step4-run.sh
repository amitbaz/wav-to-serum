#!/bin/zsh
# PROTOTYPE, throw away. "Step 4: add a filter envelope"
#   [SET=step1] ./step4-run.sh SPLIT [BUDGET]   match every sound in SPLIT (adjust | held_out); SET=step1|step2b|step3b reruns those; rerun resumes, finished sounds are skipped
#   ./step4-run.sh pause | resume | status
cd ~/wav-to-serum-work/w
PY=$HOME/wav-to-serum-work/venv/bin/python
JOBS='step4\.py (match|truth|near)'
case $1 in
  pause|resume)
    p=($(pgrep -f $JOBS)); [[ -z $p ]] && { echo "not running"; exit; }
    kill -$([[ $1 = pause ]] && echo STOP || echo CONT) $p $(for i in $p; do pgrep -P $i; done); echo "${1}d" ;;
  status) ls ${OUT:-step4}/*_match.json 2>/dev/null | wc -l | xargs echo "matched:"; p=$(pgrep -f $JOBS | head -1)
    [[ -z $p ]] && echo "-- not running" || echo "-- $(ps -o stat= -p $p | grep -q T && echo paused || echo running)" ;;
  *) caffeinate -i -w $$ &
     names=($($PY -c "import json;print(' '.join(s['name'] for s in json.load(open('${SET:-step4}/sounds.json')) if s['split']=='$1'))"))
     $PY -W ignore step4.py match ${2:-2000} $names 2>&1 | grep --line-buffered '^{' >> ${OUT:-step4}/run.log ;;
esac
