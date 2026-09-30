"""Build a bounded, data-backed dashboard view; no invented anatomy or wiring."""
from pathlib import Path
import json, hashlib
import numpy as np
import pyarrow.feather as feather
import pyarrow.parquet as parquet

root=Path(__file__).resolve().parents[1]
pack=root/'vendor/drosophila-brain-mlx/data/pack/male_cns_v1'
raw=root/'vendor/drosophila-brain-mlx/data/raw/male_cns/body-annotations-male-cns-v1.0-minconf-0.5.feather'
names=parquet.read_table(pack/'names.parquet').to_pylist()
annotations=feather.read_table(raw,columns=['bodyId','somaLocation','somaNeuromere']).to_pylist()
locations={str(r['bodyId']):r['somaLocation'] for r in annotations if r['somaLocation'] is not None and len(r['somaLocation'])==3}
points=np.array(list(locations.values()),dtype=float)
center=(points.min(axis=0)+points.max(axis=0))/2
scale=float(np.ptp(points,axis=0).max()/2)
def position(body):
 p=locations.get(str(body))
 return None if p is None else [round(float(x),5) for x in (np.array(p)-center)/scale]
ptr=np.load(pack/'row_ptr.npy',mmap_mode='r');dst=np.load(pack/'destinations.npy',mmap_mode='r');w=np.load(pack/'signed_counts.npy',mmap_mode='r')
inputs=[i for i,r in enumerate(names) if r['instance'] in ('LB3b_R','LB3c_R')]
outputs=[i for i,r in enumerate(names) if r['instance'] in ('MN9_L','MN9_R')]
steer=[i for i,r in enumerate(names) if r['type'] in ('PFL3','DNa02','DNa03')]
# Display intermediates on strong two-edge sensory->MN9 paths, when present.
strength={}
for i in inputs:
 for j,weight in zip(dst[ptr[i]:ptr[i+1]],w[ptr[i]:ptr[i+1]]):
  strength[int(j)]=strength.get(int(j),0)+abs(int(weight))
paths=[]
for i,value in strength.items():
 d=dst[ptr[i]:ptr[i+1]];weights=w[ptr[i]:ptr[i+1]]
 onward=int(np.abs(weights[np.isin(d,outputs)]).sum())
 if onward:paths.append((value*onward,i))
intermediates=[i for _,i in sorted(paths,reverse=True) if i not in inputs+outputs+steer][:16]
selected=inputs+intermediates+outputs+steer
nodes=[]
for i in selected:
 r=names[i]
 group='taste' if i in inputs else 'feeding' if i in outputs else 'relay' if i in intermediates else 'steering'
 nodes.append({'id':str(r['bodyId']),'label':r['instance'] or r['type'] or str(r['bodyId']),
               'type':r['type'],'group':group,'position':position(r['bodyId'])})
edges=[]
chosen=set(selected)
for i in selected:
 for j,weight in zip(dst[ptr[i]:ptr[i+1]],w[ptr[i]:ptr[i+1]]):
  if int(j) in chosen:
   edges.append({'source':str(names[i]['bodyId']),'target':str(names[int(j)]['bodyId']), 'weight':int(weight)})
available=[r for r in names if str(r['bodyId']) in locations]
rng=np.random.default_rng(7331)
idx=sorted(rng.choice(len(available),size=min(6000,len(available)),replace=False))
cloud=[position(available[i]['bodyId']) for i in idx]
# Spatial bins summarize every model cell with an annotated soma, not only circuit cells.
model_positions=np.array([position(r['bodyId']) for r in available])
keys=np.floor((model_positions+1)*3).astype(int).clip(0,5)
unique,region_index=np.unique(keys,axis=0,return_inverse=True)
regions=[]
for i,key in enumerate(unique):
 members=model_positions[region_index==i]
 regions.append({'position':members.mean(axis=0).round(5).tolist(),'neurons':len(members)})
index_by_id={str(r['bodyId']):i for i,r in enumerate(names)}
layout_path=root/'src/lauff/web/brain-layout.npz'
np.savez_compressed(layout_path,
 neuron_ids=np.array([str(r['bodyId']) for r in names]),
 mapped_indices=np.array([index_by_id[str(r['bodyId'])] for r in available]),
 region_index=region_index, cloud_indices=np.array([index_by_id[str(available[i]['bodyId'])] for i in idx]),
 node_indices=np.array(selected),node_ids=np.array([str(names[i]['bodyId']) for i in selected]))
manifest=json.loads((pack/'manifest.json').read_text())
data={'dataset':manifest['dataset'],'neurons':manifest['neurons'],'edges_total':manifest['edges'],
      'somas_available':len(available),'cloud':cloud,'regions':regions,'cloud_ids':[str(available[i]['bodyId']) for i in idx],'nodes':nodes,'edges':edges,
      'sample_seed':7331,'coordinate_source':'MaleCNS somaLocation; uniformly normalized annotation coordinates',
      'annotation_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
      'layout_note':'Anatomy: sampled annotated soma locations, not neurites. Circuit: diagram layout, real selected edges. Activity is measured per neuron and spatial bin over each one-second trial, not spike timing.'}
# Embed JSON in HTML so the already-running viewer can serve it without restarting the worker.
p=root/'src/lauff/web/index.html';s=p.read_text()
start='<script id="brain-data" type="application/json">';end='</script><!-- brain-data -->'
blob=start+json.dumps(data,separators=(',',':')).replace('<','\\u003c')+end
if start in s:
 a=s.index(start);b=s.index(end,a)+len(end);s=s[:a]+blob+s[b:]
else:s=s.replace('</body>',blob+'\n</body>')
p.write_text(s)
print(json.dumps({k:data[k] for k in ['neurons','edges_total','somas_available']}))
print(f'{len(cloud)} sampled somas; {len(nodes)} circuit neurons; {len(edges)} real selected edges')
