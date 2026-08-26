# plane_game_with_modular_fuel.py
# Full game merged with a modular fuel system you can drop into any similar project.

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import sys, random, time, math

WIN_W, WIN_H = 900, 600

# ----------------------
# Global game variables
# ----------------------
plane_pos = {'x':0.0, 'y':0.0, 'z':0.0}
controls = {'left':False,'right':False,'up':False,'down':False}
speed = .5
forward_speed = .5
world_z = 0.0

# Trees (same logic as before)
tree_spacing = 5
tree_rows = 50
track_width = 8
trees_left = []
trees_right = []

# Items: shared list for hazards, heals, fuel
# item format: {'type': 'hazard'/'heal'/'fuel', 'x':..., 'y':..., 'z':..., 'size':...}
items = []
item_size = 0.9

# Hazard/heal spawn timing (kept from earlier)
hazard_spawn_range = (3.0, 4.0)   # every ~3-4s
heal_spawn_range = (6.0, 8.0)     # every ~6-8s
_next_hazard_spawn = 0.0
_next_heal_spawn = 0.0

# Game state
score = 0
highscore = 0
lives = 3
max_lives = 3
game_over = False

# Camera
first_person = False

# Shield
shield_enabled = False
shield_expires_at = 0.0
shield_radius = 1.6

# Cheat mode
cheat_mode = False

# Combat/health
max_health = 100
health = 100

# Enemies and bullets
enemies = []  # each: {'x','y','z','size','fire_interval','last_fire','pulse'}
enemy_spawn_range = (1.6, 2.4)
_next_enemy_spawn = 0.0

bullets = []  # each: {'x','y','z','vx','vy','vz','speed','radius'} in world coords
bullet_speed = 0.5
bullet_radius = 0.25

# Player bullets
player_bullets = []  # {'x','y','z','vx','vy','vz','radius'} in world coordinates
player_bullet_speed = 0.8
player_bullet_radius = 0.22
_player_fire_cooldown = 0.18  # seconds
_player_last_fire = 0.0

# Blinking lights (plane)
blink_interval = 0.5
_last_blink_time = time.time()
_wing_light_on = True

# Time tracking for frame-rate independent updates
_last_update_time = time.time()

# ----------------------
# Fuel system variables
# ----------------------
fuel_time_remaining = 20.0    # seconds of fuel
_fuel_spawn_min = 13.0        # spawn delay lower bound (sec)
_fuel_spawn_max = 14.0        # spawn delay upper bound (sec)
_next_fuel_spawn = 0.0        # timestamp when fuel + should spawn
fuel_item_active = False      # is there a fuel item currently active?

# ----------------------
# Utility initializers
# ----------------------
def reset_trees():
    trees_left.clear()
    trees_right.clear()
    for i in range(tree_rows):
        z_pos = i * tree_spacing
        # left
        trees_left.append({'x': -track_width, 'z': z_pos,
                           'trunk': random.uniform(1.0, 2.0),
                           'leaves': random.randint(2, 4)})
        # right
        trees_right.append({'x': track_width, 'z': z_pos,
                            'trunk': random.uniform(1.0, 2.0),
                            'leaves': random.randint(2, 4)})

def schedule_next_hazard_heal(now=None):
    global _next_hazard_spawn, _next_heal_spawn
    if now is None: now = time.time()
    _next_hazard_spawn = now + random.uniform(*hazard_spawn_range)
    _next_heal_spawn = now + random.uniform(*heal_spawn_range)

def schedule_next_fuel_spawn(now=None):
    global _next_fuel_spawn
    if now is None: now = time.time()
    _next_fuel_spawn = now + random.uniform(_fuel_spawn_min, _fuel_spawn_max)

def schedule_next_enemy_spawn(now=None):
    global _next_enemy_spawn
    if now is None: now = time.time()
    _next_enemy_spawn = now + random.uniform(*enemy_spawn_range)

# initialize spawns and trees
reset_trees()
schedule_next_hazard_heal()
schedule_next_fuel_spawn()
schedule_next_enemy_spawn()

# ----------------------
# Drawing helpers
# ----------------------
def draw_tree(x, z, trunk_height, leaf_layers):
    glColor3f(0.55,0.27,0.07)  # brown
    glPushMatrix()
    glTranslatef(x, -3 + trunk_height/2, -z)
    glScalef(0.5, trunk_height, 0.5)
    glutSolidCube(1.0)
    glPopMatrix()
    glColor3f(0.0,0.5,0.0)
    for i in range(leaf_layers):
        glPushMatrix()
        glTranslatef(x, -3 + trunk_height + i*0.5, -z)
        scale = 1.5 - 0.2*i
        glScalef(scale, 0.5, scale)
        glutSolidSphere(1.0,20,20)
        glPopMatrix()

def draw_plane():
    global _wing_light_on
    glPushMatrix()
    glTranslatef(plane_pos['x'], plane_pos['y'], plane_pos['z'])
    # fuselage
    glColor3f(0.2,0.5,0.9)
    glPushMatrix(); glScalef(0.5,0.5,4.0); glutSolidSphere(1.0,24,24); glPopMatrix()
    # nose
    glColor3f(0.9,0.5,0.1)
    glPushMatrix(); glTranslatef(0,0,2.1); glScalef(0.5,0.5,1.0); glutSolidSphere(1.0,20,20); glPopMatrix()
    # wings
    glColor3f(0.15,0.15,0.15)
    glPushMatrix(); glTranslatef(-2.0,0,0); glRotatef(2,0,1,0); glScalef(3.5,0.08,0.8); glutSolidCube(1.0); glPopMatrix()
    glPushMatrix(); glTranslatef(2.0,0,0); glRotatef(-2,0,1,0); glScalef(3.5,0.08,0.8); glutSolidCube(1.0); glPopMatrix()
    # blinking wing lights
    if _wing_light_on:
        glColor3f(1.0,0.0,0.0); glPushMatrix(); glTranslatef(-3.5,0.1,0); glutSolidSphere(0.15,12,12); glPopMatrix()
        glColor3f(0.0,1.0,0.0); glPushMatrix(); glTranslatef(3.5,0.1,0); glutSolidSphere(0.15,12,12); glPopMatrix()
    # tail + cockpit
    glColor3f(0.2,0.5,0.9); glPushMatrix(); glTranslatef(0,0.9,-1.8); glScalef(0.15,1.2,0.1); glutSolidCube(1.0); glPopMatrix()
    glPushMatrix(); glTranslatef(-1.0,0,-1.8); glScalef(1.0,0.08,0.3); glutSolidCube(1.0); glPopMatrix()
    glPushMatrix(); glTranslatef(1.0,0,-1.8); glScalef(1.0,0.08,0.3); glutSolidCube(1.0); glPopMatrix()
    glColor3f(0.0,0.35,0.5); glPushMatrix(); glTranslatef(0,0.3,0.7); glScalef(0.45,0.4,0.8); glutSolidSphere(1.0,20,20); glPopMatrix()
    glPopMatrix()

def draw_track():
    slice_length = 20.0
    num_slices = 20
    glColor3f(0.16,0.6,0.18)
    for i in range(num_slices):
        z = i*slice_length - (world_z % slice_length)
        glPushMatrix(); glTranslatef(0.0,-3.0,-z); glScalef(20.0,0.5,slice_length); glutSolidCube(1.0); glPopMatrix()
    all_trees = trees_left + trees_right
    all_trees.sort(key=lambda t: t['z'] - world_z, reverse=True)
    for tree in all_trees:
        z_pos = tree['z'] - world_z
        if -50 < z_pos < 50:
            draw_tree(tree['x'], z_pos, tree['trunk'], tree['leaves'])

def draw_items():
    for item in items:
        z_pos = item['z'] - world_z
        if -60 < z_pos < 60:
            glPushMatrix()
            glTranslatef(item['x'], item['y'], -z_pos)
            s = item.get('size', 1.0) * item_size
            glScalef(s, s, s)
            t = item['type']
            if t == 'heal':
                glColor3f(0.0, 0.9, 0.0)
                glutWireTorus(0.08, 0.45, 12, 20)
            elif t == 'hazard':
                glColor3f(1.0, 0.0, 0.0)
                glPushMatrix(); glRotatef(45,0,0,1); glScalef(1.0,0.18,0.18); glutSolidCube(1.0); glPopMatrix()
                glPushMatrix(); glRotatef(-45,0,0,1); glScalef(1.0,0.18,0.18); glutSolidCube(1.0); glPopMatrix()
            elif t == 'fuel':
                # deep red plus sign (vertical + horizontal bars)
                glColor3f(0.7, 0.0, 0.0)
                glPushMatrix(); glScalef(0.28, 1.2, 0.28); glutSolidCube(1.0); glPopMatrix()
                glPushMatrix(); glScalef(1.2, 0.28, 0.28); glutSolidCube(1.0); glPopMatrix()
            else:
                glColor3f(1.0,1.0,0.0); glutSolidSphere(0.4,12,12)
            glPopMatrix()

def draw_enemies():
    for e in enemies:
        z_pos = e['z'] - world_z
        if -60 < z_pos < 60:
            glPushMatrix()
            glTranslatef(e['x'], e['y'], -z_pos)
            # enemy plane scale
            glScalef(1.0, 1.0, 1.0)

            # fuselage
            glColor3f(0.6, 0.6, 0.65)
            glPushMatrix(); glScalef(0.45, 0.45, 3.2); glutSolidSphere(1.0, 18, 18); glPopMatrix()
            # nose
            glColor3f(0.85, 0.1, 0.1)
            glPushMatrix(); glTranslatef(0, 0, 1.75); glScalef(0.45, 0.45, 0.9); glutSolidSphere(1.0, 16, 16); glPopMatrix()
            # wings
            glColor3f(0.2, 0.2, 0.2)
            glPushMatrix(); glTranslatef(-1.6, 0, 0); glRotatef(3, 0, 1, 0); glScalef(2.4, 0.06, 0.65); glutSolidCube(1.0); glPopMatrix()
            glPushMatrix(); glTranslatef( 1.6, 0, 0); glRotatef(-3, 0, 1, 0); glScalef(2.4, 0.06, 0.65); glutSolidCube(1.0); glPopMatrix()
            # tail
            glColor3f(0.6, 0.6, 0.65)
            glPushMatrix(); glTranslatef(0, 0.7, -1.4); glScalef(0.12, 0.9, 0.1); glutSolidCube(1.0); glPopMatrix()
            glPushMatrix(); glTranslatef(-0.8, 0, -1.4); glScalef(0.7, 0.06, 0.25); glutSolidCube(1.0); glPopMatrix()
            glPushMatrix(); glTranslatef( 0.8, 0, -1.4); glScalef(0.7, 0.06, 0.25); glutSolidCube(1.0); glPopMatrix()

            glPopMatrix()

def draw_bullets():
    glColor3f(1.0, 0.85, 0.0)
    for b in bullets:
        z_pos = b['z'] - world_z
        if -60 < z_pos < 60:
            glPushMatrix()
            glTranslatef(b['x'], b['y'], -z_pos)
            glutSolidSphere(b.get('radius', bullet_radius), 10, 10)
            glPopMatrix()

def draw_player_bullets():
    glColor3f(0.2, 0.9, 1.0)
    for b in player_bullets:
        z_pos = b['z'] - world_z
        if -60 < z_pos < 120:
            glPushMatrix()
            glTranslatef(b['x'], b['y'], -z_pos)
            glutSolidSphere(b.get('radius', player_bullet_radius), 10, 10)
            glPopMatrix()

def draw_shield():
    if not shield_enabled:
        return
    # draw around plane local coordinates (plane_pos z is local)
    glColor3f(0.2, 0.8, 1.0)
    glPushMatrix()
    glTranslatef(plane_pos['x'], plane_pos['y'], plane_pos['z'])
    glutWireSphere(shield_radius, 16, 12)
    glPopMatrix()

# ----------------------
# Item spawn functions
# ----------------------
def spawn_hazard():
    x = random.uniform(-6.0, 6.0)
    y = random.uniform(-2.0, 2.0)
    z = world_z + random.uniform(40.0, 70.0)
    size = random.uniform(0.8, 1.2)
    items.append({'type':'hazard','x':x,'y':y,'z':z,'size':size})

def spawn_heal():
    x = random.uniform(-6.0, 6.0)
    y = random.uniform(-2.0, 2.0)
    z = world_z + random.uniform(45.0, 85.0)
    size = random.uniform(0.9, 1.3)
    items.append({'type':'heal','x':x,'y':y,'z':z,'size':size})

def spawn_enemy():
    x = random.uniform(-6.0, 6.0)
    y = random.uniform(-1.0, 2.0)
    z = world_z + random.uniform(45.0, 80.0)
    fire_interval = random.uniform(0.8, 1.4)
    enemies.append({'x':x,'y':y,'z':z,'size':1.0,'fire_interval':fire_interval,'last_fire':time.time(),'pulse':random.random()*math.tau})

def enemy_try_fire(now):
    # Fire bullets towards the plane from enemies that are in front
    target_world_z = world_z + plane_pos['z']
    for e in enemies:
        if now - e['last_fire'] >= e['fire_interval']:
            ex, ey, ez = e['x'], e['y'], e['z']
            dx = plane_pos['x'] - ex
            dy = plane_pos['y'] - ey
            dz = target_world_z - ez
            dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
            vx = (dx / dist) * bullet_speed
            vy = (dy / dist) * bullet_speed
            vz = (dz / dist) * bullet_speed
            bullets.append({'x':ex,'y':ey,'z':ez,'vx':vx,'vy':vy,'vz':vz,'speed':bullet_speed,'radius':bullet_radius})
            e['last_fire'] = now

# ----------------------
# --- Modular Fuel API
# ----------------------
def init_fuel():
    """Call this at game start or restart to reset fuel state."""
    global fuel_time_remaining, fuel_item_active
    fuel_time_remaining = 20.0
    fuel_item_active = False
    schedule_next_fuel_spawn()    # prepare the next spawn time

def spawn_fuel():
    """Place a fuel '+' ahead in the world and mark it active."""
    global fuel_item_active
    if not fuel_item_active:
        x = random.uniform(-4.0, 4.0)
        y = random.uniform(-1.5, 1.5)
        z = world_z + random.uniform(45.0, 65.0)
        items.append({'type':'fuel','x':x,'y':y,'z':z,'size':1.0})
        fuel_item_active = True

def handle_fuel_pickup(item):
    global fuel_time_remaining, fuel_item_active, score
    fuel_time_remaining = 20.0
    fuel_item_active = False
    score += 1
    schedule_next_fuel_spawn()
    return True


def update_fuel(dt, now):
    global fuel_time_remaining, fuel_item_active, lives, game_over, _next_fuel_spawn
    
    # In cheat mode, fuel never decreases
    if not cheat_mode:
        fuel_time_remaining -= dt
    
    if (not fuel_item_active) and (now >= _next_fuel_spawn):
        spawn_fuel()
    
    # In cheat mode, fuel never runs out
    if not cheat_mode and fuel_time_remaining <= 0.0:
        lives -= 1
        fuel_time_remaining = 20.0
        fuel_item_active = False
        schedule_next_fuel_spawn()
        if lives <= 0:
            update_highscore_on_death()
            game_over = True


# ----------------------
# Collisions / hit logic
# ----------------------
def update_highscore_on_death():
    global highscore, score
    if score > highscore:
        highscore = score

def handle_collision(item):
    """
    Central collision handler for item effects.
    Return True means remove item after handling.
    """
    global lives, score, game_over  # <--- move this up front
    t = item['type']
    if t == 'heal':
        if lives < max_lives:
            lives += 1
        else:
            score += 1
        return True
    elif t == 'hazard':
        lives -= 1
        if lives <= 0:
            update_highscore_on_death()
            game_over = True
        return True
    elif t == 'fuel':
        return handle_fuel_pickup(item)
    else:
        return True


def check_collisions():
    plane_x, plane_y, plane_z = plane_pos['x'], plane_pos['y'], plane_pos['z']
    remove_list = []
    for item in list(items):
        rel_z = item['z'] - world_z
        dx = plane_x - item['x']; dy = plane_y - item['y']; dz = plane_z - rel_z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        hit_radius = 1.2 * (0.6 * item.get('size', 1.0))
        if dist < hit_radius:
            if handle_collision(item):
                remove_list.append(item)
    # remove items collided
    for r in remove_list:
        if r in items:
            items.remove(r)

# ----------------------
# Text / HUD
# ----------------------
def draw_text(x, y, text, color=(0,0,0)):
    glColor3f(*color)
    # glWindowPos2f is reliable for HUD overlay
    glWindowPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))

# ----------------------
# Display & update loop
# ----------------------
def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    if first_person:
        eye_x = plane_pos['x']
        eye_y = plane_pos['y'] + 0.4
        eye_z = 1.2
        cen_x = plane_pos['x']
        cen_y = plane_pos['y'] + 0.25
        cen_z = -5.0
        gluLookAt(eye_x, eye_y, eye_z,  cen_x, cen_y, cen_z,  0,1,0)
    else:
        eye_x = plane_pos['x']
        eye_y = plane_pos['y'] + 3.0
        eye_z = 10.0
        cen_x = plane_pos['x']
        cen_y = plane_pos['y']
        cen_z = 0.0
        gluLookAt(eye_x, eye_y, eye_z,  cen_x, cen_y, cen_z,  0,1,0)

    # world
    draw_track()
    draw_enemies()
    draw_bullets()
    draw_player_bullets()
    draw_shield()
    if not first_person:
        draw_plane()
    draw_items()

    # HUD (use window coordinates)
    cheat_text = " [CHEAT MODE]" if cheat_mode else ""
    draw_text(10, WIN_H - 30, f"Score: {score}   Lives: {lives}   Health: {health}   Fuel: {int(fuel_time_remaining)}s   Highscore: {highscore}{cheat_text}", (0.0,0.0,0.0))
    draw_text(10, WIN_H - 55, f"R: restart  C: toggle view  B: fire  N: shield {'ON' if shield_enabled else 'OFF'}  L: cheat mode  Collect + to refill fuel. Avoid red crosses.", (0.0,0.0,0.0))
    if game_over:
        draw_text(WIN_W//2 - 120, WIN_H//2, "GAME OVER - Press R to Restart", (1.0,0.0,0.0))

    glutSwapBuffers()

def update():
    global world_z, _next_hazard_spawn, _next_heal_spawn, _last_blink_time, _wing_light_on, _last_update_time, _next_fuel_spawn, _next_enemy_spawn, health, lives, game_over, shield_enabled, shield_expires_at

    now = time.time()
    dt = now - _last_update_time if _last_update_time is not None else 0.016
    # cap dt so a large pause doesn't skip logic
    dt = min(dt, 0.1)
    _last_update_time_local_update(dt := dt)  # keep local copy for fuel update (we'll explain below)

    # if game over, only redraw
    if game_over:
        glutPostRedisplay()
        return

    # plane movement
    if controls['left']: plane_pos['x'] -= speed
    if controls['right']: plane_pos['x'] += speed
    if controls['up']: plane_pos['y'] += speed
    if controls['down']: plane_pos['y'] -= speed

    # clamp plane
    plane_pos['x'] = max(-6, min(6, plane_pos['x']))
    plane_pos['y'] = max(-2, min(2, plane_pos['y']))

    # world scroll (use dt)
    world_z += forward_speed * (dt * 60.0)  # scale so forward feels similar as before

    # recycle trees
    for tree in trees_left + trees_right:
        if tree['z'] - world_z < -10:
            tree['z'] += tree_rows * tree_spacing
            tree['trunk'] = random.uniform(1.0, 2.0)
            tree['leaves'] = random.randint(2, 4)

    # spawn hazards / heals if time
    if now >= _next_hazard_spawn:
        spawn_hazard()
        _next_hazard_spawn = now + random.uniform(*hazard_spawn_range)
    if now >= _next_heal_spawn:
        spawn_heal()
        _next_heal_spawn = now + random.uniform(*heal_spawn_range)

    # spawn enemies
    if now >= _next_enemy_spawn:
        spawn_enemy()
        schedule_next_enemy_spawn(now)

    # remove items that went behind the plane
    items[:] = [it for it in items if (it['z'] - world_z) > -30]

    # enemy movement and culling
    move_step = (dt * 60.0) * 0.05
    for e in enemies:
        e['pulse'] = e.get('pulse', 0.0) + (dt * 2.5)
        # drift towards plane laterally
        dx = plane_pos['x'] - e['x']
        dy = plane_pos['y'] - e['y']
        dist_xy = math.hypot(dx, dy) + 1e-6
        e['x'] += (dx / dist_xy) * move_step
        e['y'] += (dy / dist_xy) * move_step
        # clamp to track bounds
        e['x'] = max(-6.5, min(6.5, e['x']))
        e['y'] = max(-2.5, min(2.5, e['y']))
    enemies[:] = [e for e in enemies if (e['z'] - world_z) > -30]

    # enemy fire and bullet updates
    enemy_try_fire(now)
    # move bullets in world space
    if bullets:
        step = dt * 60.0
        for b in bullets:
            b['x'] += b['vx'] * step
            b['y'] += b['vy'] * step
            b['z'] += b['vz'] * step
    # cull bullets behind or too far
    bullets[:] = [b for b in bullets if (-40 < (b['z'] - world_z) < 120 and -30 < b['x'] < 30 and -10 < b['y'] < 10)]

    # move player bullets
    if player_bullets:
        step = dt * 60.0
        for b in list(player_bullets):
            b['x'] += b['vx'] * step
            b['y'] += b['vy'] * step
            b['z'] += b['vz'] * step
    # cull player bullets
    player_bullets[:] = [b for b in player_bullets if ((b['z'] - world_z) < 220 and -30 < b['x'] < 30 and -10 < b['y'] < 10)]

    # update fuel system (modular call)
    update_fuel(dt, now)

    # shield timeout (disabled in cheat mode)
    if shield_enabled and now >= shield_expires_at and not cheat_mode:
        shield_enabled = False
    
    # In cheat mode, shield is always active
    if cheat_mode:
        shield_enabled = True

    # check collisions (centralized)
    check_collisions()

    # bullet-plane collisions
    plane_x, plane_y, plane_z = plane_pos['x'], plane_pos['y'], plane_pos['z']
    hit_bullets = []
    for b in bullets:
        rel_z = b['z'] - world_z
        dx = plane_x - b['x']; dy = plane_y - b['y']; dz = plane_z - rel_z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist < (0.7 + b.get('radius', bullet_radius)):
            hit_bullets.append(b)
    if hit_bullets:
        for hb in hit_bullets:
            if hb in bullets:
                bullets.remove(hb)
        # In cheat mode, health never decreases from bullets
        if not shield_enabled and not cheat_mode:
            health -= 2 * len(hit_bullets)
            if health <= 0:
                lives -= 1
                health = max_health
                if lives <= 0:
                    update_highscore_on_death()
                    game_over = True

    # enemy-plane collisions => immediate game over (disabled in cheat mode)
    if not game_over and not cheat_mode:
        enemy_hit = False
        for e in enemies:
            rel_z = e['z'] - world_z
            dx = plane_x - e['x']; dy = plane_y - e['y']; dz = plane_z - rel_z
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            # approximate enemy plane bounding radius
            if dist < 1.2:
                enemy_hit = True
                break
        if enemy_hit:
            lives = 0
            update_highscore_on_death()
            game_over = True

    # player bullet vs enemy collisions
    if not game_over and player_bullets and enemies:
        remove_pbs = []
        remove_enemies = []
        for pb in player_bullets:
            for e in enemies:
                rel_z = e['z'] - world_z
                dx = pb['x'] - e['x']; dy = pb['y'] - e['y']; dz = (pb['z'] - world_z) - rel_z
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist < (1.0 + pb.get('radius', player_bullet_radius)):
                    remove_pbs.append(pb)
                    remove_enemies.append(e)
                    break
        if remove_enemies:
            for e in remove_enemies:
                if e in enemies:
                    enemies.remove(e)
            for pb in remove_pbs:
                if pb in player_bullets:
                    player_bullets.remove(pb)
            globals()['score'] = score + len(remove_enemies)

    # update blinking lights
    if now - _last_blink_time >= blink_interval:
        _wing_light_on = not _wing_light_on
        _last_blink_time = now

    glutPostRedisplay()

# helper to update the _last_update_time (keeps code readable)
def _last_update_time_local_update(dt):
    global _last_update_time
    _last_update_time = time.time()

# ----------------------
# Input handling
# ----------------------
def keyboard_down(key, x, y):
    global game_over, lives, world_z, items, highscore, score, fuel_time_remaining, fuel_item_active, first_person, health, enemies, bullets, player_bullets, _player_last_fire, shield_enabled, shield_expires_at, cheat_mode
    k = key.decode('utf-8') if isinstance(key, bytes) else key
    if k in ('a','A'): controls['left']=True
    if k in ('d','D'): controls['right']=True
    if k in ('w','W'): controls['up']=True
    if k in ('s','S'): controls['down']=True

    if k in ('r','R'):
        # update highscore before restart
        if score > highscore:
            globals()['highscore'] = score
        # reset global game state
        score = 0
        lives = max_lives
        health = max_health
        world_z = 0.0
        items.clear()
        enemies.clear()
        bullets.clear()
        plane_pos['x'], plane_pos['y'], plane_pos['z'] = 0.0, 0.0, 0.0
        game_over = False
        init_fuel()
        schedule_next_hazard_heal(time.time())
        schedule_next_enemy_spawn(time.time())

    if k in ('c','C'):
        first_person = not first_person

    if k in ('b','B') and not game_over:
        now_t = time.time()
        if now_t - _player_last_fire >= _player_fire_cooldown:
            # spawn near nose in world space
            bx = plane_pos['x']
            by = plane_pos['y']
            bz = world_z + plane_pos['z'] + 3.0
            # aim at nearest enemy if available
            if enemies:
                nearest = None
                min_d2 = float('inf')
                for e in enemies:
                    dxw = e['x'] - bx
                    dyw = e['y'] - by
                    dzw = e['z'] - bz
                    d2 = dxw*dxw + dyw*dyw + dzw*dzw
                    if d2 < min_d2:
                        min_d2 = d2
                        nearest = e
                if nearest is not None and min_d2 > 0.0:
                    d = math.sqrt(min_d2)
                    vx = (nearest['x'] - bx) / d * player_bullet_speed
                    vy = (nearest['y'] - by) / d * player_bullet_speed
                    vz = (nearest['z'] - bz) / d * player_bullet_speed
                else:
                    vx, vy, vz = 0.0, 0.0, player_bullet_speed
            else:
                vx, vy, vz = 0.0, 0.0, player_bullet_speed
            player_bullets.append({'x':bx,'y':by,'z':bz,'vx':vx,'vy':vy,'vz':vz,'radius':player_bullet_radius})
            _player_last_fire = now_t

    if k in ('n','N') and not game_over:
        shield_enabled = True
        shield_expires_at = time.time() + 5.0

    if k in ('l','L') and not game_over:
        cheat_mode = not cheat_mode
        if cheat_mode:
            # When enabling cheat mode, ensure infinite resources
            health = max_health
            lives = max_lives
            fuel_time_remaining = 20.0
            shield_enabled = True

    if k == '\x1b':
        sys.exit(0)

def keyboard_up(key, x, y):
    k = key.decode('utf-8') if isinstance(key, bytes) else key
    if k in ('a','A'): controls['left']=False
    if k in ('d','D'): controls['right']=False
    if k in ('w','W'): controls['up']=False
    if k in ('s','S'): controls['down']=False

def special_down(key, x, y):
    if key==GLUT_KEY_LEFT: controls['left']=True
    if key==GLUT_KEY_RIGHT: controls['right']=True
    if key==GLUT_KEY_UP: controls['up']=True
    if key==GLUT_KEY_DOWN: controls['down']=True

def special_up(key, x, y):
    if key==GLUT_KEY_LEFT: controls['left']=False
    if key==GLUT_KEY_RIGHT: controls['right']=False
    if key==GLUT_KEY_UP: controls['up']=False
    if key==GLUT_KEY_DOWN: controls['down']=False

# ----------------------
# GL init & main
# ----------------------
def init_gl():
    glClearColor(0.53,0.81,0.98,1.0)
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(60, WIN_W/WIN_H, 0.1, 200.0)
    glMatrixMode(GL_MODELVIEW)

def main():
    # init fuel & spawns
    init_fuel()
    schedule_next_hazard_heal()

    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)
    glutInitWindowSize(WIN_W, WIN_H)
    glutCreateWindow(b"3D Plane Track - Modular Fuel System")
    init_gl()
    glutDisplayFunc(display)
    glutKeyboardFunc(keyboard_down)
    glutKeyboardUpFunc(keyboard_up)
    glutSpecialFunc(special_down)
    glutSpecialUpFunc(special_up)
    glutIdleFunc(update)
    glutMainLoop()

if __name__ == "__main__":
    main()
