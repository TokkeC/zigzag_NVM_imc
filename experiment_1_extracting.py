import os
import json
import glob
from math import prod
import matplotlib.pyplot as plt
import numpy as np
import re


def natural_sort_key(s: str) -> list:
    """
    Key for natural sorting of layer names (e.g., conv1, layer1.0, layer1.1, layer2.0...).
    This helps order the layers correctly on the plot's x-axis.
    """
    # Handle the initial conv1 and final fc layers specifically for correct ordering
    if 'conv1' in s and 'layer' not in s:
        return [0]  # Make sure conv1 comes first
    if 'fc' in s:
        return [999]  # Make sure fc comes last

    # Extract numbers for sorting the main layers
    numbers = [int(x) for x in re.findall(r'\d+', s)]
    # Add a flag for downsample layers to sort them correctly within a block
    is_downsample = 1 if 'ds' in get_short_layer_name(s) else 0
    return numbers + [is_downsample]


def get_short_layer_name(long_name: str) -> str:
    """
    Converts a long, path-like layer name from the JSON file into a short,
    descriptive label for plotting.
    Example: '/layer1/layer1.0/conv1/Conv' -> 'L1.0 C1'
    """
    if 'fc' in long_name.lower() or 'gemm' in long_name.lower():
        return 'FC'
    if 'conv1/Conv' in long_name and 'layer' not in long_name:
        return 'Initial C'

    # Regex to find patterns like 'layerX.Y' and 'convZ'
    match = re.search(r'layer(\d+)/layer\d+\.(\d+)/conv(\d+)', long_name)
    if match:
        return f"L{match.group(1)}.{match.group(2)} C{match.group(3)}"

    # Handle downsample layers
    match_ds = re.search(r'layer(\d+)/layer\d+\.(\d+)/downsample.*conv', long_name, re.IGNORECASE)
    if match_ds:
        return f"L{match_ds.group(1)}.{match_ds.group(2)} DS"

    # Fallback for any other format
    return os.path.basename(long_name).replace('_complete.json', '')


def calculate_performance_for_arch(directory_path: str) -> dict:
    """
    Parses all ZigZag JSON output files in a directory to calculate performance metrics.
    """
    json_files = glob.glob(os.path.join(directory_path, '_*.json'))
    if not json_files:
        print(f"Warning: No ZigZag layer output files found in directory: {directory_path}")
        return {}

    results = {}

    for file_path in json_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            layer_name = data.get('inputs', {}).get('layer', {}).get('name', os.path.basename(file_path))
            loop_dims = data.get('inputs', {}).get('layer', {}).get('loop_dimensions', {})
            if not loop_dims:
                continue

            # --- Extract data from JSON ---
            total_energy_pj = data.get('outputs', {}).get('energy', {}).get('energy_total', 0)
            operational_energy_pj = data.get('outputs', {}).get('energy', {}).get('operational_energy', 0)

            latency_info = data.get('outputs', {}).get('latency', {})
            tclk_ns = data.get('outputs', {}).get('clock', {}).get('tclk (ns)', 0)

            total_area_mm2 = data.get('outputs', {}).get('area (mm^2)', {}).get('total_area', 0)
            imc_area_mm2 = data.get('outputs', {}).get('area (mm^2)', {}).get('total_area_breakdown:', {}).get(
                'imc_area', total_area_mm2)

            # --- Calculate Total Operations ---
            total_macs = prod(loop_dims.values())
            total_ops = total_macs * 2

            # --- Calculate Latencies in Seconds ---
            mac_computation_cycles = latency_info.get('computation_breakdown', {}).get('mac_computation', 0)
            onloading_latency_cycles = latency_info.get('data_onloading', 0)
            offloading_latency_cycles = latency_info.get('data_offloading', 0)
            # Effective latency includes onloading, computation (with stalls), and offloading
            effective_total_cycles = latency_info.get('computation',
                                                      0) + onloading_latency_cycles + offloading_latency_cycles

            operational_latency_s = (mac_computation_cycles * tclk_ns) * 1e-9
            effective_latency_s = (effective_total_cycles * tclk_ns) * 1e-9

            # --- Calculate Energies in Joules ---
            total_energy_j = total_energy_pj * 1e-12
            operational_energy_j = operational_energy_pj * 1e-12

            # --- Calculate Throughputs (TOP/s) ---
            effective_throughput_tops = (total_ops / effective_latency_s) / 1e12 if effective_latency_s > 0 else 0
            operational_throughput_tops = (total_ops / operational_latency_s) / 1e12 if operational_latency_s > 0 else 0

            # --- Calculate Energy Efficiencies (TOPS/W) ---
            effective_tops_per_watt = (total_ops / total_energy_j) / 1e12 if total_energy_j > 0 else 0
            operational_tops_per_watt = (total_ops / operational_energy_j) / 1e12 if operational_energy_j > 0 else 0

            # --- Calculate Area Efficiencies (TOPS/mm^2) ---
            effective_tops_per_mm2 = effective_throughput_tops / total_area_mm2 if total_area_mm2 > 0 else 0
            operational_tops_per_mm2 = operational_throughput_tops / imc_area_mm2 if imc_area_mm2 > 0 else 0

            results[layer_name] = {
                'effective_throughput_tops': effective_throughput_tops,
                'operational_throughput_tops': operational_throughput_tops,
                'effective_tops_per_watt': effective_tops_per_watt,
                'operational_tops_per_watt': operational_tops_per_watt,
                'effective_tops_per_mm2': effective_tops_per_mm2,
                'operational_tops_per_mm2': operational_tops_per_mm2,
            }

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error processing file {file_path}: {e}")
            continue

    return results


def plot_performance_comparison(all_results: dict, peak_performance_data: dict):
    """
    Generates and saves plots comparing the performance of different architectures.
    """
    if not all_results:
        print("No results to plot.")
        return

    all_layer_names = set()
    for res in all_results.values():
        all_layer_names.update(res.keys())

    sorted_layer_names = sorted(list(all_layer_names), key=natural_sort_key)
    short_layer_names = [get_short_layer_name(name) for name in sorted_layer_names]
    x_pos = np.arange(len(short_layer_names))

    colors = plt.cm.get_cmap('Dark2', len(all_results))

    # --- Plot 1: Throughput (TOP/s) ---
    fig, ax = plt.subplots(figsize=(20, 9))
    for i, (arch_name, results) in enumerate(all_results.items()):
        color = colors(i)
        y_effective = [results.get(layer, {}).get('effective_throughput_tops', 0) for layer in sorted_layer_names]
        y_operational = [results.get(layer, {}).get('operational_throughput_tops', 0) for layer in sorted_layer_names]
        peak_val = peak_performance_data.get(arch_name, {}).get('throughput_tops', 0)

        ax.plot(x_pos, y_effective, marker='o', linestyle='-', color=color, label=f'{arch_name} - Effective (Workload)' , linewidth=2.5, markersize=8)
        ax.plot(x_pos, y_operational, marker='x', linestyle=':', color=color, label=f'{arch_name} - Effective Only Compute (Workload)')
        ax.axhline(y=peak_val, color=color, linestyle='--', label=f'{arch_name} - Peak (Hardware Limit)')

    ax.set_xlabel('ResNet-18 Layers', fontsize=12)
    ax.set_ylabel('Throughput (TOP/s)', fontsize=12)
    ax.set_title('Throughput $\eta_{ops}$ : Peak vs. Effective Workload', fontsize=16)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(short_layer_names, rotation=45, ha="right", fontsize=10)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    ax.legend(fontsize=10)
    ax.set_yscale('log')
    fig.tight_layout()
    plt.show()
    # plt.savefig('throughput_comparison.png')
    # print("Saved throughput plot to throughput_comparison.png")
    plt.close(fig)

    # --- Plot 2: Energy Efficiency (TOPS/W) ---
    fig, ax = plt.subplots(figsize=(20, 9))
    for i, (arch_name, results) in enumerate(all_results.items()):
        color = colors(i)
        y_effective = [results.get(layer, {}).get('effective_tops_per_watt', 0) for layer in sorted_layer_names]
        y_operational = [results.get(layer, {}).get('operational_tops_per_watt', 0) for layer in sorted_layer_names]
        peak_val = peak_performance_data.get(arch_name, {}).get('tops_per_watt', 0)

        ax.plot(x_pos, y_effective, marker='o', linestyle='-', color=color, label=f'{arch_name} - Effective (Workload)')
        ax.plot(x_pos, y_operational, marker='x', linestyle=':', color=color, label=f'{arch_name} - Effective Only Compute (Workload)')
        ax.axhline(y=peak_val, color=color, linestyle='--', label=f'{arch_name} - Peak (Hardware Limit)')

    ax.set_xlabel('ResNet-18 Layers', fontsize=12)
    ax.set_ylabel('Energy Efficiency (TOP/s/W)', fontsize=12)
    ax.set_title('Energy Efficiency $\epsilon_{ops}$: Peak vs. Effective Workload', fontsize=16)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(short_layer_names, rotation=45, ha="right", fontsize=10)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    ax.legend(fontsize=10)
    ax.set_yscale('log')
    fig.tight_layout()
    plt.show()
    # plt.savefig('energy_efficiency_comparison.png')
    # print("Saved energy efficiency plot to energy_efficiency_comparison.png")
    plt.close(fig)

    # --- Plot 3: Area Efficiency (TOPS/mm^2) ---
    fig, ax = plt.subplots(figsize=(20, 9))
    for i, (arch_name, results) in enumerate(all_results.items()):
        color = colors(i)
        y_effective = [results.get(layer, {}).get('effective_tops_per_mm2', 0) for layer in sorted_layer_names]
        y_operational = [results.get(layer, {}).get('operational_tops_per_mm2', 0) for layer in sorted_layer_names]
        peak_val = peak_performance_data.get(arch_name, {}).get('tops_per_mm2', 0)

        ax.plot(x_pos, y_effective, marker='o', linestyle='-', color=color, label=f'{arch_name} - Effective (Workload)')
        ax.plot(x_pos, y_operational, marker='x', linestyle=':', color=color, label=f'{arch_name} - Effective Only Compute (Workload)')
        ax.axhline(y=peak_val, color=color, linestyle='--', label=f'{arch_name} - Peak (Hardware Limit)')

    ax.set_xlabel('ResNet-18 Layers', fontsize=12)
    ax.set_ylabel('Area Efficiency (TOP/s/mm²)', fontsize=12)
    ax.set_title('Area Efficiency $\delta_{ops}$: Peak vs. Effective Workload', fontsize=16)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(short_layer_names, rotation=45, ha="right", fontsize=10)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    ax.legend(fontsize=10)
    ax.set_yscale('log')
    fig.tight_layout()
    plt.show()
    # plt.savefig('area_efficiency_comparison.png')
    # print("Saved area efficiency plot to area_efficiency_comparison.png")
    plt.close(fig)


if __name__ == '__main__':
    # --- DEFINE YOUR ARCHITECTURES AND THEIR DIRECTORY PATHS HERE ---
    architectures_to_compare = {
        "1T1R": "outputs/Experiment1_paper4_template-resnet18",
        "2T2R Pseudo-Crossbar": "outputs/Experiment1_paper3_template-resnet18",
    }

    # --- DEFINE THE PEAK PERFORMANCE DATA YOU PROVIDED ---
    peak_performance_data = {
        "1T1R": {
            "tops_per_watt": 33.810,
            "tops_per_mm2": 0.486,
            "throughput_tops": 0.315
        },
        "2T2R Pseudo-Crossbar": {
            "tops_per_watt": 84.082,
            "tops_per_mm2": 6.345,
            "throughput_tops": 2.84
        }
    }

    all_arch_results = {}
    for arch_name, dir_path in architectures_to_compare.items():
        print(f"\nProcessing Architecture: {arch_name}")
        if not os.path.isdir(dir_path):
            print(f"Error: Directory not found at '{dir_path}'. Please update the path.")
            continue

        results = calculate_performance_for_arch(dir_path)
        if results:
            all_arch_results[arch_name] = results

    # Plot the combined results, passing the peak performance data
    plot_performance_comparison(all_arch_results, peak_performance_data)
