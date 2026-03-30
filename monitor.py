class SystemMonitor:
    """Monitors all PHCs at regular intervals during the simulation.

    Wakes up every check_interval hours, reads the current state of
    every PHC, logs a snapshot, and flags any PHC that meets the
    composite overload condition.

    Attributes:
        env:                SimPy environment
        phc_objects:        Dictionary of all PHC objects being monitored
        check_interval:     How often to check, in hours
        overload_threshold: Utilization level component of overload condition
        service_rate:       System-wide service rate (patients/hour per staff)
        log:                Full time-series snapshot list
        overload_events:    List of confirmed composite overload alerts
    """

    def __init__(self, env, phc_objects, check_interval,
                 overload_threshold, service_rate):
        self.env                = env
        self.phc_objects        = phc_objects
        self.check_interval     = check_interval
        self.overload_threshold = overload_threshold
        self.service_rate       = service_rate

        self.log             = []  # Full time-series snapshot log
        self.overload_events = []  # Confirmed composite overload alerts only

    def run(self):
        """SimPy generator process -- the monitor's heartbeat.

        Wakes up every check_interval hours and takes a snapshot
        of the entire system. Runs for the full simulation duration.
        """
        while True:
            yield self.env.timeout(self.check_interval)
            self._take_snapshot()

    def _is_overloaded(self, live_utilization, queue_length):
        """Evaluate the composite overload condition.

        Both conditions must be true:
        - Staff utilization is at or above the threshold
        - At least 2 patients are waiting in the queue

        A single patient waiting could be momentary noise.
        Two or more indicates a genuine, building backlog.

        """
        return live_utilization >= self.overload_threshold and queue_length >= 2

    def _take_snapshot(self):
        """Read the current state of all PHCs and record it.

        Called automatically by run() at each interval.
        """
        current_time = self.env.now

        for name, phc in self.phc_objects.items():

            queue_length        = len(phc.resource.queue)
            patients_in_service = phc.resource.count

            if phc.staff > 0:
                live_utilization = phc.resource.count / phc.staff
            else:
                live_utilization = 0

            # Apply composite overload check
            overloaded = self._is_overloaded(live_utilization, queue_length)

            snapshot = {
                "time"               : round(current_time, 3),
                "phc"                : name,
                "queue_length"       : queue_length,
                "patients_in_service": patients_in_service,
                "live_utilization"   : round(live_utilization, 3),
                "patients_arrived"   : phc.patients_arrived,
                "patients_served"    : phc.patients_served,
                "overloaded"         : overloaded
            }

            self.log.append(snapshot)

            if overloaded:
                self.overload_events.append({
                    "time"            : round(current_time, 3),
                    "phc"             : name,
                    "live_utilization": round(live_utilization, 3),
                    "queue_length"    : queue_length
                })

    def print_summary(self):
        """Print a readable summary of monitoring results after simulation ends."""
        print("\n" + "=" * 70)
        print("  SYSTEM MONITOR LOG")
        print("=" * 70)
        print(f"  {'Time':<8} {'PHC':<10} {'Queue':>6} {'In Svc':>8} "
              f"{'Live Util':>10} {'Status':>10}")
        print("-" * 70)

        for entry in self.log:
            status = "!! OVERLOAD" if entry["overloaded"] else "OK"
            print(f"  {entry['time']:<8} {entry['phc']:<10} "
                  f"{entry['queue_length']:>6} {entry['patients_in_service']:>8} "
                  f"{entry['live_utilization']:>10.2f} {status:>10}")

        print("\n" + "=" * 70)
        if self.overload_events:
            print(f"  OVERLOAD ALERTS DETECTED: {len(self.overload_events)}")
            print("  (Composite condition: utilization >= threshold AND queue >= 2)")
            print("=" * 70)
            for alert in self.overload_events:
                print(f"  Hour {alert['time']:<6} | {alert['phc']:<10} | "
                      f"Utilization: {alert['live_utilization']:.2f} | "
                      f"Queue: {alert['queue_length']} patients waiting")
        else:
            print("  NO OVERLOAD EVENTS DETECTED")
            print("=" * 70)
        print()