import simpy
import random
from phc_model import PHC
from config import PHCS, SERVICE_RATE, SIM_HOURS

# Set seed for reproducible results across different simulation runs
random.seed(42)

def run_simulation():
    """Run a discrete event simulation of Primary Health Centers (PHCs).
    
    Simulates patient arrivals, queueing, and service at multiple PHCs
    with different staffing levels and arrival rates. Results are output
    as patients served and average waiting time per PHC.
    """
    env = simpy.Environment()

    phc_objects = {}

    for name, params in PHCS.items():
        phc = PHC(env, name, params["staff"], params["arrival_rate"], SERVICE_RATE)
        phc_objects[name] = phc
        env.process(phc.arrival_process())

    # Run simulation past SIM_HOURS to allow in-process patients to complete service
    # This prevents data loss from patients cut off by the simulation end
    env.run(until=SIM_HOURS + 2)

    # Print results for each PHC
    print(f"\n{'PHC':<5} | {'Arrived':<10} | {'Served':<10} | {'Avg Wait (hr)':<15} | {'Utilization':<12}")
    print("-" * 75)

    for name, phc in phc_objects.items():
        if phc.waiting_times:
            avg_wait = sum(phc.waiting_times) / len(phc.waiting_times)
        else:
            avg_wait = 0

        completion_rate = (phc.patients_served / phc.patients_arrived * 100) if phc.patients_arrived > 0 else 0

        # utilization calculation
        staff = PHCS[name]["staff"]
        arrival_rate = PHCS[name]["arrival_rate"]
        utilization = arrival_rate / (staff * SERVICE_RATE)

        print(f"{name:<5} | {phc.patients_arrived:<10} | {phc.patients_served:<10} | {avg_wait:<15.2f} | {utilization:<12.2f}")
        print(f"       Service completion rate: {completion_rate:.1f}%")

if __name__ == "__main__":
    run_simulation()

    