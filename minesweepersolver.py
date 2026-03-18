import tkinter as tk
import random
import time
import csv
import os
import argparse
import copy

MASTER_SEED = 42
THRESHOLD = 0.04

class Minesweeper:
    def __init__(self, master, rows=16, cols=30, mines=99, click_delay=0, assist_mode=False):
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
        self.actual_flags = 0
        self.start_time = None
        self.last_move_prob = None
        self.last_move_entropy = None
        self.clicked_mine = None
        self.move_queue = [] 
        self.pre_lethal_state_and_probs = None
        self.current_seed = None 
        self.last_saved_file = None
        self.virtual_flags = set()
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

    def _update_neighbors(self, row, col):
        for rr in range(max(0, row-1), min(self.rows, row+2)):
            for cc in range(max(0, col-1), min(self.cols, col+2)):
                if not self.grid[rr][cc]['mine']:
                    self.grid[rr][cc]['count'] += 1

    def _reveal(self, r, c):
        if self.game_over or self.grid[r][c]['flagged']:
            return
        
        # if self.grid[r][c]['mine']:
        #     grid_copy = copy.deepcopy(self.grid)
        #     probs_before_click = self._get_current_probabilities()
        #     self.pre_lethal_state_and_probs = {
        #         "grid": grid_copy,
        #         "probs": probs_before_click,
        #     }
        
        if not self.assist_mode:
            current_time = time.time()
            if current_time - self.last_click_time < self.click_delay:
                return
            self.last_click_time = current_time
        
        self._reveal_recursive(r, c)
        # REMOVED: The expensive cache cleaning code
        
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
            self.save_game_state("win", self.grid, probs=None)
            self.log_game_result("win")
            # Print will be handled by check_time() before the next game

    def _lose(self):
        if hasattr(self, '_loss_processed'):
            return  # Already processing this loss
        self._loss_processed = True
        
        self.game_over = True
        
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
        
        if self.spanning_area > 1:
            if self.pre_lethal_state_and_probs:
                self.save_game_state(
                    "lose",
                    self.pre_lethal_state_and_probs["grid"],
                    self.pre_lethal_state_and_probs["probs"]
                )
            else:
                final_probs = self._get_current_probabilities()
                self.save_game_state("lose", self.grid, final_probs)
            
            self.log_game_result("lose")
        
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
            
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w') as f:
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
            
            print(f"Game state saved: {filename}", flush=True)  # ADD THIS BACK
            self.last_saved_file = filename
            return filename
        except Exception as e:
            print(f"Failed to save game state: {e}", flush=True)
            self.last_saved_file = None
            return None

    def calculate_and_display_probabilities(self):
        """Calculate probabilities and display them (used in assist mode)"""
        probs = self._get_current_probabilities()
        
        if not probs:
            global_mine_density = self.initial_mines / (self.rows * self.cols)
            for r in range(self.rows):
                for c in range(self.cols):
                    if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged']:
                        probs[(r, c)] = {'p': global_mine_density, 'q': 1 - global_mine_density}
        
        self.display_probabilities(probs)
        return probs

    def _get_current_probabilities(self):
        """Calculate probabilities for ALL unrevealed cells using global constraints"""
        
        # Collect ALL unrevealed cells
        unrevealed_cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged']:
                    unrevealed_cells.append((r, c))
        
        if not unrevealed_cells:
            return {}
        
        total_virtual_flags = len(self.virtual_flags)
        remaining_mines = self.initial_mines - self.actual_flags - total_virtual_flags
        
        # Count only non-virtual cells for density calculation
        non_virtual_cells_list = [c for c in unrevealed_cells if c not in self.virtual_flags]
        non_virtual_count = len(non_virtual_cells_list)
        global_mine_density = remaining_mines / non_virtual_count if non_virtual_count > 0 else 0
        
        # WARM START: Use cached probabilities or initialize
        probs = {}
        for (r, c) in unrevealed_cells:
            if (r, c) in self.virtual_flags:
                # Virtual flags: p=1.0, locked (but NOT in constraints as unknown)
                probs[(r, c)] = {'p': 1.0, 'q': 0.0, 'locked': True}
            elif hasattr(self, '_cached_probs') and (r, c) in self._cached_probs:
                # WARM START: Use previous probability
                cached = self._cached_probs[(r, c)]
                if 'locked' in cached and cached['locked']:
                    probs[(r, c)] = cached.copy()
                else:
                    probs[(r, c)] = {'p': cached['p'], 'q': cached['q'], 'locked': False}
            else:
                # New cell: initialize with global density
                probs[(r, c)] = {'p': global_mine_density, 'q': 1 - global_mine_density, 'locked': False}
        
        # Build constraints from ALL revealed cells
        # CRITICAL: Virtual flags are counted as known mines, NOT in unknown list
        # FIXED: Properly handle board boundaries - cells outside board cannot be mines
        constraints = []
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if cell['revealed'] and not cell['mine']:
                    unknown = []
                    known_mines = 0  # Actual flags + virtual flags
                    
                    # Check all 8 potential neighbors
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            if dr == 0 and dc == 0:
                                continue
                            
                            nr, nc = r + dr, c + dc
                            
                            # FIXED: Outside board = no mine (skip entirely, don't count)
                            # This is the key fix - we simply skip out-of-bounds cells
                            if nr < 0 or nr >= self.rows or nc < 0 or nc >= self.cols:
                                continue
                            
                            # Count actual flags AND virtual flags as known mines
                            if self.grid[nr][nc]['flagged'] or (nr, nc) in self.virtual_flags:
                                known_mines += 1
                            elif not self.grid[nr][nc]['revealed']:
                                # ONLY include non-virtual unrevealed cells in unknown
                                unknown.append((nr, nc))
                    
                    # Now the constraint correctly accounts for board boundaries:
                    # - cell['count'] is the total mines in neighbors
                    # - known_mines are the flags we've placed
                    # - unknown are the cells we don't know about
                    # - Cells outside the board are not counted anywhere (correct!)
                    if unknown:
                        remaining_mines_here = cell['count'] - known_mines
                        constraints.append({
                            'cells': unknown, 
                            'remaining': remaining_mines_here
                        })
        
        # PRE-PROCESSING: Apply trivial constraints
        changed = True
        max_preprocess_rounds = 10
        for round_num in range(max_preprocess_rounds):
            if not changed:
                break
            changed = False
            
            for con in constraints:
                cells = con['cells']
                rem = con['remaining']
                
                # Only process unlocked cells (virtual flags not in this list anymore)
                unlocked_cells = [c for c in cells if c in probs and not probs[c].get('locked', False)]
                
                if not unlocked_cells:
                    continue
                
                eps = 1e-9
                
                # If remaining == number of unlocked cells, all must be mines
                if abs(rem - len(unlocked_cells)) < eps:
                    for cell in unlocked_cells:
                        if probs[cell]['p'] < 1.0 - eps:
                            probs[cell] = {'p': 1.0, 'q': 0.0, 'locked': False}
                            changed = True
                
                # If remaining == 0, all must be safe
                elif rem < eps and rem > -eps:
                    for cell in unlocked_cells:
                        if probs[cell]['p'] > eps:
                            probs[cell] = {'p': 0.0, 'q': 1.0, 'locked': False}
                            changed = True
        
        # Global constraint only on non-locked cells
        non_locked_cells = [c for c in probs.keys() if not probs[c].get('locked', False)]
        if non_locked_cells and remaining_mines >= 0:
            constraints.append({'cells': non_locked_cells, 'remaining': remaining_mines})
        
        if not constraints:
            self._cached_probs = probs
            return probs
        
        # Iterative solving
        max_iter, threshold = 100, 0.01
        for iteration in range(max_iter):
            max_change = 0
            
            for con in constraints:
                cells, rem = con['cells'], con['remaining']
                valid_cells = [cell for cell in cells if cell in probs and not probs[cell].get('locked', False)]
                if not valid_cells: 
                    continue
                
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
            
            # Normalize
            for cell in probs:
                if probs[cell].get('locked', False):
                    continue
                p_val, q_val = probs[cell]['p'], probs[cell]['q']
                total = p_val + q_val
                if total > 1e-10:
                    new_p, new_q = p_val / total, q_val / total
                    max_change = max(max_change, abs(new_p - p_val), abs(new_q - q_val))
                    probs[cell]['p'], probs[cell]['q'] = new_p, new_q
            
            if max_change < threshold: 
                break
        
        # After convergence, detect NEW virtual flags
        VIRTUAL_FLAG_THRESHOLD = 0.999
        new_virtual_flags = []
        for (r, c), vals in probs.items():
            if not vals.get('locked', False) and vals['p'] >= VIRTUAL_FLAG_THRESHOLD:
                new_virtual_flags.append((r, c))
        
        # If we found new virtual flags, add them and RE-ITERATE
        if new_virtual_flags:
            for cell in new_virtual_flags:
                self.virtual_flags.add(cell)
                if cell in probs:
                    probs[cell] = {'p': 1.0, 'q': 0.0, 'locked': True}
            
            self._cached_probs = probs
            return self._get_current_probabilities()
        
        # Cache for next call
        self._cached_probs = probs
        return probs

    def solve_minesweeper_entropy(self):
        if self.game_over:
            return

        try:
            # Priority 1: If there are moves in the queue, execute the next one.
            if self.move_queue:
                action, (r, c), prob = self.move_queue.pop(0)

                if action == 'reveal' and not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged']:
                    # SAVE GAME STATE BEFORE REVEALING (for potential loss)
                    if self.grid[r][c]['mine']:
                        grid_copy = copy.deepcopy(self.grid)
                        # Use the CACHED probabilities from when we made the decision
                        if hasattr(self, '_last_calculated_probs'):
                            self.pre_lethal_state_and_probs = {
                                "grid": grid_copy,
                                "probs": self._last_calculated_probs,
                            }
                    
                    self.last_move_prob = prob
                    self.last_move_entropy = min(prob, 1 - prob)
                    self._reveal(r, c)
                    
                    # CRITICAL: After revealing, check if global mine density changed significantly
                    if not self.game_over and hasattr(self, '_queue_global_density'):
                        # Calculate current global density
                        total_virtual_flags = len(self.virtual_flags)
                        remaining_mines = self.initial_mines - self.actual_flags - total_virtual_flags
                        
                        # Count unrevealed non-virtual cells
                        unrevealed_count = 0
                        for r in range(self.rows):
                            for c in range(self.cols):
                                if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged'] and (r, c) not in self.virtual_flags:
                                    unrevealed_count += 1
                        
                        current_density = remaining_mines / unrevealed_count if unrevealed_count > 0 else 0
                        
                        # If density increased significantly, recalculate
                        if current_density > self._queue_global_density * 1.1:  # 10% increase
                            # print(f"DEBUG: Global density increased from {self._queue_global_density:.4f} to {current_density:.4f}, clearing queue", flush=True)
                            self.move_queue.clear()
                            if hasattr(self, '_queue_global_density'):
                                delattr(self, '_queue_global_density')
            
            # Priority 2: If the queue is empty, calculate probabilities and repopulate it.
            else:
                if self.spanning_area == 0:
                    self.last_move_prob = self.initial_mines / (self.rows * self.cols)
                    self.last_move_entropy = min(self.last_move_prob, 1 - self.last_move_prob)
                    self._reveal(0, 0)
                else:
                    old_virtual_count = len(self.virtual_flags)
                    
                    probs = self._get_current_probabilities()
                    
                    # CACHE the probabilities for potential loss state saving
                    self._last_calculated_probs = probs.copy() if probs else {}
                    
                    if len(self.virtual_flags) > old_virtual_count:
                        self.move_queue.clear()
                        if hasattr(self, '_queue_global_density'):
                            delattr(self, '_queue_global_density')
                        if not self.game_over:
                            self.master.after(10, self.solve_minesweeper_entropy)
                        return
                                    
                    if not probs:
                        if not self.game_over:
                            print(f"WARNING: No probabilities calculated, but game not over. Forcing loss.", flush=True)
                            self.game_over = True
                        return
                    
                    self.display_probabilities(probs)

                    # Calculate global mine density
                    total_virtual_flags = len(self.virtual_flags)
                    remaining_mines = self.initial_mines - self.actual_flags - total_virtual_flags
                    
                    unrevealed_count = 0
                    for r in range(self.rows):
                        for c in range(self.cols):
                            if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged'] and (r, c) not in self.virtual_flags:
                                unrevealed_count += 1
                    
                    global_density = remaining_mines / unrevealed_count if unrevealed_count > 0 else 0
                    
                    certain_safe_cells = []
                    uncertain_cells = []

                    CERTAIN_SAFE_THRESHOLD = THRESHOLD

                    for (r, c), vals in probs.items():
                        prob = vals['p']
                        
                        if (r, c) in self.virtual_flags:
                            continue
                        
                        if prob < CERTAIN_SAFE_THRESHOLD:
                            certain_safe_cells.append(((r, c), prob))
                        elif prob < 0.96:
                            uncertain_cells.append((prob, (r, c)))

                    # SIMPLIFIED BATCHING: Queue all safe cells (prob < THRESHOLD)
                    # The density check will protect us from stale probabilities
                    if certain_safe_cells:
                        self.move_queue = [('reveal', coords, prob) for coords, prob in certain_safe_cells]
                        self._queue_global_density = global_density
                        # print(f"DEBUG: Batching {len(certain_safe_cells)} moves with prob < {CERTAIN_SAFE_THRESHOLD:.4f} (global density: {global_density:.4f})", flush=True)
                            
                    elif uncertain_cells:
                        prob, coords = min(uncertain_cells)
                        self.move_queue.append(('reveal', coords, prob))
                        if hasattr(self, '_queue_global_density'):
                            delattr(self, '_queue_global_density')
                    else:
                        if not self.game_over:
                            if self.non_mines == 0:
                                self._check_win()
                            else:
                                self.game_over = True
                        return

                    if self.move_queue:
                        self.solve_minesweeper_entropy()
                        return

        except Exception as e:
            print(f"ERROR in solve_minesweeper_entropy: {e}", flush=True)
            import traceback
            traceback.print_exc()
            if not self.game_over:
                self.game_over = True
            return

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
        self.virtual_flags = set()
        self.start_time = None  # Will be reset in _init_game
        self.last_move_prob = None
        self.last_move_entropy = None
        self.clicked_mine = None
        self.move_queue = []
        self.pre_lethal_state_and_probs = None
        self.last_saved_file = None
        if hasattr(self, '_cached_probs'):
            delattr(self, '_cached_probs')
        if hasattr(self, '_restart_scheduled'):
            delattr(self, '_restart_scheduled')
        if hasattr(self, '_loss_processed'):
            delattr(self, '_loss_processed')
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
                if prob < THRESHOLD: 
                    color = '#5b8c5a'
                elif prob > 1 - THRESHOLD: 
                    color = '#ff6361'
                else: 
                    color = 'white'
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
                writer.writerow(["Outcome", "Spanning Area", "Rows", "Cols", "Mines", 
                            "Flags Placed", "Mode", "Duration (s)", "Last Move Prob", 
                            "Last Move Entropy", "Game Seed", "State File"])
            
            mode = "Assist" if self.assist_mode else "Auto"
            
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
    parser.add_argument('-r', '--rows', type=int, default=16, help='Number of rows (default: 16)')
    parser.add_argument('-c', '--cols', type=int, default=30, help='Number of columns (default: 30)')
    parser.add_argument('-m', '--mines', type=int, default=99, help='Number of mines (default: 99)')
    parser.add_argument('--seed', type=int, default=MASTER_SEED, help=f'Master random seed (default: {MASTER_SEED})')
    parser.add_argument('--game-seed', type=int, default=None, 
                       help='Specific game seed to use (overrides -n and --seed)')
    
    args = parser.parse_args()

    if args.game_seed is not None:
        random.seed(args.game_seed)
        game_seeds = None
        num_games = 1
        current_seed_for_game = args.game_seed
        print(f"Running single game with seed {args.game_seed}")
    else:
        random.seed(args.seed)
        if args.num_games:
            # Generate 1.5x seeds as buffer
            cache_size = int(args.num_games * 1.5)
            game_seeds = [random.randint(0, 2**31 - 1) for _ in range(cache_size)]
            print(f"Auto mode: Playing {args.num_games} games with master seed {args.seed}")
            print(f"  Generated {cache_size} seed cache (1.5x buffer)")
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
            if game.game_over:
                # Add a small delay to ensure all UI updates are complete
                if hasattr(game, '_restart_scheduled'):
                    # Already scheduled, but still need to keep checking
                    root.after(100, check_time)
                    return
                
                game._restart_scheduled = True
                
                # Increment total game counter
                current_game_index[0] += 1
                
                # Only print and count games with spanning_area > 1
                if game.spanning_area > 1:
                    games_played[0] += 1
                    
                    # Print game result
                    if "You win!" in root.title():
                        print(f"Game {games_played[0]}: Win! Spanning area: {game.spanning_area}", flush=True)
                    else:
                        print(f"Game {games_played[0]}: Loss. Spanning area: {game.spanning_area}", flush=True)
                    
                    # Check if we should exit
                    if args.game_seed is not None or (num_games and games_played[0] >= num_games):
                        print(f"\nCompleted {games_played[0]} valid game(s) out of {current_game_index[0]} total games. Exiting.", flush=True)
                        root.destroy()
                        return
                
                # Get next seed for the next game
                if game_seeds and current_game_index[0] < len(game_seeds):
                    new_seed = game_seeds[current_game_index[0]]
                    random.seed(new_seed)
                    game.current_seed = new_seed
                elif not game_seeds and not args.game_seed:
                    new_seed = random.randint(0, 2**31 - 1)
                    random.seed(new_seed)
                    game.current_seed = new_seed

                # Schedule restart after a small delay
                def do_restart():
                    game.restart_game()
                    # Schedule check_time to resume after restart
                    root.after(100, check_time)
                
                root.after(50, do_restart)
                return  # Don't schedule check_time here - do_restart will handle it
            else:
                # Game is still running - check for timeout
                if hasattr(game, 'start_time') and game.start_time:
                    elapsed = time.time() - game.start_time
                    if elapsed > 300:  # 5 minute timeout
                        print(f"WARNING: Game timeout after {elapsed:.1f}s. Forcing loss.", flush=True)
                        game.game_over = True
                        # Will be handled on next check_time call
                
                # Continue checking
                root.after(100, check_time)
        
        root.after(30, game.solve_minesweeper_entropy)
        root.after(100, check_time)
    
    root.mainloop()