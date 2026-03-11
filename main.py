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

    Args:
        config_path: Path to the JSON configuration file.
    """
    # --- Load configuration ---
    config      = load_config(config_path)
    SIM_HOURS   = config["simulation_hours"]
    SERVICE_RATE = config["service_rate"]
    PHC_LIST    = config["phcs"]
    SEED        = config.get("random_seed", 42)  # Default to 42 if not specified

    # Set random seed for reproducibility
    random.seed(SEED)

    # --- Build simulation environment ---
    env = simpy.Environment()
    phc_objects = {}

    # Dynamically create one PHC object per entry in the config
    # This is what makes the system work for any number of PHCs
    for phc_data in PHC_LIST:
        name         = phc_data["name"]
        staff        = phc_data["staff"]
        arrival_rate = phc_data["arrival_rate"]

        phc = PHC(env, name, staff, arrival_rate, SERVICE_RATE)
        phc_objects[name] = phc
        env.process(phc.arrival_process())

    # --- Run simulation ---
    # Run past SIM_HOURS to allow in-progress patients to finish
    env.run(until=SIM_HOURS + 2)

    # --- Print results ---
    print(f"\n{'='*65}")
    print(f"  PHC SIMULATION RESULTS  |  Duration: {SIM_HOURS}h  |  Seed: {SEED}")
    print(f"{'='*65}")
    print(f"{'PHC':<10} {'Arrived':>8} {'Served':>8} {'Avg Wait':>12} {'Util':>8} {'Complete':>10}")
    print(f"{'-'*65}")

    for name, phc in phc_objects.items():
        avg_wait        = sum(phc.waiting_times) / len(phc.waiting_times) if phc.waiting_times else 0
        avg_wait_min    = avg_wait * 60
        completion_rate = (phc.patients_served / phc.patients_arrived * 100) if phc.patients_arrived > 0 else 0

        # Theoretical utilization: rho = lambda / (c * mu)
        staff       = next(p["staff"] for p in PHC_LIST if p["name"] == name)
        utilization = phc.arrival_rate / (staff * SERVICE_RATE)

        print(f"{name:<10} {phc.patients_arrived:>8} {phc.patients_served:>8} "
              f"{avg_wait_min:>10.1f}m {utilization:>8.2f} {completion_rate:>9.1f}%")

    print(f"{'='*65}\n")


if __name__ == "__main__":
    run_simulation()