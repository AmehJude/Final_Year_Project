import math


class CoordinationEngine:
    """Emergency staff redeployment engine.

    At regular
    intervals it scans all PHCs for overload conditions and, when
    found, identifies a suitable donor PHC and simulates staff
    redeployment with a realistic travel time delay.

    Overload detection uses the same composite condition as the monitor:
        live_utilization >= overload_threshold AND queue_length >= 2

    Donor selection rules:
        - The donor must not be overloaded itself
        - After donating, the donor must retain enough staff to stay
          at or below the safety_utilization threshold
        - The donor with the lowest current utilization is preferred
          (least busy facility gives up staff first)

    Staff redeployment mechanics:
        - Staff leave the donor immediately when the decision is made
        - They arrive at the recipient after travel_time hours
        - Only then does the recipient gain the extra capacity
        - This models the real-world delay of physically moving staff

    Attributes:
        env:                SimPy environment
        phc_objects:        Dictionary of all PHC objects
        service_rate:       System-wide service rate (patients/hour per staff)
        overload_threshold: Utilization component of overload condition
        travel_time:        Hours it takes for staff to travel between PHCs
        check_interval:     How often the engine checks for overloads (hours)
        safety_utilization: Minimum utilization floor donors must stay above
        redeployment_log:   Record of every redeployment decision made
        active_recipients:  PHC names currently awaiting or receiving staff
    """

    def __init__(self, env, phc_objects, service_rate, overload_threshold,
                 travel_time, check_interval, safety_utilization=0.75):
        self.env                = env
        self.phc_objects        = phc_objects
        self.service_rate       = service_rate
        self.overload_threshold = overload_threshold
        self.travel_time        = travel_time
        self.check_interval     = check_interval
        self.safety_utilization = safety_utilization

        self.redeployment_log  = []   # Full record of all redeployments
        self.active_recipients = set() # PHCs currently being helped

    def run(self):
        """
        Wakes up every check_interval hours, scans for overloaded PHCs,
        and triggers redeployment if a valid donor exists.
        """
        while True:
            yield self.env.timeout(self.check_interval)
            self._evaluate()

    # ------------------------------------------------------------------
    # Internal evaluation methods
    # ------------------------------------------------------------------

    def _live_utilization(self, phc):
        """Calculate what fraction of this PHC's staff are currently busy."""
        return phc.resource.count / phc.staff if phc.staff > 0 else 0

    def _is_overloaded(self, phc):
        """Check composite overload condition -- same logic as the monitor.

        Both must be true:
          - Live utilization at or above the overload threshold
          - At least 2 patients waiting in the queue
        """
        util  = self._live_utilization(phc)
        queue = len(phc.resource.queue)
        return util >= self.overload_threshold and queue >= 2

    def _min_safe_staff(self, phc):
        """Calculate the minimum staff this PHC must keep to remain safe.

        Uses the safety utilization floor:
            min_staff = ceil(arrival_rate / (service_rate * safety_utilization))
        """
        minimum = math.ceil(
            phc.arrival_rate / (self.service_rate * self.safety_utilization)
        )
        return max(1, minimum)  # Always keep at least 1 staff member

    def _can_donate(self, phc):
        """Check whether this PHC can safely spare a staff member.

        Two conditions must both be true:
        - PHC has more staff than its safe minimum
        - At least one staff member is currently free
        
        """
        has_spare_above_minimum = phc.staff > self._min_safe_staff(phc)
        has_free_staff          = phc.resource.count < phc.staff
        return has_spare_above_minimum and has_free_staff

    def _find_best_donor(self, recipient_name):
        """Find the most suitable PHC to donate a staff member.

        Searches all PHCs except the recipient. Among those that
        can donate, selects the one with the lowest live utilization
        -- the least busy facility gives up staff first.
        """
        best_donor   = None
        lowest_util  = float("inf")

        for name, phc in self.phc_objects.items():
            if name == recipient_name:
                continue
            if self._can_donate(phc):
                util = self._live_utilization(phc)
                if util < lowest_util:
                    lowest_util = util
                    best_donor  = phc

        return best_donor

    def _evaluate(self):
        """Scan all PHCs for overload and trigger redeployment where needed.

        Called automatically by run() at each check interval.
        Skips PHCs already receiving help to avoid duplicate deployments.
        """
        for name, phc in self.phc_objects.items():

            # Skip if already receiving a redeployment
            if name in self.active_recipients:
                continue

            if self._is_overloaded(phc):
                donor = self._find_best_donor(name)

                if donor:
                    # Mark recipient as being helped before spawning process
                    self.active_recipients.add(name)
                    self.env.process(self._redeploy(donor, phc))

    def _redeploy(self, donor, recipient):
        """SimPy generator process simulating one staff redeployment.

        1 -- Staff member leaves donor immediately.
                  Donor loses one staff slot right away.
        2 -- Travel time passes.
                  Staff is in transit, unavailable to both PHCs.
        3 -- Staff member arrives at recipient.
                  Recipient gains one staff slot.
                  SimPy automatically begins serving waiting patients.
        """
        decision_time = self.env.now

        # Step 1 -- Remove staff from donor immediately
        donor.staff              -= 1
        donor.resource._capacity -= 1

        # Step 2 -- Simulate travel time
        yield self.env.timeout(self.travel_time)

        # Step 3 -- Staff arrives at recipient
        recipient.staff              += 1
        recipient.resource._capacity += 1

        arrival_time = self.env.now

        # Log the completed redeployment
        self.redeployment_log.append({
            "decision_time": round(decision_time, 3),
            "arrival_time" : round(arrival_time, 3),
            "donor"        : donor.name,
            "recipient"    : recipient.name,
            "travel_time"  : self.travel_time
        })

        # Release the recipient so it can be helped again if still overloaded
        self.active_recipients.discard(recipient.name)

    # ------------------------------------------------------------------
    # Results output
    # ------------------------------------------------------------------

    def print_summary(self):
        """Print a summary of all redeployment decisions after simulation ends."""
        print("\n" + "=" * 70)
        if self.redeployment_log:
            print(f"  COORDINATION ENGINE  |  {len(self.redeployment_log)} REDEPLOYMENT(S) MADE")
            print("=" * 70)
            print(f"  {'Decision':>10} {'Donor':<10} {'Recipient':<12} {'Arrived':>10}")
            print("-" * 70)
            for r in self.redeployment_log:
                print(f"  Hour {r['decision_time']:<6} "
                      f"{r['donor']:<10} >> {r['recipient']:<12} "
                      f"Hour {r['arrival_time']}")
        else:
            print("  COORDINATION ENGINE  |  NO REDEPLOYMENTS TRIGGERED")
            print("=" * 70)
        print()