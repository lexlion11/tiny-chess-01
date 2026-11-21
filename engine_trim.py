"""tiny-chess-01: 0x88 board, alpha-beta + quiescence, PST eval, node budget."""
import json, os, sys, urllib.request

ENV = os.environ.get("MAKEFUN_ENV_URL")

VAL = {'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 0}

KN = (33, 31, 18, 14, -33, -31, -18, -14)
BD = (17, 15, -17, -15)
RD = (16, -16, 1, -1)
KD = (16, -16, 1, -1, 17, 15, -17, -15)

# Piece-square tables (white perspective, a1..h8 as 64-index rows)
PST = {
 'p': (0,0,0,0,0,0,0,0, 5,10,10,-20,-20,10,10,5, 5,-5,-10,0,0,-10,-5,5,
       0,0,0,20,20,0,0,0, 5,5,10,25,25,10,5,5, 10,10,20,30,30,20,10,10,
       50,50,50,50,50,50,50,50, 0,0,0,0,0,0,0,0),
 'n': (-50,-40,-30,-30,-30,-30,-40,-50, -40,-20,0,5,5,0,-20,-40,
       -30,5,10,15,15,10,5,-30, -30,0,15,20,20,15,0,-30,
       -30,5,15,20,20,15,5,-30, -30,0,10,15,15,10,0,-30,
       -40,-20,0,0,0,0,-20,-40, -50,-40,-30,-30,-30,-30,-40,-50),
 'b': (-20,-10,-10,-10,-10,-10,-10,-20, -10,5,0,0,0,0,5,-10,
       -10,10,10,10,10,10,10,-10, -10,0,10,10,10,10,0,-10,
       -10,5,5,10,10,5,5,-10, -10,0,5,10,10,5,0,-10,
       -10,0,0,0,0,0,0,-10, -20,-10,-10,-10,-10,-10,-10,-20),
 'r': (0,0,0,5,5,0,0,0, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
       -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
       5,10,10,10,10,10,10,5, 0,0,0,0,0,0,0,0),
 'q': (-20,-10,-10,-5,-5,-10,-10,-20, -10,0,5,0,0,0,0,-10,
       -10,5,5,5,5,5,0,-10, 0,0,5,5,5,5,0,-5,
       -5,0,5,5,5,5,0,-5, -10,0,5,5,5,5,0,-10,
       -10,0,0,0,0,0,0,-10, -20,-10,-10,-5,-5,-10,-10,-20),
 'k': (20,30,10,0,0,10,30,20, 20,20,0,0,0,0,20,20,
       -10,-20,-20,-20,-20,-20,-20,-10, -20,-30,-30,-40,-40,-30,-30,-20,
       -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
       -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30),
}


class Board:
    def __init__(self, fen):
        self.sq = ['.'] * 128
        self.side = 0
        self.ep = -1
        self.castle = 0
        self.king = [0, 0]
        parts = fen.split()
        for r, row in enumerate(parts[0].split('/')):
            f = 0
            for c in row:
                if c.isdigit():
                    f += int(c)
                else:
                    s = (7 - r) * 16 + f
                    self.sq[s] = c
                    if c == 'K':
                        self.king[0] = s
                    elif c == 'k':
                        self.king[1] = s
                    f += 1
        self.side = 0 if parts[1] == 'w' else 1
        if len(parts) > 2 and parts[2] != '-':
            for i, ch in enumerate('KQkq'):
                if ch in parts[2]:
                    self.castle |= 1 << i
        if len(parts) > 3 and parts[3] != '-':
            self.ep = (int(parts[3][1]) - 1) * 16 + ord(parts[3][0]) - 97

    def attacked(self, s, by_w):
        q = self.sq
        if by_w:
            for d in (-15, -17):
                t = s + d
                if not (t & 0x88) and q[t] == 'P':
                    return True
        else:
            for d in (15, 17):
                t = s + d
                if not (t & 0x88) and q[t] == 'p':
                    return True
        for d in KN:
            t = s + d
            if not (t & 0x88) and q[t] == ('N' if by_w else 'n'):
                return True
        for d in KD:
            t = s + d
            if not (t & 0x88) and q[t] == ('K' if by_w else 'k'):
                return True
        # sliding bishop/queen
        for d in BD:
            t = s + d
            while not (t & 0x88):
                p = q[t]
                if p != '.':
                    if p in ('B' if by_w else 'b', 'Q' if by_w else 'q'):
                        return True
                    break
                t += d
        for d in RD:
            t = s + d
            while not (t & 0x88):
                p = q[t]
                if p != '.':
                    if p in ('R' if by_w else 'r', 'Q' if by_w else 'q'):
                        return True
                    break
                t += d
        return False

    def in_check(self):
        return self.attacked(self.king[self.side], self.side != 0)

    def gen_pseudo(self):
        moves = []
        q = self.sq
        white = self.side == 0
        for s in range(128):
            if s & 0x88:
                continue
            p = q[s]
            if p == '.' or (p.isupper() != white):
                continue
            pl = p.lower()
            if pl == 'p':
                d = 16 if white else -16
                t = s + d
                if not (t & 0x88) and q[t] == '.':
                    self._pawn(moves, s, t, white)
                    t2 = t + d
                    if (s >> 4) == (1 if white else 6) and not (t2 & 0x88) and q[t2] == '.':
                        moves.append((s, t2, None))
                for dd in (d + 1, d - 1):
                    t = s + dd
                    if not (t & 0x88):
                        c = q[t]
                        if c != '.' and (c.isupper() != white):
                            self._pawn(moves, s, t, white)
                        elif t == self.ep and c == '.':
                            moves.append((s, t, None))
            elif pl in ('n', 'k'):
                for d in (KN if pl == 'n' else KD):
                    t = s + d
                    if not (t & 0x88):
                        c = q[t]
                        if c == '.' or c.isupper() != white:
                            moves.append((s, t, None))
                if pl == 'k':
                    if white and s == 0x04:
                        if (self.castle & 1 and q[0x05] == '.' and q[0x06] == '.'
                                and q[0x07] == 'R' and not self.attacked(0x04, False)
                                and not self.attacked(0x05, False)
                                and not self.attacked(0x06, False)):
                            moves.append((s, 0x06, None))
                        if (self.castle & 2 and q[0x03] == '.' and q[0x02] == '.'
                                and q[0x01] == '.' and q[0x00] == 'R'
                                and not self.attacked(0x04, False)
                                and not self.attacked(0x03, False)
                                and not self.attacked(0x02, False)):
                            moves.append((s, 0x02, None))
                    elif not white and s == 0x74:
                        if (self.castle & 4 and q[0x75] == '.' and q[0x76] == '.'
                                and q[0x77] == 'r' and not self.attacked(0x74, True)
                                and not self.attacked(0x75, True)
                                and not self.attacked(0x76, True)):
                            moves.append((s, 0x76, None))
                        if (self.castle & 8 and q[0x73] == '.' and q[0x72] == '.'
                                and q[0x71] == '.' and q[0x70] == 'r'
                                and not self.attacked(0x74, True)
                                and not self.attacked(0x73, True)
                                and not self.attacked(0x72, True)):
                            moves.append((s, 0x72, None))
            else:
                dirs = BD if pl == 'b' else RD if pl == 'r' else BD + RD
                for d in dirs:
                    t = s + d
                    while not (t & 0x88):
                        c = q[t]
                        if c == '.':
                            moves.append((s, t, None))
                        else:
                            if c.isupper() != white:
                                moves.append((s, t, None))
                            break
                        t += d
        return moves

    def _pawn(self, moves, frm, to, white):
        if (to >> 4) == (7 if white else 0):
            for promo in ('q', 'r', 'b', 'n'):
                moves.append((frm, to, promo))
        else:
            moves.append((frm, to, None))

    def make(self, move):
        frm, to, promo = move
        q = self.sq
        piece = q[frm]
        captured = q[to]
        white = self.side == 0
        ep_cap = -1
        old_ep, old_castle = self.ep, self.castle
        wk, bk = self.king
        q[to] = piece
        q[frm] = '.'
        if piece in ('P', 'p') and to == self.ep and captured == '.':
            ep_cap = to - 16 if white else to + 16
            captured = q[ep_cap]
            q[ep_cap] = '.'
        if promo:
            q[to] = promo.upper() if white else promo
        if piece in ('K', 'k'):
            self.king[self.side] = to
            if to - frm == 2:
                q[to - 1], q[to + 1] = q[to + 1], '.'
            elif to - frm == -2:
                q[to + 1], q[to - 2] = q[to - 2], '.'
        if piece == 'K':
            self.castle &= ~3
        elif piece == 'k':
            self.castle &= ~12
        for s, b in ((0x00, 2), (0x07, 1), (0x70, 8), (0x77, 4)):
            if frm == s or to == s:
                self.castle &= ~b
        self.ep = -1
        if piece in ('P', 'p') and abs(to - frm) == 32:
            self.ep = (frm + to) // 2
        self.side ^= 1
        return (frm, to, promo, piece, captured, ep_cap, old_ep, old_castle, wk, bk)

    def unmake(self, u):
        frm, to, promo, piece, captured, ep_cap, ep, castle, wk, bk = u
        q = self.sq
        self.side ^= 1
        q[frm] = piece
        q[to] = '.'
        if ep_cap >= 0:
            q[ep_cap] = captured
        elif captured != '.':
            q[to] = captured
        if piece in ('K', 'k'):
            if to - frm == 2:
                q[to + 1], q[to - 1] = q[to - 1], '.'
            elif to - frm == -2:
                q[to - 2], q[to + 1] = q[to + 1], '.'
        self.ep = ep
        self.castle = castle
        self.king[0], self.king[1] = wk, bk

    def legal_moves(self):
        out = []
        for m in self.gen_pseudo():
            u = self.make(m)
            if not self.attacked(self.king[self.side ^ 1], self.side == 0):
                out.append(m)
            self.unmake(u)
        return out


def move_uci(m):
    frm, to, promo = m
    s = chr(97 + (frm & 7)) + str((frm >> 4) + 1) + chr(97 + (to & 7)) + str((to >> 4) + 1)
    return s + promo if promo else s


def evaluate(b):
    score = 0
    q = b.sq
    for s in range(128):
        if s & 0x88:
            continue
        p = q[s]
        if p == '.':
            continue
        pl = p.lower()
        if p.isupper():
            score += VAL[pl] + PST[pl][(s >> 4) * 8 + (s & 7)]
        else:
            score -= VAL[pl] + PST[pl][(7 - (s >> 4)) * 8 + (s & 7)]
    return score if b.side == 0 else -score


MAX_DEPTH = 6
NODE_BUDGET = 200000
nodes = [0]
budget_hit = [False]


def mvv_lva(b, m):
    victim = b.sq[m[1]]
    if victim == '.':
        if b.sq[m[0]].lower() == 'p' and m[1] == b.ep:
            return 105
        return 0
    return 100 + VAL[victim.lower()] * 10 - VAL[b.sq[m[0]].lower()]


def gen_captures(b):
    q = b.sq
    return [m for m in b.gen_pseudo()
            if q[m[1]] != '.' or (q[m[0]].lower() == 'p' and m[1] == b.ep)]


def quiesce(b, alpha, beta, depth=0):
    nodes[0] += 1
    stand = evaluate(b)
    if stand >= beta:
        return beta
    if stand > alpha:
        alpha = stand
    if depth > 3:
        return alpha
    moves = gen_captures(b)
    moves.sort(key=lambda m: -mvv_lva(b, m))
    for m in moves:
        u = b.make(m)
        if b.attacked(b.king[b.side ^ 1], b.side == 0):
            b.unmake(u)
            continue
        score = -quiesce(b, -beta, -alpha, depth + 1)
        b.unmake(u)
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def alphabeta(b, depth, alpha, beta):
    nodes[0] += 1
    if budget_hit[0] or nodes[0] > NODE_BUDGET:
        budget_hit[0] = True
        return 0
    if depth == 0:
        return quiesce(b, alpha, beta)
    moves = b.gen_pseudo()
    moves.sort(key=lambda m: -mvv_lva(b, m))
    has_legal = False
    in_chk = b.in_check()
    for m in moves:
        u = b.make(m)
        if b.attacked(b.king[b.side ^ 1], b.side == 0):
            b.unmake(u)
            continue
        has_legal = True
        score = -alphabeta(b, depth - 1, -beta, -alpha)
        b.unmake(u)
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    if not has_legal:
        return -30000 - depth if in_chk else 0
    return alpha


def search(b, max_depth=MAX_DEPTH):
    nodes[0] = 0
    budget_hit[0] = False
    best_move, best_score = None, 0
    legal = []
    for m in b.gen_pseudo():
        u = b.make(m)
        if not b.attacked(b.king[b.side ^ 1], b.side == 0):
            legal.append(m)
        b.unmake(u)
    if not legal:
        return None, 0
    legal.sort(key=lambda m: -mvv_lva(b, m))
    for depth in range(1, max_depth + 1):
        budget_hit[0] = False
        alpha, beta = -40000, 40000
        cur_best, cur_score = None, -40000
        for m in legal:
            u = b.make(m)
            score = -alphabeta(b, depth - 1, -beta, -alpha)
            b.unmake(u)
            if score > cur_score:
                cur_score, cur_best = score, m
            if score > alpha:
                alpha = score
        if budget_hit[0]:
            break
        if cur_best is not None:
            best_move, best_score = cur_best, cur_score
        if cur_best in legal:
            legal.remove(cur_best)
            legal.insert(0, cur_best)
        if nodes[0] > NODE_BUDGET:
            break
    return best_move, best_score


def post(path, body):
    req = urllib.request.Request(ENV + path, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req) as res:
        return json.load(res)


def main():
    if not ENV:
        sys.exit("MAKEFUN_ENV_URL is not set")
    while True:
        g = post("/game", {})
        if g["status"] == "done":
            break
        while g["status"] == "your_move":
            b = Board(g["fen"])
            legal_uci = g["legal_moves"]
            legal_set = set(legal_uci)
            move, score = search(b)
            if move is None:
                best = legal_uci[0]
            else:
                best = move_uci(move)
                if best not in legal_set:
                    best = legal_uci[0]
            g = post("/move", {"game": g["game"], "move": best})
        print(f"game {g['game']}: {g['outcome']} by {g['reason']}", file=sys.stderr)
    print(f"done: {g.get('wins')} won, {g.get('draws')} drawn, {g.get('losses')} lost",
          file=sys.stderr)


if __name__ == "__main__":
    main()
