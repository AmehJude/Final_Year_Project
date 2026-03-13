import simpy
import random
import json

from phc_model import PHC


def load_config(filepath="phc_config.json"):
    """Load simulation configuration from a JSON file.

    Args:
        filepath: Path to the JSON configuration file.

    Returns:
        dict: Parsed configuration containing simulation settings and PHC list.

    Raises:
        FileNotFoundError: If the config file does not exist at the given path.
        KeyError: If required fields are missing from the config file.
    """
    with open(filepath, "r") as file:
        config = json.load(file)

    # Validate that required top-level keys exist
    required_keys = ["simulation_hours", "service_rate", "phcs"]
    for key in required_keys:
        if key not in config:
            raise KeyError(f"Missing required config field: '{key}'")

    return config


def run_simulation(config_path="phc_config.json"):
    """Run the PHC discrete-event simulation.

    Loads PHC network configuration from JSON, builds the simulation
    dynamically, runs it, and prints performance metrics per PHC.
    Supports optional surge simulation for specific PHCs.

    Args:
        config_path: Path to the JSON configuration file.
    """
    # --- Load configuration ---
    config       = load_config(config_path)
    SIM_HOURS    = config["simulation_hours"]
    SERVICE_RATE = config["service_rate"]
    PHC_LIST     = config["phcs"]
    SEED         = config.get("random_seed", 42)

    # --- Load surge configuration if present ---
    surge_config   = config.get("surge", {})
    surge_enabled  = surge_config.get("enabled", False)
    surge_start    = surge_config.get("start_hour", None)
    surge_duration = surge_config.get("duration_hours", 0)
    surge_end      = (surge_start + surge_duration) if surge_enabled else None
    affected_phcs  = surge_config.get("affected_phcs", {})

    # Set random seed for reproducibility
    random.seed(SEED)

    # --- Build simulation environment ---
    env = simpy.Environment()
    phc_objects = {}

    for phc_data in PHC_LIST:
        name         = phc_data["name"]
        staff        = phc_data["staff"]
        arrival_rate = phc_data["arrival_rate"]

        # Check if this PHC is affected by the surge
        # If not in affected_phcs, multiplier defaults to 1.0 (no change)
        surge_multiplier = affected_phcs.get(name, 1.0) if surge_enabled else 1.0

        phc = PHC(
            env, name, staff, arrival_rate, SERVICE_RATE,
            surge_multiplier = surge_multiplier,
            surge_start      = surge_start if surge_enabled else None,
            surge_end        = surge_end
        )
        phc_objects[name] = phc
        env.process(phc.arrival_process())

    # --- Run simulation ---
    env.run(until=SIM_HOURS + 2)

    # --- Print results ---
    surge_label = (f"Surge: Hour {surge_start}–{surge_end}"
                   if surge_enabled else "No Surge")

    print(f"\n{'='*70}")
    print(f"  PHC SIMULATION RESULTS  |  Duration: {SIM_HOURS}h  |  {surge_label}")
    print(f"{'='*70}")
    print(f"{'PHC':<10} {'Arrived':>8} {'Served':>8} {'Avg Wait':>11} {'Util':>7} {'Complete':>10}")
    print(f"{'-'*70}")

    for name, phc in phc_objects.items():
        avg_wait        = sum(phc.waiting_times) / len(phc.waiting_times) if phc.waiting_times else 0
        avg_wait_min    = avg_wait * 60
        completion_rate = (phc.patients_served / phc.patients_arrived * 100) if phc.patients_arrived > 0 else 0
        staff           = next(p["staff"] for p in PHC_LIST if p["name"] == name)
        utilization     = phc.arrival_rate / (staff * SERVICE_RATE)

        print(f"{name:<10} {phc.patients_arrived:>8} {phc.patients_served:>8} "
              f"{avg_wait_min:>9.1f}m {utilization:>7.2f} {completion_rate:>9.1f}%")

        # If this PHC was surge-affected, print additional surge breakdown
        if surge_enabled and name in affected_phcs:
            multiplier = affected_phcs[name]
            surge_rate = phc.arrival_rate * multiplier

            if phc.waiting_times_surge:
                avg_surge_wait = sum(phc.waiting_times_surge) / len(phc.waiting_times_surge) * 60
            else:
                avg_surge_wait = 0

            print(f"  >> SURGE AFFECTED  |  Multiplier: x{multiplier}"
                  f"  |  Surge rate: {surge_rate:.0f} pts/hr"
                  f"  |  Surge arrivals: {phc.surge_patients_arrived}"
                  f"  |  Surge avg wait: {avg_surge_wait:.1f}m")

    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_simulation()