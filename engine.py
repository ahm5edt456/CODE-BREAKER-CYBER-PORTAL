"""CODE BREAKER: Programming Maze (V3 polished 13x9 edition)."""
import random
import sys
import pygame
from mazegenerator import MazeGenerator
from questions import pick_questions, check_answer

pygame.init()
WIDTH, HEIGHT = 1280, 720
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('CODE BREAKER | Programming Maze')
CLOCK = pygame.time.Clock()
FPS = 60

SIZE = (13, 9)          # Match the reference image: 13 columns x 9 rows
CELL = 48
GAP = 2
BOARD_W = SIZE[0] * CELL
BOARD_H = SIZE[1] * CELL
OX, OY = 42, 132

BG = (8, 15, 28)
BG2 = (13, 24, 41)
PANEL = (18, 31, 51)
PANEL_2 = (22, 39, 63)
FLOOR_A = (19, 38, 63)
FLOOR_B = (22, 44, 72)
WALL = (56, 82, 120)
WALL_INNER = (78, 110, 152)
GRID_OUTLINE = (6, 13, 24)
WHITE = (232, 242, 253)
MUTED = (154, 178, 204)
CYAN = (64, 219, 232)
CYAN_SOFT = (116, 236, 245)
GREEN = (84, 225, 138)
RED = (255, 101, 132)
RED_SOFT = (255, 138, 158)
YELLOW = (247, 201, 96)
SHADOW = (0, 0, 0, 85)

FONT = pygame.font.SysFont('dejavusans', 23)
SMALL = pygame.font.SysFont('dejavusans', 18)
TINY = pygame.font.SysFont('dejavusans', 15)
MONO = pygame.font.SysFont('dejavusansmono', 19)
BIG = pygame.font.SysFont('dejavusans', 44, bold=True)
TITLE = pygame.font.SysFont('dejavusans', 30, bold=True)
MOVES = {(0, -1): 1, (1, 0): 2, (0, 1): 4, (-1, 0): 8}
LETTERS = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}


def text(value, x, y, color=WHITE, font=FONT):
    SCREEN.blit(font.render(str(value), True, color), (x, y))


def centered(value, y, color=WHITE, font=FONT):
    image = font.render(value, True, color)
    SCREEN.blit(image, image.get_rect(center=(WIDTH // 2, y)))


def edge_key(a, b):
    return tuple(sorted((a, b)))


def shadow_rect(rect, radius=14, offset=4):
    surf = pygame.Surface((rect.w + offset * 2, rect.h + offset * 2), pygame.SRCALPHA)
    pygame.draw.rect(surf, SHADOW, (offset, offset, rect.w, rect.h), border_radius=radius)
    SCREEN.blit(surf, (rect.x - offset, rect.y - offset))


def pill(x, y, w, h, color, label, label_color=(255, 255, 255)):
    rect = pygame.Rect(x, y, w, h)
    shadow_rect(rect, radius=12, offset=3)
    pygame.draw.rect(SCREEN, color, rect, border_radius=12)
    img = SMALL.render(label, True, label_color)
    SCREEN.blit(img, img.get_rect(center=rect.center))


def make_gates(path, count):
    edges = []
    pos = (0, 0)
    for letter in path:
        dx, dy = LETTERS[letter]
        next_pos = (pos[0] + dx, pos[1] + dy)
        edges.append(edge_key(pos, next_pos))
        pos = next_pos
    if len(edges) < count + 2:
        raise ValueError('Generated path is too short for requested doors')
    indexes = [max(1, min(len(edges) - 2, round((i + 1) * (len(edges) - 1) / (count + 1))))
               for i in range(count)]
    if len(set(indexes)) != count:
        raise ValueError('Not enough unique gate positions')
    return [edges[i] for i in indexes]


class Game:
    def __init__(self):
        self.mode = 'menu'
        self.language = 'Python'
        self.level = 0
        self.lives = 3
        self.remaining = 240.0
        self.maze = None
        self.player = (0, 0)
        self.gates = {}
        self.active_gate = None
        self.lines = []
        self.line = 0
        self.col = 0
        self.view_top = 0
        self.message = ''
        self.message_time = 0
        self.move_wait = 0
        self.score = 0
        self.seed = None
        self.player_pulse = 0.0

    def notify(self, message):
        self.message = message
        self.message_time = 3.7

    def start_level(self):
        self.lives = 3
        self.remaining = [240, 300, 360][self.level]
        self.player = (0, 0)
        self.move_wait = 0
        self.seed = random.randrange(1, 2_000_000_000)
        count = 2 if getattr(self, "sprint", False) else [2, 3, 4][self.level]
        min_path = [10, 16, 22][self.level]
        for _ in range(300):
            self.maze = MazeGenerator(size=SIZE, perfect=True, seed=self.seed)
            path = self.maze.shortest_path
            if path and len(path) >= min_path and (not getattr(self, "sprint", False) or 20 <= len(path) <= 34):
                break
            self.seed += 1
        else:
            raise RuntimeError('Could not generate a long enough maze path for the chosen size')
        edges = make_gates(path, count)
        questions = pick_questions(self.language, getattr(self, "difficulty", self.level), count)
        self.gates = {edge: {'question': q, 'open': False, 'id': i + 1}
                      for i, (edge, q) in enumerate(zip(edges, questions))}
        self.active_gate = None
        self.mode = 'maze'
        self.notify(f'Level {self.level + 1}: solve {count} code gates and reach the exit')

    def nearby_gate(self):
        x, y = self.player
        for dx, dy in MOVES:
            candidate = edge_key((x, y), (x + dx, y + dy))
            if candidate in self.gates and not self.gates[candidate]['open']:
                return candidate
        return None

    def open_editor(self, gate):
        self.active_gate = gate
        self.lines = self.gates[gate]['question']['code'].split('\n')
        self.line = 0
        self.col = len(self.lines[0])
        self.view_top = 0
        self.mode = 'editor'
        self.notify('Run / F5 is free. Submit / F6 checks your solution.')
        pygame.key.start_text_input()

    def close_editor(self):
        pygame.key.stop_text_input()
        self.mode = 'maze'
        self.active_gate = None

    def run_code(self):
        q = self.gates[self.active_gate]['question']
        if check_answer('\n'.join(self.lines), q):
            self.gates[self.active_gate]['open'] = True
            self.score += 100
            self.close_editor()
            self.notify('ACCESS GRANTED! Gate opened. +100 points')
        else:
            self.lives -= 1
            if not self.lives:
                self.close_editor()
                self.mode = 'lost'
            else:
                self.notify(f'Incorrect fix! {self.lives} lives remaining.')

    def edit(self, ev):
        if ev.type == pygame.TEXTINPUT:
            for character in ev.text:
                if character in '\r\n':
                    continue
                current = self.lines[self.line]
                self.lines[self.line] = current[:self.col] + character + current[self.col:]
                self.col += len(character)
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        if k == pygame.K_ESCAPE:
            self.close_editor()
        elif k == pygame.K_F5:
            self.run_code()
        elif k == pygame.K_F1:
            self.notify('HINT: ' + self.gates[self.active_gate]['question']['hint'])
        elif k == pygame.K_r and ev.mod & pygame.KMOD_CTRL:
            self.lines = self.gates[self.active_gate]['question']['code'].split('\n')
            self.line = self.col = self.view_top = 0
        elif k == pygame.K_BACKSPACE:
            if self.col:
                row = self.lines[self.line]
                self.lines[self.line] = row[:self.col - 1] + row[self.col:]
                self.col -= 1
            elif self.line:
                tail = self.lines.pop(self.line)
                self.line -= 1
                self.col = len(self.lines[self.line])
                self.lines[self.line] += tail
        elif k == pygame.K_DELETE:
            row = self.lines[self.line]
            if self.col < len(row):
                self.lines[self.line] = row[:self.col] + row[self.col + 1:]
            elif self.line < len(self.lines) - 1:
                self.lines[self.line] += self.lines.pop(self.line + 1)
        elif k == pygame.K_RETURN:
            row = self.lines[self.line]
            self.lines[self.line] = row[:self.col]
            self.lines.insert(self.line + 1, row[self.col:])
            self.line += 1
            self.col = 0
        elif k == pygame.K_TAB:
            row = self.lines[self.line]
            self.lines[self.line] = row[:self.col] + '    ' + row[self.col:]
            self.col += 4
        elif k == pygame.K_LEFT:
            if self.col:
                self.col -= 1
            elif self.line:
                self.line -= 1
                self.col = len(self.lines[self.line])
        elif k == pygame.K_RIGHT:
            if self.col < len(self.lines[self.line]):
                self.col += 1
            elif self.line < len(self.lines) - 1:
                self.line += 1
                self.col = 0
        elif k == pygame.K_UP:
            self.line = max(0, self.line - 1)
            self.col = min(self.col, len(self.lines[self.line]))
        elif k == pygame.K_DOWN:
            self.line = min(len(self.lines) - 1, self.line + 1)
            self.col = min(self.col, len(self.lines[self.line]))
        elif k == pygame.K_HOME:
            self.col = 0
        elif k == pygame.K_END:
            self.col = len(self.lines[self.line])
        self.view_top = min(self.view_top, self.line)
        if self.line >= self.view_top + 12:
            self.view_top = self.line - 11

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if self.mode == 'editor':
            self.edit(ev)
            return
        if ev.type != pygame.KEYDOWN:
            return
        if self.mode == 'menu' and ev.key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.language = {pygame.K_1: 'Python', pygame.K_2: 'Java', pygame.K_3: 'C++'}[ev.key]
            self.level = 0
            self.score = 0
            self.start_level()
        elif self.mode == 'maze':
            if ev.key == pygame.K_e:
                gate = self.nearby_gate()
                if gate:
                    self.open_editor(gate)
                else:
                    self.notify('Stand next to a red code gate, then press E.')
            elif ev.key == pygame.K_m:
                self.mode = 'menu'
        elif self.mode in ('lost', 'won'):
            if ev.key == pygame.K_r:
                if self.mode == 'won':
                    self.mode = 'menu'
                else:
                    self.start_level()
            elif ev.key == pygame.K_m:
                self.mode = 'menu'

    def update(self, dt):
        self.message_time = max(0, self.message_time - dt)
        self.player_pulse += dt * 2.5
        if self.mode not in ('maze', 'editor'):
            return
        self.remaining = max(0, self.remaining - dt)
        if self.remaining == 0:
            if self.mode == 'editor':
                pygame.key.stop_text_input()
            self.mode = 'lost'
            return
        if self.mode != 'maze':
            return
        self.move_wait = max(0, self.move_wait - dt)
        if self.move_wait:
            return
        keys = pygame.key.get_pressed()
        dx = dy = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx = -1
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx = 1
        elif keys[pygame.K_w] or keys[pygame.K_UP]:
            dy = -1
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy = 1
        if not (dx or dy):
            return
        self.move_wait = .11
        x, y = self.player
        nx, ny = x + dx, y + dy
        if not (0 <= nx < SIZE[0] and 0 <= ny < SIZE[1]):
            return
        if self.maze.maze[y][x] & MOVES[(dx, dy)]:
            return
        gate = self.gates.get(edge_key((x, y), (nx, ny)))
        if gate and not gate['open']:
            self.notify('LOCKED: press E to debug this door.')
            return
        self.player = (nx, ny)
        if self.player == self.maze.maze_exit and not getattr(self, "return_to_start", False) and not getattr(self, "manual_stage_completion", False):
            if any(not g['open'] for g in self.gates.values()):
                self.notify('Open every debug gate to escape!')
            elif self.level == getattr(self, "sector_count", 3) - 1:
                self.score += int(self.remaining)
                self.mode = 'won'
            else:
                self.score += int(self.remaining)
                self.level += 1
                self.start_level()

    def draw_bg(self):
        for y in range(HEIGHT):
            ratio = y / HEIGHT
            r = int(BG[0] * (1 - ratio) + BG2[0] * ratio)
            g = int(BG[1] * (1 - ratio) + BG2[1] * ratio)
            b = int(BG[2] * (1 - ratio) + BG2[2] * ratio)
            pygame.draw.line(SCREEN, (r, g, b), (0, y), (WIDTH, y))
        for i in range(0, WIDTH, 64):
            pygame.draw.line(SCREEN, (12, 25, 42), (i, 0), (i, HEIGHT), 1)
        for i in range(0, HEIGHT, 64):
            pygame.draw.line(SCREEN, (12, 25, 42), (0, i), (WIDTH, i), 1)

    def draw_maze(self):
        maze = self.maze.maze
        board_rect = pygame.Rect(OX - 10, OY - 10, BOARD_W + 20, BOARD_H + 20)
        shadow_rect(board_rect, radius=18, offset=5)
        pygame.draw.rect(SCREEN, PANEL, board_rect, border_radius=18)
        pygame.draw.rect(SCREEN, PANEL_2, board_rect.inflate(-12, -12), border_radius=15)
        for y, row in enumerate(maze):
            for x, bits in enumerate(row):
                px, py = OX + x * CELL, OY + y * CELL
                tile = pygame.Rect(px + GAP // 2, py + GAP // 2, CELL - GAP, CELL - GAP)
                color = FLOOR_A if (x + y) % 2 == 0 else FLOOR_B
                pygame.draw.rect(SCREEN, color, tile, border_radius=8)
                pygame.draw.rect(SCREEN, GRID_OUTLINE, tile, width=1, border_radius=8)
                if bits & 1:
                    pygame.draw.line(SCREEN, WALL, (px + 4, py + 2), (px + CELL - 4, py + 2), 6)
                    pygame.draw.line(SCREEN, WALL_INNER, (px + 7, py + 4), (px + CELL - 7, py + 4), 2)
                if bits & 2:
                    pygame.draw.line(SCREEN, WALL, (px + CELL - 2, py + 4), (px + CELL - 2, py + CELL - 4), 6)
                    pygame.draw.line(SCREEN, WALL_INNER, (px + CELL - 4, py + 7), (px + CELL - 4, py + CELL - 7), 2)
                if bits & 4:
                    pygame.draw.line(SCREEN, WALL, (px + 4, py + CELL - 2), (px + CELL - 4, py + CELL - 2), 6)
                    pygame.draw.line(SCREEN, WALL_INNER, (px + 7, py + CELL - 4), (px + CELL - 7, py + CELL - 4), 2)
                if bits & 8:
                    pygame.draw.line(SCREEN, WALL, (px + 2, py + 4), (px + 2, py + CELL - 4), 6)
                    pygame.draw.line(SCREEN, WALL_INNER, (px + 4, py + 7), (px + 4, py + CELL - 7), 2)

        for (a, b), gate in self.gates.items():
            ax, ay = a
            bx, by = b
            is_open = gate['open']
            gate_color = GREEN if is_open else RED
            label_color = (10, 18, 30) if is_open else (255, 245, 248)
            if ax != bx:
                gx, gy = OX + max(ax, bx) * CELL, OY + ay * CELL + CELL // 2
                bounds = pygame.Rect(gx - 8, gy - 18, 16, 36)
            else:
                gx, gy = OX + ax * CELL + CELL // 2, OY + max(ay, by) * CELL
                bounds = pygame.Rect(gx - 18, gy - 8, 36, 16)
            shadow_rect(bounds, radius=7, offset=2)
            pygame.draw.rect(SCREEN, gate_color, bounds, border_radius=7)
            if not is_open:
                gid = TINY.render(str(gate['id']), True, label_color)
                SCREEN.blit(gid, gid.get_rect(center=bounds.center))

        gx, gy = self.maze.maze_exit
        exit_rect = pygame.Rect(OX + gx * CELL + 9, OY + gy * CELL + 9, CELL - 18, CELL - 18)
        shadow_rect(exit_rect, radius=10, offset=2)
        pygame.draw.rect(SCREEN, GREEN, exit_rect, border_radius=10)
        ex = FONT.render('X', True, (12, 26, 24))
        SCREEN.blit(ex, ex.get_rect(center=exit_rect.center))

        px, py = self.player
        cx, cy = OX + px * CELL + CELL // 2, OY + py * CELL + CELL // 2
        pulse = int(1.5 * (1 + pygame.math.Vector2(1, 0).rotate(self.player_pulse * 40).x))
        pygame.draw.circle(SCREEN, (25, 61, 82), (cx, cy + 2), 16)
        pygame.draw.circle(SCREEN, CYAN, (cx, cy), 16 + pulse // 3)
        pygame.draw.circle(SCREEN, (13, 42, 56), (cx, cy), 12)
        pygame.draw.circle(SCREEN, CYAN_SOFT, (cx - 4, cy - 3), 2)
        pygame.draw.circle(SCREEN, CYAN_SOFT, (cx + 4, cy - 3), 2)
        pygame.draw.arc(SCREEN, CYAN_SOFT, (cx - 5, cy - 2, 10, 8), 0.3, 2.84, 2)

        legend = pygame.Rect(720, 132, 515, 432)
        shadow_rect(legend, radius=18, offset=5)
        pygame.draw.rect(SCREEN, PANEL, legend, border_radius=18)
        pygame.draw.rect(SCREEN, PANEL_2, legend.inflate(-10, -10), border_radius=16)
        text('SHADOW HACKER', 748, 160, CYAN, TITLE)
        text('Programming Maze', 749, 195, WHITE, SMALL)
        pill(748, 236, 92, 34, RED, 'Locked')
        pill(853, 236, 92, 34, GREEN, 'Open', label_color=(10, 28, 21))
        pill(958, 236, 92, 34, GREEN, 'Exit X', label_color=(10, 28, 21))
        text('Maze size', 748, 304, MUTED, SMALL)
        text('13 x 9', 1108, 304, WHITE, SMALL)
        text('Level gates', 748, 338, MUTED, SMALL)
        text(f'{len(self.gates)}', 1118, 338, YELLOW, SMALL)
        text('Solved gates', 748, 372, MUTED, SMALL)
        text(f'{sum(g["open"] for g in self.gates.values())}/{len(self.gates)}', 1088, 372, WHITE, SMALL)
        text('Controls', 748, 428, CYAN, SMALL)
        text('Move with WASD or Arrow Keys', 748, 458, WHITE, SMALL)
        text('Press E near a red gate to debug', 748, 486, WHITE, SMALL)
        text('Press M to return to menu', 748, 514, WHITE, SMALL)

    def draw_editor(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 8, 15, 235))
        SCREEN.blit(overlay, (0, 0))
        panel = pygame.Rect(46, 38, 1188, 644)
        shadow_rect(panel, radius=18, offset=6)
        pygame.draw.rect(SCREEN, PANEL, panel, border_radius=18)
        pygame.draw.rect(SCREEN, PANEL_2, panel.inflate(-12, -12), border_radius=15)
        q = self.gates[self.active_gate]['question']
        text('CODELINK DEBUG TERMINAL', 76, 64, CYAN, TITLE)
        pill(984, 60, 100, 34, YELLOW, self.language, label_color=(30, 24, 0))
        pill(1096, 60, 100, 34, RED, f'Gate {self.gates[self.active_gate]["id"]}')
        text(q['title'], 78, 108, WHITE, FONT)
        text(q['prompt'], 78, 140, MUTED, SMALL)
        code_rect = pygame.Rect(70, 176, 820, 380)
        pygame.draw.rect(SCREEN, (10, 22, 37), code_rect, border_radius=12)
        pygame.draw.rect(SCREEN, (6, 18, 31), (70, 176, 820, 38), border_top_left_radius=12, border_top_right_radius=12)
        text('main.code', 92, 186, CYAN, SMALL)
        for i in range(self.view_top, min(len(self.lines), self.view_top + 12)):
            yy = 225 + (i - self.view_top) * 27
            text(f'{i + 1:>2}', 92, yy, MUTED, MONO)
            SCREEN.set_clip(pygame.Rect(145, 216, 730, 326))
            text(self.lines[i], 150, yy, WHITE, MONO)
            SCREEN.set_clip(None)
        if self.view_top <= self.line < self.view_top + 12:
            before = self.lines[self.line][:self.col]
            cx = min(865, 150 + MONO.size(before)[0])
            cy = 226 + (self.line - self.view_top) * 27
            pygame.draw.line(SCREEN, CYAN, (cx, cy), (cx, cy + 20), 2)
        side = pygame.Rect(910, 176, 286, 380)
        pygame.draw.rect(SCREEN, (10, 22, 37), side, border_radius=12)
        text('GOAL', 932, 198, CYAN, SMALL)
        text('Fix the code and make it pass', 932, 228, WHITE, SMALL)
        text('the expected solution check.', 932, 252, WHITE, SMALL)
        text('HINT', 932, 318, CYAN, SMALL)
        hint_lines = [q['hint'][i:i+27] for i in range(0, len(q['hint']), 27)]
        for idx, line in enumerate(hint_lines[:5]):
            text(line, 932, 350 + idx * 24, MUTED, SMALL)
        text('F5 = Check', 932, 478, WHITE, SMALL)
        text('F1 = Hint', 932, 504, WHITE, SMALL)
        text('Ctrl+R = Reset', 932, 530, WHITE, SMALL)
        text('Esc = Back', 932, 556, WHITE, SMALL)
        text('Incorrect fix: -1 life', 78, 582, RED_SOFT, SMALL)
        if self.message_time:
            text(self.message[:112], 78, 618, YELLOW, SMALL)

    def draw(self):
        self.draw_bg()
        top = pygame.Rect(24, 22, WIDTH - 48, 84)
        shadow_rect(top, radius=18, offset=4)
        pygame.draw.rect(SCREEN, PANEL, top, border_radius=18)
        pygame.draw.rect(SCREEN, PANEL_2, top.inflate(-10, -10), border_radius=16)
        text('CODE BREAKER', 48, 34, CYAN, TITLE)
        text('Programming Maze', 49, 68, WHITE, SMALL)

        if self.mode == 'menu':
            centered('DEBUG YOUR WAY OUT', 212, WHITE, BIG)
            centered('Pick a language and enter the maze', 264, MUTED)
            pill(WIDTH // 2 - 230, 344, 170, 46, GREEN, '1  PYTHON', label_color=(7, 26, 17))
            pill(WIDTH // 2 - 85, 410, 170, 46, YELLOW, '2  JAVA', label_color=(30, 24, 0))
            pill(WIDTH // 2 + 60, 476, 170, 46, RED, '3  C++')
            centered('3 levels • 3 lives • random mazes • code gates', 590, MUTED, SMALL)
            centered('Visual size matches the 13 x 9 reference grid', 620, MUTED, SMALL)
        elif self.mode in ('maze', 'editor'):
            pill(340, 40, 94, 34, CYAN, f'L{self.level + 1}')
            pill(448, 40, 110, 34, YELLOW, self.language, label_color=(30, 24, 0))
            pill(574, 40, 126, 34, RED, '♥ ' * self.lives)
            pill(1018, 40, 170, 34, GREEN, f'{int(self.remaining)//60:02}:{int(self.remaining)%60:02}', label_color=(10, 28, 21))
            self.draw_maze()
            if self.message_time and self.mode == 'maze':
                bottom = pygame.Rect(42, 646, 1194, 40)
                pygame.draw.rect(SCREEN, PANEL, bottom, border_radius=12)
                text(self.message[:112], 58, 656, YELLOW, SMALL)
            if self.mode == 'editor':
                self.draw_editor()
        elif self.mode == 'lost':
            centered('GAME OVER', 274, RED, BIG)
            centered('No lives or time remaining.', 334)
            centered('R: Retry this level    M: Menu', 390, MUTED)
        elif self.mode == 'won':
            centered('SYSTEM RESTORED!', 270, GREEN, BIG)
            centered('You solved all programming mazes!', 334)
            centered(f'Final Score: {self.score}', 388, YELLOW)
            centered('R: Menu    M: Menu', 446, MUTED)
        pygame.display.flip()


def main():
    game = Game()
    while True:
        dt = min(CLOCK.tick(FPS) / 1000.0, 0.1)
        for event in pygame.event.get():
            game.handle(event)
        game.update(dt)
        game.draw()


if __name__ == '__main__':
    main()
