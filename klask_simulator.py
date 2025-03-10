from enum import unique, Enum
from klask_constants import *

from Box2D.b2 import contactListener, world, edgeShape, pi
from dataclasses import dataclass
from random import choice
from math import dist
from PIL import Image

import pygame

class KlaskSimulator():
    @dataclass
    class FixtureUserData:
        name: str
        color: tuple

    @unique
    class GameStates(Enum):
        PLAYING = 0
        P1_WIN = 1
        P2_WIN = 2

    class KlaskContactListener(contactListener):
        def __init__(self):
            contactListener.__init__(self)

            # List of puck to biscuit collisions
            self.collision_list = []

        def PreSolve(self, contact, oldManifold):
            # Change the characteristics of the contact before the collision response is calculated

            # Check if a collision with a static body
            if contact.fixtureA.userData is None or contact.fixtureB.userData is None:
                return
            
            names = {contact.fixtureA.userData.name : contact.fixtureA, contact.fixtureB.userData.name : contact.fixtureB}
            keys = list(names.keys())

            # Determine if collision is between puck and biscuit
            if any(["puck" in x for x in keys]) and any(["biscuit" in x for x in keys]):
               
                # Retrieve fixtures
                puck = names[min(keys, key=len)]
                biscuit = names[max(keys, key=len)]

                # Disable contact
                contact.enabled = False

                # Mark biscuit for deletion
                self.collision_list.append((puck, biscuit))

    def __init__(self, render_mode="human", length_scaler=100, pixels_per_meter=20, target_fps=120):
        # Store user parameters
        self.render_mode = render_mode              # "human" shows the rendered frame at the specificed frame rate. 
        self.length_scaler = length_scaler          # Box2D doesn't simulate small objects well. Scale klask_constants length values into the meter range.
        self.pixels_per_meter = pixels_per_meter    # Box2D uses 1 pixel / 1 meter by default. Change for better viewing.
        self.target_fps = target_fps

        # Compute additional parameters
        self.time_step = 1.0 / self.target_fps
        self.screen_width = KG_BOARD_WIDTH * self.pixels_per_meter * self.length_scaler
        self.screen_height = KG_BOARD_HEIGHT * self.pixels_per_meter * self.length_scaler

        # PyGame variables
        self.screen = None
        self.clock = None
        self.game_board = None

        # Box2D variables
        self.world = None
        self.bodies = None
        self.magnet_bodies = None
        self.render_bodies = None

    def reset(self, ball_start_position="random"):
        # Create world
        self.world = world(contactListener=self.KlaskContactListener(), gravity=(0, 0), doSleep=True)

        # Create static bodies
        self.bodies = {}

        self.bodies["wall_bottom"] = self.world.CreateStaticBody(position=(0, 0), shapes=edgeShape(vertices=[(0,0), (KG_BOARD_WIDTH * self.length_scaler, 0)]))
        self.bodies["wall_left"] = self.world.CreateStaticBody(position=(0, 0), shapes=edgeShape(vertices=[(0,0), (0, KG_BOARD_HEIGHT * self.length_scaler)]))
        self.bodies["wall_right"] = self.world.CreateStaticBody(position=(0, 0), shapes=edgeShape(vertices=[(KG_BOARD_WIDTH * self.length_scaler, 0), (KG_BOARD_WIDTH * self.length_scaler, KG_BOARD_HEIGHT * self.length_scaler)]))
        self.bodies["wall_top"] = self.world.CreateStaticBody(position=(0, 0), shapes=edgeShape(vertices=[(0, KG_BOARD_HEIGHT * self.length_scaler), (KG_BOARD_WIDTH * self.length_scaler, KG_BOARD_HEIGHT * self.length_scaler)]))
        self.bodies["divider_left"] = self.world.CreateStaticBody(position=(0, 0), shapes=edgeShape(vertices=[(KG_BOARD_WIDTH * self.length_scaler / 2 - KG_DIVIDER_WIDTH * self.length_scaler / 2, 0), (KG_BOARD_WIDTH * self.length_scaler / 2 - KG_DIVIDER_WIDTH * self.length_scaler / 2, KG_BOARD_HEIGHT * self.length_scaler)]))
        self.bodies["divider_right"] = self.world.CreateStaticBody(position=(0, 0), shapes=edgeShape(vertices=[(KG_BOARD_WIDTH * self.length_scaler / 2 + KG_DIVIDER_WIDTH * self.length_scaler / 2, 0), (KG_BOARD_WIDTH * self.length_scaler / 2 + KG_DIVIDER_WIDTH * self.length_scaler / 2, KG_BOARD_HEIGHT * self.length_scaler)]))
        self.bodies["ground"] = self.world.CreateStaticBody(position=(0,0))
        
        self.bodies["divider_left"].fixtures[0].filterData.categoryBits=0x0010
        self.bodies["divider_right"].fixtures[0].filterData.categoryBits=0x0010

        # Create dynamic bodies
        self.bodies["puck1"] = self.world.CreateDynamicBody(position=(KG_BOARD_WIDTH * self.length_scaler / 3, KG_BOARD_HEIGHT * self.length_scaler / 2), fixedRotation=True, bullet=True)
        self.bodies["puck1"].CreateCircleFixture(radius=KG_PUCK_RADIUS * self.length_scaler, restitution=0.0, userData=self.FixtureUserData("puck1", KG_PUCK_COLOR), density=KG_PUCK_MASS / (pi * (KG_PUCK_RADIUS * self.length_scaler)**2))

        self.bodies["puck2"] = self.world.CreateDynamicBody(position=(2 * KG_BOARD_WIDTH * self.length_scaler / 3, KG_BOARD_HEIGHT * self.length_scaler / 2), fixedRotation=True, bullet=True)
        self.bodies["puck2"].CreateCircleFixture(radius=KG_PUCK_RADIUS * self.length_scaler, restitution=0.0, userData=self.FixtureUserData("puck2", KG_PUCK_COLOR), density=KG_PUCK_MASS / (pi * (KG_PUCK_RADIUS * self.length_scaler)**2))

        ball_start_positions = {"top_right" : (KG_BOARD_WIDTH * self.length_scaler - KG_CORNER_RADIUS * self.length_scaler / 2, KG_BOARD_HEIGHT * self.length_scaler - KG_CORNER_RADIUS * self.length_scaler / 2),
                                "bottom_right" : (KG_BOARD_WIDTH * self.length_scaler - KG_CORNER_RADIUS * self.length_scaler / 2, KG_CORNER_RADIUS * self.length_scaler / 2),
                                "top_left" : (KG_CORNER_RADIUS * self.length_scaler / 2, KG_BOARD_HEIGHT * self.length_scaler - KG_CORNER_RADIUS * self.length_scaler / 2),
                                "bottom_left" : (KG_CORNER_RADIUS * self.length_scaler / 2, KG_CORNER_RADIUS * self.length_scaler / 2)}
        ball_start_positions["random"] = choice(list(ball_start_positions.values()))

        self.bodies["ball"] = self.world.CreateDynamicBody(position=ball_start_positions[ball_start_position], bullet=True)
        self.bodies["ball"].CreateCircleFixture(radius=KG_BALL_RADIUS * self.length_scaler, restitution=KG_RESTITUTION_COEF, userData=self.FixtureUserData("ball", KG_BALL_COLOR), density=KG_BALL_MASS / (pi * (KG_BALL_RADIUS * self.length_scaler)**2), maskBits=0xFF0F)

        self.bodies["biscuit1"] = self.world.CreateDynamicBody(position=(KG_BOARD_WIDTH * self.length_scaler / 2, KG_BOARD_HEIGHT * self.length_scaler / 2), bullet=True)
        self.bodies["biscuit1"].CreateCircleFixture(radius=KG_BISCUIT_RADIUS * self.length_scaler, restitution=KG_RESTITUTION_COEF, userData=self.FixtureUserData("biscuit1", KG_BISCUIT_COLOR), density=KG_BISCUIT_MASS / (pi * (KG_BISCUIT_RADIUS * self.length_scaler)**2), maskBits=0xFF0F)

        self.bodies["biscuit2"] = self.world.CreateDynamicBody(position=(KG_BOARD_WIDTH * self.length_scaler / 2, (KG_BOARD_HEIGHT * self.length_scaler / 2) + KG_BISCUIT_START_OFFSET_Y * self.length_scaler), bullet=True)
        self.bodies["biscuit2"].CreateCircleFixture(radius=KG_BISCUIT_RADIUS * self.length_scaler, restitution=KG_RESTITUTION_COEF, userData=self.FixtureUserData("biscuit2", KG_BISCUIT_COLOR), density=KG_BISCUIT_MASS / (pi * (KG_BISCUIT_RADIUS * self.length_scaler)**2), maskBits=0xFF0F)

        self.bodies["biscuit3"] = self.world.CreateDynamicBody(position=(KG_BOARD_WIDTH * self.length_scaler / 2, (KG_BOARD_HEIGHT * self.length_scaler / 2) - KG_BISCUIT_START_OFFSET_Y * self.length_scaler), bullet=True)
        self.bodies["biscuit3"].CreateCircleFixture(radius=KG_BISCUIT_RADIUS * self.length_scaler, restitution=KG_RESTITUTION_COEF, userData=self.FixtureUserData("biscuit3", KG_BISCUIT_COLOR), density=KG_BISCUIT_MASS / (pi * (KG_BISCUIT_RADIUS * self.length_scaler)**2), maskBits=0xFF0F)

        # Create groupings
        self.magnet_bodies = ["biscuit1", "biscuit2", "biscuit3"]
        self.render_bodies = ["puck1", "puck2", "ball", "biscuit1", "biscuit2", "biscuit3"]

        # Create joints
        self.world.CreateFrictionJoint(bodyA=self.bodies["ground"], bodyB=self.bodies["ball"], maxForce=self.bodies["ball"].mass*KG_GRAVITY)
        self.world.CreateFrictionJoint(bodyA=self.bodies["ground"], bodyB=self.bodies["biscuit1"], maxForce=self.bodies["biscuit1"].mass*KG_GRAVITY)
        self.world.CreateFrictionJoint(bodyA=self.bodies["ground"], bodyB=self.bodies["biscuit2"], maxForce=self.bodies["biscuit2"].mass*KG_GRAVITY)
        self.world.CreateFrictionJoint(bodyA=self.bodies["ground"], bodyB=self.bodies["biscuit3"], maxForce=self.bodies["biscuit3"].mass*KG_GRAVITY)

        # Render frame
        self.__render_frame()

    def step(self, action1, action2):
        # Apply forces to puck1
        self.bodies["puck1"].ApplyLinearImpulse(action1, self.bodies["puck1"].position, wake=True)

        # Apply forces to puck2
        self.bodies["puck2"].ApplyLinearImpulse(action2, self.bodies["puck2"].position, wake=True)

        # Apply magnetic forces to biscuits
        for body_key in self.magnet_bodies:
            self.__apply_magnet_force(self.bodies["puck1"], self.bodies[body_key])
            self.__apply_magnet_force(self.bodies["puck2"], self.bodies[body_key])

        # Step the physics simulation
        self.world.Step(self.time_step, 10, 10)

        # Handle resultant puck to biscuit collisions
        while self.world.contactListener.collision_list:
            # Retrieve fixtures
            puck, biscuit = self.world.contactListener.collision_list.pop()
            
            # Compute new biscuit position
            position = (biscuit.body.position - puck.body.position)
            position.Normalize()
            position = position * (puck.shape.radius + biscuit.shape.radius)

            # Create new biscuit fixture
            new_biscuit = puck.body.CreateCircleFixture(radius=biscuit.shape.radius, pos=position, userData=biscuit.userData)
            new_biscuit.sensor = True

            # Remove old biscuit body
            self.magnet_bodies.remove(biscuit.userData.name)
            self.render_bodies.remove(biscuit.userData.name)
            self.world.DestroyBody(biscuit.body)

        # Render the resulting frame
        self.__render_frame()

        # Update game states
        states = self.__determine_game_state()

    def __determine_game_state(self):
        # Determines the state of the game
        states = []

        # Determine puck 1 win conditions
        if self.__is_in_goal(self.bodies["puck2"])[1] or self.__is_in_goal(self.bodies["ball"])[1] or self.__num_biscuits_on_puck(self.bodies["puck2"]) >= 2:
            states.append(self.GameStates.P1_WIN)
        
        # Determine puck 2 win conditions
        if self.__is_in_goal(self.bodies["puck1"])[0] or self.__is_in_goal(self.bodies["ball"])[0] or self.__num_biscuits_on_puck(self.bodies["puck1"]) >= 2:
            states.append(self.GameStates.P2_WIN)

        # Determine if win condition was met
        if not len(states):
            states.append(self.GameStates.PLAYING)

        return states

    def __num_biscuits_on_puck(self, puck_body):
        # Get the number of biscuits attached to a puck
        return len(puck_body.fixtures) - 1
    
    def __is_in_goal(self, body):
        # Determine if the puck/ball/biscuit is inside the goal

        # Define return type, idx 0 is left goal, idx 1 is right goal
        response = [False, False]
        
        # Determine if body in left goal
        if dist(body.position, (KG_GOAL_OFFSET_X * self.length_scaler, (KG_BOARD_HEIGHT / 2) * self.length_scaler)) <= KG_GOAL_RADIUS * self.length_scaler:
            response[0] = True
    
        # Determine if body in right goal
        if dist(body.position, ((KG_BOARD_WIDTH - KG_GOAL_OFFSET_X) * self.length_scaler, (KG_BOARD_HEIGHT / 2) * self.length_scaler)) <= KG_GOAL_RADIUS * self.length_scaler:
            response[1] = True
    
        return response

    def __apply_magnet_force(self, puck_body, biscuit_body):
        # Get the distance vector between the two bodies
        force = (puck_body.position - biscuit_body.position)

        # Normalize the distance vector and get the Euclidean distance between the two bodies
        separation = force.Normalize()

        # Compute magnetic force between two points
        force *= (KG_PERMEABILITY_AIR * KG_MAGNETIC_CHARGE**2) / (4 * pi * separation**2)

        # Apply forces to bodies
        biscuit_body.ApplyForceToCenter(force=force, wake=True)

    def __render_frame(self):
        # Setup PyGame if needed
        if self.screen is None and self.render_mode == "human":
            self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
            pygame.display.set_caption('Klask Simulator')
        if self.clock is None and self.render_mode == "human":
            self.clock = pygame.time.Clock()

        # Render game board surface
        if self.game_board is None:
            self.game_board = self.__render_game_board()
        
        # Create a new surface
        surface = pygame.Surface((self.screen_width, self.screen_height), 0, 32)

        # Display the game board
        surface.blit(self.game_board, (0,0))

        # Display the bodies
        for body_key in self.render_bodies:
            for fixture in self.bodies[body_key]:
                self.__render_circle_fixture(fixture, surface)

        # Display to screen if needed
        if self.render_mode == "human":
            # Display surface to screen
            self.screen.blit(surface, (0,0))
            pygame.event.pump()
            pygame.display.flip()

            # Manage frame rate
            self.clock.tick(self.target_fps)

        # Return rendered frame
        return surface

    def __render_circle_fixture(self, circle, surface):
        # Render a circle fixture onto a surface
        position = circle.body.transform * circle.shape.pos * self.pixels_per_meter
        position = (position[0], self.screen_height - position[1])
        pygame.draw.circle(surface, circle.userData.color, [int(x) for x in position], int(circle.shape.radius * self.pixels_per_meter))

    def __render_game_board(self):
        # Create a new surface
        surface = pygame.Surface((self.screen_width, self.screen_height), 0, 32)

        # Render Game Board
        pygame.draw.rect(surface, KG_BOARD_COLOR, pygame.Rect(0, 0, self.screen_width, self.screen_height))

        # Render Goals
        pygame.draw.circle(surface, KG_GOAL_COLOR, (KG_GOAL_OFFSET_X * self.pixels_per_meter * self.length_scaler, (KG_BOARD_HEIGHT / 2) * self.pixels_per_meter * self.length_scaler), KG_GOAL_RADIUS * self.pixels_per_meter * self.length_scaler)
        pygame.draw.circle(surface, KG_GOAL_COLOR, ((KG_BOARD_WIDTH - KG_GOAL_OFFSET_X) * self.pixels_per_meter * self.length_scaler, (KG_BOARD_HEIGHT / 2) * self.pixels_per_meter * self.length_scaler), KG_GOAL_RADIUS * self.pixels_per_meter * self.length_scaler)

        # Render Corners
        pygame.draw.circle(surface, KG_CORNER_COLOR, (0, 0), KG_CORNER_RADIUS * self.pixels_per_meter * self.length_scaler, int(KG_CORNER_THICKNESS * self.pixels_per_meter * self.length_scaler))
        pygame.draw.circle(surface, KG_CORNER_COLOR, (KG_BOARD_WIDTH * self.pixels_per_meter * self.length_scaler, 0), KG_CORNER_RADIUS * self.pixels_per_meter * self.length_scaler, int(KG_CORNER_THICKNESS * self.pixels_per_meter * self.length_scaler))
        pygame.draw.circle(surface, KG_CORNER_COLOR, (KG_BOARD_WIDTH * self.pixels_per_meter * self.length_scaler, KG_BOARD_HEIGHT * self.pixels_per_meter * self.length_scaler), KG_CORNER_RADIUS * self.pixels_per_meter * self.length_scaler, int(KG_CORNER_THICKNESS * self.pixels_per_meter * self.length_scaler))
        pygame.draw.circle(surface, KG_CORNER_COLOR, (0, KG_BOARD_HEIGHT * self.pixels_per_meter * self.length_scaler), KG_CORNER_RADIUS * self.pixels_per_meter * self.length_scaler, int(KG_CORNER_THICKNESS * self.pixels_per_meter * self.length_scaler))

        # Render Biscuit Start
        pygame.draw.circle(surface, KG_BISCUIT_START_COLOR, ((KG_BOARD_WIDTH / 2) * self.pixels_per_meter * self.length_scaler, (KG_BOARD_HEIGHT / 2) * self.pixels_per_meter * self.length_scaler), KG_BISCUIT_START_RADIUS * self.pixels_per_meter * self.length_scaler, int(KG_BISCUIT_START_THICKNESS * self.pixels_per_meter * self.length_scaler))
        pygame.draw.circle(surface, KG_BISCUIT_START_COLOR, ((KG_BOARD_WIDTH / 2) * self.pixels_per_meter * self.length_scaler, ((KG_BOARD_HEIGHT / 2) - KG_BISCUIT_START_OFFSET_Y) * self.pixels_per_meter * self.length_scaler), KG_BISCUIT_START_RADIUS * self.pixels_per_meter * self.length_scaler, int(KG_BISCUIT_START_THICKNESS * self.pixels_per_meter * self.length_scaler))
        pygame.draw.circle(surface, KG_BISCUIT_START_COLOR, ((KG_BOARD_WIDTH / 2) * self.pixels_per_meter * self.length_scaler, ((KG_BOARD_HEIGHT / 2) + KG_BISCUIT_START_OFFSET_Y) * self.pixels_per_meter * self.length_scaler), KG_BISCUIT_START_RADIUS * self.pixels_per_meter * self.length_scaler, int(KG_BISCUIT_START_THICKNESS * self.pixels_per_meter * self.length_scaler))

        # Render Game Board Logo
        pil_image = Image.open(KG_BOARD_LOGO_PATH)
        logo = pygame.image.fromstring(pil_image.tobytes("raw", "RGBA"), pil_image.size, "RGBA")
        logo = pygame.transform.scale(logo, (KG_BOARD_LOGO_WIDTH * self.pixels_per_meter * self.length_scaler, KG_BOARD_LOGO_HEIGHT * self.pixels_per_meter * self.length_scaler))

        logo_right = pygame.transform.rotate(logo, 90)
        logo_left = pygame.transform.rotate(logo, -90)

        surface.blit(logo_left, (((KG_BOARD_WIDTH / 3) - KG_BOARD_LOGO_HEIGHT) * self.pixels_per_meter * self.length_scaler, ((KG_BOARD_HEIGHT / 2) - (KG_BOARD_LOGO_WIDTH / 2)) * self.pixels_per_meter * self.length_scaler))
        surface.blit(logo_right, ((2 * (KG_BOARD_WIDTH / 3)) * self.pixels_per_meter * self.length_scaler, ((KG_BOARD_HEIGHT / 2) - (KG_BOARD_LOGO_WIDTH / 2)) * self.pixels_per_meter * self.length_scaler))

        # Return surface
        return surface

    def close(self):
        if self.screen is not None:
            pygame.quit()
