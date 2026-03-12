import tkinter as tk
import random
import time
import csv
import os

class Minesweeper:
    def __init__(self, master, rows=16, cols=30, mines=99, click_delay=0.05, label=""):
        self.master = master
        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.non_mines = rows * cols - mines
        self.click_delay = click_delay
        self.grid = []
        self.buttons = []
        self.game_over = False
        self.last_click_time = 0
        self.colors = {
            1: 'blue', 2: 'green', 3: 'red', 4: 'darkblue',
            5: 'brown', 6: 'cyan', 7: 'black', 8: 'gray'
        }
        self.flag_emoji = "\u2691"
        self.mine_emoji = "\U0001F4A3"
        self.spanning_area = 0
        self.label = label
        self._init_game()

    def _init_game(self):
        self._create_grid()
        self._create_buttons()
        self._place_mines()
        self.master.title("Minesweeper Automatic Solver Running...")

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
                btn.grid(row=r, column=c, padx=1, pady=1)
                row_btns.append(btn)
            self.buttons.append(row_btns)

    def _place_mines(self):
        # More efficient mine placement
        positions = random.sample(range(self.rows * self.cols), self.mines)
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
        current_time = time.time()
        if current_time - self.last_click_time < self.click_delay:
            return
        self.last_click_time = current_time
        self._reveal_recursive(r, c)
        self.master.update_idletasks()  # Force update for stability

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
        current_time = time.time()
        if current_time - self.last_click_time < self.click_delay:
            return
        self.last_click_time = current_time
        self.grid[r][c]['flagged'] = not self.grid[r][c]['flagged']
        self.buttons[r][c].config(
            text=self.flag_emoji if self.grid[r][c]['flagged'] else '', 
            fg='red', 
            width=2, 
            height=1, 
            font=('Arial', 10, 'bold')
        )
        if self.grid[r][c]['flagged']:
            self.mines -= 1
        else:
            self.mines += 1
        self.master.update_idletasks()  # Force update for stability

    def _check_win(self):
        if self.non_mines == 0:
            self.game_over = True
            for r in range(self.rows):
                for c in range(self.cols):
                    btn = self.buttons[r][c]
                    if self.grid[r][c]['mine']:
                        btn.config(
                            text=self.mine_emoji, 
                            fg='black', 
                            bg='red', 
                            width=2, 
                            height=1, 
                            font=('Arial', 10, 'bold')
                        )
            self.master.title("You win!")
            self.log_game_result("win")

    def _lose(self):
        self.game_over = True
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c]['mine']:
                    self.buttons[r][c].config(
                        text=self.mine_emoji, 
                        fg='black', 
                        bg='red', 
                        width=2, 
                        height=1, 
                        font=('Arial', 10, 'bold')
                    )
        self.master.title("Game Over")
        self.log_game_result("lose")

    def solve_minesweeper_entropy(self):
        if self.game_over:
            return

        # Step 1: Check for trivial safe/mine cells FIRST (strategic improvement)
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
                    
                    # All unknown neighbors are mines
                    if unknown and remaining == len(unknown):
                        trivial_mines.extend(unknown)
                    # All unknown neighbors are safe
                    elif unknown and remaining == 0:
                        trivial_safe.extend(unknown)
        
        # Remove duplicates
        trivial_safe = list(set(trivial_safe))
        trivial_mines = list(set(trivial_mines))
        
        # Execute trivial moves first (STRATEGIC)
        if trivial_safe:
            for r, c in trivial_safe:
                if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged']:
                    self._reveal(r, c)
                    self.master.after(50, self.solve_minesweeper_entropy)
                    return
        
        if trivial_mines:
            for r, c in trivial_mines:
                if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged']:
                    self._flag(r, c)
                    self.master.after(50, self.solve_minesweeper_entropy)
                    return

        # Step 2: Build probability model for non-trivial cases
        global_mine_density = self.mines / (self.rows * self.cols)
        probs = {}
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if not cell['revealed'] and not cell['flagged']:
                    probs[(r, c)] = {'p': global_mine_density, 'q': 1 - global_mine_density}

        # Gather constraints
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
        
        if not constraints:
            # No constraints; choose a cell (prefer corners/edges for opening)
            if probs:
                # Try corners first, then edges, then center
                for r, c in [(0, 0), (0, self.cols-1), (self.rows-1, 0), (self.rows-1, self.cols-1)]:
                    if (r, c) in probs:
                        self._reveal(r, c)
                        self.master.after(50, self.solve_minesweeper_entropy)
                        return
                # Otherwise take first available
                pos = list(probs.keys())[0]
                self._reveal(pos[0], pos[1])
            self.master.after(50, self.solve_minesweeper_entropy)
            return

        # Step 3: Iterative probability refinement (OPTIMIZED)
        max_iter = 100
        threshold = 0.001
        for iteration in range(max_iter):
            max_change = 0
            for con in constraints:
                cells = con['cells']
                rem = con['remaining']
                
                # Only process cells that still exist in probs
                valid_cells = [cell for cell in cells if cell in probs]
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
                p_val = probs[cell]['p']
                q_val = probs[cell]['q']
                total = p_val + q_val
                if total > 1e-10:
                    new_p = p_val / total
                    new_q = q_val / total
                    max_change = max(max_change, abs(new_p - p_val), abs(new_q - q_val))
                    probs[cell]['p'] = new_p
                    probs[cell]['q'] = new_q
            
            if max_change < threshold:
                break

        # Step 4: Strategic decision making
        move_made = False
        safe_move = None
        flagged_move = None
        min_prob = 1.1
        
        # STRATEGIC: Prioritize cells with extreme probabilities
        for (r, c), vals in probs.items():
            prob = vals['p']
            
            # Very safe - click immediately
            if prob < 0.1:
                safe_move = (r, c)
                break
            # Very likely mine - flag immediately  
            if prob > 0.9:
                flagged_move = (r, c)
                break
            # Track safest cell above baseline
            if global_mine_density < prob < min_prob:
                min_prob = prob
                safe_move = (r, c)
        
        if safe_move:
            self._reveal(safe_move[0], safe_move[1])
            move_made = True
        elif flagged_move:
            self._flag(flagged_move[0], flagged_move[1])
            move_made = True

        # Display probabilities (throttled for performance)
        if iteration % 3 == 0:  # Only update every 3rd iteration
            self.display_probabilities(probs)

        if move_made and not self.game_over:
            self.master.after(50, self.solve_minesweeper_entropy)

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
        self.mines = 99
        self.non_mines = self.rows * self.cols - self.mines
        self.spanning_area = 0
        for widget in self.master.winfo_children():
            widget.destroy()
        self._init_game()
        self.master.after(0, self.solve_minesweeper_entropy)

    def display_probabilities(self, probs):
        for (r, c), vals in probs.items():
            prob = vals['p']
            if not self.grid[r][c]['revealed'] and not self.grid[r][c]['flagged']:
                self.buttons[r][c].config(
                    text=f'{prob:.1f}',
                    fg='white',
                    font=('Arial', 10, 'bold'),
                    width=2,
                    height=1
                )

    def log_game_result(self, outcome):
        log_file = "minesweeper_log.csv"
        file_exists = os.path.isfile(log_file)
        with open(log_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Outcome", "Spanning Area", "Label", "Rows", "Cols", "Mines"])
            writer.writerow([outcome, self.spanning_area, self.label, self.rows, self.cols, self.mines])

if __name__ == '__main__':
    root = tk.Tk()
    label = "demo"
    game = Minesweeper(root, rows=16, cols=30, mines=99, click_delay=0.01, label=label)
    timelimit = 600
    start_time = time.time()

    def check_time():
        if time.time() - start_time > timelimit:
            root.destroy()
        elif game.game_over:
            if "You win!" in root.title():
                print("You win!")
                root.destroy()
            else:
                game.restart_game()
        root.after(100, check_time)

    root.after(30, game.solve_minesweeper_entropy)
    root.after(100, check_time)
    root.mainloop()