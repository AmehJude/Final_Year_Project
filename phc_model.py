import simpy
import random

class PHC:
    """Primary Health Centre (PHC) simulation model.

    Models an M/M/c queue system where patients arrive randomly,
    wait in queue, and are served by available staff.

    Attributes:
        env:              SimPy environment for discrete event simulation
        name:             PHC identifier (e.g., 'PHC_A')
        arrival_rate:     Patient arrival rate (patients/hour)
        service_rate:     Service rate per staff member (patients/hour)
        resource:         SimPy Resource representing staff capacity
        patients_arrived: Total patients who entered the system
        patients_served:  Patients who completed service
        waiting_times:    List of waiting times (hours) for served patients
    """

    def __init__(self, env, name, staff, arrival_rate, service_rate):
        self.env = env
        self.name = name
        self.arrival_rate = arrival_rate
        self.service_rate = service_rate

        # SimPy Resource — capacity equals number of staff
        # Only this many patients can be in service simultaneously
        self.resource = simpy.Resource(env, capacity=staff)

        # Metrics tracking
        self.patients_arrived = 0  # All arrivals including those not yet served
        self.patients_served  = 0  # Only patients who completed service
        self.waiting_times    = [] # Wait time per served patient (hours)

    def patient(self):
        """SimPy generator process representing one patient's journey.

        Flow: arrival → join queue → wait for staff → receive service → depart
        """
        arrival_time = self.env.now

        # Request a staff member — patient waits here if all staff are busy
        with self.resource.request() as request:
            yield request

            # Staff is now free — calculate how long the patient waited
            wait = self.env.now - arrival_time
            self.waiting_times.append(wait)

            # Draw a random service duration from exponential distribution
            # expovariate(rate) gives mean = 1/rate hours
            service_time = random.expovariate(self.service_rate)
            yield self.env.timeout(service_time)

            # Service complete
            self.patients_served += 1

    def arrival_process(self):
        """SimPy generator process that continuously generates patient arrivals.

        Runs for the entire simulation. Each iteration draws a random
        inter-arrival time, waits, then spawns a new patient process.
        """
        while True:
            # Draw random gap until next patient arrives
            # expovariate(rate) gives mean inter-arrival = 1/rate hours
            inter_arrival = random.expovariate(self.arrival_rate)
            yield self.env.timeout(inter_arrival)

            # Patient has arrived — record and spawn their process
            self.patients_arrived += 1
            self.env.process(self.patient())