"""tiny-chess-01 engine: alpha-beta with quiescence, 0x88 board, PST eval."""

import json, os, sys, urllib.request

ENV = os.environ.get("MAKEFUN_ENV_URL")

# ── 0x88 board ──────────────────────────────────────────────────────────────
# 128 squares; index & 0x88 != 0 → off-board. Square = rank*16 + file.
# White pieces: PNBRQK, black: pnbrqk, empty: '.'

# Piece values for evaluation and MVV-LVA
VAL = {'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 0}

# Direction offsets (0x88)
KNIGHT_OFFS = (33, 31, 18, 14, -33, -31, -18, -14)
BISHOP_DIRS = (17, 15, -17, -15)
ROOK_DIRS = (16, -16, 1, -1)
KING_OFFS = (16, -16, 1, -1, 17, 15, -17, -15)

# Piece-square tables (from white's perspective, a1=0 ... h8=119 in 0x88)
# Compressed: only need 64 values per piece type, mapped to 0x88 indices
PST_PAWN = (
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, -20, -20, 10, 10, 5,
    5, -5, -10, 0, 0, -10, -5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, 5, 10, 25, 25, 10, 5, 5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
    0, 0, 0, 0, 0, 0, 0, 0,
)
PST_KNIGHT = (
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
)
PST_BISHOP = (
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
)
PST_ROOK = (
    0, 0, 0, 5, 5, 0, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
)
PST_QUEEN = (
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -10, 5, 5, 5, 5, 5, 0, -10,
    0, 0, 5, 5, 5, 5, 0, -5,
    -5, 0, 5, 5, 5, 5, 0, -5,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
)
PST_KING = (
    20, 30, 10, 0, 0, 10, 30, 20,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
)

# Map 64-index PST to 0x88 index: pst[sq64] where sq64 = (sq88 >> 4) * 8 + (sq88 & 7)
def pst_index(sq88):
    return ((sq88 >> 4) << 3) | (sq88 & 7)

PSTS = {'p': PST_PAWN, 'n': PST_KNIGHT, 'b': PST_BISHOP,
        'r': PST_ROOK, 'q': PST_QUEEN, 'k': PST_KING}


class Board:
    """0x88 chess board with full move generation."""

    def __init__(self, fen):
        self.squares = ['.'] * 128
        self.side = 0  # 0 = white to move, 1 = black
        self.ep = -1  # en passant target square (0x88)
        self.castle = 0  # bit 0: white K, 1: white Q, 2: black K, 3: black Q
        self.king_sq = [0, 0]  # white king, black king squares

        parts = fen.split()
        rows = parts[0].split('/')
        for r, row in enumerate(rows):
            f = 0
            for c in row:
                if c.isdigit():
                    f += int(c)
                else:
                    sq = (7 - r) * 16 + f
                    self.squares[sq] = c
                    if c == 'K':
                        self.king_sq[0] = sq
                    elif c == 'k':
                        self.king_sq[1] = sq
                    f += 1
        self.side = 0 if parts[1] == 'w' else 1
        if len(parts) > 2 and parts[2] != '-':
            for i, ch in enumerate('KQkq'):
                if ch in parts[2]:
                    self.castle |= 1 << i
        if len(parts) > 3 and parts[3] != '-':
            f = ord(parts[3][0]) - ord('a')
            r = int(parts[3][1]) - 1
            self.ep = r * 16 + f

    def piece_at(self, sq):
        return self.squares[sq]

    def is_white(self, piece):
        return piece.isupper()

    def own_piece(self, piece):
        return piece != '.' and (piece.isupper() != bool(self.side))

    def attacked(self, sq, by_white):
        """Is square sq attacked by the given side?"""
        sqs = self.squares
        # Pawns
        if by_white:
            for d in (-15, -17):
                s = sq + d
                if not (s & 0x88) and sqs[s] == 'P':
                    return True
        else:
            for d in (15, 17):
                s = sq + d
                if not (s & 0x88) and sqs[s] == 'p':
                    return True
        # Knights
        for d in KNIGHT_OFFS:
            s = sq + d
            if not (s & 0x88) and sqs[s] in ('N' if by_white else 'n'):
                return True
        # King
        for d in KING_OFFS:
            s = sq + d
            if not (s & 0x88) and sqs[s] in ('K' if by_white else 'k'):
                return True
        # Sliding: bishop/queen
        for d in BISHOP_DIRS:
            s = sq + d
            while not (s & 0x88):
                p = sqs[s]
                if p != '.':
                    if p in ('B' if by_white else 'b', 'Q' if by_white else 'q'):
                        return True
                    break
                s += d
        # Sliding: rook/queen
        for d in ROOK_DIRS:
            s = sq + d
            while not (s & 0x88):
                p = sqs[s]
                if p != '.':
                    if p in ('R' if by_white else 'r', 'Q' if by_white else 'q'):
                        return True
                    break
                s += d
        return False

    def in_check(self):
        """Is the side to move in check?"""
        return self.attacked(self.king_sq[self.side], self.side == 0)

    def gen_pseudo(self):
        """Generate pseudo-legal moves as (from, to, promo) tuples."""
        moves = []
        sqs = self.squares
        white = self.side == 0
        for sq in range(128):
            if sq & 0x88:
                continue
            p = sqs[sq]
            if p == '.' or (p.isupper() != white):
                continue
            pl = p.lower()
            if pl == 'p':
                # Push
                d = 16 if white else -16
                s2 = sq + d
                if not (s2 & 0x88) and sqs[s2] == '.':
                    self._add_pawn(moves, sq, s2, white)
                    # Double push
                    s3 = s2 + d
                    start_rank = 1 if white else 6
                    if (sq >> 4) == start_rank and not (s3 & 0x88) and sqs[s3] == '.':
                        moves.append((sq, s3, None))
                # Captures
                for dd in (d + 1, d - 1):
                    s2 = sq + dd
                    if not (s2 & 0x88):
                        t = sqs[s2]
                        if t != '.' and (t.isupper() != white):
                            self._add_pawn(moves, sq, s2, white)
                        elif s2 == self.ep and t == '.':
                            moves.append((sq, s2, None))
            elif pl == 'n':
                for d in KNIGHT_OFFS:
                    s2 = sq + d
                    if not (s2 & 0x88):
                        t = sqs[s2]
                        if t == '.' or t.isupper() != white:
                            moves.append((sq, s2, None))
            elif pl == 'k':
                for d in KING_OFFS:
                    s2 = sq + d
                    if not (s2 & 0x88):
                        t = sqs[s2]
                        if t == '.' or t.isupper() != white:
                            moves.append((sq, s2, None))
                # Castling
                if white and sq == 0x04:
                    if (self.castle & 1 and sqs[0x05] == '.' and sqs[0x06] == '.'
                            and sqs[0x07] == 'R'
                            and not self.attacked(0x04, False)
                            and not self.attacked(0x05, False)
                            and not self.attacked(0x06, False)):
                        moves.append((sq, 0x06, None))
                    if (self.castle & 2 and sqs[0x03] == '.' and sqs[0x02] == '.'
                            and sqs[0x01] == '.' and sqs[0x00] == 'R'
                            and not self.attacked(0x04, False)
                            and not self.attacked(0x03, False)
                            and not self.attacked(0x02, False)):
                        moves.append((sq, 0x02, None))
                elif not white and sq == 0x74:
                    if (self.castle & 4 and sqs[0x75] == '.' and sqs[0x76] == '.'
                            and sqs[0x77] == 'r'
                            and not self.attacked(0x74, True)
                            and not self.attacked(0x75, True)
                            and not self.attacked(0x76, True)):
                        moves.append((sq, 0x76, None))
                    if (self.castle & 8 and sqs[0x73] == '.' and sqs[0x72] == '.'
                            and sqs[0x71] == '.' and sqs[0x70] == 'r'
                            and not self.attacked(0x74, True)
                            and not self.attacked(0x73, True)
                            and not self.attacked(0x72, True)):
                        moves.append((sq, 0x72, None))
            else:
                dirs = BISHOP_DIRS if pl == 'b' else ROOK_DIRS if pl == 'r' else BISHOP_DIRS + ROOK_DIRS
                for d in dirs:
                    s2 = sq + d
                    while not (s2 & 0x88):
                        t = sqs[s2]
                        if t == '.':
                            moves.append((sq, s2, None))
                        else:
                            if t.isupper() != white:
                                moves.append((sq, s2, None))
                            break
                        s2 += d
        return moves

    def _add_pawn(self, moves, frm, to, white):
        """Add pawn move with promotions if on last rank."""
        last = 7 if white else 0
        if (to >> 4) == last:
            for promo in ('q', 'r', 'b', 'n'):
                moves.append((frm, to, promo))
        else:
            moves.append((frm, to, None))

    def make(self, move):
        """Apply move, return undo info."""
        frm, to, promo = move
        sqs = self.squares
        piece = sqs[frm]
        captured = sqs[to]
        white = self.side == 0
        ep_cap = -1  # en passant capture square (-1 = none)
        old_ep = self.ep
        old_castle = self.castle
        old_kings = (self.king_sq[0], self.king_sq[1])

        sqs[to] = piece
        sqs[frm] = '.'

        # En passant capture
        if piece in ('P', 'p') and to == self.ep and captured == '.':
            ep_cap = to - 16 if white else to + 16
            captured = sqs[ep_cap]
            sqs[ep_cap] = '.'

        # Promotion
        if promo:
            sqs[to] = promo.upper() if white else promo

        # Castling: move rook
        if piece in ('K', 'k'):
            self.king_sq[self.side] = to
            if to - frm == 2:  # kingside
                sqs[to - 1] = sqs[to + 1]
                sqs[to + 1] = '.'
            elif to - frm == -2:  # queenside
                sqs[to + 1] = sqs[to - 2]
                sqs[to - 2] = '.'

        # Update castling rights
        if piece == 'K':
            self.castle &= ~3
        elif piece == 'k':
            self.castle &= ~12
        if frm == 0x00 or to == 0x00:
            self.castle &= ~2
        if frm == 0x07 or to == 0x07:
            self.castle &= ~1
        if frm == 0x70 or to == 0x70:
            self.castle &= ~8
        if frm == 0x77 or to == 0x77:
            self.castle &= ~4

        # En passant target
        self.ep = -1
        if piece in ('P', 'p') and abs(to - frm) == 32:
            self.ep = (frm + to) // 2

        self.side ^= 1
        return (frm, to, promo, piece, captured, ep_cap,
                old_ep, old_castle, old_kings[0], old_kings[1])

    def unmake(self, undo):
        frm, to, promo, piece, captured, ep_cap, ep, castle, wk, bk = undo
        sqs = self.squares
        self.side ^= 1
        sqs[frm] = piece
        sqs[to] = '.'
        if ep_cap >= 0:
            # En passant: captured pawn was beside the target
            sqs[ep_cap] = captured
        elif captured != '.':
            sqs[to] = captured
        # Castling: move rook back
        if piece in ('K', 'k'):
            if to - frm == 2:
                sqs[to + 1] = sqs[to - 1]
                sqs[to - 1] = '.'
            elif to - frm == -2:
                sqs[to - 2] = sqs[to + 1]
                sqs[to + 1] = '.'
        self.ep = ep
        self.castle = castle
        self.king_sq[0] = wk
        self.king_sq[1] = bk

    def legal_moves(self):
        """Generate legal moves (pseudo-legal filtered by king safety)."""
        result = []
        for m in self.gen_pseudo():
            undo = self.make(m)
            if not self.attacked(self.king_sq[self.side ^ 1], self.side == 0):
                result.append(m)
            self.unmake(undo)
        return result


def sq88_to_uci(sq):
    return chr(97 + (sq & 7)) + str((sq >> 4) + 1)


def uci_to_sq88(uci):
    return (int(uci[1]) - 1) * 16 + (ord(uci[0]) - 97)


def move_uci(move):
    frm, to, promo = move
    s = sq88_to_uci(frm) + sq88_to_uci(to)
    if promo:
        s += promo
    return s


# ── Evaluation ──────────────────────────────────────────────────────────────

def evaluate(board):
    """Static evaluation from the side-to-move's perspective."""
    score = 0
    sqs = board.squares
    for sq in range(128):
        if sq & 0x88:
            continue
        p = sqs[sq]
        if p == '.':
            continue
        pl = p.lower()
        val = VAL[pl]
        pst = PSTS[pl]
        idx = pst_index(sq)
        if p.isupper():
            score += val + pst[idx]
        else:
            # Mirror PST for black: flip rank
            idx = (7 - (sq >> 4)) * 8 + (sq & 7)
            score -= val + pst[idx]
    # Side to move perspective
    return score if board.side == 0 else -score


# ── Search ──────────────────────────────────────────────────────────────────

MAX_DEPTH = 6
NODE_BUDGET = 200000

nodes = [0]
budget_hit = [False]


def mvv_lva(board, move):
    """Move ordering: captures by value."""
    frm, to, promo = move
    victim = board.squares[to]
    if victim == '.':
        if board.squares[frm].lower() == 'p' and to == board.ep:
            return 105
        return 0
    attacker = board.squares[frm].lower()
    return 100 + VAL[victim.lower()] * 10 - VAL[attacker]


def gen_captures(board):
    """Generate only captures (for quiescence)."""
    moves = []
    sqs = board.squares
    white = board.side == 0
    for m in board.gen_pseudo():
        if sqs[m[1]] != '.' or (sqs[m[0]].lower() == 'p' and m[1] == board.ep):
            moves.append(m)
    return moves


def quiesce(board, alpha, beta, depth=0):
    """Quiescence search: only captures."""
    nodes[0] += 1
    stand = evaluate(board)
    if stand >= beta:
        return beta
    if stand > alpha:
        alpha = stand
    if depth > 3:
        return alpha
    moves = gen_captures(board)
    moves.sort(key=lambda m: -mvv_lva(board, m))
    for m in moves:
        undo = board.make(m)
        if board.attacked(board.king_sq[board.side ^ 1], board.side == 0):
            board.unmake(undo)
            continue
        score = -quiesce(board, -beta, -alpha, depth + 1)
        board.unmake(undo)
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def alphabeta(board, depth, alpha, beta):
    """Alpha-beta search with inline legality check."""
    nodes[0] += 1
    if budget_hit[0] or nodes[0] > NODE_BUDGET:
        budget_hit[0] = True
        return 0
    if depth == 0:
        return quiesce(board, alpha, beta)
    moves = board.gen_pseudo()
    moves.sort(key=lambda m: -mvv_lva(board, m))
    has_legal = False
    in_check = board.in_check()
    for m in moves:
        undo = board.make(m)
        if board.attacked(board.king_sq[board.side ^ 1], board.side == 0):
            board.unmake(undo)
            continue
        has_legal = True
        score = -alphabeta(board, depth - 1, -beta, -alpha)
        board.unmake(undo)
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    if not has_legal:
        if in_check:
            return -30000 - depth  # Checkmate
        return 0  # Stalemate
    return alpha


def search(board, max_depth=MAX_DEPTH):
    """Iterative deepening search, returns best move."""
    best_move = None
    best_score = 0
    legal = []
    # Root: use legal moves (need them for the env anyway)
    for m in board.gen_pseudo():
        undo = board.make(m)
        if not board.attacked(board.king_sq[board.side ^ 1], board.side == 0):
            legal.append(m)
        board.unmake(undo)
    if not legal:
        return None, 0
    legal.sort(key=lambda m: -mvv_lva(board, m))
    for depth in range(1, max_depth + 1):
        budget_hit[0] = False
        alpha, beta = -40000, 40000
        cur_best = None
        cur_score = -40000
        for m in legal:
            undo = board.make(m)
            score = -alphabeta(board, depth - 1, -beta, -alpha)
            board.unmake(undo)
            if score > cur_score:
                cur_score = score
                cur_best = m
            if score > alpha:
                alpha = score
        # Only accept this depth's result if budget wasn't exceeded
        if budget_hit[0]:
            break
        if cur_best is not None:
            best_move = cur_best
            best_score = cur_score
        # Move ordering: best first for next iteration
        if cur_best in legal:
            legal.remove(cur_best)
            legal.insert(0, cur_best)
        if nodes[0] > NODE_BUDGET:
            break
    return best_move, best_score


# ── Main loop ───────────────────────────────────────────────────────────────

def post(path, body):
    req = urllib.request.Request(
        ENV + path,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
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
            board = Board(g["fen"])
            legal_uci = g["legal_moves"]
            # Convert env's legal moves to our format for ordering
            legal_set = set(legal_uci)
            move, score = search(board)
            if move is None:
                # Fallback: pick first legal move from env
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
