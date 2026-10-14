import random
from fixtures import *
from sim import Session

SLOTS = [ref(DRINK,"status"), ref(AMOUNT,"amount"), ref(AMOUNT,"kind"), ref(SLEEP,"hours"), ref(VISIT,"times"), ref(PAIN,"level"), ref(NOTE,"text"), ref("q_none","x"), ref(SLEEP,"zzz")]
TEXTS = ["마시고요","안 마시고요","두 병","세 잔","소주","맥주","7시간","8시간","30시간","주에 두 번","두 번","두세 번","가끔","약함","심함","없음","음","7시간쯤"]
INTENTS = ["ANSWERED_INTENT"]*8+["CORRECTION_MARKED"]*2+["SAYS_UNKNOWN","SAYS_REFUSAL","CONFIRM_YES","CONFIRM_NO","PROGRESS_OP","GUIDE_REQUEST","USER_CALLED_STAFF","OUT_OF_SCOPE","UNRECOGNIZED","RISK_SIGNAL"]

def rand_items(rng, s):
    n = rng.choice([0,1,1,1,2,2,3])
    items=[]
    for i in range(n):
        intent = rng.choice(INTENTS)
        tq = rng.random()
        if tq < .6: t = rng.choice(SLOTS)
        elif tq < .8: t = whole(rng.choice([DRINK,AMOUNT,SLEEP,VISIT,PAIN,NOTE]))
        else: t = None
        if intent == "ANSWERED_INTENT" and t is None: t = rng.choice(SLOTS)
        val = rng.choice(TEXTS) if intent in ("ANSWERED_INTENT","CORRECTION_MARKED") and rng.random()<.85 else None
        if intent == "ANSWERED_INTENT" and val is None: val = rng.choice(TEXTS)
        if intent in ("CONFIRM_YES","CONFIRM_NO") and rng.random()<.7: t=None
        op = rng.choice(["REPEAT","WAIT","LATER","STOP"]) if intent=="PROGRESS_OP" else None
        guide = rng.choice(["g_why","g_left","g_none"]) if intent=="GUIDE_REQUEST" else None
        items.append(item(i, t, val, intent, op=op, guide=guide))
    return items

def run(seed, turns=40):
    rng = random.Random(seed)
    s = Session()
    s.nonutterance("SESSION_START")
    log=[]
    for k in range(turns):
        if s.flow == "END": break
        if s.status == "PAUSED_RISK" and rng.random()<.7:
            s.nonutterance("RESUME"); log.append("RESUME"); continue
        items = rand_items(rng, s)
        s.turn(items); log.append((items, s.last["action"]))
        skipped = {x["question_id"] for x in s.skipped}
        # 건너뛴 문항은 묻는 행동의 대상이 아니다(다시 묻지 않는다)
        if s.last["action"] in ("ASK_NEXT","ASK_MISSING","ASK_AFTER_UNKNOWN","ASK_AFTER_REFUSAL"):
            for t in s.last["targets"]:
                assert t["question_id"] not in skipped, (seed, k, s.last["action"], t)
    return s

if __name__ == "__main__":
    import sys, traceback
    bad=0
    for seed in range(int(sys.argv[1]) if len(sys.argv)>1 else 300):
        try: run(seed)
        except Exception as e:
            bad+=1
            if bad<=5:
                print("SEED",seed); traceback.print_exc()
    print("bad",bad)
