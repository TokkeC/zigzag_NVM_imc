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
    is_downsample = 1 if 'ds' in get_short_layer_name(s).lower() else 0
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
    Generates a single figure with three subplots comparing the performance of different architectures.
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

    # Define a color map for the architectures with good contrast
    colors = plt.cm.get_cmap('Dark2', len(all_results))

    # --- Create a figure with 3 subplots side-by-side ---
    fig, axes = plt.subplots(1, 3, figsize=(15, 6.5))  # 1 row, 3 columns

    # --- Plot 1: Throughput (TOP/s) ---
    ax1 = axes[0]
    for i, (arch_name, results) in enumerate(all_results.items()):
        color = colors(i)
        y_effective = [results.get(layer, {}).get('effective_throughput_tops', 0) for layer in sorted_layer_names]
        y_operational = [results.get(layer, {}).get('operational_throughput_tops', 0) for layer in sorted_layer_names]
        peak_val = peak_performance_data.get(arch_name, {}).get('throughput_tops', 0)

        ax1.plot(x_pos, y_effective, marker='o', linestyle='-', color=color)
        ax1.plot(x_pos, y_operational, marker='x', linestyle=':', color=color)
        ax1.axhline(y=peak_val, color=color, linestyle='--')

    ax1.set_title('Throughput ($\eta_{ops}$)', fontsize=22)
    ax1.set_ylabel('TOP/s', fontsize=18)
    ax1.set_yscale('log')

    # --- Plot 2: Energy Efficiency (TOPS/W) ---
    ax2 = axes[1]
    for i, (arch_name, results) in enumerate(all_results.items()):
        color = colors(i)
        y_effective = [results.get(layer, {}).get('effective_tops_per_watt', 0) for layer in sorted_layer_names]
        y_operational = [results.get(layer, {}).get('operational_tops_per_watt', 0) for layer in sorted_layer_names]
        peak_val = peak_performance_data.get(arch_name, {}).get('tops_per_watt', 0)

        ax2.plot(x_pos, y_effective, marker='o', linestyle='-', color=color)
        ax2.plot(x_pos, y_operational, marker='x', linestyle=':', color=color)
        ax2.axhline(y=peak_val, color=color, linestyle='--')

    ax2.set_title('Energy Efficiency ($\epsilon_{ops}$)', fontsize=22)
    ax2.set_ylabel('TOP/s/W', fontsize=18)
    ax2.set_yscale('log')

    # --- Plot 3: Area Efficiency (TOPS/mm^2) ---
    ax3 = axes[2]
    for i, (arch_name, results) in enumerate(all_results.items()):
        color = colors(i)
        y_effective = [results.get(layer, {}).get('effective_tops_per_mm2', 0) for layer in sorted_layer_names]
        y_operational = [results.get(layer, {}).get('operational_tops_per_mm2', 0) for layer in sorted_layer_names]
        peak_val = peak_performance_data.get(arch_name, {}).get('tops_per_mm2', 0)

        ax3.plot(x_pos, y_effective, marker='o', linestyle='-', color=color)
        ax3.plot(x_pos, y_operational, marker='x', linestyle=':', color=color)
        ax3.axhline(y=peak_val, color=color, linestyle='--')

    ax3.set_title('Area Efficiency ($\delta_{ops}$)', fontsize=22)
    ax3.set_ylabel('TOP/s/mm²)', fontsize=18)
    ax3.set_yscale('log')

    # --- General formatting for all subplots ---
    for ax in axes:
        ax.set_xlabel('ResNet-18 Layers', fontsize=18)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(short_layer_names, rotation=90, fontsize=12)
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        ax.tick_params(axis='y', labelsize=12)

    # --- Create a single, shared legend for the entire figure ---
    # Create dummy lines for the legend categories
    from matplotlib.lines import Line2D
    legend_elements = []
    for i, arch_name in enumerate(all_results.keys()):
        color = colors(i)
        legend_elements.append(
            Line2D([0], [0], color=color, lw=2, linestyle='-', label=f'{arch_name}'))

    color = 'black'
    legend_elements.append(
        Line2D([0], [0], color=color, lw=2, linestyle='-', marker='o', label=f'Effective (Workload)'))
    legend_elements.append(
        Line2D([0], [0], color=color, lw=2, linestyle=':', marker='x', label=f'Operational (Workload)'))
    legend_elements.append(
        Line2D([0], [0], color=color, lw=2, linestyle='--', label=f'Peak (Hardware Limit)'))

    fig.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, 0.95 ), ncol=3, fontsize=16)

    # Adjust layout to prevent titles/labels from overlapping
    fig.tight_layout(rect=[0, 0.01, 1, 0.83])   # Adjust rect to make space for the legend at the top
    fig.suptitle(f"Performance Comparison ResNet-18: ReRAM CiM 1T1R and 2T2R Pseudo-Crossbar", fontsize=24, y=1.00)

    # plt.show()
    plt.savefig('performance_comparison_combined.png', dpi=300)
    print("Saved combined performance plot to performance_comparison_combined.png")
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
            "throughput_tops": 0.03942358174612351,
            "tops_per_watt": 4.92338048670841,
            "tops_per_mm2": 0.06081661325756115
        },
        "2T2R Pseudo-Crossbar": {
            "throughput_tops": 0.6596885310730545,
            "tops_per_watt": 20.889162469462704,
            "tops_per_mm2": 1.316715805422651
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
