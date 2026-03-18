import os
import glob
from PIL import Image, ImageDraw, ImageFont

def render_game_state(filename):
    """Render a saved game state to PNG"""
    try:
        # Read the file
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        # Parse metadata
        outcome = lines[0].split(': ')[1].strip()
        spanning_area = int(lines[1].split(': ')[1].strip())
        
        # Handle different line formats for dimensions
        dims_line = lines[2]
        if 'Rows:' in dims_line:
             parts = dims_line.strip().split(', ')
             rows = int(parts[0].split(': ')[1])
             cols = int(parts[1].split(': ')[1])
             mines = int(parts[2].split(': ')[1])
        else: # Legacy format support
            parts = dims_line.split()
            rows, cols, mines = int(parts[1]), int(parts[3]), int(parts[5])

        clicked_mine_str = lines[3].split(': ')[1].strip()
        clicked_mine = eval(clicked_mine_str) if clicked_mine_str != 'None' else None
        
        # Parse grid
        grid_lines = [l for l in lines if ',' in l and len(l.split(',')) >= 6]
        grid = [[None for _ in range(cols)] for _ in range(rows)]
        
        for line in grid_lines:
            parts = line.strip().split(',')
            r, c = int(parts[0]), int(parts[1])
            prob = float(parts[6]) if len(parts) > 6 else -1.0
            grid[r][c] = {
                'mine': bool(int(parts[2])),
                'revealed': bool(int(parts[3])),
                'flagged': bool(int(parts[4])),
                'count': int(parts[5]),
                'prob': prob
            }
        
        # Create image
        cell_size = 30
        img_width = cols * cell_size
        img_height = rows * cell_size + 75  # Extra space for new legend line
        
        img = Image.new('RGB', (img_width, img_height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Load fonts
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            small_font = ImageFont.truetype("arial.ttf", 9)
            emoji_font = ImageFont.truetype("seguiemj.ttf", 16)
        except IOError:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
            emoji_font = ImageFont.load_default()
        
        colors = {
            1: 'blue', 2: 'green', 3: 'red', 4: 'darkblue',
            5: 'brown', 6: 'cyan', 7: 'black', 8: 'gray'
        }
        
        mine_emoji = '💣'
        flag_emoji = '🚩'
        
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] is None:
                    continue
                
                cell = grid[r][c]
                x0, y0 = c * cell_size, r * cell_size
                x1, y1 = x0 + cell_size, y0 + cell_size
                
                bg = 'lightgray'
                
                if cell['revealed'] and not cell['mine']:
                    bg = 'white'
                # For losses, the clicked mine has a red background
                elif outcome == 'lose' and clicked_mine and (r, c) == clicked_mine:
                    bg = 'red'
                # An incorrectly placed flag (flag on a non-mine) also gets a red background
                elif cell['flagged'] and not cell['mine']:
                    bg = 'red'
                
                draw.rectangle([x0, y0, x1, y1], fill=bg, outline='darkgray', width=1)
                
                # --- MODIFICATION START ---
                # Re-ordered and prioritized logic for drawing cell content.

                # 1. SPECIAL CASE: The incorrectly clicked mine. Show its probability.
                if outcome == 'lose' and clicked_mine and (r, c) == clicked_mine:
                    if cell['prob'] >= 0:
                        prob_text = f"{cell['prob']:.2f}"
                        # Use a bold, clear color against the red background
                        bbox = draw.textbbox((0, 0), prob_text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                        text_x = x0 + (cell_size - text_width) // 2
                        text_y = y0 + (cell_size - text_height) // 2
                        draw.text((text_x, text_y), prob_text, fill='white', font=font)
                    # Also draw the mine emoji subtly or not at all, the probability is key.
                    # Here we are prioritizing the probability text.

                # 2. Revealed safe cells
                elif cell['revealed'] and not cell['mine']:
                    if cell['count'] > 0:
                        text = str(cell['count'])
                        color = colors.get(cell['count'], 'black')
                        bbox = draw.textbbox((0, 0), text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                        text_x = x0 + (cell_size - text_width) // 2
                        text_y = y0 + (cell_size - text_height) // 2
                        draw.text((text_x, text_y), text, fill=color, font=font)

                # 3. All other mines (not the one that was clicked)
                elif cell['mine']:
                    bbox = draw.textbbox((0, 0), mine_emoji, font=emoji_font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x0 + (cell_size - text_width) // 2
                    text_y = y0 + (cell_size - text_height) // 2
                    draw.text((text_x, text_y), mine_emoji, fill='black', font=emoji_font)
                
                # 4. Incorrectly flagged cells
                elif cell['flagged'] and not cell['mine']:
                    bbox = draw.textbbox((0, 0), flag_emoji, font=emoji_font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x0 + (cell_size - text_width) // 2
                    text_y = y0 + (cell_size - text_height) // 2
                    draw.text((text_x, text_y), flag_emoji, fill='black', font=emoji_font)
                
                # 5. Other unrevealed cells with probability info
                elif not cell['revealed'] and not cell['flagged'] and cell['prob'] >= 0:
                    prob_text = f"{cell['prob']:.2f}"
                    bbox = draw.textbbox((0, 0), prob_text, font=small_font)
                    text_width = bbox[2] - bbox[0]
                    text_x = x0 + (cell_size - text_width) // 2
                    text_y = y0 + cell_size - 11 # Position at bottom
                    draw.text((text_x, text_y), prob_text, fill='darkblue', font=small_font)
                
                # --- MODIFICATION END ---
        
        # Add legend
        legend_y = rows * cell_size + 5
        legend_font = ImageFont.truetype("arial.ttf", 11) if 'font' in locals() else ImageFont.load_default()
            
        draw.text((5, legend_y), f"{outcome.upper()} | Span: {spanning_area}", fill='black', font=legend_font)
        # --- MODIFIED LEGEND ---
        draw.text((5, legend_y + 15), "Red BG = Mistake (clicked mine or wrong flag)", fill='red', font=small_font)
        draw.text((5, legend_y + 28), f"White number on red = Probability of fatal click", fill='black', font=small_font)
        draw.text((5, legend_y + 41), f"Gray BG + {mine_emoji} = Other mine locations", fill='black', font=small_font)
        draw.text((5, legend_y + 54), "Blue numbers = Prob. of other unrevealed cells", fill='darkblue', font=small_font)
        
        # Save image
        img_filename = filename.replace('.txt', '.png')
        img.save(img_filename)
        print(f"Rendered: {img_filename}")
        
    except Exception as e:
        print(f"Failed to render {filename}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # Find all .txt files in screenshots folder
    if not os.path.exists('screenshots'):
        os.makedirs('screenshots')
        print("Created screenshots folder. No files to render yet.")
    else:
        txt_files = glob.glob('screenshots/*.txt')
        
        if not txt_files:
            print("No .txt game states found in screenshots folder to render.")
        else:
            print(f"Found {len(txt_files)} game states to render")
            for txt_file in txt_files:
                render_game_state(txt_file)
            print("Done!")