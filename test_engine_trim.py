"""Functional test for engine_trim.py and the compressed main.py payload."""
import importlib.util, sys

# 1. Load compressed main.py as a module (exec runs the lzma payload;
#    __main__ guard keeps the env loop from starting without MAKEFUN_ENV_URL)
spec = importlib.util.spec_from_file_location("main_payload", "main.py")
mp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mp)

spec2 = importlib.util.spec_from_file_location("eng", "engine_trim.py")
eng = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(eng)

# 2. Cross-check: both must agree on startpos move count and a search result
b1 = eng.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
b2 = mp.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
assert len(b1.legal_moves()) == len(b2.legal_moves()) == 20
print("PASS: engine_trim and main.py payload both give 20 startpos moves")

# 3. Perft validation on the payload module
def perft(board, depth):
    if depth == 0:
        return 1
    n = 0
    for m in board.legal_moves():
        u = board.make(m)
        n += perft(board, depth - 1)
        board.unmake(u)
    return n

b = mp.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
assert perft(b, 1) == 20
assert perft(b, 2) == 400
assert perft(b, 3) == 8902
print("PASS: startpos perft 1/2/3 = 20/400/8902")

# Kiwipete (castling/ep edge cases)
bk = mp.Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
assert perft(bk, 1) == 48
assert perft(bk, 2) == 2039
print("PASS: kiwipete perft 1/2 = 48/2039")

# 4. Search returns a legal move
mp.nodes[0] = 0
mv, score = mp.search(b, max_depth=3)
uci = mp.move_uci(mv)
legal_uci = {mp.move_uci(m) for m in b.legal_moves()}
assert uci in legal_uci, f"search returned illegal move {uci}"
print(f"PASS: search depth3 -> {uci} score={score} nodes={mp.nodes[0]}")

# 5. Checkmate scoring: back-rank mate should be found at depth 3
bm = mp.Board("6k1/5ppp/8/8/8/8/8/R6K w - - 0 1")
mvb, scb = mp.search(bm, max_depth=3)
assert mp.move_uci(mvb) == "a1a8", f"expected Ra8#, got {mp.move_uci(mvb)}"
assert scb > 30000, f"expected mate score, got {scb}"
print(f"PASS: back-rank mate found -> {mp.move_uci(mvb)} score={scb}")

# 6. Evaluation sanity
be = mp.Board("8/8/8/8/8/8/8/R6K w - - 0 1")
ev = mp.evaluate(be)
assert ev > 400, f"rook eval: {ev}"
print(f"PASS: evaluate rook endgame = {ev}")

# 7. Node budget: searching a deep position must respect the budget
mp.nodes[0] = 0
mp.search(b, max_depth=6)
assert mp.nodes[0] <= mp.NODE_BUDGET * 3, f"node blowout: {mp.nodes[0]}"
print(f"PASS: node budget respected, nodes={mp.nodes[0]} budget={mp.NODE_BUDGET}")

print("ALL TESTS PASSED")
