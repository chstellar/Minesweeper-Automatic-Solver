import tkinter as tk
import random
import time
import csv
import os
import argparse
import copy
from PIL import ImageGrab

MASTER_SEED = 42
THRESHOLD = 0.04

class Minesweeper:
    def __init__(self, master, rows=16, cols=30, mines=99, click_delay=0, label="", assist_mode=False):
        self.master = master
        self.rows = rows
        self.cols = cols
        self.initial_mines = mines
        self.mines = mines
        self.non_mines = rows * cols - mines
        self.click_delay = click_delay
        self.grid = []
        self.buttons = []
        self.game_over = False
        self.last_click_time = 0
        self.assist_mode = assist_mode
        self.colors = {
            1: 'blue', 2: 'green', 3: 'red', 4: 'darkblue',
            5: 'brown', 6: 'cyan', 7: 'black', 8: 'gray'
        }
        self.flag_emoji = "\u2691"
        self.mine_emoji = "\U0001F4A3"
        self.spanning_area = 0
        self.label = label
        self.actual_flags = 0
        self.queued_safe = []
        self.queued_mines = []
        self.start_time = None
        self.last_move_prob = None
        self.last_move_entropy = None
        self.clicked_mine = None
        self.move_queue = [] 
        self.pre_lethal_state_and_probs = None
        self.current_seed = None 
        self.last_saved_file = None
        self._init_game()

    def _init_game(self):
        self._create_grid()
        self._create_buttons()
        self._place_mines()
        mode_text = "Assist Mode" if self.assist_mode else "Auto Solver"
        self.master.title(f"Minesweeper - {mode_text}")
        self.start_time = time.time()

    def _create_grid(self):
        for _ in range(self.rows):
            row = [{'mine': False, 'revealed': False, 'flagged': False, 'count': 0}
                   for _ in range(self.cols)]
            self.grid.append(row)

    def _create_buttons(self):
        for r in range(self.rows):
            row_btns = []
            for c in range(self.cols):
                btn = tk.Button(
                    self.master, 
                    width=2, 
                    height=1, 
                    font=('Arial', 10, 'bold'),
                    relief='raised', 
                    bg='lightgrey',
                    command=lambda rr=r, cc=c: self._reveal(rr, cc)
                )
                btn.bind("<Button-3>", lambda e, rr=r, cc=c: self._flag(rr, cc))
                btn.bind("<Button-2>", lambda e, rr=r, cc=c: self._chord(rr, cc))
                btn.bind("<Double-Button-1>", lambda e, rr=r, cc=c: self._chord(rr, cc))
                btn.grid(row=r, column=c, padx=1, pady=1)
                row_btns.append(btn)
            self.buttons.append(row_btns)

    def _place_mines(self):
        positions = random.sample(range(self.rows * self.cols), self.initial_mines)
        for pos in positions:
            r, c = divmod(pos, self.cols)
            self.grid[r][c]['mine'] = True
            self._update_neighbors(r, c)
        
        for r in range(self.rows):
            for c in range(self.cols):
                virtual_mines = 0
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if nr < 0 or nr >= self.rows or nc < 0 or nc >= self.cols:
                            virtual_mines += 1
                
                self.grid[r][c]['virtual_count'] = self.grid[r][c]['count'] + virtual_mines

    def _get_neighbors_with_virtual(self, row, col):
        coords = []
        for rr in range(row-1, row+2):
            for cc in range(col-1, col+2):
                if (rr, cc) != (row, col):
                    coords.append((rr, cc))
        return coords

    def _is_virtual_cell(self, r, c):
        return r < 0 or r >= self.rows or c < 0 or c >= self.cols

    def _update_neighbors(self, row, col):
        for rr in range(max(0, row-1), min(self.rows, row+2)):
            for cc in range(max(0, col-1), min(self.cols, col+2)):
                if not self.grid[rr][cc]['mine']:
                    self.grid[rr][cc]['count'] += 1

    def _reveal(self, r, c):
        if self.game_over or self.grid[r][c]['flagged']:
            return
        
        # *** NEW: Capture state right before a lethal click ***
        if self.grid[r][c]['mine']:
            # This is a lethal move. Capture the state *before* it's processed.
            # It's important to do this before the grid is modified by _reveal_recursive.
            grid_copy = copy.deepcopy(self.grid)
            probs_before_click = self._get_current_probabilities()
            self.pre_lethal_state_and_probs = {
                "grid": grid_copy,
                "probs": probs_before_click,
            }
        
        if not self.assist_mode:
            current_time = time.time()
            if current_time - self.last_click_time < self.click_delay:
                return
            self.last_click_time = current_time
        
        self._reveal_recursive(r, c)
        self.master.update_idletasks()
        
        if self.assist_mode and not self.game_over:
            self.calculate_and_display_probabilities()

    def _reveal_recursive(self, r, c):
        if self.grid[r][c]['revealed'] or self.grid[r][c]['flagged']:
            return
        self.grid[r][c]['revealed'] = True
        self.spanning_area += 1
        count = self.grid[r][c]['count']
        color = self.colors.get(count, 'black')
        self.buttons[r][c].config(
            text='' if count == 0 else str(count),
            relief='sunken',
            width=2,
            height=1,
            bg='white',
            fg=color,
            font=('Arial', 10, 'bold')
        )
        if self.grid[r][c]['mine']:
            self.clicked_mine = (r, c)
            self._lose()
        else:
            self.non_mines -= 1
            if self.grid[r][c]['count'] == 0:
                for rr in range(max(0, r-1), min(self.rows, r+2)):
                    for cc in range(max(0, c-1), min(self.cols, c+2)):
                        if (rr, cc) != (r, c):
                            self._reveal_recursive(rr, cc)
            self._check_win()

    def _flag(self, r, c):
        if self.game_over or self.grid[r][c]['revealed']:
            return
        
        if not self.assist_mode:
            current_time = time.time()
            if current_time - self.last_click_time < self.click_delay:
                return
            self.last_click_time = current_time
        
        was_flagged = self.grid[r][c]['flagged']
        self.grid[r][c]['flagged'] = not self.grid[r][c]['flagged']
        
        if self.grid[r][c]['flagged']:
            self.actual_flags += 1
        else:
            self.actual_flags -= 1
        
        self.buttons[r][c].config(
            text=self.flag_emoji if self.grid[r][c]['flagged'] else '', 
            fg='red', 
            width=2, 
            height=1, 
            font=('Arial', 10, 'bold')
        )
        
        self.master.update_idletasks()
        
        if self.assist_mode and not self.game_over:
            self.calculate_and_display_probabilities()

    def _chord(self, r, c):
        if self.game_over or not self.grid[r][c]['revealed'] or self.grid[r][c]['mine']:
            return
        
        nbrs = self._get_neighbors(r, c)
        flagged_count = sum(1 for nr, nc in nbrs if self.grid[nr][nc]['flagged'])
        
        if flagged_count == self.grid[r][c]['count']:
            for nr, nc in nbrs:
                if not self.grid[nr][nc]['revealed'] and not self.grid[nr][nc]['flagged']:
                    self._reveal(nr, nc)
            
            if self.assist_mode and not self.game_over:
                self.calculate_and_display_probabilities()

    def _check_win(self):
        if self.non_mines == 0:
            self.game_over = True
            for r in range(self.rows):
                for c in range(self.cols):
                    if self.grid[r][c]['mine']:
                        self.buttons[r][c].config(
                            text=self.mine_emoji, 
                            fg='black', 
                            bg='lightgrey',
                            width=2, 
                            height=1, 
                            font=('Arial', 10, 'bold')
                        )
            self.master.title("You win!")
            # *** UPDATED Call ***
            self.save_game_state("win", self.grid, probs=None)
            self.log_game_result("win")

    def _lose(self):
        self.game_over = True
        
        # Visualization part: Use the final grid state to show all mines.
        # The fatal mine is highlighted in red. This remains the same.
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c]['mine']:
                    if self.clicked_mine and (r, c) == self.clicked_mine:
                        bg_color = 'red'
                    else:
                        bg_color = 'lightgrey'
                    
                    self.buttons[r][c].config(
                        text=self.mine_emoji, 
                        fg='black', 
                        bg=bg_color, 
                        width=2, 
                        height=1, 
                        font=('Arial', 10, 'bold')
                    )
        self.master.title("Game Over")
        
        # *** NEW: Saving logic for losses ***
        if self.spanning_area > 1:
            if self.pre_lethal_state_and_probs:
                # If we captured a pre-lethal state, save that.
                self.save_game_state(
                    "lose",
                    self.pre_lethal_state_and_probs["grid"],
                    self.pre_lethal_state_and_probs["probs"]
                )
            else:
                final_probs = self._calculate_final_probabilities()
                self.save_game_state("lose", self.grid, final_probs)
            
            self.log_game_result("lose")
        
        if self.assist_mode:
            self.master.after(0, self.restart_game)

    def _calculate_final_probabilities(self):
        """Calculate probabilities at game end for saving (used as a fallback)."""
        global_mine_density = self.initial_mines / (self.rows * self.cols)
        probs = {}
        
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if not cell['revealed'] and not cell['flagged']:
                    probs[(r, c)] = {'p': global_mine_density, 'q': 1 - global_mine_density}
        return probs

    def save_game_state(self, outcome, grid_to_save, probs=None):
            """Save game state to file for later rendering."""
            try:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"screenshots/{outcome}_{timestamp}_span{self.spanning_area}.txt"
                
                # Create the directory if it doesn't exist
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                
                with open(filename, 'w') as f:
                    # ... (rest of the function is the same)
                    f.write(f"Outcome: {outcome}\n")
                    f.write(f"Spanning Area: {self.spanning_area}\n")
                    f.write(f"Rows: {self.rows}, Cols: {self.cols}, Mines: {self.initial_mines}\n")
                    f.write(f"Clicked Mine: {self.clicked_mine}\n")
                    f.write(f"Last Move Prob: {self.last_move_prob}\n")
                    f.write(f"Last Move Entropy: {self.last_move_entropy}\n")
                    f.write(f"Game Seed: {self.current_seed}\n")
                    f.write("\n")
                    
                    for r in range(self.rows):
                        for c in range(self.cols):
                            cell = grid_to_save[r][c]
                            prob = -1.0
                            if probs and (r, c) in probs:
                                prob = probs[(r, c)]['p']
                            
                            f.write(f"{r},{c},{int(cell['mine'])},{int(cell['revealed'])},{int(cell['flagged'])},{cell['count']},{prob:.4f}\n")
                
                print(f"Game state saved: {filename}")
                self.last_saved_file = filename
                return filename
            except Exception as e:
                print(f"Failed to save game state: {e}")
                self.last_saved_file = None
                return None

    def calculate_and_display_probabilities(self):
        """Calculate probabilities and display them (used in both modes)"""
        trivial_safe = []
        trivial_mines = []
        
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if cell['revealed'] and not cell['mine']:
                    nbrs = self._get_neighbors(r, c)
                    unknown = []
                    flagged = 0
                    for nr, nc in nbrs:
                        if self.grid[nr][nc]['flagged']:
                            flagged += 1
                        elif not self.grid[nr][nc]['revealed']:
                            unknown.append((nr, nc))
                    
                    remaining = cell['count'] - flagged
                    
                    if unknown and remaining == len(unknown):
                        trivial_mines.extend(unknown)
                    elif unknown and remaining == 0:
                        trivial_safe.extend(unknown)
        
        trivial_safe = list(set(trivial_safe))
        trivial_mines = list(set(trivial_mines))
        
        global_mine_density = self.initial_mines / (self.rows * self.cols)
        probs = {}
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if not cell['revealed'] and not cell['flagged']:
                    if (r, c) in trivial_safe:
                        probs[(r, c)] = {'p': 0.0, 'q': 1.0}
                    elif (r, c) in trivial_mines:
                        probs[(r, c)] = {'p': 1.0, 'q': 0.0}
                    else:
                        probs[(r, c)] = {'p': global_mine_density, 'q': 1 - global_mine_density}

        constraints = []
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if cell['revealed'] and not cell['mine']:
                    nbrs = self._get_neighbors(r, c)
                    unknown = []
                    flagged = 0
                    for nr, nc in nbrs:
                        if self.grid[nr][nc]['flagged']:
                            flagged += 1
                        elif not self.grid[nr][nc]['revealed']:
                            unknown.append((nr, nc))
                    if unknown:
                        remaining = cell['count'] - flagged
                        constraints.append({'cells': unknown, 'remaining': remaining})
        
        if constraints:
            max_iter = 100
            threshold = 0.01
            for iteration in range(max_iter):
                max_change = 0
                for con in constraints:
                    cells = con['cells']
                    rem = con['remaining']
                    valid_cells = [cell for cell in cells if cell in probs]
                    if not valid_cells: continue
                    sum_p = sum(probs[cell]['p'] for cell in valid_cells)
                    sum_q = sum(probs[cell]['q'] for cell in valid_cells)
                    if sum_p > 1e-10:
                        factor_p = rem / sum_p
                        for cell in valid_cells:
                            old = probs[cell]['p']
                            probs[cell]['p'] *= factor_p
                            max_change = max(max_change, abs(probs[cell]['p'] - old))
                    if sum_q > 1e-10:
                        factor_q = (len(valid_cells) - rem) / sum_q
                        for cell in valid_cells:
                            old = probs[cell]['q']
                            probs[cell]['q'] *= factor_q
                            max_change = max(max_change, abs(probs[cell]['q'] - old))
                for cell in probs:
                    p_val, q_val = probs[cell]['p'], probs[cell]['q']
                    total = p_val + q_val
                    if total > 1e-10:
                        new_p, new_q = p_val / total, q_val / total
                        max_change = max(max_change, abs(new_p - p_val), abs(new_q - q_val))
                        probs[cell]['p'], probs[cell]['q'] = new_p, new_q
                if max_change < threshold: break
        
        self.display_probabilities(probs)
        return probs, trivial_safe, trivial_mines

    def _get_current_probabilities(self):
        """Calculate probabilities using the solver's logic, without displaying."""
        remaining_mines = self.initial_mines - self.actual_flags
        unrevealed_count = sum(1 for r in range(self.rows) for c in range(self.cols) 
                            if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged'])
        global_mine_density = remaining_mines / unrevealed_count if unrevealed_count > 0 else 0
        
        probs = {}
        for r in range(self.rows):
            for c in range(self.cols):
                if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged']:
                    probs[(r, c)] = {'p': global_mine_density, 'q': 1 - global_mine_density}

        constraints = []
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if cell['revealed'] and not cell['mine']:
                    nbrs = self._get_neighbors_with_virtual(r, c)
                    unknown, flagged = [], 0
                    for nr, nc in nbrs:
                        if self._is_virtual_cell(nr, nc) or self.grid[nr][nc]['flagged']:
                            flagged += 1
                        elif not self.grid[nr][nc]['revealed']:
                            unknown.append((nr, nc))
                    if unknown:
                        virtual_count = cell.get('virtual_count', cell['count'])
                        remaining = virtual_count - flagged
                        constraints.append({'cells': unknown, 'remaining': remaining})
        
        if probs:
            constraints.append({'cells': list(probs.keys()), 'remaining': remaining_mines})
        
        if not constraints:
            return probs
        
        max_iter, threshold = 100, 0.01
        for _ in range(max_iter):
            max_change = 0
            for con in constraints:
                cells, rem = con['cells'], con['remaining']
                valid_cells = [cell for cell in cells if cell in probs]
                if not valid_cells: continue
                sum_p = sum(probs[cell]['p'] for cell in valid_cells)
                sum_q = sum(probs[cell]['q'] for cell in valid_cells)
                if sum_p > 1e-10:
                    factor_p = rem / sum_p
                    for cell in valid_cells:
                        old = probs[cell]['p']
                        probs[cell]['p'] *= factor_p
                        max_change = max(max_change, abs(probs[cell]['p'] - old))
                if sum_q > 1e-10:
                    factor_q = (len(valid_cells) - rem) / sum_q
                    for cell in valid_cells:
                        old = probs[cell]['q']
                        probs[cell]['q'] *= factor_q
                        max_change = max(max_change, abs(probs[cell]['q'] - old))
            
            for cell in probs:
                p_val, q_val = probs[cell]['p'], probs[cell]['q']
                total = p_val + q_val
                if total > 1e-10:
                    new_p, new_q = p_val / total, q_val / total
                    max_change = max(max_change, abs(new_p - p_val), abs(new_q - q_val))
                    probs[cell]['p'], probs[cell]['q'] = new_p, new_q
            
            if max_change < threshold: break
        
        return probs

    def update_probabilities_only(self):
        """Fast probability update for display purposes."""
        probs = self._get_current_probabilities()
        self.display_probabilities(probs)

    def will_flag_help(self, r, c):
        # ... (This method remains unchanged)
        nbrs = self._get_neighbors(r, c)
        for nr, nc in nbrs:
            if not self.grid[nr][nc]['revealed'] or self.grid[nr][nc]['mine']:
                continue
            neighbor_nbrs = self._get_neighbors(nr, nc)
            unknown_count, flagged_count = 0, 0
            for nnr, nnc in neighbor_nbrs:
                if self.grid[nnr][nnc]['flagged']: flagged_count += 1
                elif not self.grid[nnr][nnc]['revealed']: unknown_count += 1
            remaining_mines = self.grid[nr][nc]['count'] - flagged_count
            if remaining_mines == 1 and unknown_count > 1:
                return True
        return False

    def solve_minesweeper_entropy(self):
        if self.game_over:
            return

        # Priority 1: If there are moves in the queue, execute the next one.
        if self.move_queue:
            action, (r, c), prob = self.move_queue.pop(0)

            is_valid_move = (action == 'reveal' and not self.grid[r][c]['revealed']) or \
                            (action == 'flag' and not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged'])

            if is_valid_move:
                self.last_move_prob = prob
                self.last_move_entropy = min(prob, 1 - prob)
                if action == 'reveal':
                    self._reveal(r, c)
                elif action == 'flag':
                    self._flag(r, c)
        
        # Priority 2: If the queue is empty, calculate probabilities and repopulate it.
        else:
            probs = self._get_current_probabilities()
            self.display_probabilities(probs)

            # --- Step A: Use STRICT thresholds to separate CERTAINTY from GUESSING ---
            # This is the most critical change to fix the bug.
            certain_safe_cells = []
            certain_mine_cells = []
            uncertain_cells = []  # This will store (probability, (r, c)) for true guesses

            # Use tight floating-point-safe thresholds for absolute certainty.
            CERTAIN_SAFE_THRESHOLD = THRESHOLD
            CERTAIN_MINE_THRESHOLD = 1 - THRESHOLD

            for (r, c), vals in probs.items():
                prob = vals['p']
                # Partition into three MUTUALLY EXCLUSIVE categories.
                if prob < CERTAIN_SAFE_THRESHOLD:
                    certain_safe_cells.append(((r, c), prob))
                elif prob > CERTAIN_MINE_THRESHOLD:
                    certain_mine_cells.append(((r, c), prob))
                else:  # Any cell that is not 100% safe or 100% a mine is a guess.
                    uncertain_cells.append((prob, (r, c)))

            # --- Step B: Populate the queue based on the user's desired hierarchy ---
            # SAFE -> GUESS -> FLAG
            
            # 1. If there are CERTAINLY SAFE cells, queue them all for revealing.
            if certain_safe_cells:
                self.move_queue = [('reveal', coords, prob) for coords, prob in certain_safe_cells]

            # 2. If NO certain safe cells, find the best GUESS from the UNCERTAIN list.
            elif uncertain_cells:
                # Find the best guess (lowest probability) from the uncertain list.
                prob, coords = min(uncertain_cells)
                # Queue only the single best guess. The board state will change, requiring recalculation.
                self.move_queue.append(('reveal', coords, prob))

            # 3. If NO certain safe cells and NO uncertain cells to guess on,
            #    the only remaining option is to flag CERTAIN MINES.
            elif certain_mine_cells:
                # This provides the solver with more info for the next cycle without risk.
                self.move_queue = [('flag', coords, prob) for coords, prob in certain_mine_cells]

            # Immediately process the first move from the newly populated queue.
            if self.move_queue:
                self.solve_minesweeper_entropy()
                return

        # Schedule the next solver cycle.
        if not self.game_over:
            self.master.after(10, self.solve_minesweeper_entropy)

    def _get_neighbors(self, row, col):
        coords = []
        for rr in range(max(0, row-1), min(self.rows, row+2)):
            for cc in range(max(0, col-1), min(self.cols, col+2)):
                if (rr, cc) != (row, col):
                    coords.append((rr, cc))
        return coords

    def restart_game(self):
        self.grid = []
        self.buttons = []
        self.game_over = False
        self.mines = self.initial_mines
        self.non_mines = self.rows * self.cols - self.initial_mines
        self.spanning_area = 0
        self.actual_flags = 0
        self.queued_safe = []
        self.queued_mines = []
        self.start_time = None
        self.last_move_prob = None
        self.last_move_entropy = None
        self.clicked_mine = None
        self.move_queue = []
        self.pre_lethal_state_and_probs = None
        self.last_saved_file = None
        for widget in self.master.winfo_children():
            widget.destroy()
        self._init_game()
        
        if self.assist_mode:
            self.master.after(0, self.calculate_and_display_probabilities)
        else:
            self.master.after(0, self.solve_minesweeper_entropy)

    def display_probabilities(self, probs):
        for (r, c), vals in probs.items():
            prob = vals['p']
            if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged']:
                if prob < THRESHOLD: color = '#5b8c5a'
                elif prob > 1 - THRESHOLD: color = '#ff6361'
                else: color = 'white'
                self.buttons[r][c].config(
                    text=f'{prob:.1f}', fg=color, font=('Arial', 10, 'bold'), width=2, height=1
                )

    def log_game_result(self, outcome):
            log_file = "minesweeper_log.csv"
            file_exists = os.path.isfile(log_file)
            
            game_duration = time.time() - self.start_time if self.start_time else 0
            
            with open(log_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                if not file_exists:
                    # Add the new headers
                    writer.writerow(["Outcome", "Spanning Area", "Rows", "Cols", "Mines", 
                                "Flags Placed", "Mode", "Duration (s)", "Last Move Prob", 
                                "Last Move Entropy", "Game Seed", "State File"])
                
                mode = "Assist" if self.assist_mode else "Auto"
                
                # Add the new data points to the row
                writer.writerow([
                    outcome, 
                    self.spanning_area, 
                    self.rows, 
                    self.cols, 
                    self.initial_mines, 
                    self.actual_flags, 
                    mode,
                    f"{game_duration:.2f}",
                    f"{self.last_move_prob:.4f}" if self.last_move_prob is not None else "N/A",
                    f"{self.last_move_entropy:.4f}" if self.last_move_entropy is not None else "N/A",
                    self.current_seed,
                    self.last_saved_file if self.last_saved_file else "N/A"
                ])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Minesweeper Solver')
    parser.add_argument('-a', '--assist', action='store_true', 
                       help='Enable assist mode (manual play with probability hints)')
    parser.add_argument('-n', '--num-games', type=int, default=None,
                       help='Number of games to play in auto mode (default: unlimited)')
    parser.add_argument('--rows', type=int, default=16, help='Number of rows (default: 16)')
    parser.add_argument('--cols', type=int, default=30, help='Number of columns (default: 30)')
    parser.add_argument('--mines', type=int, default=99, help='Number of mines (default: 99)')
    parser.add_argument('--label', type=str, default='demo', help='Label for logging (default: demo)')
    parser.add_argument('--seed', type=int, default=MASTER_SEED, help=f'Master random seed (default: {MASTER_SEED})')
    parser.add_argument('--game-seed', type=int, default=None, 
                       help='Specific game seed to use (overrides -n and --seed)')
    
    args = parser.parse_args()
    
    current_seed_for_game = None

    if args.game_seed is not None:
        random.seed(args.game_seed)
        game_seeds = None
        num_games = 1
        current_seed_for_game = args.game_seed
        print(f"Running single game with seed {args.game_seed}")
    else:
        random.seed(args.seed)
        if args.num_games:
            game_seeds = [random.randint(0, 2**31 - 1) for _ in range(args.num_games)]
        else:
            game_seeds = None
        num_games = args.num_games
    
    root = tk.Tk()
    current_game_index = [0]
    
    if game_seeds:
        current_seed_for_game = game_seeds[0]
        random.seed(current_seed_for_game)
    elif args.game_seed is None:
        current_seed_for_game = random.randint(0, 2**31 - 1)
        random.seed(current_seed_for_game)
        
    game = Minesweeper(root, 
                      rows=args.rows, 
                      cols=args.cols, 
                      mines=args.mines, 
                      click_delay=0, 
                      label=args.label,
                      assist_mode=args.assist)
    
    game.current_seed = current_seed_for_game

    if args.assist:
        print("Assist mode enabled. Click cells to reveal or right-click to flag.")
        print("Green = safe, White = uncertain, Red = mine")
        root.after(100, game.calculate_and_display_probabilities)
    else:
        games_played = [0]
        
        if args.game_seed is not None:
            print(f"Auto mode: Playing 1 game with seed {args.game_seed}")
        elif num_games:
            print(f"Auto mode: Playing {num_games} games with master seed {args.seed}")
        else:
            print(f"Auto mode: Playing games with master seed {args.seed}")
        
        def check_time():
            global current_seed_for_game
            if game.game_over:
                if game.spanning_area > 1:
                    games_played[0] += 1
                    
                    if "You win!" in root.title():
                        print(f"Game {games_played[0]}: Win! Spanning area: {game.spanning_area}")
                    else:
                        print(f"Game {games_played[0]}: Loss. Spanning area: {game.spanning_area}")
                    
                    if args.game_seed is not None or (num_games and games_played[0] >= num_games):
                        print(f"\nCompleted {games_played[0]} valid game(s). Exiting.")
                        root.destroy()
                        return

                current_game_index[0] += 1
                if game_seeds and current_game_index[0] < len(game_seeds):
                    current_seed_for_game = game_seeds[current_game_index[0]]
                    random.seed(current_seed_for_game)
                    print(f"Starting game {current_game_index[0] + 1} with seed {current_seed_for_game}")
                elif not game_seeds and not args.game_seed:
                    current_seed_for_game = random.randint(0, 2**31 - 1)
                    random.seed(current_seed_for_game)
                    print(f"Starting next game with new seed {current_seed_for_game}")

                game.restart_game()
                game.current_seed = current_seed_for_game
            
            root.after(100, check_time)
        
        root.after(30, game.solve_minesweeper_entropy)
        root.after(100, check_time)
    
    root.mainloop()