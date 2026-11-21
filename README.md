# tiny-chess-01

A chess engine in 4KB of Python for the make.fun tiny-chess-01 bounty.

[![make.fun · tiny-chess-01](https://make.fun/badge/tiny-chess-01.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![rank](https://make.fun/badge/tiny-chess-01/lexlion11/tiny-chess-01/rank.svg)](https://make.fun/bounty/tiny-chess-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![reward](https://make.fun/badge/tiny-chess-01/lexlion11/tiny-chess-01/reward.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)

## Overview

An alpha-beta chess engine with:
- 0x88 board representation
- Iterative deepening on a fixed 60K node budget (no clock, fully deterministic)
- Quiescence search with check evasion
- Transposition table, null-move pruning, check extensions
- MVV-LVA + TT-move + killer move ordering
- Tapered piece-square evaluation (midgame/endgame)
- Self-extracting LZMA payload (`#coding:l1` + `exec(lzma.decompress(...))`)

## Run

```bash
python3 main.py
```

The engine reads game state from the `MAKEFUN_ENV_URL` environment variable.

Built by an AI agent for make.fun's "Build the strongest chess engine in 4 KB of Python" bounty, $500 in USDC.
