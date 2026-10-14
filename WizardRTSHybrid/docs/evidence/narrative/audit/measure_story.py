"""Measure: does story_quantum fire in an ordinary AI campaign world, and what does it cost? (evidence for the narrative audit)"""
import os, sys, time, cProfile, pstats, io
sys.path[:0] = [os.path.abspath('.'), os.path.abspath('..')]
os.environ['HYBRID_AI'] = '1'
from wizard_rts.world import HybridWorld
from wizard_rts import story
seed = int(sys.argv[1]); minutes = int(sys.argv[2]); profile = sys.argv[3] if len(sys.argv) > 3 else 'campaign'
w = HybridWorld(seed, terrain=True, map_size='standard', profile=profile)
t0 = time.time()
pr = cProfile.Profile()
pr.enable()
for i in range(minutes * 60):
    w.advance(1000, i + 1, snapshot=False)
pr.disable()
wall = time.time() - t0
s = story.state(w)
quests = {qid: (w.dmb.quests[qid]['status'], q.get('family', 'shortage')) for qid, q in s['quests'].items()}
st = pstats.Stats(pr)
story_t = sum(v[3] for k, v in st.stats.items() if k[0].endswith('story.py') and k[2] == 'story_quantum')
print({'seed': seed, 'minutes': minutes, 'profile': profile, 'wall_s': round(wall, 1), 'x_realtime': round(minutes*60/wall, 1),
       'story_quantum_cum_s': round(story_t, 3), 'story_share_pct': round(100*story_t/wall, 2),
       'quests': quests, 'npcs': len(s['npcs']), 'people': len(w.dmb.people), 'dungeons': len(s['dungeons']),
       'buildings': len(w.buildings), 'settlements': len(w.dmb.settlements), 'workers': len(w.workers)})
