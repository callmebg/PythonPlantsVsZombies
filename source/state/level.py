import os
import json
import pygame as pg
from .. import tool
from .. import constants as c
from ..component import map, plant, zombie, menubar

class Level(tool.State):
    def __init__(self):
        tool.State.__init__(self)
    
    def startup(self, current_time, persist):
        self.game_info = persist
        self.persist = self.game_info
        self.game_info[c.CURRENT_TIME] = current_time
        self.map_y_len = c.GRID_Y_LEN
        self.map = map.Map(c.GRID_X_LEN, self.map_y_len)

        # 默认显然不用显示菜单
        self.showLittleMenu = False
        
        self.loadMap()
        self.setupBackground()
        self.initState()

    def loadMap(self):
        if c.LITTLEGAME_BUTTON in self.game_info:
            map_file = 'littleGame_' + str(self.game_info[c.LEVEL_NUM]) + '.json'
        else:
            map_file = 'level_' + str(self.game_info[c.LEVEL_NUM]) + '.json'
        file_path = os.path.join('resources', 'data', 'map', map_file)
        # 最后一关之后应该结束了
        try:
            f = open(file_path)
            self.map_data = json.load(f)
            f.close()
        except Exception as e:
            print("游戏结束")
            self.done = True
            self.next = c.MAIN_MENU
            return
        if self.map_data[c.SHOVEL] == 0:
            self.hasShovel = False
        else:
            self.hasShovel = True

    
    def setupBackground(self):
        img_index = self.map_data[c.BACKGROUND_TYPE]
        self.background_type = img_index
        self.background = tool.GFX[c.BACKGROUND_NAME][img_index]
        self.bg_rect = self.background.get_rect()

        self.level = pg.Surface((self.bg_rect.w, self.bg_rect.h)).convert()
        self.viewport = tool.SCREEN.get_rect(bottom=self.bg_rect.bottom)
        self.viewport.x += c.BACKGROUND_OFFSET_X

    
    def setupGroups(self):
        self.sun_group = pg.sprite.Group()
        self.head_group = pg.sprite.Group()

        self.plant_groups = []
        self.zombie_groups = []
        self.hypno_zombie_groups = [] #zombies who are hypno after eating hypnoshroom
        self.bullet_groups = []
        for i in range(self.map_y_len):
            self.plant_groups.append(pg.sprite.Group())
            self.zombie_groups.append(pg.sprite.Group())
            self.hypno_zombie_groups.append(pg.sprite.Group())
            self.bullet_groups.append(pg.sprite.Group())
    
    def setupZombies(self):
        def takeTime(element):
            return element[0]

        self.zombie_list = []
        for data in self.map_data[c.ZOMBIE_LIST]:
            self.zombie_list.append((data['time'], data['name'], data['map_y']))
        self.zombie_start_time = 0
        self.zombie_list.sort(key=takeTime)

    def setupCars(self):
        self.cars = []
        for i in range(self.map_y_len):
            _, y = self.map.getMapGridPos(0, i)
            self.cars.append(plant.Car(-25, y+20, i))
    
    # 更新函数每帧被调用，将鼠标事件传入给状态处理函数
    def update(self, surface, current_time, mouse_pos, mouse_click):
        self.current_time = self.game_info[c.CURRENT_TIME] = current_time
        if self.state == c.CHOOSE:
            self.choose(mouse_pos, mouse_click)
        elif self.state == c.PLAY:
            self.play(mouse_pos, mouse_click)

        self.draw(surface)

    def initBowlingMap(self):
        print('initBowlingMap')
        for x in range(3, self.map.width):
            for y in range(self.map.height):
                self.map.setMapGridType(x, y, c.MAP_EXIST)

    def initState(self):
        # 小游戏才有CHOOSEBAR_TYPE
        if c.CHOOSEBAR_TYPE in self.map_data:
            self.bar_type = self.map_data[c.CHOOSEBAR_TYPE]
        else:
            self.bar_type = c.CHOOSEBAR_STATIC

        if self.bar_type == c.CHOOSEBAR_STATIC:
            self.initChoose()
        else:
            card_pool = menubar.getCardPool(self.map_data[c.CARD_POOL])
            self.initPlay(card_pool)
            if self.bar_type == c.CHOSSEBAR_BOWLING:
                self.initBowlingMap()

    def initChoose(self):
        self.state = c.CHOOSE
        self.panel = menubar.Panel(menubar.all_card_list, self.map_data[c.INIT_SUN_NAME])

    def choose(self, mouse_pos, mouse_click):
        if mouse_pos and mouse_click[0]:
            self.panel.checkCardClick(mouse_pos)
            if self.panel.checkStartButtonClick(mouse_pos):
                self.initPlay(self.panel.getSelectedCards())

    def initPlay(self, card_list):
        self.state = c.PLAY
        if self.bar_type == c.CHOOSEBAR_STATIC:
            self.menubar = menubar.MenuBar(card_list, self.map_data[c.INIT_SUN_NAME])
        else:
            self.menubar = menubar.MoveBar(card_list)
        
        # 是否拖住植物或者铲子
        self.drag_plant = False
        self.drag_shovel = False

        self.hint_image = None
        self.hint_plant = False
        if self.background_type == c.BACKGROUND_DAY and self.bar_type == c.CHOOSEBAR_STATIC:
            self.produce_sun = True
        else:
            self.produce_sun = False
        self.sun_timer = self.current_time

        self.removeMouseImage()
        self.setupGroups()
        self.setupZombies()
        self.setupCars()

        # 地图有铲子才添加铲子
        if self.hasShovel:
            #  导入小铲子
            frame_rect = [0, 0, 71, 67]
            self.shovel = tool.get_image_menu(tool.GFX[c.SHOVEL], *frame_rect, c.BLACK, 1.1)
            self.shovel_rect = self.shovel.get_rect()
            frame_rect = [0, 0, 77, 75]
            self.shovel_positon = (550, 2)
            self.shovel_box = tool.get_image_menu(tool.GFX[c.SHOVEL_BOX], *frame_rect, c.BLACK, 1.1)
            self.shovel_box_rect = self.shovel_box.get_rect()
            self.shovel_rect.x = self.shovel_box_rect.x = self.shovel_positon[0]
            self.shovel_rect.y = self.shovel_box_rect.y = self.shovel_positon[1] 

        self.setupLittleMenu()

    # 小菜单
    def setupLittleMenu(self):
        # 具体运行游戏必定有个小菜单, 导入菜单和选项
        frame_rect = [0, 0, 108, 31]
        self.little_menu = tool.get_image_menu(tool.GFX[c.LITTLE_MENU], *frame_rect, c.BLACK, 1.1)
        self.little_menu_rect = self.little_menu.get_rect()
        self.little_menu_rect.x = 650
        self.little_menu_rect.y = 0 

        frame_rect = [0, 0, 500, 500]
        self.big_menu = tool.get_image_menu(tool.GFX[c.BIG_MENU], *frame_rect, c.BLACK, 1.1)
        self.big_menu_rect = self.big_menu.get_rect()
        self.big_menu_rect.x = 150
        self.big_menu_rect.y = 0

        frame_rect = [0, 0, 342, 87]
        self.return_button = tool.get_image_menu(tool.GFX[c.RETURN_BUTTON], *frame_rect, c.BLACK, 1.1)
        self.return_button_rect = self.return_button.get_rect()
        self.return_button_rect.x = 220
        self.return_button_rect.y = 440

        frame_rect = [0, 0, 207, 45]
        self.restart_button = tool.get_image_menu(tool.GFX[c.RESTART_BUTTON], *frame_rect, c.BLACK, 1.1)
        self.restart_button_rect = self.restart_button.get_rect()
        self.restart_button_rect.x = 295
        self.restart_button_rect.y = 325

        frame_rect = [0, 0, 206, 43]
        self.mainMenu_button = tool.get_image_menu(tool.GFX[c.MAINMENU_BUTTON], *frame_rect, c.BLACK, 1.1)
        self.mainMenu_button_rect = self.mainMenu_button.get_rect()
        self.mainMenu_button_rect.x = 299
        self.mainMenu_button_rect.y = 372

    # 检查小菜单有没有被点击
    def checkLittleMenuClick(self, mouse_pos):
        x, y = mouse_pos
        if(x >= self.little_menu_rect.x and x <= self.little_menu_rect.right and
           y >= self.little_menu_rect.y and y <= self.little_menu_rect.bottom):
            return True
        return False

    # 检查小菜单的返回有没有被点击
    def checkReturnClick(self, mouse_pos):
        x, y = mouse_pos
        if(x >= self.return_button_rect.x and x <= self.return_button_rect.right and
           y >= self.return_button_rect.y and y <= self.return_button_rect.bottom):
            return True
        return False

    # 检查小菜单的重新开始有没有被点击
    def checkRestartClick(self, mouse_pos):
        x, y = mouse_pos
        if(x >= self.restart_button_rect.x and x <= self.restart_button_rect.right and
           y >= self.restart_button_rect.y and y <= self.restart_button_rect.bottom):
            return True
        return False
    
    # 检查小菜单的主菜单有没有被点击
    def checkMainMenuClick(self, mouse_pos):
        x, y = mouse_pos
        if(x >= self.mainMenu_button_rect.x and x <= self.mainMenu_button_rect.right and
           y >= self.mainMenu_button_rect.y and y <= self.mainMenu_button_rect.bottom):
            return True
        return False

    # 用小铲子移除植物
    def shovelRemovePlant(self, mouse_pos):
        x, y = mouse_pos
        map_x, map_y = self.map.getMapIndex(x, y)
        for i in self.plant_groups[map_y]:
            if(x >= i.rect.x and x <= i.rect.right and
               y >= i.rect.y and y <= i.rect.bottom):
               i.kill()
               return 

    # 检查小铲子的位置有没有被点击
    # 方便放回去
    def checkShovelClick(self, mouse_pos):
        x, y = mouse_pos
        if(x >= self.shovel_box_rect.x and x <= self.shovel_box_rect.right and
           y >= self.shovel_box_rect.y and y <= self.shovel_box_rect.bottom):
            return True
        return False

    def play(self, mouse_pos, mouse_click):
        # 如果暂停
        if self.showLittleMenu:
            if mouse_click[0]:
                if self.checkReturnClick(mouse_pos):
                    # 暂停 显示菜单
                    self.showLittleMenu = False
                elif self.checkRestartClick(mouse_pos):
                    self.done = True
                    self.next = c.LEVEL
                elif self.checkMainMenuClick(mouse_pos):
                    self.done = True
                    self.next = c.MAIN_MENU
                    self.persist = {c.CURRENT_TIME:0.0, c.LEVEL_NUM:c.START_LEVEL_NUM}
            return

        if self.zombie_start_time == 0:
            self.zombie_start_time = self.current_time
        elif len(self.zombie_list) > 0:
            data = self.zombie_list[0]
            if  data[0] <= (self.current_time - self.zombie_start_time):
                self.createZombie(data[1], data[2])
                self.zombie_list.remove(data)

        for i in range(self.map_y_len):
            self.bullet_groups[i].update(self.game_info)
            self.plant_groups[i].update(self.game_info)
            self.zombie_groups[i].update(self.game_info)
            self.hypno_zombie_groups[i].update(self.game_info)
            for zombie in self.hypno_zombie_groups[i]:
                if zombie.rect.x > c.SCREEN_WIDTH:
                    zombie.kill()

        self.head_group.update(self.game_info)
        self.sun_group.update(self.game_info)
        
        # wcb 添加
        # 检查是否点击菜单
        if mouse_click[0]:
            if self.checkLittleMenuClick(mouse_pos):
                # 暂停 显示菜单
                self.showLittleMenu = True
            elif self.checkShovelClick(mouse_pos):
                self.drag_shovel = not self.drag_shovel
                if self.drag_shovel:
                    # 小铲子要隐藏鼠标
                    pg.mouse.set_visible(False)
                else:
                    self.removeMouseImagePlus()
            elif self.drag_shovel:
                # 移出这地方的植物
                self.shovelRemovePlant(mouse_pos)
        
        # 拖动植物或者铲子
        if not self.drag_plant and mouse_pos and mouse_click[0]:
            result = self.menubar.checkCardClick(mouse_pos)
            if result:
                self.setupMouseImage(result[0], result[1])
        elif self.drag_plant:
            if mouse_click[1]:
                self.removeMouseImage()
            elif mouse_click[0]:
                if self.menubar.checkMenuBarClick(mouse_pos):
                    self.removeMouseImage()
                else:
                    self.addPlant()
            elif mouse_pos is None:
                self.setupHintImage()
        elif self.drag_shovel:
            if mouse_click[1]:
                self.removeMouseImagePlus()
        

        if self.produce_sun:
            if(self.current_time - self.sun_timer) > c.PRODUCE_SUN_INTERVAL:
                self.sun_timer = self.current_time
                map_x, map_y = self.map.getRandomMapIndex()
                x, y = self.map.getMapGridPos(map_x, map_y)
                self.sun_group.add(plant.Sun(x, 0, x, y))
        
        # 检查有没有捡到阳光
        if not self.drag_plant and not self.drag_shovel and mouse_pos and mouse_click[0]:
            for sun in self.sun_group:
                if sun.checkCollision(mouse_pos[0], mouse_pos[1]):
                    self.menubar.increaseSunValue(sun.sun_value)

        for car in self.cars:
            car.update(self.game_info)

        self.menubar.update(self.current_time)


        # 检查碰撞啥的
        self.checkBulletCollisions()
        self.checkZombieCollisions()
        self.checkPlants()
        self.checkCarCollisions()
        self.checkGameState()

    def createZombie(self, name, map_y):
        x, y = self.map.getMapGridPos(0, map_y)
        if name == c.NORMAL_ZOMBIE:
            self.zombie_groups[map_y].add(zombie.NormalZombie(c.ZOMBIE_START_X, y, self.head_group))
        elif name == c.CONEHEAD_ZOMBIE:
            self.zombie_groups[map_y].add(zombie.ConeHeadZombie(c.ZOMBIE_START_X, y, self.head_group))
        elif name == c.BUCKETHEAD_ZOMBIE:
            self.zombie_groups[map_y].add(zombie.BucketHeadZombie(c.ZOMBIE_START_X, y, self.head_group))
        elif name == c.FLAG_ZOMBIE:
            self.zombie_groups[map_y].add(zombie.FlagZombie(c.ZOMBIE_START_X, y, self.head_group))
        elif name == c.NEWSPAPER_ZOMBIE:
            self.zombie_groups[map_y].add(zombie.NewspaperZombie(c.ZOMBIE_START_X, y, self.head_group))

    def canSeedPlant(self):
        x, y = pg.mouse.get_pos()
        return self.map.showPlant(x, y)
        
    # 种植物
    def addPlant(self):
        pos = self.canSeedPlant()
        if pos is None:
            return

        if self.hint_image is None:
            self.setupHintImage()
        x, y = self.hint_rect.centerx, self.hint_rect.bottom
        map_x, map_y = self.map.getMapIndex(x, y)
        if self.plant_name == c.SUNFLOWER:
            new_plant = plant.SunFlower(x, y, self.sun_group)
        elif self.plant_name == c.PEASHOOTER:
            new_plant = plant.PeaShooter(x, y, self.bullet_groups[map_y])
        elif self.plant_name == c.SNOWPEASHOOTER:
            new_plant = plant.SnowPeaShooter(x, y, self.bullet_groups[map_y])
        elif self.plant_name == c.WALLNUT:
            new_plant = plant.WallNut(x, y)
        elif self.plant_name == c.CHERRYBOMB:
            new_plant = plant.CherryBomb(x, y)
        elif self.plant_name == c.THREEPEASHOOTER:
            new_plant = plant.ThreePeaShooter(x, y, self.bullet_groups, map_y)
        elif self.plant_name == c.REPEATERPEA:
            new_plant = plant.RepeaterPea(x, y, self.bullet_groups[map_y])
        elif self.plant_name == c.CHOMPER:
            new_plant = plant.Chomper(x, y)
        elif self.plant_name == c.PUFFSHROOM:
            new_plant = plant.PuffShroom(x, y, self.bullet_groups[map_y])
        elif self.plant_name == c.POTATOMINE:
            new_plant = plant.PotatoMine(x, y)
        elif self.plant_name == c.SQUASH:
            new_plant = plant.Squash(x, y)
        elif self.plant_name == c.SPIKEWEED:
            new_plant = plant.Spikeweed(x, y)
        elif self.plant_name == c.JALAPENO:
            new_plant = plant.Jalapeno(x, y)
        elif self.plant_name == c.SCAREDYSHROOM:
            new_plant = plant.ScaredyShroom(x, y, self.bullet_groups[map_y])
        elif self.plant_name == c.SUNSHROOM:
            new_plant = plant.SunShroom(x, y, self.sun_group)
        elif self.plant_name == c.ICESHROOM:
            new_plant = plant.IceShroom(x, y)
        elif self.plant_name == c.HYPNOSHROOM:
            new_plant = plant.HypnoShroom(x, y)
        elif self.plant_name == c.WALLNUTBOWLING:
            new_plant = plant.WallNutBowling(x, y, map_y, self)
        elif self.plant_name == c.REDWALLNUTBOWLING:
            new_plant = plant.RedWallNutBowling(x, y)

        if new_plant.can_sleep and self.background_type == c.BACKGROUND_DAY:
            new_plant.setSleep()
        self.plant_groups[map_y].add(new_plant)
        if self.bar_type == c.CHOOSEBAR_STATIC:
            self.menubar.decreaseSunValue(self.select_plant.sun_cost)
            self.menubar.setCardFrozenTime(self.plant_name)
        else:
            self.menubar.deleateCard(self.select_plant)

        if self.bar_type != c.CHOSSEBAR_BOWLING:
            self.map.setMapGridType(map_x, map_y, c.MAP_EXIST)
        self.removeMouseImage()
        #print('addPlant map[%d,%d], grid pos[%d, %d] pos[%d, %d]' % (map_x, map_y, x, y, pos[0], pos[1]))

    def setupHintImage(self):
        pos = self.canSeedPlant()
        if pos and self.mouse_image:
            if (self.hint_image and pos[0] == self.hint_rect.x and
                pos[1] == self.hint_rect.y):
                return
            width, height = self.mouse_rect.w, self.mouse_rect.h
            image = pg.Surface([width, height])
            image.blit(self.mouse_image, (0, 0), (0, 0, width, height))
            image.set_colorkey(c.BLACK)
            image.set_alpha(128)
            self.hint_image = image
            self.hint_rect = image.get_rect()
            self.hint_rect.centerx = pos[0]
            self.hint_rect.bottom = pos[1]
            self.hint_plant = True
        else:
            self.hint_plant = False

    def setupMouseImage(self, plant_name, select_plant):
        frame_list = tool.GFX[plant_name]
        if plant_name in tool.PLANT_RECT:
            data = tool.PLANT_RECT[plant_name]
            x, y, width, height = data['x'], data['y'], data['width'], data['height']
        else:
            x, y = 0, 0
            rect = frame_list[0].get_rect()
            width, height = rect.w, rect.h

        if (plant_name == c.POTATOMINE or plant_name == c.SQUASH or
            plant_name == c.SPIKEWEED or plant_name == c.JALAPENO or
            plant_name == c.SCAREDYSHROOM or plant_name == c.SUNSHROOM or
            plant_name == c.ICESHROOM or plant_name == c.HYPNOSHROOM or
            plant_name == c.WALLNUTBOWLING or plant_name == c.REDWALLNUTBOWLING):
            color = c.WHITE
        else:
            color = c.BLACK
        self.mouse_image = tool.get_image(frame_list[0], x, y, width, height, color, 1)
        self.mouse_rect = self.mouse_image.get_rect()
        pg.mouse.set_visible(False)
        self.drag_plant = True
        self.plant_name = plant_name
        self.select_plant = select_plant

    def removeMouseImage(self):
        pg.mouse.set_visible(True)
        self.drag_plant = False
        self.mouse_image = None
        self.hint_image = None
        self.hint_plant = False

    # 移除小铲子
    def removeMouseImagePlus(self):
        pg.mouse.set_visible(True)
        self.drag_shovel = False
        self.shovel_rect.x = self.shovel_positon[0]
        self.shovel_rect.y = self.shovel_positon[1]

    def checkBulletCollisions(self):
        collided_func = pg.sprite.collide_circle_ratio(0.7)
        for i in range(self.map_y_len):
            for bullet in self.bullet_groups[i]:
                if bullet.state == c.FLY:
                    zombie = pg.sprite.spritecollideany(bullet, self.zombie_groups[i], collided_func)
                    if zombie and zombie.state != c.DIE:
                        zombie.setDamage(bullet.damage, bullet.ice)
                        bullet.setExplode()
    
    def checkZombieCollisions(self):
        if self.bar_type == c.CHOSSEBAR_BOWLING:
            ratio = 0.6
        else:
            ratio = 0.7
        collided_func = pg.sprite.collide_circle_ratio(ratio)
        for i in range(self.map_y_len):
            hypo_zombies = []
            for zombie in self.zombie_groups[i]:
                if zombie.state != c.WALK:
                    continue
                plant = pg.sprite.spritecollideany(zombie, self.plant_groups[i], collided_func)
                if plant:
                    if plant.name == c.WALLNUTBOWLING:
                        if plant.canHit(i):
                            zombie.setDamage(c.WALLNUT_BOWLING_DAMAGE)
                            plant.changeDirection(i)
                    elif plant.name == c.REDWALLNUTBOWLING:
                        if plant.state == c.IDLE:
                            plant.setAttack()
                    elif plant.name != c.SPIKEWEED:
                        zombie.setAttack(plant)

            for hypno_zombie in self.hypno_zombie_groups[i]:
                if hypno_zombie.health <= 0:
                    continue
                zombie_list = pg.sprite.spritecollide(hypno_zombie,
                               self.zombie_groups[i], False,collided_func)
                for zombie in zombie_list:
                    if zombie.state == c.DIE:
                        continue
                    if zombie.state == c.WALK:
                        zombie.setAttack(hypno_zombie, False)
                    if hypno_zombie.state == c.WALK:
                        hypno_zombie.setAttack(zombie, False)

    def checkCarCollisions(self):
        collided_func = pg.sprite.collide_circle_ratio(0.8)
        for car in self.cars:
            zombies = pg.sprite.spritecollide(car, self.zombie_groups[car.map_y], False, collided_func)
            for zombie in zombies:
                if zombie and zombie.state != c.DIE:
                    car.setWalk()
                    zombie.setDie()
            if car.dead:
                self.cars.remove(car)

    def boomZombies(self, x, map_y, y_range, x_range):
        for i in range(self.map_y_len):
            if abs(i - map_y) > y_range:
                continue
            for zombie in self.zombie_groups[i]:
                if abs(zombie.rect.centerx - x) <= x_range:
                    zombie.setBoomDie()

    def freezeZombies(self, plant):
        for i in range(self.map_y_len):
            for zombie in self.zombie_groups[i]:
                if zombie.rect.centerx < c.SCREEN_WIDTH:
                    zombie.setFreeze(plant.trap_frames[0])

    def killPlant(self, plant):
        x, y = plant.getPosition()
        map_x, map_y = self.map.getMapIndex(x, y)
        if self.bar_type != c.CHOSSEBAR_BOWLING:
            self.map.setMapGridType(map_x, map_y, c.MAP_EMPTY)
        if (plant.name == c.CHERRYBOMB or plant.name == c.JALAPENO or
            (plant.name == c.POTATOMINE and not plant.is_init) or
            plant.name == c.REDWALLNUTBOWLING):
            self.boomZombies(plant.rect.centerx, map_y, plant.explode_y_range,
                            plant.explode_x_range)
        elif plant.name == c.ICESHROOM and plant.state != c.SLEEP:
            self.freezeZombies(plant)
        elif plant.name == c.HYPNOSHROOM and plant.state != c.SLEEP:
            zombie = plant.kill_zombie
            zombie.setHypno()
            _, map_y = self.map.getMapIndex(zombie.rect.centerx, zombie.rect.bottom)
            self.zombie_groups[map_y].remove(zombie)
            self.hypno_zombie_groups[map_y].add(zombie)
        plant.kill()

    def checkPlant(self, plant, i):
        zombie_len = len(self.zombie_groups[i])
        if plant.name == c.THREEPEASHOOTER:
            if plant.state == c.IDLE:
                if zombie_len > 0:
                    plant.setAttack()
                elif (i-1) >= 0 and len(self.zombie_groups[i-1]) > 0:
                    plant.setAttack()
                elif (i+1) < self.map_y_len and len(self.zombie_groups[i+1]) > 0:
                    plant.setAttack()
            elif plant.state == c.ATTACK:
                if zombie_len > 0:
                    pass
                elif (i-1) >= 0 and len(self.zombie_groups[i-1]) > 0:
                    pass
                elif (i+1) < self.map_y_len and len(self.zombie_groups[i+1]) > 0:
                    pass
                else:
                    plant.setIdle()
        elif plant.name == c.CHOMPER:
            for zombie in self.zombie_groups[i]:
                if plant.canAttack(zombie):
                    plant.setAttack(zombie, self.zombie_groups[i])
                    break
        elif plant.name == c.POTATOMINE:
            for zombie in self.zombie_groups[i]:
                if plant.canAttack(zombie):
                    plant.setAttack()
                    break
        elif plant.name == c.SQUASH:
            for zombie in self.zombie_groups[i]:
                if plant.canAttack(zombie):
                    plant.setAttack(zombie, self.zombie_groups[i])
                    break
        elif plant.name == c.SPIKEWEED:
            can_attack = False
            for zombie in self.zombie_groups[i]:
                if plant.canAttack(zombie):
                    can_attack = True
                    break
            if plant.state == c.IDLE and can_attack:
                plant.setAttack(self.zombie_groups[i])
            elif plant.state == c.ATTACK and not can_attack:
                plant.setIdle()
        elif plant.name == c.SCAREDYSHROOM:
            need_cry = False
            can_attack = False
            for zombie in self.zombie_groups[i]:
                if plant.needCry(zombie):
                    need_cry = True
                    break
                elif plant.canAttack(zombie):
                    can_attack = True
            if need_cry:
                if plant.state != c.CRY:
                    plant.setCry()
            elif can_attack:
                if plant.state != c.ATTACK:
                    plant.setAttack()
            elif plant.state != c.IDLE:
                plant.setIdle()
        elif(plant.name == c.WALLNUTBOWLING or
             plant.name == c.REDWALLNUTBOWLING):
            pass
        else:
            can_attack = False
            if (plant.state == c.IDLE and zombie_len > 0):
                for zombie in self.zombie_groups[i]:
                    if plant.canAttack(zombie):
                        can_attack = True
                        break
            if plant.state == c.IDLE and can_attack:
                plant.setAttack()
            elif (plant.state == c.ATTACK and not can_attack):
                plant.setIdle()

    def checkPlants(self):
        for i in range(self.map_y_len):
            for plant in self.plant_groups[i]:
                if plant.state != c.SLEEP:
                    self.checkPlant(plant, i)
                if plant.health <= 0:
                    self.killPlant(plant)

    def checkVictory(self):
        if len(self.zombie_list) > 0:
            return False
        for i in range(self.map_y_len):
            if len(self.zombie_groups[i]) > 0:
                return False
        return True
    
    def checkLose(self):
        for i in range(self.map_y_len):
            for zombie in self.zombie_groups[i]:
                if zombie.rect.right < 0:
                    return True
        return False

    def checkGameState(self):
        if self.checkVictory():
            self.game_info[c.LEVEL_NUM] += 1
            self.next = c.GAME_VICTORY
            self.done = True
        elif self.checkLose():
            self.next = c.GAME_LOSE
            self.done = True

    def drawMouseShow(self, surface):
        if self.hint_plant:
            surface.blit(self.hint_image, self.hint_rect)
        x, y = pg.mouse.get_pos()
        self.mouse_rect.centerx = x
        self.mouse_rect.centery = y
        surface.blit(self.mouse_image, self.mouse_rect)
    
    def drawMouseShowPlus(self, surface):
        x, y = pg.mouse.get_pos()
        self.shovel_rect.centerx = x
        self.shovel_rect.centery = y
        surface.blit(self.shovel, self.shovel_rect)

    def drawZombieFreezeTrap(self, i, surface):
        for zombie in self.zombie_groups[i]:
            zombie.drawFreezeTrap(surface)

    def draw(self, surface):
        self.level.blit(self.background, self.viewport, self.viewport)
        surface.blit(self.level, (0,0), self.viewport)
        if self.state == c.CHOOSE:
            self.panel.draw(surface)
        elif self.state == c.PLAY:
            if self.hasShovel:
                # 画铲子
                surface.blit(self.shovel_box, self.shovel_box_rect)
                surface.blit(self.shovel, self.shovel_rect)
            # 画小菜单
            surface.blit(self.little_menu, self.little_menu_rect)

            self.menubar.draw(surface)
            for i in range(self.map_y_len):
                self.plant_groups[i].draw(surface)
                self.zombie_groups[i].draw(surface)
                self.hypno_zombie_groups[i].draw(surface)
                self.bullet_groups[i].draw(surface)
                self.drawZombieFreezeTrap(i, surface)
            for car in self.cars:
                car.draw(surface)
            self.head_group.draw(surface)
            self.sun_group.draw(surface)

            if self.drag_plant:
                self.drawMouseShow(surface)
            
            if self.hasShovel and self.drag_shovel:
                self.drawMouseShowPlus(surface)

            if self.showLittleMenu:
                surface.blit(self.big_menu, self.big_menu_rect)
                surface.blit(self.return_button, self.return_button_rect)
                surface.blit(self.restart_button, self.restart_button_rect)
                surface.blit(self.mainMenu_button, self.mainMenu_button_rect)