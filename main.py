import pygame
import numpy as np
import random
from point_mass import PointMass, generate_pointmass, points_colliding
from planet import Planet


class Window:
    def __init__(self, screen_size=(800, 800), point_mass_list=None) -> None:
        """_summary_

        Args:
            screen_size (tuple, optional): _description_. Defaults to (800, 800).
            point_mass_list (_type_, optional): _description_. Defaults to None.
        """

        # Dictionary of all planets and their masses(kg) and colours(rgb)
        # https://nssdc.gsfc.nasa.gov/planetary/factsheet/
        self.planet_list = [
            Planet("Sun", 2e30, (255, 100, 0)),
            Planet("Mercury", 0.330e24, (255, 50, 50)),
            Planet("Venus", 4.87e24, (255, 144, 33)),
            Planet("Earth", 5.97e24, (90, 255, 28)),
            Planet("Mars", 0.642e24, (255, 132, 79)),
            Planet("Jupiter", 1898e24, (156, 81, 48)),
            Planet("Saturn", 568e24, (156, 119, 72)),
            Planet("Uranus", 86.8e24, (61, 96, 156)),
            Planet("Neptune", 102e24, (0, 0, 255)),
            Planet("Pluto", 0.0130e24, (204, 215, 222))
        ]

        self.selected_planet = 1
        self.number_of_shots_taken = 0

        self.WINDOW_WIDTH, self.WINDOW_HEIGHT = screen_size
        pygame.init()
        self.SCREEN = pygame.display.set_mode(
            [self.WINDOW_WIDTH, self.WINDOW_HEIGHT])
        self.CLOCK = pygame.time.Clock()
        self.FPS = 60

        # Sufficiently small arbritrary number for first frame. Redefined in main loop.
        self.delta_t = 1/self.FPS
        self.time_mult = 1e6
        self.seconds_passed = 0

        self.COLLISION_ON = True

        # Remains constant until final scenario, multiplicative.
        self.NOTIFICATION_FADEOUT = 0.98

        self.notification_opacity = 1

        self.notification_text = ""

        self.G = 6.67e-11  # gravitational constant
        self.AU = 1.5e11  # one astronomical unit in metres
        PIXELS_PER_AU = 200

        self.slingshot_power = 2e2  # Multiplies the power the slingshot input has
        self.mouse_click_coordinate_pixels = [None, None]

        self.AU_PIXELS_CONVERSION = PIXELS_PER_AU / self.AU

        self.TEXT_FONT = pygame.freetype.Font('COMIC.ttf', 30)

        self.object_list = []

        # Max velocity reached in a scenario. Incentivises gravity slingshot.
        self.max_velocity = 0

        # scales off of number of shots taken and max_velocity.
        self.final_score = 0
        self.sandbox_mode = False  # If true, the game cannot progress past scenario one
        self.scenario_won = False
        self.scenario = 1  # default scenario
        self.start_scenario()

    def start_scenario(self):
        if self.sandbox_mode:
            self.show_notification("Sandbox mode Active")
            return

        self.object_list = []  # Refresh object list

        if self.number_of_shots_taken > 0:
            self.final_score += (self.max_velocity *
                                 1e3) // self.number_of_shots_taken

        self.number_of_shots_taken = 0
        self.max_velocity = 0

        if self.scenario == 1:

            self.show_notification(
                "Binary Earths Orbiting the Sun. Target: The Sun")

            Earth = self.planet_list[3]
            Sun = self.planet_list[0]

            self.object_list = [
                PointMass([-30e3, 0], [2*self.AU, 3*self.AU],
                          Earth.mass, Earth.colour),
                PointMass([0, 0], [2*self.AU, 2*self.AU], Sun.mass,
                          Sun.colour, is_target=True),
                PointMass([+30e3, 0], [2*self.AU, 1*self.AU],
                          Earth.mass, Earth.colour)
            ]

        elif self.scenario == 2:
            # generate range(N) random pointmasses
            self.object_list = [generate_pointmass(
                (0, self.WINDOW_WIDTH/self.AU_PIXELS_CONVERSION), (0, self.WINDOW_HEIGHT/self.AU_PIXELS_CONVERSION)) for _ in range(100)]

            self.NOTIFICATION_FADEOUT = 1
            # self.show_notification(
            #    f"You Won! Final Score: {round(self.final_score)}. Press R to Restart")

    def main_loop(self) -> None:
        """_summary_
        """
        running = True

        while running:
            self.SCREEN.fill((0, 0, 0))

            self.draw_scale_bar()

            running = self.event_handler()

            for object in self.object_list:

                if object.is_deleted:
                    continue

                pixel_x = object.positions[0] * self.AU_PIXELS_CONVERSION
                pixel_y = self.WINDOW_HEIGHT - \
                    object.positions[1] * self.AU_PIXELS_CONVERSION

                flipped_y_position = np.asarray(
                    [pixel_x, pixel_y])

                pygame.draw.circle(
                    self.SCREEN, object.colour, flipped_y_position, object.radius*self.AU_PIXELS_CONVERSION)

                # updates velocity and position based on gravitational attraction
                self.update_object(object)

            # Objects not removed mid-iteration to avoid issues
            for object in self.object_list:
                if object.is_deleted:
                    self.object_list.remove(object)

            self.show_notification()

            if self.scenario_won:
                self.scenario_won = False
                self.scenario += 1
                self.start_scenario()

            pygame.display.flip()  # update drawing canvas

            self.delta_t = self.CLOCK.tick(self.FPS) * 1e-3

    def update_object_collision(self, object1, object2):
        # Bug where if two objects are the same size, they both disappear

        larger_object = (object1, object2)[
            np.argmax((object1.mass, object2.mass))]

        smaller_object = (object1, object2)[
            np.argmin((object1.mass, object2.mass))]

        smaller_object.is_deleted = True

        combined_mass = object1.mass + object2.mass

        # Inelastic collision / conservation of momentum
        larger_object.velocities = (
            object1.mass*object1.velocities + object2.mass*object2.velocities) / combined_mass

        larger_object.mass = combined_mass

        # Smaller object scaled by 1/4 to more accurately model absorption and to limit exponential growth
        larger_object.radius = larger_object.radius + smaller_object.radius//4

        # If player-spawned object collided with target
        target_collision = larger_object.is_target is True or smaller_object.is_target is True
        player_collided = larger_object.player_spawned or smaller_object.player_spawned
        if target_collision and player_collided:
            self.scenario_won = True

    def update_object(self, object: PointMass) -> None:
        """_summary_

        Args:
            object (PointMass): _description_
        """

        """
        ΔVx = GMcos(θ)/(r*t)
        ΔVy = GMsin(θ)/(r*t)
        """

        for other_object in self.object_list:
            if other_object.id == object.id:  # Do not compute force of object on itself
                continue

            if self.COLLISION_ON:
                if points_colliding(object, other_object):

                    # handles object collision logic
                    self.update_object_collision(object, other_object)

                    # Returns here to avoid unintended behaviour from deleting object. May cause time inaccuracies if low fps or many collisions
                    return

            dx, dy = other_object.positions - object.positions

            # Quadrant-based arctan. Corrects for discrepancies based on sign flipping
            angle = np.arctan2(dy, dx)

            separation = np.hypot(dx, dy)

            # Sums the velocities due to pull from each mass. Same as net forces.
            delta_v = (self.G * other_object.mass *
                       self.delta_t) / (separation**2)

            if delta_v > self.max_velocity and True in (object.player_spawned, other_object.player_spawned):
                self.max_velocity = delta_v

            delta_vx = delta_v * np.cos(angle) * self.time_mult
            delta_vy = delta_v * np.sin(angle) * self.time_mult

            object.velocities += np.asarray([delta_vx,
                                            delta_vy], dtype=np.float64)

        # Updates positions with *Net* velocities, hence why outside the loop. Reduces number of calculations per frame.
        object.positions = object.positions + \
            (object.velocities * self.delta_t * self.time_mult)

    def calculate_slingshot_velocity(self) -> tuple:
        # function name likely needs changing
        # refers to the slingshot motion of spawning new planets
        mouse_x, mouse_y = pygame.mouse.get_pos()
        stored_x, stored_y = self.mouse_click_coordinate_pixels

        if None in self.mouse_click_coordinate_pixels:
            return None

        dy = stored_y - mouse_y
        dx = stored_x - mouse_x

        au_x = stored_x / self.AU_PIXELS_CONVERSION
        au_y = (self.WINDOW_HEIGHT - stored_y) / self.AU_PIXELS_CONVERSION

        coordinates_au = [au_x, au_y]

        vx = dx * self.slingshot_power
        vy = - dy * self.slingshot_power

        velocities = [vx, vy]

        return au_x, au_y, vx, vy

    def mouse_event_handler(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            left_mouse_pressed = pygame.mouse.get_pressed()[0]

            if left_mouse_pressed:

                mouse_x, mouse_y = pygame.mouse.get_pos()

                self.mouse_click_coordinate_pixels = [mouse_x, mouse_y]

        elif event.type == pygame.MOUSEBUTTONUP:
            left_mouse_released = not pygame.mouse.get_pressed()[0]

            if left_mouse_released:

                au_vel = self.calculate_slingshot_velocity()

                # if no stored coordinates
                if au_vel is None:
                    return

                au_x, au_y, vx, vy = au_vel

                planet = self.planet_list[self.selected_planet]

                self.object_list.append(
                    PointMass([vx, vy], [au_x,
                                         au_y], planet.mass, radius=7e9, colour=planet.colour, player_spawned=True)
                )

                self.mouse_click_coordinate_pixels = [None, None]
                self.number_of_shots_taken += 1

    def keyboard_event_handler(self, event):
        if event.type == pygame.KEYDOWN:

            # If escape is pressed when lmb is held down
            if event.key == pygame.K_ESCAPE and pygame.mouse.get_pressed()[0] == True:
                self.mouse_click_coordinate_pixels = [
                    None, None]  # Cancel action
                self.show_notification("Input Cancelled")

            elif event.key == pygame.K_COMMA:
                self.time_mult /= 5
                self.show_notification(f"x{self.time_mult:.0f} Speed")

            elif event.key == pygame.K_PERIOD:
                self.time_mult *= 5
                self.show_notification(f"x{self.time_mult:.0f} Speed")

            elif event.unicode.isdigit():
                self.selected_planet = int(event.unicode)
                planet = self.planet_list[self.selected_planet]
                self.show_notification(
                    f"{planet.name}: {planet.mass:.0e}Kg")

            elif event.key == pygame.K_r:
                # restart game
                self.seconds_passed = 0
                self.notification_opacity = 0.98
                self.max_velocity = 0
                self.number_of_shots_taken = 0
                self.scenario = 1
                self.start_scenario()

    def event_handler(self) -> bool:

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            self.mouse_event_handler(event)

            self.keyboard_event_handler(event)

        if not None in self.mouse_click_coordinate_pixels:
            self.draw_arrow(np.array(self.mouse_click_coordinate_pixels), np.array(
                pygame.mouse.get_pos()))

        return True

    def draw_scale_bar(self) -> None:
        """_summary_
        """

        # Very ugly. Needs fixing.

        x1 = 50
        x2 = x1 + (self.AU * self.AU_PIXELS_CONVERSION)

        y = 50
        half_arm_width = 25

        pygame.draw.line(self.SCREEN, (255, 255, 255),
                         (x1, self.WINDOW_HEIGHT-y), (x2, self.WINDOW_HEIGHT-y))
        pygame.draw.line(self.SCREEN, (255, 255, 255), (x1, self.WINDOW_HEIGHT -
                         y-half_arm_width), (x1, self.WINDOW_HEIGHT-y+half_arm_width))
        pygame.draw.line(self.SCREEN, (255, 255, 255), (x2, self.WINDOW_HEIGHT -
                         y-half_arm_width), (x2, self.WINDOW_HEIGHT-y+half_arm_width))
        self.TEXT_FONT.render_to(self.SCREEN, ((
            x2-x1)/2, self.WINDOW_HEIGHT-y-half_arm_width), '1 AU', (250, 250, 250))

        self.seconds_passed += self.delta_t * self.time_mult

        years_passed = self.seconds_passed / (3600*24*365)

        months_passed = 12 * (years_passed % 1)

        years_passed = self.seconds_passed / (3600*24*365)

        self.TEXT_FONT.render_to(self.SCREEN, (
            x2+50, self.WINDOW_HEIGHT-2*half_arm_width), f"{np.floor(years_passed)} Years {np.floor(months_passed)} Month(s) Passed", (250, 250, 250))
        self.TEXT_FONT.render_to(self.SCREEN, (
            x2+50, self.WINDOW_HEIGHT-4*half_arm_width), f"{self.number_of_shots_taken} Shots Taken", (250, 250, 250))

    def show_notification(self, text=None) -> None:
        x = 10
        y = 50

        if text:
            self.notification_text = text
            self.notification_opacity = 1

        color = np.array((250, 250, 250), dtype=np.int32) * \
            self.notification_opacity
        if any(color) < 0:
            self.notification_opacity = 1
            self.notification_text = ""

        self.TEXT_FONT.render_to(
            self.SCREEN, (x, y), self.notification_text, color)

        self.notification_opacity *= self.NOTIFICATION_FADEOUT

    def draw_arrow(self, start_pos, end_pos) -> None:

        new_end_pos = (2*start_pos - end_pos)

        pygame.draw.line(self.SCREEN, (255, 255, 255), start_pos, new_end_pos)

        _, _, vx, vy = self.calculate_slingshot_velocity()

        velocity = f"{round(np.hypot(vx, vy)*1e-3)}Km/s"

        self.TEXT_FONT.render_to(
            self.SCREEN, new_end_pos + 10, str(velocity), (250, 250, 250))


if __name__ == '__main__':

    # UI will likely malfunction with increasing screen_size for now.
    screen_size = (800, 800)
    Window(screen_size, []).main_loop()
