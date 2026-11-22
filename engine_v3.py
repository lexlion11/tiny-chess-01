import json, os, sys, urllib.error, urllib.request

MATE = 100000
INF = 999999
BUDGET = 75000

MV = (0, 100, 320, 330, 500, 900, 0)

PMG = (0,0,0,0,5,10,10,-20,5,-5,-10,0,0,0,20,20,5,5,10,25,10,10,20,30,50,50,50,50,0,0,0,0)
PEG = (0,0,0,0,0,0,0,0,5,5,5,10,10,10,15,20,20,20,25,30,35,35,40,45,60,60,65,70,0,0,0,0)
NMG = (-50,-40,-30,-30,-40,-20,0,5,-30,5,10,15,-30,0,15,20,-30,5,15,20,-30,0,10,15,-40,-20,0,0,-50,-40,-30,-30)
BMG = (-20,-10,-10,-10,-10,5,0,0,-10,10,10,10,-10,0,10,10,-10,5,5,10,-10,0,5,10,-10,0,0,0,-20,-10,-10,-10)
RMG = (0,0,0,5,-5,0,0,0,-5,0,0,0,-5,0,0,0,-5,0,0,0,-5,0,0,0,5,10,10,10,0,0,0,0)
QMG = (-20,-10,-10,-5,-10,0,5,0,-10,5,5,5,0,0,5,5,-5,0,5,5,-10,0,5,0,-10,0,0,0,-20,-10,-10,-5)
KMG = (20,30,10,0,20,20,0,0,-10,-20,-10,-10,-20,-30,-10,-15,-30,-40,-20,-20,-30,-40,-20,-25,-30,-40,-20,-25,-30,-40,-20,-25)
KEG = (-50,-30,-30,-30,-30,-30,0,0,-30,-10,20,30,-30,-10,30,40,-30,-10,30,40,-30,-10,20,30,-30,-20,-10,0,-50,-30,-30,-30)

TAB = ((), PMG, NMG, BMG, RMG, QMG, KMG)
TEG = ((), PEG, NMG, BMG, RMG, QMG, KEG)

KN = (33, 31, 18, 14, -33, -31, -18, -14)
KG = (16, -16, 1, -1, 15, -15, 17, -17)
DG = (15, 17, -15, -17)
RT = (16, -16, 1, -1)
SQ = tuple(s for s in range(128) if not s & 0x88)

bd = [0] * 128
sd = 1
cr = 0
ep = -1
kw = kb = 4
hist = []
tt = {}
kl = {}
ht = {}
nodes = 0


class _Stop(Exception):
    pass


def setpos(fen):
    global bd, sd, cr, ep, kw, kb, hist
    bd = [0] * 128
    parts = fen.split()
    for i, row in enumerate(parts[0].split("/")):
        f = 0
        for c in row:
            if c.isdigit():
                f += int(c)
            else:
                v = "PNBRQK".index(c.upper()) + 1
                s = (7 - i) * 16 + f
                bd[s] = v if c.isupper() else -v
                if v == 6:
                    if c.isupper():
                        kw = s
                    else:
                        kb = s
                f += 1
    sd = 1 if parts[1] == "w" else -1
    cr = 0
    for c in parts[2] if len(parts) > 2 else "":
        cr |= {"K": 1, "Q": 2, "k": 4, "q": 8}.get(c, 0)
    ep = -1
    if len(parts) > 3 and parts[3] != "-":
        ep = (ord(parts[3][0]) - 97) + (int(parts[3][1]) - 1) * 16
    hist = []


def atk(sq, by):
    """Is square sq attacked by side `by` (by=+1 white, -1 black)?"""
    if by > 0:
        for o in (-15, -17):
            s = sq + o
            if not s & 0x88 and bd[s] == 1:
                return True
    else:
        for o in (15, 17):
            s = sq + o
            if not s & 0x88 and bd[s] == -1:
                return True
    for o in KN:
        s = sq + o
        if not s & 0x88 and bd[s] == by * 2:
            return True
    for o in KG:
        s = sq + o
        if not s & 0x88 and bd[s] == by * 6:
            return True
    for o in DG:
        s = sq + o
        while not s & 0x88:
            p = bd[s]
            if p:
                if p == by * 3 or p == by * 5:
                    return True
                break
            s += o
    for o in RT:
        s = sq + o
        while not s & 0x88:
            p = bd[s]
            if p:
                if p == by * 4 or p == by * 5:
                    return True
                break
            s += o
    return False


def gen():
    """Generate pseudo-legal moves as (from, to, promo, flag).
    flag: 0 normal, 1 ep-capture, 2 castle, 3 double-push."""
    mv = []
    for sq in SQ:
        p = bd[sq]
        if not p or p * sd < 0:
            continue
        t = p if p > 0 else -p
        if t == 1:
            d = sd * 16
            f1 = sq + d
            if not bd[f1]:
                if (sd > 0 and f1 > 111) or (sd < 0 and f1 < 8):
                    for q in (2, 3, 4, 5):
                        mv.append((sq, f1, q, 0))
                else:
                    mv.append((sq, f1, 0, 0))
                    if (sd > 0 and 15 < sq < 24) or (sd < 0 and 95 < sq < 104):
                        f2 = f1 + d
                        if not bd[f2]:
                            mv.append((sq, f2, 0, 3))
            for o in (15, 17):
                to = sq + o * sd
                if to & 0x88:
                    continue
                q = bd[to]
                if q and q * sd < 0:
                    if (sd > 0 and to > 111) or (sd < 0 and to < 8):
                        for r in (2, 3, 4, 5):
                            mv.append((sq, to, r, 0))
                    else:
                        mv.append((sq, to, 0, 0))
                elif to == ep and ep >= 0:
                    mv.append((sq, to, 0, 1))
        elif t == 2 or t == 6:
            for o in KN if t == 2 else KG:
                to = sq + o
                if to & 0x88:
                    continue
                q = bd[to]
                if not q or q * sd < 0:
                    mv.append((sq, to, 0, 0))
        else:
            for o in DG if t == 3 else RT if t == 4 else KG:
                to = sq + o
                while not to & 0x88:
                    q = bd[to]
                    if not q:
                        mv.append((sq, to, 0, 0))
                        to += o
                        continue
                    if q * sd < 0:
                        mv.append((sq, to, 0, 0))
                    break
    if sd > 0:
        if (cr & 1 and not bd[5] and not bd[6]
                and not atk(4, -1) and not atk(5, -1) and not atk(6, -1)):
            mv.append((4, 6, 0, 2))
        if (cr & 2 and not bd[3] and not bd[2] and not bd[1]
                and not atk(4, -1) and not atk(3, -1) and not atk(2, -1)):
            mv.append((4, 2, 0, 2))
    else:
        if (cr & 4 and not bd[117] and not bd[118]
                and not atk(116, 1) and not atk(117, 1) and not atk(118, 1)):
            mv.append((116, 118, 0, 2))
        if (cr & 8 and not bd[115] and not bd[114] and not bd[113]
                and not atk(116, 1) and not atk(115, 1) and not atk(114, 1)):
            mv.append((116, 114, 0, 2))
    return mv


def make(m):
    global sd, cr, ep, kw, kb
    f, t, pr, fl = m
    p = bd[f]
    c = bd[t]
    hist.append((c, ep, cr))
    bd[f] = 0
    bd[t] = sd * pr if pr else p
    ep = -1
    if fl == 1:
        bd[t - sd * 16] = 0
    elif fl == 2:
        if t == 6:
            bd[5] = bd[7]; bd[7] = 0
        elif t == 2:
            bd[3] = bd[0]; bd[0] = 0
        elif t == 118:
            bd[117] = bd[119]; bd[119] = 0
        else:
            bd[115] = bd[112]; bd[112] = 0
    elif fl == 3:
        ep = (f + t) >> 1
    if abs(p) == 6:
        if p > 0:
            kw = t
        else:
            kb = t
        cr &= 12 if p > 0 else 3
    if f == 0 or t == 0:
        cr &= ~2
    if f == 7 or t == 7:
        cr &= ~1
    if f == 112 or t == 112:
        cr &= ~8
    if f == 119 or t == 119:
        cr &= ~4
    sd = -sd


def unmake(m):
    global sd, cr, ep, kw, kb
    sd = -sd
    f, t, pr, fl = m
    c, ep, cr = hist.pop()
    p = bd[t]
    if pr:
        bd[f] = sd
    else:
        bd[f] = p
        if abs(p) == 6:
            if p > 0:
                kw = f
            else:
                kb = f
    bd[t] = c
    if fl == 1:
        bd[t - sd * 16] = -sd
    elif fl == 2:
        if t == 6:
            bd[7] = bd[5]; bd[5] = 0
        elif t == 2:
            bd[0] = bd[3]; bd[3] = 0
        elif t == 118:
            bd[119] = bd[117]; bd[117] = 0
        else:
            bd[112] = bd[115]; bd[115] = 0


def chk():
    """Side to move is in check?"""
    return atk(kw if sd > 0 else kb, -sd)


def illegal():
    """The move just made leaves own king attacked."""
    return atk(kw if sd < 0 else kb, sd)


def cap(m):
    return bd[m[1]] or m[2] or m[3] == 1


def evaluate():
    mg = eg = ph = bc = 0
    for sq in SQ:
        p = bd[sq]
        if not p:
            continue
        t = p if p > 0 else -p
        r = sq >> 4
        f = sq & 7
        if f > 3:
            f = 7 - f
        i = r * 4 + f
        if p > 0:
            mg += MV[t] + TAB[t][i]
            eg += MV[t] + TEG[t][i]
        else:
            j = (7 - r) * 4 + f
            mg -= MV[t] + TAB[t][j]
            eg -= MV[t] + TEG[t][j]
        ph += (0, 0, 1, 1, 2, 4, 0)[t]
        if t == 3:
            bc += p // 3
    if ph > 24:
        ph = 24
    if bc > 1:
        mg += 30
        eg += 10
    elif bc < -1:
        mg -= 30
        eg -= 10
    # king safety: own pawn shield in front of king
    for o in (15, 16, 17):
        s = kw + o
        if not s & 0x88 and bd[s] == 1:
            mg += 10
        s = kb - o
        if not s & 0x88 and bd[s] == -1:
            mg -= 10
    return (mg * ph + eg * (24 - ph)) // 24 * sd


def big():
    for sq in SQ:
        p = bd[sq]
        if p * sd > 0 and 1 < abs(p) < 6:
            return True
    return False


def qsearch(a, b, ply):
    global nodes
    nodes += 1
    if nodes > BUDGET:
        raise _Stop
    in_chk = chk()
    if not in_chk:
        s = evaluate()
        if s >= b:
            return s
        best = s
        if s > a:
            a = s
    else:
        best = -MATE + ply
    # order captures MVV-LVA so stand-pat cuts happen sooner
    cs = []
    for m in gen():
        if not in_chk and not cap(m):
            continue
        if in_chk or bd[m[1]] or m[2]:
            v = MV[abs(bd[m[1]])] * 16 - MV[abs(bd[m[0]])] + (MV[m[2]] if m[2] else 0)
        else:
            v = 0
        cs.append((v, m))
    cs.sort(reverse=True)
    for v, m in cs:
        make(m)
        if illegal():
            unmake(m)
            continue
        s = -qsearch(-b, -a, ply + 1)
        unmake(m)
        if s > best:
            best = s
            if s > a:
                a = s
                if s >= b:
                    return s
    return best


def search(depth, a, b, ply):
    global nodes, sd, ep
    nodes += 1
    if nodes > BUDGET:
        raise _Stop
    in_chk = chk()
    if in_chk:
        depth += 1
    if depth <= 0:
        return qsearch(a, b, ply)
    key = (tuple(bd), sd, cr, ep)
    e = tt.get(key)
    ttm = e[3] if e else None
    if e and e[0] >= depth:
        s = e[1]
        if s > MATE - 1000:
            s -= ply
        elif s < -MATE + 1000:
            s += ply
        if e[2] == 0 or (e[2] == 1 and s >= b) or (e[2] == 2 and s <= a):
            return s
    if depth >= 4 and not in_chk and big():
        oep = ep
        ep = -1
        sd = -sd
        s = -search(depth - 3, -b, -b + 1, ply + 1)
        sd = -sd
        ep = oep
        if s >= b:
            return b
    ms = []
    for m in gen():
        if m == ttm:
            v = 2000000
        elif bd[m[1]]:
            v = 1000000 + MV[abs(bd[m[1]])] * 16 - MV[abs(bd[m[0]])] + (MV[m[2]] if m[2] else 0)
        else:
            kk = kl.get(ply)
            v = 900000 - kk.index(m) * 1000 if kk and m in kk else min(ht.get((m[0], m[1]), 0), 899997)
        ms.append((v, m))
    ms.sort(reverse=True)
    best = -INF
    bm = None
    flag = 2
    for i, (v, m) in enumerate(ms):
        make(m)
        if illegal():
            unmake(m)
            continue
        q = not cap(m)
        if i:
            r = depth - 2 if (depth >= 3 and i > 2 and q and m != ttm and not in_chk) else depth - 1
            s = -search(r, -a - 1, -a, ply + 1)
            if a < s < b:
                s = -search(depth - 1, -b, -a, ply + 1)
        else:
            s = -search(depth - 1, -b, -a, ply + 1)
        unmake(m)
        if s > best:
            best = s
            bm = m
            if s > a:
                a = s
                flag = 0
                if s >= b:
                    flag = 1
                    if q:
                        kk = kl.get(ply)
                        if not kk or m != kk[0]:
                            kl[ply] = (m, kk[0] if kk else None)
                        k = (m[0], m[1])
                        ht[k] = ht.get(k, 0) + depth * depth
                    break
    if best == -INF:
        return -MATE + ply if in_chk else 0
    if best > MATE - 1000:
        best += ply
    elif best < -MATE + 1000:
        best -= ply
    if len(tt) > 100000:
        tt.clear()
    tt[key] = (depth, best, flag, bm)
    return best


def go():
    global nodes
    nodes = 0
    kl.clear()
    ht.clear()
    ms = []
    for m in gen():
        make(m)
        ok = not illegal()
        unmake(m)
        if ok:
            ms.append(m)
    if not ms:
        return None
    ms.sort(key=lambda m: MV[abs(bd[m[1]])] if bd[m[1]] else 0, reverse=True)
    best = ms[0]
    for d in range(1, 64):
        if d > 1:
            ms.remove(best)
            ms.insert(0, best)
        try:
            a = -INF
            cur = None
            for i, m in enumerate(ms):
                make(m)
                if i:
                    s = -search(d - 1, -a - 1, -a, 1)
                    if s > a:
                        s = -search(d - 1, -INF, -a, 1)
                else:
                    s = -search(d - 1, -INF, -a, 1)
                unmake(m)
                if s > a:
                    a = s
                    cur = m
            if cur:
                best = cur
                if abs(a) > MATE - 1000:
                    break
        except _Stop:
            break
    return best


def sqn(s):
    return chr(97 + (s & 7)) + chr(49 + (s >> 4))


def uci(m):
    return sqn(m[0]) + sqn(m[1]) + ("nbrq"[m[2] - 2] if m[2] else "")


def post(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    env = os.environ.get("MAKEFUN_ENV_URL") or sys.exit("MAKEFUN_ENV_URL is not set")
    while True:
        g = post(env + "/game", {})
        if g.get("status") == "done":
            break
        while g.get("status") == "your_move":
            setpos(g["fen"])
            m = go()
            lm = g.get("legal_moves") or []
            u = uci(m) if m else ""
            if not u or (lm and u not in lm):
                u = lm[0] if lm else "0000"
            try:
                g = post(env + "/move", {"game": g["game"], "move": u})
            except urllib.error.HTTPError:
                g = post(env + "/game", {})
    print("trial: %sW %sD %sL" % (g.get("wins"), g.get("draws"), g.get("losses")), file=sys.stderr)


if __name__ == "__main__":
    main()
