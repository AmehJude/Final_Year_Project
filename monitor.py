class SystemMonitor:
    """Monitors all PHCs at regular intervals during the simulation

        env:                SimPy environment (for current time and process)
        phc_objects:        Dictionary of all PHC objects being monitored
        check_interval:     How often to check, in hours
        overload_threshold: Utilization level that triggers an overload alert
        service_rate:       System-wide service rate (patients/hour per staff)
        log:                List of snapshot dictionaries recorded over time
        overload_events:    List of overload alert dictionaries
    """

    def __init__(self, env, phc_objects, check_interval,
                 overload_threshold, service_rate):
        self.env                = env
        self.phc_objects        = phc_objects
        self.check_interval     = check_interval
        self.overload_threshold = overload_threshold
        self.service_rate       = service_rate

        # Storage for everything the monitor records
        self.log             = []  # Full time-series snapshot log
        self.overload_events = []  # Only the moments a PHC crossed the threshold

    def run(self):
        
        while True:
            # Wait until the next scheduled check
            yield self.env.timeout(self.check_interval)

            # Take a snapshot of every PHC at this moment
            self._take_snapshot()

    def _take_snapshot(self):

        current_time = self.env.now

        for name, phc in self.phc_objects.items():

            # Queue length — patients currently waiting for a staff member
            # SimPy tracks this internally via the resource queue
            queue_length = len(phc.resource.queue)

            # Patients in service right now — staff slots currently occupied
            patients_in_service = phc.resource.count

            # Live utilization — what fraction of staff are busy right now
            # This is different from theoretical utilization (lambda / c*mu)
            # because it reflects the actual simulation state at this moment
            if phc.staff > 0:
                live_utilization = phc.resource.count / phc.staff
            else:
                live_utilization = 0

            # Snapshot dictionary for this PHC at this time
            snapshot = {
                "time"               : round(current_time, 3),
                "phc"                : name,
                "queue_length"       : queue_length,
                "patients_in_service": patients_in_service,
                "live_utilization"   : round(live_utilization, 3),
                "patients_arrived"   : phc.patients_arrived,
                "patients_served"    : phc.patients_served,
                "overloaded"         : live_utilization >= self.overload_threshold
            }

            # Add snapshot to the full log
            self.log.append(snapshot)

            # If this PHC is overloaded, record a separate alert
            if snapshot["overloaded"]:
                alert = {
                    "time"            : round(current_time, 3),
                    "phc"             : name,
                    "live_utilization": round(live_utilization, 3),
                    "queue_length"    : queue_length
                }
                self.overload_events.append(alert)

    def print_summary(self):

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

        # Overload events summary
        print("\n" + "=" * 70)
        if self.overload_events:
            print(f"  OVERLOAD ALERTS DETECTED: {len(self.overload_events)}")
            print("=" * 70)
            for alert in self.overload_events:
                print(f"  Hour {alert['time']:<6} | {alert['phc']:<10} | "
                      f"Utilization: {alert['live_utilization']:.2f} | "
                      f"Queue: {alert['queue_length']} patients waiting")
        else:
            print("  NO OVERLOAD EVENTS DETECTED")
            print("=" * 70)

        print()