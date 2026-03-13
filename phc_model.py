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

    def __init__(self, env, name, staff, arrival_rate, service_rate,
                 surge_multiplier=1.0, surge_start=None, surge_end=None):
        self.env = env
        self.name = name
        self.arrival_rate = arrival_rate      # Base arrival rate (patients/hour)
        self.service_rate = service_rate

        # Surge parameters — defaults mean no surge behaviour
        # surge_multiplier: how many times busier the PHC gets during the surge
        # surge_start/end: simulation hours when the surge begins and ends
        self.surge_multiplier = surge_multiplier
        self.surge_start      = surge_start
        self.surge_end        = surge_end

        # SimPy Resource — capacity equals number of staff
        # Only this many patients can be in service simultaneously
        self.resource = simpy.Resource(env, capacity=staff)

        # Metrics tracking
        self.patients_arrived       = 0   # All arrivals including those not yet served
        self.patients_served        = 0   # Only patients who completed service
        self.waiting_times          = []  # Wait times for all served patients (hours)
        self.surge_patients_arrived = 0   # Arrivals specifically during surge window
        self.waiting_times_surge    = []  # Wait times recorded during surge window

    def _is_surge_active(self):
        """Check whether the simulation clock is currently inside the surge window.

        Returns:
            bool: True if surge is active right now, False otherwise.
        """
        if self.surge_start is None or self.surge_end is None:
            return False
        return self.surge_start <= self.env.now < self.surge_end

    def patient(self, arrived_during_surge=False):
        """SimPy generator process representing one patient's journey.

        Flow: arrival → join queue → wait for staff → receive service → depart

        Args:
            arrived_during_surge: Whether this patient arrived during a surge.
                                  Used to record surge-specific waiting times.
        """
        arrival_time = self.env.now

        # Request a staff member — patient waits here if all staff are busy
        with self.resource.request() as request:
            yield request

            # Staff is now free — calculate how long the patient waited
            wait = self.env.now - arrival_time
            self.waiting_times.append(wait)

            # If this patient arrived during the surge, record their wait separately
            # This lets us compare surge vs normal waiting times in the results
            if arrived_during_surge:
                self.waiting_times_surge.append(wait)

            # Draw a random service duration from exponential distribution
            # expovariate(rate) gives mean = 1/rate hours
            service_time = random.expovariate(self.service_rate)
            yield self.env.timeout(service_time)

            # Service complete
            self.patients_served += 1

    def arrival_process(self):
        """SimPy generator process that continuously generates patient arrivals.

        Runs for the entire simulation. Each iteration:
        1. Checks whether a surge is currently active
        2. Uses the appropriate arrival rate (base or surge)
        3. Waits the inter-arrival gap
        4. Spawns a new patient process
        """
        while True:
            # Determine the current arrival rate based on surge status
            # During a surge the rate is multiplied — more patients per hour
            surge_active = self._is_surge_active()

            if surge_active:
                current_rate = self.arrival_rate * self.surge_multiplier
            else:
                current_rate = self.arrival_rate

            # Draw random gap until next patient arrives at the current rate
            inter_arrival = random.expovariate(current_rate)
            yield self.env.timeout(inter_arrival)

            # Re-check surge status at the moment the patient actually arrives
            # (surge may have started or ended during the inter-arrival wait)
            arrived_during_surge = self._is_surge_active()

            # Record arrival and update surge counter if applicable
            self.patients_arrived += 1
            if arrived_during_surge:
                self.surge_patients_arrived += 1

            # Spawn patient process, passing whether they arrived during surge
            self.env.process(self.patient(arrived_during_surge))