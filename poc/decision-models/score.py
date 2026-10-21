import csv,sys,statistics as st,os
GT={r['event_id'][:8]:r for r in csv.DictReader(open(os.path.join(os.path.dirname(__file__),'..','..','ground_truth_v5.csv'),encoding='utf-8'))}
M={'TP':'T','FP':'F','Benign':'B','判別不可':'U','Undetermined':'U'}
L='lmhc'
for line in open(sys.argv[1]):
    name,rest=line.strip().split(':',1)
    rows=[x.split(',') for x in rest.split(';')]
    d=raw=u=u1=tpmiss=0;lat=[];confs=[]
    for r in rows:
        g=GT[r[0]];gd=M[g['disposition']];gu=g['urgency'][0].lower()
        if r[1]: continue
        d+=r[2]==gd; raw+=r[3]==gd; u+=r[5]==gu; u1+=abs(L.index(r[5])-L.index(gu))<=1
        tpmiss+= gd=='T' and r[2] in 'FB'
        lat.append(int(r[7])); confs.append(float(r[4]))
    n=len(rows)
    print(f"{name}: n={n} disp={d} raw_choice={raw} urg={u} urg±1={u1} TPmissed={tpmiss} conf_median={st.median(confs):.2f} latency_ms median={st.median(lat)} max={max(lat)}")
