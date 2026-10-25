import os
import pygame
from random import randint
from sys import exit

pygame.init()
WIDTH, HEIGHT = 800, 400
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('Cat Chase')
clock = pygame.time.Clock()

BASE = os.path.dirname(os.path.abspath(__file__))


def path(name):
    return os.path.join(BASE, 'images', name)

FONT_FILE = 'calibri.ttf'
FONT_FALLBACKS = 'calibri,carlito,nunito,quicksand,arial'


def load_font(size, bold=False):
    font_path = os.path.join(BASE, 'fonts', FONT_FILE)
    if os.path.exists(font_path):
        return pygame.font.Font(font_path, size)
    return pygame.font.SysFont(FONT_FALLBACKS, size, bold=bold)


font = load_font(52)
big_font = load_font(100, bold=True)


# ---------- LOADING YOUR OWN ART ----------
def load_scaled(name, scale, fallback_size, fallback_color):
    """Load a PNG and scale it. Missing file -> colored placeholder."""
    try:
        img = pygame.image.load(path(name)).convert_alpha()
        w, h = img.get_size()
        return pygame.transform.smoothscale(img, (int(w * scale), int(h * scale)))
    except (FileNotFoundError, pygame.error):
        ph = pygame.Surface(fallback_size, pygame.SRCALPHA)
        pygame.draw.rect(ph, fallback_color, ph.get_rect(), border_radius=10)
        pygame.draw.rect(ph, (30, 20, 30), ph.get_rect(), 3, border_radius=10)
        return ph


def load_background(name):
    """Scales to the window height, then mirrors it so the loop has no seam."""
    try:
        img = pygame.image.load(path(name)).convert()
        w, h = img.get_size()
        one = pygame.transform.smoothscale(img, (round(w * HEIGHT / h), HEIGHT))
    except (FileNotFoundError, pygame.error):
        one = pygame.Surface((WIDTH, HEIGHT))
        one.fill((100, 160, 100))
        pygame.draw.rect(one, (50, 110, 50), (0, 350, WIDTH, 50))
    strip = pygame.Surface((one.get_width() * 2, HEIGHT))
    strip.blit(one, (0, 0))
    strip.blit(pygame.transform.flip(one, True, False), (one.get_width(), 0))
    return strip


# ---------- SETTINGS (tweak these) ----------
CAT_SCALE = 0.3          # how big your cat drawings are in the game
GROUND_Y = 380           # where the cat's feet touch the grass
CAT_RIGHT = 210          # the cat's nose stays at this x position
JUMP_POWER = 17          # bigger = higher jump
GRAVITY = 1
START_SPEED = 7          # how fast the world scrolls
MAX_SPEED = 11
CHASE_RATE = 0.4         # how fast the cat gains on the mouse each frame
START_GAP = 330          # distance to the mouse at the start / after a catch
CATCH_GAP = 60           # closer than this = caught
ESCAPE_GAP = 620         # farther than this = the mouse got away
STUMBLE = 110            # how far the mouse pulls ahead when you hit a block

# ---------- ART ----------
background = load_background('background.png')
bg_w = background.get_width()
cat_run = [load_scaled('cat_run1.png', CAT_SCALE, (130, 75), (60, 60, 80)),
           load_scaled('cat_run2.png', CAT_SCALE, (130, 75), (60, 60, 80))]
cat_idle = load_scaled('cat_idle.png', CAT_SCALE, (84, 106), (60, 60, 80))
cat_duck = load_scaled('cat_duck.png', CAT_SCALE, (150, 60), (60, 60, 80))
cat_jump = [load_scaled('cat_jump1.png', CAT_SCALE, (115, 97), (60, 60, 80)),
            load_scaled('cat_jump2.png', CAT_SCALE, (124, 62), (60, 60, 80))]
# Not drawn yet? These placeholders get replaced as soon as you add the PNGs.
mouse_frames = [load_scaled('mouse_1.png', 0.12, (100, 38), (190, 190, 190)),
                load_scaled('mouse_2.png', 0.12, (100, 40), (170, 170, 170))]
# Three block colors; each block that appears picks one at random
block_imgs = [load_scaled(f'block_{i}.png', 0.108, (56, 53), (150, 105, 160)) for i in (1, 2, 3)]
BLOCK_HIGH_BOTTOM = GROUND_Y - 52   # how far above the ground the "duck" blocks float

# Hitboxes are smaller than the drawings so near-misses feel fair
HIT_W = 70
HIT_H_STAND = 62
HIT_H_DUCK = 40

# ---------- GAME STATE ----------
state = 'start'          # 'start', 'play', 'over'
best = 0


def reset():
    global cat_lift, vel_y, gap, score, blocks, speed, frame, spawn_cd, hurt, bg_x
    cat_lift = 0.0       # how far the cat is above the ground
    vel_y = 0.0
    gap = float(START_GAP)
    score = 0
    blocks = []          # list of (rect, image)
    speed = START_SPEED
    frame = 0.0
    spawn_cd = 60
    hurt = 0
    bg_x = 0.0


reset()


def cat_pose(ducking):
    if cat_lift > 0:
        return cat_jump[0] if vel_y < 0 else cat_jump[1]
    if ducking:
        return cat_duck
    return cat_run[int(frame) % 2]


while True:
    jump_pressed = False
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()
        if event.type == pygame.KEYDOWN:
            if state in ('start', 'over') and event.key == pygame.K_SPACE:
                reset()
                state = 'play'
            elif state == 'play' and event.key == pygame.K_UP:
                jump_pressed = True

    keys = pygame.key.get_pressed()
    ducking = False

    if state == 'play':
        # --- Cat: UP = jump, DOWN (hold) = duck ---
        if jump_pressed and cat_lift == 0:
            vel_y = -JUMP_POWER
            cat_lift = 0.001
        if cat_lift > 0:
            vel_y += GRAVITY
            cat_lift -= vel_y
            if cat_lift <= 0:
                cat_lift = 0.0
                vel_y = 0.0
        ducking = bool(keys[pygame.K_DOWN]) and cat_lift == 0

        frame += 0.15
        speed = min(MAX_SPEED, START_SPEED + score * 0.4)
        bg_x -= speed
        if bg_x <= -bg_w:
            bg_x += bg_w

        # --- Blocks: low ones (jump) and high ones (duck) ---
        spawn_cd -= 1
        if spawn_cd <= 0:
            img = block_imgs[randint(0, 2)]
            if randint(0, 1) == 0:      # on the ground: jump over it
                r = img.get_rect(bottomleft=(WIDTH + 20, GROUND_Y))
            else:                       # floating: duck under it
                r = img.get_rect(bottomleft=(WIDTH + 20, BLOCK_HIGH_BOTTOM))
            blocks.append((r, img))
            spawn_cd = int(randint(65, 110) * START_SPEED / speed)

        # --- Hitbox for the cat's current pose ---
        h = HIT_H_DUCK if ducking else HIT_H_STAND
        hitbox = pygame.Rect(0, 0, HIT_W, h)
        hitbox.bottomright = (CAT_RIGHT - 12, GROUND_Y - cat_lift)

        for item in blocks[:]:
            rect, img = item
            rect.x -= speed
            if rect.right < 0:
                blocks.remove(item)
            elif hitbox.colliderect(rect.inflate(-10, -10)):
                gap += STUMBLE
                hurt = 30
                blocks.remove(item)

        # --- The chase ---
        gap -= CHASE_RATE
        if gap < CATCH_GAP:
            score += 1
            gap = float(START_GAP)
        if gap > ESCAPE_GAP:
            best = max(best, score)
            state = 'over'
        if hurt > 0:
            hurt -= 1

    # ---------- DRAWING ----------
    screen.blit(background, (bg_x, 0))
    screen.blit(background, (bg_x + bg_w, 0))

    if state == 'start':
        pose = cat_idle
        screen.blit(pose, pose.get_rect(bottomright=(WIDTH // 2 + 42, GROUND_Y)))
        title = big_font.render('Cat Chase', False, 'Pink')
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 90)))
        msg = font.render('Press SPACE to play', False, 'Pink')
        screen.blit(msg, msg.get_rect(center=(WIDTH // 2, 150)))
        tip = font.render('UP = jump    DOWN = duck', False, 'Pink')
        screen.blit(tip, tip.get_rect(center=(WIDTH // 2, 200)))
    elif state == 'play':
        for rect, img in blocks:
            screen.blit(img, rect)
        m = mouse_frames[int(frame) % 2]
        screen.blit(m, m.get_rect(midbottom=(CAT_RIGHT + gap, GROUND_Y)))
        pose = cat_pose(ducking)
        if hurt == 0 or (hurt // 4) % 2 == 0:   # blink while stumbling
            screen.blit(pose, pose.get_rect(bottomright=(CAT_RIGHT, GROUND_Y - cat_lift)))
        hud = font.render(f'Caught: {score}   Best: {max(best, score)}', False, 'Pink')
        screen.blit(hud, hud.get_rect(midtop=(WIDTH // 2, 10)))
    else:
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        screen.blit(dim, (0, 0))
        m1 = big_font.render('It got away!', False, 'Pink')
        m2 = font.render(f'Caught: {score}    Best: {best}', False, 'Pink')
        m3 = font.render('Press SPACE to try again', False, 'Pink')
        screen.blit(m1, m1.get_rect(center=(WIDTH // 2, 130)))
        screen.blit(m2, m2.get_rect(center=(WIDTH // 2, 200)))
        screen.blit(m3, m3.get_rect(center=(WIDTH // 2, 250)))

    pygame.display.update()
    clock.tick(60)
