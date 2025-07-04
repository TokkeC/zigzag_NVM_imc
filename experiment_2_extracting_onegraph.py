import os
import json
import glob
from math import prod
import matplotlib.pyplot as plt
import numpy as np
import re


def get_performance_for_layers(directory_path: str, target_layer_names: list[str]) -> dict:
    """
    Parses all ZigZag JSON output files in a directory to find the target layers
    and calculate their performance metrics.
    """
    json_files = glob.glob(os.path.join(directory_path, '_*.json'))
    if not json_files:
        print(f"Warning: No ZigZag layer output files found in directory: {directory_path}")
        return {}

    layer_results = {}
    found_layers = set()

    for file_path in json_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            current_layer_name = data.get('inputs', {}).get('layer', {}).get('name', '')
            if current_layer_name not in target_layer_names:
                continue

            # --- Found a target layer, extract data and calculate metrics ---
            loop_dims = data.get('inputs', {}).get('layer', {}).get('loop_dimensions', {})
            if not loop_dims:
                continue

            total_energy_pj = data.get('outputs', {}).get('energy', {}).get('energy_total', 0)
            operational_energy_pj = data.get('outputs', {}).get('energy', {}).get('operational_energy', 0)
            latency_info = data.get('outputs', {}).get('latency', {})
            tclk_ns = data.get('outputs', {}).get('clock', {}).get('tclk (ns)', 0)
            total_area_mm2 = data.get('outputs', {}).get('area (mm^2)', {}).get('total_area', 0)
            imc_area_mm2 = data.get('outputs', {}).get('area (mm^2)', {}).get('total_area_breakdown:', {}).get(
                'imc_area', total_area_mm2)

            total_macs = prod(loop_dims.values())
            total_ops = total_macs * 2

            mac_computation_cycles = latency_info.get('computation_breakdown', {}).get('mac_computation', 0)
            onloading_latency_cycles = latency_info.get('data_onloading', 0)
            offloading_latency_cycles = latency_info.get('data_offloading', 0)
            effective_total_cycles = latency_info.get('computation',
                                                      0) + onloading_latency_cycles + offloading_latency_cycles

            operational_latency_s = (mac_computation_cycles * tclk_ns) * 1e-9
            effective_latency_s = (effective_total_cycles * tclk_ns) * 1e-9

            total_energy_j = total_energy_pj * 1e-12
            operational_energy_j = operational_energy_pj * 1e-12

            layer_results[current_layer_name] = {
                'effective_throughput_tops': (total_ops / effective_latency_s) / 1e12 if effective_latency_s > 0 else 0,
                'operational_throughput_tops': (
                                                           total_ops / operational_latency_s) / 1e12 if operational_latency_s > 0 else 0,
                'effective_tops_per_watt': (total_ops / total_energy_j) / 1e12 if total_energy_j > 0 else 0,
                'operational_tops_per_watt': (
                                                         total_ops / operational_energy_j) / 1e12 if operational_energy_j > 0 else 0,
                'effective_tops_per_mm2': ((
                                                       total_ops / effective_latency_s) / 1e12) / imc_area_mm2 if imc_area_mm2 > 0 and effective_latency_s > 0 else 0,
                'operational_tops_per_mm2': ((
                                                         total_ops / operational_latency_s) / 1e12) / imc_area_mm2 if imc_area_mm2 > 0 and operational_latency_s > 0 else 0,
            }
            found_layers.add(current_layer_name)

            # If we've found all target layers, we can stop searching
            if len(found_layers) == len(target_layer_names):
                break

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error processing file {file_path}: {e}")
            continue

    if len(found_layers) != len(target_layer_names):
        missing = set(target_layer_names) - found_layers
        print(f"Warning: Could not find data for all target layers in {directory_path}. Missing: {missing}")

    return layer_results


def plot_arch_comparison_for_two_layers(arch_results: dict, peak_performance_data: dict, target_layer_names: list[str]):
    """
    Generates a figure with three bar chart subplots comparing the performance
    of different architectures for two specified layers.
    """
    if not arch_results or len(target_layer_names) != 2:
        print("Error: Requires results for exactly two layers to plot.")
        return

    arch_names = list(arch_results.keys())
    x_pos = np.arange(len(arch_names))
    bar_width = 0.2  # Narrower bars for grouping

    fig, axes = plt.subplots(1, 3, figsize=(15, 6.5))

    layer1_name, layer2_name = target_layer_names
    layer1_short_name = layer1_name.split('/')[-2]
    layer1_short_name = "L1.0 C1"
    layer2_short_name = layer2_name.split('/')[-2]
    layer2_short_name = "L4.1 C2"

    # Colors for the two layers, chosen fr good contrast and colorblind-friendliness
    colors_l1 = ('#1f77b4', '#aec7e8')  # Effective (dark blue), Operational (light blue)
    colors_l2 = ('#ff7f0e', '#ffbb78')  # Effective (dark orange), Operational (light orange)

    # --- Data Extraction ---
    metrics = ['throughput_tops', 'tops_per_watt', 'tops_per_mm2']
    plot_data = {metric: {} for metric in metrics}

    for metric in metrics:
        plot_data[metric]['l1_eff'] = [d.get(layer1_name, {}).get(f'effective_{metric}', 0) for d in
                                       arch_results.values()]
        plot_data[metric]['l1_op'] = [d.get(layer1_name, {}).get(f'operational_{metric}', 0) for d in
                                      arch_results.values()]
        plot_data[metric]['l2_eff'] = [d.get(layer2_name, {}).get(f'effective_{metric}', 0) for d in
                                       arch_results.values()]
        plot_data[metric]['l2_op'] = [d.get(layer2_name, {}).get(f'operational_{metric}', 0) for d in
                                      arch_results.values()]
        # Correctly get the peak performance key, which matches the 'metric' variable
        plot_data[metric]['peak'] = [peak_performance_data.get(name, {}).get(metric, 0) for name in arch_names]

    # --- Plotting ---
    plot_titles = ['Throughput ($\eta_{ops}$)', 'Energy Efficiency ($\epsilon_{ops}$)',
                   'Area Efficiency ($\delta_{ops}$)']
    y_labels = ['TOP/s', 'TOP/s/W', 'TOP/s/mm²']

    for i, (ax, metric) in enumerate(zip(axes, metrics)):
        # Plot bars
        ax.bar(x_pos - 1.5 * bar_width, plot_data[metric]['l1_eff'], bar_width, color=colors_l1[0])
        ax.bar(x_pos - 0.5 * bar_width, plot_data[metric]['l1_op'], bar_width, color=colors_l1[1])
        ax.bar(x_pos + 0.5 * bar_width, plot_data[metric]['l2_eff'], bar_width, color=colors_l2[0])
        ax.bar(x_pos + 1.5 * bar_width, plot_data[metric]['l2_op'], bar_width, color=colors_l2[1])

        # Plot peak performance lines across each group
        for j, peak_val in enumerate(plot_data[metric]['peak']):
            ax.hlines(y=peak_val, xmin=x_pos[j] - 2 * bar_width, xmax=x_pos[j] + 2 * bar_width,
                      color='red', linestyle='-', linewidth=2.5, zorder=5)

        # Formatting
        ax.set_title(plot_titles[i], fontsize=22, pad=20)
        ax.set_ylabel(y_labels[i], fontsize=18)
        ax.set_yscale('log')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(arch_names, rotation=45, ha="right", fontsize=12)
        ax.grid(True, which='both', axis='y', linestyle='--', linewidth=0.5)
        ax.tick_params(axis='y', labelsize=12)

    # --- Legend and Layout ---
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=colors_l1[0], label=f'{layer1_short_name} Effective (Workload)'),
        Patch(facecolor=colors_l1[1], label=f'{layer1_short_name} Operational (Workload)'),
        Patch(facecolor=colors_l2[0], label=f'{layer2_short_name} Effective (Workload)'),
        Patch(facecolor=colors_l2[1], label=f'{layer2_short_name} Operational (Workload)'),
        Line2D([0], [0], color='red', linestyle='-', linewidth=2, label='Peak (Hardware Limit)')
    ]

    fig.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, 0.96), ncol=3, fontsize=16)
    fig.suptitle(f"Performance Comparison across ReRAM and SRAM Architectures (same area)", fontsize=24, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    # plt.show()
    plt.savefig('performance_comparison_exp2_samearea.png', dpi=300)
    plt.close(fig)


if __name__ == '__main__':
    # ========================== USER CONFIGURATION ==========================
    # --- 1. SET THE TWO TARGET LAYER NAMES ---
    TARGET_LAYER_NAMES = ["/layer1/layer1.0/conv1/Conv", "/layer4/layer4.1/conv2/Conv"]

    # --- 2. DEFINE YOUR 8 ARCHITECTURES AND THEIR DIRECTORY PATHS ---
    architectures_to_compare = {
        "1T1R-R/S": "outputs/Experiment2_paper4_reram-resnet18",
        "1T1R-R/R": "outputs/Experiment2_paper4_reram_rbuffer-resnet18",
        "1T1R-S/S": "outputs/Experiment2_paper4_sram-resnet18",
        "1T1R-S/R": "outputs/Experiment2_paper4_sram_rbuffer-resnet18",

        "2T2R-R/S": "outputs/Experiment2_paper3_reram-resnet18",
        "2T2R-R/R": "outputs/Experiment2_paper3_reram_rbuffer-resnet18",
        "2T2R-S/S": "outputs/Experiment2_paper3_sram-resnet18",
        "2T2R-S/R": "outputs/Experiment2_paper3_sram_rbuffer-resnet18",
    }

    # --- 3. DEFINE THE PEAK PERFORMANCE DATA FOR EACH ARCHITECTURE ---
    # The keys here MUST match the metric names: 'throughput_tops', 'tops_per_watt', 'tops_per_mm2'
    # same array size
    # peak_performance_data = {
    #     "1T1R-S/R": {"throughput_tops": 1.037, "tops_per_watt": 34.11, "tops_per_mm2": 1.176},
    #     "1T1R-S/S": {"throughput_tops": 1.037, "tops_per_watt": 34.11, "tops_per_mm2": 1.176},
    #     "1T1R-R/R": {"throughput_tops": 0.03942358174612351, "tops_per_watt": 4.92338048670841, "tops_per_mm2": 0.06081661325756115},
    #     "1T1R-R/S": {"throughput_tops": 0.03942358174612351, "tops_per_watt": 4.92338048670841, "tops_per_mm2": 0.06081661325756115},
    #     "2T2R-S/R": {"throughput_tops": 3.8400825017724993, "tops_per_watt": 59.28581930630848, "tops_per_mm2": 0.7591355438930302},
    #     "2T2R-S/S": {"throughput_tops": 3.8400825017724993, "tops_per_watt": 59.28581930630848, "tops_per_mm2": 0.7591355438930302},
    #     "2T2R-R/R": {"throughput_tops": 0.6596885310730545, "tops_per_watt": 20.889162469462704, "tops_per_mm2": 1.316715805422651},
    #     "2T2R-R/S": {"throughput_tops": 0.6596885310730545, "tops_per_watt": 20.889162469462704, "tops_per_mm2": 1.316715805422651},
    # }
    # same number of ADCs
    # peak_performance_data = {
    #     "1T1R-S/R": {"throughput_tops": 0.016216592868499902, "tops_per_watt": 34.115689244707, "tops_per_mm2": 1.1762292878967673},
    #     "1T1R-S/S": {"throughput_tops": 0.016216592868499902, "tops_per_watt": 34.115689244707, "tops_per_mm2": 1.1762292878967673},
    #     "1T1R-R/R": {"throughput_tops": 0.03942358174612351, "tops_per_watt": 4.92338048670841, "tops_per_mm2": 0.06081661325756115},
    #     "1T1R-R/S": {"throughput_tops": 0.03942358174612351, "tops_per_watt": 4.92338048670841, "tops_per_mm2": 0.06081661325756115},
    #     "2T2R-S/R": {"throughput_tops": 0.1200025781803906, "tops_per_watt": 27.408803885965394, "tops_per_mm2": 0.7591355438930302},
    #     "2T2R-S/S": {"throughput_tops": 0.1200025781803906, "tops_per_watt": 27.408803885965394, "tops_per_mm2": 0.7591355438930302},
    #     "2T2R-R/R": {"throughput_tops": 0.6596885310730545, "tops_per_watt": 20.889162469462704, "tops_per_mm2": 1.316715805422651},
    #     "2T2R-R/S": {"throughput_tops": 0.6596885310730545, "tops_per_watt": 20.889162469462704, "tops_per_mm2": 1.316715805422651},
    # }
    # Same area
    peak_performance_data = {
        "1T1R-S/R": {"throughput_tops": 0.8330528316826986, "tops_per_watt": 31.61563557103075,
                     "tops_per_mm2": 1.3035410730646246},
        "1T1R-S/S": {"throughput_tops": 0.8330528316826986, "tops_per_watt": 31.61563557103075,
                     "tops_per_mm2": 1.3035410730646246},
        "1T1R-R/R": {"throughput_tops": 0.03942358174612351, "tops_per_watt": 4.92338048670841,
                     "tops_per_mm2": 0.06081661325756115},
        "1T1R-R/S": {"throughput_tops": 0.03942358174612351, "tops_per_watt": 4.92338048670841,
                     "tops_per_mm2": 0.06081661325756115},
        "2T2R-S/R": {"throughput_tops": 0.445193095691076, "tops_per_watt": 32.726424594353155,
                     "tops_per_mm2": 0.6831200320656732},
        "2T2R-S/S": {"throughput_tops": 0.445193095691076, "tops_per_watt": 32.726424594353155,
                     "tops_per_mm2": 0.6831200320656732},
        "2T2R-R/R": {"throughput_tops": 0.9059443328334794, "tops_per_watt": 21.126737838950753,
                     "tops_per_mm2": 1.3929096584658391},
        "2T2R-R/S": {"throughput_tops": 0.9059443328334794, "tops_per_watt": 21.126737838950753,
                     "tops_per_mm2": 1.3929096584658391},
    }
    # ========================================================================

    all_arch_results = {}
    for arch_name, dir_path in architectures_to_compare.items():
        print(f"\nProcessing Architecture: {arch_name}")
        if not os.path.isdir(dir_path):
            print(f"Error: Directory not found at '{dir_path}'. Please update the path.")
            continue

        results = get_performance_for_layers(dir_path, TARGET_LAYER_NAMES)
        if results:
            all_arch_results[arch_name] = results

    if all_arch_results:
        plot_arch_comparison_for_two_layers(all_arch_results, peak_performance_data, TARGET_LAYER_NAMES)
    else:
        print("\nNo valid data found for any architecture. Cannot generate plot.")
