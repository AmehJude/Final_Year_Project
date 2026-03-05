# Simulation Settings
# Simulation length in hours (actual run time will be longer to drain queue)
SIM_HOURS = 8

# Service rate in patients per hour per staff member
# expovariate(SERVICE_RATE) gives mean service time of 1/SERVICE_RATE hours
SERVICE_RATE = 3  # ~20 minutes per patient on average

# PHC Definitions
# arrival_rate: patients per hour (used with expovariate for inter-arrival times)
PHCS = {
    "A": {"staff": 6, "arrival_rate": 10},
    "B": {"staff": 4, "arrival_rate": 7},
    "C": {"staff": 2, "arrival_rate": 4},
    "D": {"staff": 2, "arrival_rate": 5}
}