import simpy
import random

class PHC:
    """Primary Health Centre (PHC) simulation model.
    
    Models an M/M/c queue system where patients arrive randomly,
    wait in queue, and are served by available staff.
    
    Attributes:
        env: SimPy environment for discrete event simulation
        name: PHC identifier (e.g., 'A', 'B')
        arrival_rate: Patient arrival rate (patients/hour)
        service_rate: Service rate per staff (patients/hour)
        resource: SimPy Resource representing staff capacity
        patients_arrived: Total patients who entered the system
        patients_served: Patients who completed service
        waiting_times: List of waiting times (hours) for served patients
    """
    
    def __init__(self, env, name, staff, arrival_rate, service_rate):
        self.env = env
        self.name = name
        self.arrival_rate = arrival_rate
        self.service_rate = service_rate

        # SimPy Resource with capacity equal to number of staff
        self.resource = simpy.Resource(env, capacity=staff)

        # Tracking metrics
        self.patients_arrived = 0  # Total arrivals (including those cut off)
        self.patients_served = 0   # Completions only
        self.waiting_times = []    # Wait time for each served patient

    def patient(self):
        """SimPy process for a single patient.
        
        Simulates: arrival -> wait in queue -> service -> departure
        Records waiting time and increments service counter.
        """
        arrival_time = self.env.now

        # Request a staff member (block if all busy)
        with self.resource.request() as request:
            yield request

            # Calculate time spent waiting in queue
            wait = self.env.now - arrival_time
            self.waiting_times.append(wait)

            # Simulate service time with exponential distribution
            # expovariate(lambda) gives mean = 1/lambda
            service_time = random.expovariate(self.service_rate)
            yield self.env.timeout(service_time)

            # Patient successfully completed service
            self.patients_served += 1

    def arrival_process(self):
        """SimPy process that generates patient arrivals.
        
        Generates patients indefinitely with exponential inter-arrival times.
        Each arrival spawns a patient() process to handle queueing and service.
        """
        while True:
            # Inter-arrival time with exponential distribution
            # expovariate(lambda) gives mean = 1/lambda
            inter_arrival = random.expovariate(self.arrival_rate)
            yield self.env.timeout(inter_arrival)
            
            # Patient arrives at the system
            self.patients_arrived += 1
            
            # Spawn patient process to handle queueing and service
            self.env.process(self.patient())