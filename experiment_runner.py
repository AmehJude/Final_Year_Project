"""
Experiment Runner — PHC Surge Coordination Study
=================================================
Runs three controlled scenarios using identical random seeds,
collects structured results, exports to CSV, and generates
comparison graphs for dissertation use.

Scenarios
---------
1. Baseline       — Normal operations. No surge. No coordination.
2. Surge Only     — Surge active. Coordination disabled.
3. Surge + Coord  — Surge active. Coordination enabled.

The same random seed is used across all three scenarios so that
patient arrivals are identical. Any difference in results is
caused purely by the presence or absence of surge and coordination,
not by random variation between runs.

Outputs (saved to results/ folder)
-----------------------------------
- experiment_results.csv       — Full per-PHC metrics for all scenarios
- avg_wait_comparison.png      — Bar chart: avg wait per PHC per scenario
- queue_over_time_phc_d.png    — Line chart: PHC_D queue length over time
- overload_events_comparison.png — Bar chart: overload alert counts per scenario
"""

import os
import csv
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — saves to file, no screen popup
import matplotlib.pyplot as plt

from main import run_simulation


# -----------------------------------------------------------------------
# Scenario definitions
# -----------------------------------------------------------------------

SCENARIOS = [
    {
        "label"         : "Baseline",
        "surge_override": False,
        "coord_override": False
    },
    {
        "label"         : "Surge Only",
        "surge_override": True,
        "coord_override": False
    },
    {
        "label"         : "Surge + Coordination",
        "surge_override": True,
        "coord_override": True
    }
]

# Output folder — created automatically if it doesn't exist
RESULTS_DIR = "results"


# -----------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------

def run_experiments(config_path="phc_config.json"):
    """Run all three scenarios and collect results.

    Args:
        config_path: Path to the JSON configuration file.

    Returns:
        list: One results dictionary per scenario.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)

    all_results = []

    for i, scenario in enumerate(SCENARIOS, start=1):
        print(f"\n{'='*70}")
        print(f"  RUNNING SCENARIO {i} OF {len(SCENARIOS)}: {scenario['label']}")
        print(f"{'='*70}")

        results = run_simulation(
            config_path     = config_path,
            surge_override  = scenario["surge_override"],
            coord_override  = scenario["coord_override"],
            silent          = False
        )

        # Attach scenario label to results for identification
        results["label"] = scenario["label"]
        all_results.append(results)

    return all_results


# -----------------------------------------------------------------------
# CSV Export
# -----------------------------------------------------------------------

def export_csv(all_results):
    """Export per-PHC metrics for all scenarios to a CSV file.

    Each row represents one PHC in one scenario. Columns include
    all key performance metrics for dissertation tables.

    Args:
        all_results: List of results dictionaries from run_experiments()
    """
    filepath = os.path.join(RESULTS_DIR, "experiment_results.csv")

    fieldnames = [
        "scenario",
        "phc",
        "patients_arrived",
        "patients_served",
        "avg_wait_min",
        "utilization",
        "completion_rate",
        "surge_patients_arrived",
        "avg_surge_wait_min",
        "overload_alerts",
        "redeployments_made"
    ]

    with open(filepath, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for results in all_results:
            scenario_label   = results["label"]
            overload_count   = len(results["overload_events"])
            redeployment_count = len(results["redeployments"])

            # Count overload alerts per PHC for this scenario
            phc_overload_counts = {}
            for event in results["overload_events"]:
                phc_name = event["phc"]
                phc_overload_counts[phc_name] = phc_overload_counts.get(phc_name, 0) + 1

            for phc_name, phc_r in results["phc_results"].items():
                writer.writerow({
                    "scenario"              : scenario_label,
                    "phc"                   : phc_name,
                    "patients_arrived"      : phc_r["patients_arrived"],
                    "patients_served"       : phc_r["patients_served"],
                    "avg_wait_min"          : phc_r["avg_wait_min"],
                    "utilization"           : phc_r["utilization"],
                    "completion_rate"       : phc_r["completion_rate"],
                    "surge_patients_arrived": phc_r["surge_patients_arrived"],
                    "avg_surge_wait_min"    : phc_r["avg_surge_wait_min"],
                    "overload_alerts"       : phc_overload_counts.get(phc_name, 0),
                    "redeployments_made"    : redeployment_count
                })

    print(f"\n  [EXPORT] Results saved to: {filepath}")


# -----------------------------------------------------------------------
# Graph 1 — Average Waiting Time Comparison
# -----------------------------------------------------------------------

def graph_avg_wait(all_results):
    """Bar chart comparing average waiting time per PHC across scenarios.

    Each PHC gets a group of bars — one bar per scenario.
    This directly shows which PHCs were most affected by the surge
    and how much coordination reduced waiting times.
    """
    # Collect PHC names from first result
    phc_names     = list(all_results[0]["phc_results"].keys())
    scenario_labels = [r["label"] for r in all_results]
    n_scenarios   = len(all_results)
    n_phcs        = len(phc_names)

    # Build data matrix: rows = scenarios, cols = PHCs
    data = []
    for results in all_results:
        row = [results["phc_results"][phc]["avg_wait_min"] for phc in phc_names]
        data.append(row)

    # Chart layout
    fig, ax  = plt.subplots(figsize=(12, 6))
    bar_width = 0.25
    x         = range(n_phcs)
    colors    = ["#4C9BE8", "#E87B4C", "#4CE87B"]

    for i, (scenario_data, label) in enumerate(zip(data, scenario_labels)):
        positions = [pos + i * bar_width for pos in x]
        bars = ax.bar(positions, scenario_data, bar_width,
                      label=label, color=colors[i], edgecolor="white", linewidth=0.8)

        # Add value labels on top of each bar
        for bar, val in zip(bars, scenario_data):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.3,
                    f"{val:.1f}m",
                    ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Primary Health Centre", fontsize=12)
    ax.set_ylabel("Average Waiting Time (minutes)", fontsize=12)
    ax.set_title("Average Patient Waiting Time by PHC and Scenario", fontsize=14)
    ax.set_xticks([pos + bar_width for pos in x])
    ax.set_xticklabels(phc_names)
    ax.legend(title="Scenario")
    ax.set_ylim(0, max(max(row) for row in data) * 1.25)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    filepath = os.path.join(RESULTS_DIR, "avg_wait_comparison.png")
    plt.savefig(filepath, dpi=150)
    plt.close()
    print(f"  [GRAPH] Average wait comparison saved to: {filepath}")


# -----------------------------------------------------------------------
# Graph 2 — PHC_D Queue Length Over Time
# -----------------------------------------------------------------------

def graph_queue_over_time(all_results):
    """Line chart showing PHC_D queue length over simulation time.

    One line per scenario. This chart most clearly shows the surge
    impact and the coordination engine's effect on the backlog.
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    colors  = ["#4C9BE8", "#E87B4C", "#4CE87B"]
    styles  = ["-", "--", "-."]

    for results, color, style in zip(all_results, colors, styles):
        label     = results["label"]
        # Filter monitor log entries for PHC_D only
        phc_d_log = [entry for entry in results["monitor_log"]
                     if entry["phc"] == "PHC_D"]

        times   = [entry["time"]         for entry in phc_d_log]
        queues  = [entry["queue_length"] for entry in phc_d_log]

        ax.plot(times, queues, label=label, color=color,
                linestyle=style, linewidth=2, marker="o", markersize=4)

    # Mark surge window with a shaded region
    # Read from first result's scenario info
    surge_on = all_results[1]["scenario"]["surge_enabled"]
    if surge_on:
        ax.axvspan(3, 5, alpha=0.12, color="red", label="Surge Window (Hr 3-5)")

    ax.set_xlabel("Simulation Time (hours)", fontsize=12)
    ax.set_ylabel("Queue Length (patients waiting)", fontsize=12)
    ax.set_title("PHC_D Queue Length Over Time by Scenario", fontsize=14)
    ax.legend(title="Scenario")
    ax.grid(linestyle="--", alpha=0.5)

    plt.tight_layout()
    filepath = os.path.join(RESULTS_DIR, "queue_over_time_phc_d.png")
    plt.savefig(filepath, dpi=150)
    plt.close()
    print(f"  [GRAPH] PHC_D queue over time saved to: {filepath}")


# -----------------------------------------------------------------------
# Graph 3 — Overload Events Comparison
# -----------------------------------------------------------------------

def graph_overload_events(all_results):
    """Bar chart showing total overload alert count per scenario.

    Also breaks down alerts by PHC so it's clear which facilities
    were most affected in each scenario.
    """
    phc_names       = list(all_results[0]["phc_results"].keys())
    scenario_labels = [r["label"] for r in all_results]
    n_scenarios     = len(all_results)
    n_phcs          = len(phc_names)

    # Count overload alerts per PHC per scenario
    data = []
    for results in all_results:
        phc_counts = {phc: 0 for phc in phc_names}
        for event in results["overload_events"]:
            if event["phc"] in phc_counts:
                phc_counts[event["phc"]] += 1
        data.append([phc_counts[phc] for phc in phc_names])

    fig, ax   = plt.subplots(figsize=(12, 6))
    bar_width = 0.25
    x         = range(n_phcs)
    colors    = ["#4C9BE8", "#E87B4C", "#4CE87B"]

    for i, (scenario_data, label) in enumerate(zip(data, scenario_labels)):
        positions = [pos + i * bar_width for pos in x]
        bars = ax.bar(positions, scenario_data, bar_width,
                      label=label, color=colors[i], edgecolor="white", linewidth=0.8)

        for bar, val in zip(bars, scenario_data):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.1,
                        str(val),
                        ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Primary Health Centre", fontsize=12)
    ax.set_ylabel("Number of Overload Alerts", fontsize=12)
    ax.set_title("Overload Alerts per PHC by Scenario\n"
                 "(Composite condition: utilization >= 0.85 AND queue >= 2)",
                 fontsize=13)
    ax.set_xticks([pos + bar_width for pos in x])
    ax.set_xticklabels(phc_names)
    ax.legend(title="Scenario")
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    filepath = os.path.join(RESULTS_DIR, "overload_events_comparison.png")
    plt.savefig(filepath, dpi=150)
    plt.close()
    print(f"  [GRAPH] Overload events comparison saved to: {filepath}")


# -----------------------------------------------------------------------
# Summary Table — printed to terminal
# -----------------------------------------------------------------------

def print_comparison_table(all_results):
    """Print a side by side summary of key metrics across all scenarios.

    This is the quick-reference comparison table for the dissertation.
    """
    phc_names = list(all_results[0]["phc_results"].keys())

    print(f"\n{'='*75}")
    print("  EXPERIMENT COMPARISON SUMMARY")
    print(f"{'='*75}")

    header = f"  {'Metric':<35}"
    for r in all_results:
        header += f" {r['label']:>18}"
    print(header)
    print(f"{'-'*75}")

    # Per-PHC average wait rows
    for phc in phc_names:
        row = f"  {phc + ' Avg Wait (min)':<35}"
        for r in all_results:
            val = r["phc_results"][phc]["avg_wait_min"]
            row += f" {val:>18.1f}"
        print(row)

    print(f"{'-'*75}")

    # Per-PHC completion rate rows
    for phc in phc_names:
        row = f"  {phc + ' Completion Rate':<35}"
        for r in all_results:
            val = r["phc_results"][phc]["completion_rate"]
            row += f" {val:>17.1f}%"
        print(row)

    print(f"{'-'*75}")

    # Total overload alerts
    row = f"  {'Total Overload Alerts':<35}"
    for r in all_results:
        row += f" {len(r['overload_events']):>18}"
    print(row)

    # Redeployments made
    row = f"  {'Redeployments Made':<35}"
    for r in all_results:
        row += f" {len(r['redeployments']):>18}"
    print(row)

    print(f"{'='*75}\n")


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

if __name__ == "__main__":
    print("\n  PHC SURGE COORDINATION — EXPERIMENT RUNNER")
    print("  Three scenarios | Matched seeds | Auto export\n")

    # Run all three scenarios
    all_results = run_experiments()

    # Export CSV
    export_csv(all_results)

    # Generate graphs
    print("\n  Generating graphs...")
    graph_avg_wait(all_results)
    graph_queue_over_time(all_results)
    graph_overload_events(all_results)

    # Print comparison table
    print_comparison_table(all_results)

    print("  All outputs saved to the 'results/' folder.\n")