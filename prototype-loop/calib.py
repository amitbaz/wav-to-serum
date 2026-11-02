import json; from pathlib import Path; import numpy as np, soundfile as sf; from scipy.stats import spearmanr
import tune as t, compare as c
r=json.load(open('close-numbers-ratings.json'))['ratings'];k=json.load(open('close-numbers-key.json'))
old=Path.home()/'Desktop/w2s-listen'
POC={"Bass 1": "B_765", "Bass 2": "F_432", "Lead 1": "A_372", "Lead 4": "E_960", "Synth 1": "D_315", "Synth 4": "C_364"}
rows=[]
for x,v in k.items():
    tag=v['sound'].replace(' ','')
    src={'poc_best':old/f"{POC[v['sound']]}.wav",'true_random':Path(f'oracle/{tag}_s1.wav'),'true_near05':Path(f'oracle/{tag}_s1_near0.05.wav'),'library':Path(f'retrieved/{tag}_tuned.wav')}[v['arm']]
    T,_=sf.read(f'oracle/{tag}_target.wav',always_2d=True);G,_=sf.read(src,always_2d=True)
    rows.append((v['sound'],v['arm'],r[x]['rating'],t.score(t.features(G.T),t.features(T.T)),c.near(T.T,G.T)))
rows.sort(key=lambda w:w[3])
for w in rows: print(f"{w[0]:8} {w[1]:12} ear {w[2]}  score {w[3]:.2f}  near {w[4]:.2f}")
e=[w[2] for w in rows]
print('spearman score',round(spearmanr([w[3] for w in rows],e).statistic,2),'near',round(spearmanr([w[4] for w in rows],e).statistic,2))
for th in (2.0,2.5,3.0):
    lo=[w[2] for w in rows if w[3]<th]; hi=[w[2] for w in rows if w[3]>=th]
    print(f'score<{th}: {sum(v>=3 for v in lo)}/{len(lo)} rate 3+;  >= {th}: {sum(v>=3 for v in hi)}/{len(hi)}')
