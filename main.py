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


def run_simulation(config_path="phc_config.json",
                   surge_override=None,
                   coord_override=None,
                   silent=False):
    """Run the PHC discrete-event simulation.

    Loads PHC network configuration from JSON, builds the simulation
    dynamically, runs it, prints performance metrics, and returns
    structured results for use by the experiment runner.

    Args:
        config_path:    Path to the JSON configuration file.
        surge_override: If provided (True/False), overrides the surge
                        enabled setting in the config. Used by the
                        experiment runner to control scenarios without
                        editing the JSON file.
        coord_override: If provided (True/False), overrides the
                        coordination enabled setting in the config.
        silent:         If True, suppresses all printed output.
                        Used by the experiment runner which handles
                        its own output formatting.

    Returns:
        dict: Structured results containing per-PHC metrics, monitor
              log, overload events, and redeployment log.
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

    # Apply override if the experiment runner passed one in
    if surge_override is not None:
        surge_enabled = surge_override
        if not surge_enabled:
            surge_start = None
            surge_end   = None

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

    # Apply override if the experiment runner passed one in
    if coord_override is not None:
        coord_enabled = coord_override

    # Set random seed — same seed for every scenario ensures fair comparison
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

    # --- Collect structured results ---
    # This is what gets returned to the experiment runner
    phc_results = {}
    for name, phc in phc_objects.items():
        avg_wait        = sum(phc.waiting_times) / len(phc.waiting_times) if phc.waiting_times else 0
        avg_wait_min    = round(avg_wait * 60, 2)
        completion_rate = round((phc.patients_served / phc.patients_arrived * 100)
                                if phc.patients_arrived > 0 else 0, 1)
        utilization     = round(phc.arrival_rate / (phc.staff * SERVICE_RATE), 2)

        avg_surge_wait = 0
        if surge_enabled and phc.waiting_times_surge:
            avg_surge_wait = round(
                sum(phc.waiting_times_surge) / len(phc.waiting_times_surge) * 60, 2
            )

        phc_results[name] = {
            "patients_arrived"      : phc.patients_arrived,
            "patients_served"       : phc.patients_served,
            "avg_wait_min"          : avg_wait_min,
            "utilization"           : utilization,
            "completion_rate"       : completion_rate,
            "surge_patients_arrived": phc.surge_patients_arrived,
            "avg_surge_wait_min"    : avg_surge_wait
        }

    results = {
        "scenario": {
            "surge_enabled": surge_enabled,
            "coord_enabled": coord_enabled,
            "seed"         : SEED
        },
        "phc_results"     : phc_results,
        "monitor_log"     : monitor.log,
        "overload_events" : monitor.overload_events,
        "redeployments"   : coordinator.redeployment_log if coordinator else []
    }

    # --- Print output (skipped when called from experiment runner) ---
    if not silent:
        surge_label = (f"Surge: Hour {surge_start}-{surge_end}"
                       if surge_enabled else "No Surge")
        coord_label = "Coordination: ON" if coord_enabled else "Coordination: OFF"

        print(f"\n{'='*70}")
        print(f"  PHC SIMULATION RESULTS  |  {surge_label}  |  {coord_label}")
        print(f"{'='*70}")
        print(f"{'PHC':<10} {'Arrived':>8} {'Served':>8} {'Avg Wait':>11} "
              f"{'Util':>7} {'Complete':>10}")
        print(f"{'-'*70}")

        for name, r in phc_results.items():
            print(f"{name:<10} {r['patients_arrived']:>8} {r['patients_served']:>8} "
                  f"{r['avg_wait_min']:>9.1f}m {r['utilization']:>7.2f} "
                  f"{r['completion_rate']:>9.1f}%")

            if surge_enabled and name in affected_phcs:
                multiplier = affected_phcs[name]
                surge_rate = phc_objects[name].arrival_rate * multiplier
                print(f"  >> SURGE AFFECTED  |  Multiplier: x{multiplier}"
                      f"  |  Surge rate: {surge_rate:.0f} pts/hr"
                      f"  |  Surge arrivals: {r['surge_patients_arrived']}"
                      f"  |  Surge avg wait: {r['avg_surge_wait_min']:.1f}m")

        print(f"{'='*70}")
        monitor.print_summary()
        if coordinator:
            coordinator.print_summary()

    return results


if __name__ == "__main__":
    run_simulation()