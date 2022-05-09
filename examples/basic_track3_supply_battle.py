import time
import random
import argparse

from rich.progress import track
from rich.console import Console

console = Console()

from inspirai_fps import Game, ActionVariable
from inspirai_fps.utils import get_position


parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=50051)
parser.add_argument("--timeout", type=int, default=10)
parser.add_argument("--map-id", type=int, default=1)
parser.add_argument("--random-seed", type=int, default=0)
parser.add_argument("--num-episodes", type=int, default=1)
parser.add_argument("--engine-dir", type=str, default="../unity3d")
parser.add_argument("--map-dir", type=str, default="../data")
parser.add_argument("--num-agents", type=int, default=1)
parser.add_argument("--use-depth-map", action="store_true")
parser.add_argument("--record", action="store_true")
parser.add_argument("--replay-suffix", type=str, default="")
parser.add_argument("--start-location", type=float, nargs=3, default=[0, 0, 0])
parser.add_argument("--walk-speed", type=float, default=1)
args = parser.parse_args()


# Define a random policy
def my_policy(state, ts):
    jump = False
    attack = 0
    reload = False
    pickup = True

    if ts % 60 == 0:
        jump = True
    if ts % 30 == 0:
        attack = 1
    if (state.weapon_ammo == 0) and (state.spare_ammo > 0):
        reload = True

    return [
        random.randint(0, 360),  # walk_dir
        args.walk_speed,  # walk_speed
        jump,  # jump
        1,  # turn left right
        0,  # look up down
        attack,  # attack
        reload,  # reload
        pickup,  # collect
    ]


# valid actions
used_actions = [
    ActionVariable.WALK_DIR,
    ActionVariable.WALK_SPEED,
    ActionVariable.JUMP,
    ActionVariable.TURN_LR_DELTA,
    ActionVariable.LOOK_UD_DELTA,
    ActionVariable.ATTACK,
    ActionVariable.RELOAD,
    ActionVariable.PICKUP,
]

# instantiate Game
game = Game(map_dir=args.map_dir, engine_dir=args.engine_dir)
game.set_game_mode(Game.MODE_SUP_BATTLE)
game.set_supply_heatmap_center([args.start_location[0], args.start_location[2]])
game.set_supply_heatmap_radius(50)
game.set_supply_indoor_richness(80)
game.set_supply_outdoor_richness(20)
game.set_supply_indoor_quantity_range(10, 50)
game.set_supply_outdoor_quantity_range(1, 5)
game.set_supply_spacing(5)
game.set_episode_timeout(args.timeout)
game.set_start_location(args.start_location)  # set start location of the first agent
game.set_available_actions(used_actions)
game.set_map_id(args.map_id)

if args.use_depth_map:
    game.turn_on_depth_map()

if args.record:
    game.turn_on_record()

for agent_id in range(1, args.num_agents):
    game.add_agent()
    game.random_start_location(agent_id)

game.init()

for ep in track(range(args.num_episodes), description="Running Episodes ..."):
    game.set_game_replay_suffix(f"{args.replay_suffix}_episode_{ep}")
    game.new_episode()

    while not game.is_episode_finished():
        ts = game.get_time_step()

        t = time.perf_counter()
        state_all = game.get_state_all()
        action_all = {
            agent_id: my_policy(state_all[agent_id], ts) for agent_id in state_all
        }
        game.make_action(action_all)
        dt = time.perf_counter() - t

        for agent_id, state in state_all.items():
            step_info = {
                "Episode": ep,
                "TimeStep": ts,
                "AgentID": agent_id,
                "Location": get_position(state),
                "Action": {
                    name: val for name, val in zip(used_actions, action_all[agent_id])
                },
                "#SupplyInfo": len(state.supply_states),
                "#EnemyInfo": len(state.enemy_states),
                "StepRate": round(1 / dt),
            }
            if args.use_depth_map:
                step_info["DepthMap"] = state.depth_map.shape
            console.print(step_info, style="bold magenta")

    print("episode ended ...")

game.close()
