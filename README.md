# Minesweeper-Automatic-Solver
Minesweeper automatic solver by iterative scaling with GUI visualization built in Python using Tkinter.

## Features

- Iterative constraint propagation for mine probability estimation
- Strategic solver that prioritizes certain moves over probabilistic ones
- Real-time probability visualization on interactive board
- Automated game logging (outcomes, coverage stats) to CSV

## Usage

The script requires Python 3.6+ and tkinter (usually included with Python). To run the solver:

```bash
python minesweepersolver.py
```

## Results

Over 128 automated runs, the solver achieved a ~10% win rate. Successful runs accounted for 37% of the total 13,070 cells explored across all games.

## Reference

Mike Sheppard. A simple Minesweeper algorithm. Authoritative Minesweeper (2023). Accessed on Feb 23, 2025. https://minesweepergame.com/math/a-simple-minesweeper-algorithm-2023.pdf
