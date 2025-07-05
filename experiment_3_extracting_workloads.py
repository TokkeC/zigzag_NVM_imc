import os
import json
import glob
from math import prod
import matplotlib.pyplot as plt
import numpy as np

# ========================== USER CONFIGURATION ==========================

# --- 1. SET THE BASE DIRECTORY FOR YOUR EXPERIMENTS ---
BASE_DIRECTORY = "outputs/Experiment3"

# --- 2. DEFINE THE IMC SIZES FOR THE X-AXIS ---
IMC_SIZES = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096]

# --- 3. DEFINE THE WORKLOADS TO PLOT ---
# For each workload to plot, map a legend label to the model name in the folder path.
WORKLOADS_TO_PLOT = {
    'ResNet-18': 'resnet18',
    'ResNet-50': 'resnet50',
    'MobileNetV2': 'mobilenetv2',
    'LLaMA-7B (Prefill)': 'llama2-7b_conv_prefill',
    'LLaMA-7B (Decode)': 'llama2-7b_conv_decode',
}

# --- 4. DEFINE THE PEAK PERFORMANCE DATA (remains the same) ---
PEAK_PERFORMANCE_DATA = {
    16: {'tops_per_watt': 4.496303165580095, 'tops_per_mm2': 8.988652173408909e-05},
    32: {'tops_per_watt': 7.501700473486302, 'tops_per_mm2': 0.00035941618742890165},
    64: {'tops_per_watt': 11.267326547366244, 'tops_per_mm2': 0.0014345913334402405},
    128: {'tops_per_watt': 15.042854986832618, 'tops_per_mm2': 0.005708110499066903},
    256: {'tops_per_watt': 18.07043371757108, 'tops_per_mm2': 0.022503393512180676},
    512: {'tops_per_watt': 20.09236421555545, 'tops_per_mm2': 0.0861458409526403},
    1024: {'tops_per_watt': 21.28306262620252, 'tops_per_mm2': 0.30029775828232713},
    2048: {'tops_per_watt': 21.932949514770385, 'tops_per_mm2': 0.8162776697554995},
    4096: {'tops_per_watt': 22.2730071361997, 'tops_per_mm2': 1.4681456316840247},
}


# ========================================================================

def get_workload_performance(directory_path: str) -> dict:
    """
    Parses all layer JSON files in a directory to calculate the
    performance for the complete workload.
    """
    json_files = glob.glob(os.path.join(directory_path, '*.json'))
    if not json_files:
        return {}

    total_workload_ops = 0
    total_workload_energy_j = 0
    total_workload_latency_s = 0
    # Hardware area is constant for a given run, so we only need to read it once.
    total_area_mm2 = -1

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # --- Extract data for this single layer ---
            loop_dims = data.get('inputs', {}).get('layer', {}).get('loop_dimensions', {})
            if not loop_dims:
                continue

            # Add this layer's values to the workload totals
            total_macs = prod(loop_dims.values())
            total_workload_ops += total_macs * 2

            total_energy_pj = data.get('outputs', {}).get('energy', {}).get('energy_total', 0)
            total_workload_energy_j += total_energy_pj * 1e-12

            latency_info = data.get('outputs', {}).get('latency', {})
            tclk_ns = data.get('outputs', {}).get('clock', {}).get('tclk (ns)', 0)
            onloading_latency_cycles = latency_info.get('data_onloading', 0)
            offloading_latency_cycles = latency_info.get('data_offloading', 0)
            effective_total_cycles = latency_info.get('computation',
                                                      0) + onloading_latency_cycles + offloading_latency_cycles
            total_workload_latency_s += (effective_total_cycles * tclk_ns) * 1e-9

            # Get the total area from the first file we process
            if total_area_mm2 < 0:
                total_area_mm2 = data.get('outputs', {}).get('area (mm^2)', {}).get('total_area', 0)

        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            print(f"Error processing file {file_path}: {e}")
            continue

    # --- Calculate overall workload performance from the summed totals ---
    if total_workload_energy_j > 0 and total_workload_latency_s > 0 and total_area_mm2 > 0:
        return {
            'tops_per_watt': (total_workload_ops / total_workload_energy_j) / 1e12,
            'tops_per_mm2': ((total_workload_ops / total_workload_latency_s) / 1e12) / total_area_mm2,
        }
    else:
        return {}


def plot_performance_vs_imc_size(imc_sizes: list, workload_results: dict, peak_watt_data: list, peak_area_data: list,
                                 workload_configs: dict):
    """
    Generates a figure with two subplots showing TOP/s/W and TOP/s/mm^2 vs. IMC size.
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5))
    fig.suptitle('Full Workload System Performance with Scaling Array Sizes', fontsize=22)

    markers = ['s', '^', 'D', 'v', 'P', '*', 'X']
    x_labels = [f"{s}x{s}" for s in imc_sizes]

    # --- (a) Energy Efficiency (TOP/s/W) ---
    ax1 = axes[0]
    ax1.plot(x_labels, peak_watt_data, marker='o', linestyle='-', color='green', label='Peak', zorder=10)
    for i, (workload_label, data) in enumerate(workload_results.items()):
        ax1.plot(x_labels, data['tops_per_watt'], marker=markers[i % len(markers)], linestyle='--',
                 label=workload_label)
    ax1.set_title('Energy Efficiency ($\epsilon_{ops}$)', loc='center', fontsize=18, pad=10)
    ax1.set_ylabel('TOP/s/W', fontsize=16)
    ax1.set_yscale('log')
    ax1.grid(True, which='both', linestyle='--', linewidth=0.5)

    # --- (b) Area Efficiency (TOP/s/mm²) ---
    ax2 = axes[1]
    ax2.plot(x_labels, peak_area_data, marker='o', linestyle='-', color='green', label='Peak', zorder=10)
    for i, (workload_label, data) in enumerate(workload_results.items()):
        ax2.plot(x_labels, data['tops_per_mm2'], marker=markers[i % len(markers)], linestyle='--', label=workload_label)
    ax2.set_title('Area Efficiency ($\delta_{ops}$)', loc='center', fontsize=18, pad=10)
    ax2.set_ylabel('TOP/s/mm²', fontsize=16)
    ax2.set_yscale('log')
    ax2.grid(True, which='both', linestyle='--', linewidth=0.5)

    # --- Common Formatting ---
    for ax in axes:
        ax.set_xlabel('Array size', fontsize=16)
        ax.tick_params(axis='x', rotation=45, labelsize=14)
        ax.tick_params(axis='y', labelsize=14)
    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.94), ncol=3, fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.90])

    output_filename = 'reram_cim_WORKLOAD_performance_scaling.png'
    plt.savefig(output_filename, dpi=300)
    print(f"\n✅ Plot successfully saved to {output_filename}")
    plt.show()
    plt.close(fig)


if __name__ == '__main__':
    all_results = {label: {'tops_per_watt': [], 'tops_per_mm2': []} for label in WORKLOADS_TO_PLOT.keys()}

    print("Starting data extraction for full workloads...")
    for size in IMC_SIZES:
        for workload_label, workload_model_name in WORKLOADS_TO_PLOT.items():
            dir_name = f"Experiment3_reramCiM_{size}-{workload_model_name}"
            full_path = os.path.join(BASE_DIRECTORY, dir_name)

            if not os.path.isdir(full_path):
                print(f"-> 🚨 Warning: Directory not found: '{full_path}'. Appending NaN.")
                all_results[workload_label]['tops_per_watt'].append(np.nan)
                all_results[workload_label]['tops_per_mm2'].append(np.nan)
                continue

            perf = get_workload_performance(full_path)

            if perf:
                print(f"-> Processed data for {workload_label} (size {size})")
                all_results[workload_label]['tops_per_watt'].append(perf.get('tops_per_watt', np.nan))
                all_results[workload_label]['tops_per_mm2'].append(perf.get('tops_per_mm2', np.nan))
            else:
                print(f"-> 🚨 Warning: No data found in '{full_path}'. Appending NaN.")
                all_results[workload_label]['tops_per_watt'].append(np.nan)
                all_results[workload_label]['tops_per_mm2'].append(np.nan)

    # Prepare peak data for plotting
    peak_tops_per_watt = [PEAK_PERFORMANCE_DATA.get(s, {}).get('tops_per_watt', np.nan) for s in IMC_SIZES]
    peak_tops_per_mm2 = [PEAK_PERFORMANCE_DATA.get(s, {}).get('tops_per_mm2', np.nan) for s in IMC_SIZES]

    plot_performance_vs_imc_size(
        imc_sizes=IMC_SIZES,
        workload_results=all_results,
        peak_watt_data=peak_tops_per_watt,
        peak_area_data=peak_tops_per_mm2,
        workload_configs=WORKLOADS_TO_PLOT
    )