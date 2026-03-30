import simpy
import random
import json

from phc_model    import PHC
from monitor      import SystemMonitor
from coordinator  import CoordinationEngine


def load_config(filepath="phc_config.json"):
    """Load simulation configuration from a JSON file.
    """
    with open(filepath, "r") as file:
        config = json.load(file)

    required_keys = ["simulation_hours", "service_rate", "phcs"]
    for key in required_keys:
        if key not in config:
            raise KeyError(f"Missing required config field: '{key}'")

    return config


def run_simulation(config_path="phc_config.json"):
    """Run the PHC discrete-event simulation.

    Loads PHC network configuration from JSON, builds the simulation
    dynamically, runs it, and prints performance metrics per PHC.
    Supports surge simulation, system monitoring, and coordination.
    """
    # --- Load configuration ---
    config       = load_config(config_path)
    SIM_HOURS    = config["simulation_hours"]
    SERVICE_RATE = config["service_rate"]
    PHC_LIST     = config["phcs"]
    SEED         = config.get("random_seed", 42)

    # --- Load surge configuration ---
    surge_config   = config.get("surge", {})
    surge_enabled  = surge_config.get("enabled", False)
    surge_start    = surge_config.get("start_hour", None)
    surge_duration = surge_config.get("duration_hours", 0)
    surge_end      = (surge_start + surge_duration) if surge_enabled else None
    affected_phcs  = surge_config.get("affected_phcs", {})

    # --- Load monitoring configuration ---
    monitor_config     = config.get("monitoring", {})
    check_interval_min = monitor_config.get("check_interval_minutes", 30)
    overload_threshold = monitor_config.get("overload_threshold", 0.85)
    check_interval_hrs = check_interval_min / 60

    # --- Load coordination configuration ---
    coord_config       = config.get("coordination", {})
    coord_enabled      = coord_config.get("enabled", False)
    travel_time        = coord_config.get("travel_time_hours", 0.5)
    safety_util        = coord_config.get("safety_utilization", 0.75)
    coord_interval_min = coord_config.get("check_interval_minutes", 30)
    coord_interval_hrs = coord_interval_min / 60

    # Set random seed for reproducibility
    random.seed(SEED)

    # --- Build simulation environment ---
    env = simpy.Environment()
    phc_objects = {}

    for phc_data in PHC_LIST:
        name         = phc_data["name"]
        staff        = phc_data["staff"]
        arrival_rate = phc_data["arrival_rate"]

        surge_multiplier = affected_phcs.get(name, 1.0) if surge_enabled else 1.0

        phc = PHC(
            env, name, staff, arrival_rate, SERVICE_RATE,
            surge_multiplier = surge_multiplier,
            surge_start      = surge_start if surge_enabled else None,
            surge_end        = surge_end
        )
        phc_objects[name] = phc
        env.process(phc.arrival_process())

    # --- Build and register the system monitor ---
    monitor = SystemMonitor(
        env                = env,
        phc_objects        = phc_objects,
        check_interval     = check_interval_hrs,
        overload_threshold = overload_threshold,
        service_rate       = SERVICE_RATE
    )
    env.process(monitor.run())

    # --- Build and register the coordination engine (if enabled) ---
    coordinator = None
    if coord_enabled:
        coordinator = CoordinationEngine(
            env                = env,
            phc_objects        = phc_objects,
            service_rate       = SERVICE_RATE,
            overload_threshold = overload_threshold,
            travel_time        = travel_time,
            check_interval     = coord_interval_hrs,
            safety_utilization = safety_util
        )
        env.process(coordinator.run())

    # --- Run simulation ---
    env.run(until=SIM_HOURS + 2)

    # --- Print PHC results ---
    surge_label = (f"Surge: Hour {surge_start}-{surge_end}"
                   if surge_enabled else "No Surge")
    coord_label = "Coordination: ON" if coord_enabled else "Coordination: OFF"

    print(f"\n{'='*70}")
    print(f"  PHC SIMULATION RESULTS  |  {surge_label}  |  {coord_label}")
    print(f"{'='*70}")
    print(f"{'PHC':<10} {'Arrived':>8} {'Served':>8} {'Avg Wait':>11} "
          f"{'Util':>7} {'Complete':>10}")
    print(f"{'-'*70}")

    for name, phc in phc_objects.items():
        avg_wait        = sum(phc.waiting_times) / len(phc.waiting_times) if phc.waiting_times else 0
        avg_wait_min    = avg_wait * 60
        completion_rate = (phc.patients_served / phc.patients_arrived * 100) if phc.patients_arrived > 0 else 0
        utilization     = phc.arrival_rate / (phc.staff * SERVICE_RATE)

        print(f"{name:<10} {phc.patients_arrived:>8} {phc.patients_served:>8} "
              f"{avg_wait_min:>9.1f}m {utilization:>7.2f} {completion_rate:>9.1f}%")

        if surge_enabled and name in affected_phcs:
            multiplier = affected_phcs[name]
            surge_rate = phc.arrival_rate * multiplier
            avg_surge_wait = (
                sum(phc.waiting_times_surge) / len(phc.waiting_times_surge) * 60
                if phc.waiting_times_surge else 0
            )
            print(f"  >> SURGE AFFECTED  |  Multiplier: x{multiplier}"
                  f"  |  Surge rate: {surge_rate:.0f} pts/hr"
                  f"  |  Surge arrivals: {phc.surge_patients_arrived}"
                  f"  |  Surge avg wait: {avg_surge_wait:.1f}m")

    print(f"{'='*70}")

    # --- Print monitor summary ---
    monitor.print_summary()

    # --- Print coordination summary ---
    if coordinator:
        coordinator.print_summary()


if __name__ == "__main__":
    run_simulation()