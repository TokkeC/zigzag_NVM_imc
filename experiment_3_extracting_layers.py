import os
import json
import glob
from math import prod
import matplotlib.pyplot as plt
import numpy as np
import re

# ========================== USER CONFIGURATION ==========================

# --- 1. SET THE BASE DIRECTORY FOR YOUR EXPERIMENTS ---
# This should be the path that contains all your 'Experiment3_reramCiM...' folders.
BASE_DIRECTORY = "outputs/Experiment3"  # e.g., "outputs/Experiment3" or "/path/to/your/experiments"

# --- 2. DEFINE THE IMC SIZES FOR THE X-AXIS ---
# These should match the numbers in your directory names.
IMC_SIZES = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096]

# --- 3. DEFINE THE REPRESENTATIVE LAYERS ---
# For each layer type you want to plot, create an entry in this dictionary.
# - 'workload_model': The model name used in the folder path (e.g., 'resnet18').
# - 'layer_name': The exact layer name as found inside the JSON file's "name" field.
# - 'legend_label': The label for the plot legend (e.g., 'conv', 'fc').
REPRESENTATIVE_LAYERS = {
    # 'Peak (system)': {
    #         'workload_model': 'peak_workload',
    #         'layer_name': 'peak_performance_layer',
    #         'legend_label': 'Peak (system)'
    # },
    'Conv (A)': {
        'workload_model': 'resnet18',
        'layer_name': '/layer1/layer1.0/conv1/Conv',
        'legend_label': 'Conv (A)'
    },
    'Conv (W)': {
            'workload_model': 'resnet50',
            'layer_name': '/layer3/layer3.0/conv2/Conv',
            'legend_label': 'Conv (W)'
        },
    'FC (large)': {
        'workload_model': 'llama2-7b_conv_prefill',
        'layer_name': 'key_proj',
        'legend_label': 'FC (large)'
    },
    'FC (small)': {
            'workload_model': 'resnet50',
            'layer_name': '/fc/Gemm',
            'legend_label': 'FC (small)'
        },
    'PW': {
        'workload_model': 'mobilenetv2',
        'layer_name': '/features/features.3/conv/conv.2/Conv',  #
        'legend_label': 'PW'
    },
    'DW': {
        'workload_model': 'mobilenetv2',
        'layer_name': '/features/features.6/conv/conv.1/conv.1.0/Conv',
        'legend_label': 'DW'
    },
}

# --- 4. DEFINE THE PEAK PERFORMANCE DATA ---
# For each IMC size, provide the peak TOP/s/W and TOP/s/mm^2.
# The keys MUST be the integer sizes from the IMC_SIZES list.
PEAK_PERFORMANCE_DATA = {
    # Format: size: {'tops_per_watt': value, 'tops_per_mm2': value}
    # EXAMPLE: Replace these with your actual peak performance values.
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


def get_single_layer_performance(directory_path: str, target_layer_name: str) -> dict:
    """
    Parses all ZigZag JSON output files in a directory to find ONE target layer
    and calculate its performance metrics.
    """
    json_files = glob.glob(os.path.join(directory_path, '*.json'))
    if not json_files:
        return {}

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            current_layer_name = data.get('inputs', {}).get('layer', {}).get('name', '')
            # print(current_layer_name)
            if current_layer_name != target_layer_name:
                continue

            # --- Found the target layer, extract data and calculate metrics ---
            loop_dims = data.get('inputs', {}).get('layer', {}).get('loop_dimensions', {})
            if not loop_dims:
                continue

            total_energy_pj = data.get('outputs', {}).get('energy', {}).get('energy_total', 0)
            latency_info = data.get('outputs', {}).get('latency', {})
            tclk_ns = data.get('outputs', {}).get('clock', {}).get('tclk (ns)', 0)
            total_area_mm2 = data.get('outputs', {}).get('area (mm^2)', {}).get('total_area', 0)
            imc_area_mm2 = data.get('outputs', {}).get('area (mm^2)', {}).get('total_area_breakdown:', {}).get(
                'imc_area', total_area_mm2)

            total_macs = prod(loop_dims.values())
            total_ops = total_macs * 2

            onloading_latency_cycles = latency_info.get('data_onloading', 0)
            offloading_latency_cycles = latency_info.get('data_offloading', 0)
            effective_total_cycles = latency_info.get('computation',
                                                      0) + onloading_latency_cycles + offloading_latency_cycles
            effective_latency_s = (effective_total_cycles * tclk_ns) * 1e-9
            total_energy_j = total_energy_pj * 1e-12

            return {
                'effective_tops_per_watt': (total_ops / total_energy_j) / 1e12 if total_energy_j > 0 else 0,
                'effective_tops_per_mm2': ((
                                                   total_ops / effective_latency_s) / 1e12) / total_area_mm2 if total_area_mm2 > 0 and effective_latency_s > 0 else 0,
            }

        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            print(f"Error processing file {file_path}: {e}")
            continue

    return {}


def plot_performance_vs_imc_size(imc_sizes: list, layer_results: dict, peak_watt_data: list, peak_area_data: list,
                                 layer_configs: dict):
    """
    Generates a figure with two subplots showing TOP/s/W and TOP/s/mm^2 vs. IMC size.
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5))

    # THIS IS THE NEWLY ADDED LINE TO CREATE THE MAIN TITLE
    fig.suptitle('Single Layer System Performance with Scaling Array Sizes', fontsize=22)

    markers = ['s', '^', 'D', 'v', 'P', '*', 'X']
    x_labels = [f"{s}x{s}" for s in imc_sizes]

    # --- (a) Energy Efficiency (TOP/s/W) ---
    ax1 = axes[0]
    ax1.plot(x_labels, peak_watt_data, marker='o', linestyle='-', color='green', label='Peak', zorder=10)
    for i, (layer_type, data) in enumerate(layer_results.items()):
        label = layer_configs[layer_type]['legend_label']
        ax1.plot(x_labels, data['tops_per_watt'], marker=markers[i % len(markers)], linestyle='--', label=label)

    ax1.set_title('Energy Efficiency ($\epsilon_{ops}$)', loc='center', fontsize=18, pad=15)
    ax1.set_ylabel('TOP/s/W', fontsize=16)
    ax1.set_yscale('log')
    ax1.grid(True, which='both', linestyle='--', linewidth=0.5)

    # --- (b) Area Efficiency (TOP/s/mm²) ---
    ax2 = axes[1]
    ax2.plot(x_labels, peak_area_data, marker='o', linestyle='-', color='green', label='peak', zorder=10)
    for i, (layer_type, data) in enumerate(layer_results.items()):
        label = layer_configs[layer_type]['legend_label']
        ax2.plot(x_labels, data['tops_per_mm2'], marker=markers[i % len(markers)], linestyle='--', label=label)

    ax2.set_title('Area Efficiency ($\delta_{ops}$)', loc='center', fontsize=18, pad=15)
    ax2.set_ylabel('TOP/s/mm²', fontsize=16)
    ax2.set_yscale('log')
    ax2.grid(True, which='both', linestyle='--', linewidth=0.5)

    # --- Common Formatting ---
    for ax in axes:
        ax.set_xlabel('Array size', fontsize=16)
        ax.tick_params(axis='x', rotation=45, labelsize=14)
        ax.tick_params(axis='y', labelsize=14)

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.93), ncol=len(labels), fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.93])

    output_filename = 'reram_cim_performance_scaling.png'
    plt.savefig(output_filename, dpi=300)
    print(f"\n✅ Plot successfully saved to {output_filename}")
    plt.show()
    plt.close(fig)


if __name__ == '__main__':
    all_results = {layer_type: {'tops_per_watt': [], 'tops_per_mm2': []} for layer_type in REPRESENTATIVE_LAYERS.keys()}

    print("Starting data extraction...")
    for size in IMC_SIZES:
        for layer_type, params in REPRESENTATIVE_LAYERS.items():
            workload = params['workload_model']
            target_layer = params['layer_name']

            # Construct directory name based on the pattern from your image
            dir_name = f"Experiment3_reramCiM_{size}-{workload}"
            full_path = os.path.join(BASE_DIRECTORY, dir_name)

            if not os.path.isdir(full_path):
                print(f"-> 🚨 Warning: Directory not found: '{full_path}'. Appending NaN.")
                all_results[layer_type]['tops_per_watt'].append(np.nan)
                all_results[layer_type]['tops_per_mm2'].append(np.nan)
                continue

            perf = get_single_layer_performance(full_path, target_layer)

            if perf:
                print(f"-> Found data for {layer_type} (size {size})")
                all_results[layer_type]['tops_per_watt'].append(perf.get('effective_tops_per_watt', np.nan))
                all_results[layer_type]['tops_per_mm2'].append(perf.get('effective_tops_per_mm2', np.nan))
            else:
                print(f"-> 🚨 Warning: Data for layer '{target_layer}' not found in '{full_path}'. Appending NaN.")
                all_results[layer_type]['tops_per_watt'].append(np.nan)
                all_results[layer_type]['tops_per_mm2'].append(np.nan)

    # Prepare peak data for plotting
    peak_tops_per_watt = [PEAK_PERFORMANCE_DATA.get(s, {}).get('tops_per_watt', np.nan) for s in IMC_SIZES]
    peak_tops_per_mm2 = [PEAK_PERFORMANCE_DATA.get(s, {}).get('tops_per_mm2', np.nan) for s in IMC_SIZES]

    plot_performance_vs_imc_size(
        imc_sizes=IMC_SIZES,
        layer_results=all_results,
        peak_watt_data=peak_tops_per_watt,
        peak_area_data=peak_tops_per_mm2,
        layer_configs=REPRESENTATIVE_LAYERS
    )
