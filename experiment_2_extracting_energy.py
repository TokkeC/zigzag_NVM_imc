import os
import json
import glob
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch


def get_energy_breakdown_for_layers(directory_path: str, target_layer_names: list[str]) -> dict:
    """
    Parses ZigZag JSON output files in a directory to find the target layers
    and extract their detailed energy breakdowns.
    """
    if not os.path.isdir(directory_path):
        return {}

    layer_results = {}
    found_layers = set()

    for target_layer_name in target_layer_names:
        # Construct the expected filename for the target layer
        sanitized_name = target_layer_name.replace('/', '_')
        file_pattern = os.path.join(directory_path, f"{sanitized_name}_complete.json")
        matching_files = glob.glob(file_pattern)

        if not matching_files:
            # Fallback for filenames that might not have the `_complete` suffix
            file_pattern = os.path.join(directory_path, f"{sanitized_name}.json")
            matching_files = glob.glob(file_pattern)

        if not matching_files:
            print(f"Warning: No file found for layer '{target_layer_name}' in {directory_path}")
            continue

        file_path = matching_files[0]
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            op_energy_breakdown = data.get('outputs', {}).get('energy', {}).get('operational_energy_breakdown', {})
            mem_energy_breakdown = data.get('outputs', {}).get('energy', {}).get('memory_energy_breakdown_per_level', {})

            if not op_energy_breakdown or not mem_energy_breakdown:
                print(f"Warning: No energy breakdown information in {file_path}")
                continue

            # Extract energy components, accounting for different naming conventions for ReRAM vs SRAM
            cells_energy = op_energy_breakdown.get('cells', 0)
            wl_drivers_energy = op_energy_breakdown.get('wl_drivers', 0) + op_energy_breakdown.get('mults', 0)
            bl_drivers_energy = (op_energy_breakdown.get('bl_drivers', 0) +
                                 op_energy_breakdown.get('local_bl_precharging', 0) +
                                 op_energy_breakdown.get('analog_bl_addition', 0))

            adcs_energy = op_energy_breakdown.get('adcs', 0)
            dacs_energy = op_energy_breakdown.get('dacs', 0)
            digital_energy = op_energy_breakdown.get('adders_pv', 0) + op_energy_breakdown.get('accumulators', 0)
            weight_loading_energy = sum(mem_energy_breakdown.get('W', [0]))
            io_data_movement_energy = sum(mem_energy_breakdown.get('I', [0])) + sum(mem_energy_breakdown.get('O', [0]))

            breakdown = {
                'Reading Cells Current': cells_energy,
                'WL Drivers/Mults': wl_drivers_energy,
                'BL Drivers/Pre-Charge/\nAddition': bl_drivers_energy,
                'ADCs': adcs_energy,
                'DACs': dacs_energy,
                'Digital Logic': digital_energy,
                'I/O Data Movement': io_data_movement_energy,
                'Weight Loading': weight_loading_energy,
            }

            layer_results[target_layer_name] = breakdown
            found_layers.add(target_layer_name)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error processing energy in file {file_path}: {e}")
            continue

    if len(found_layers) != len(target_layer_names):
        missing = set(target_layer_names) - found_layers
        print(f"Warning: Could not find energy data for all target layers in {directory_path}. Missing: {missing}")

    return layer_results


def plot_energy_breakdown(arch_energy_data: dict, target_layer_names: list[str]):
    """
    Generates and saves a figure with a grouped and stacked bar chart for energy breakdown.
    """
    if not arch_energy_data:
        print("No energy data provided to plot.")
        return

    fig, ax = plt.subplots(figsize=(12, 7))
    arch_names = list(arch_energy_data.keys())
    layer1_name, layer2_name = target_layer_names
    layer_short_names = ["L1.0 C1", "L4.1 C2"]

    # Prepare dataframes for each layer
    energy_l1 = {arch: data.get(layer1_name, {}) for arch, data in arch_energy_data.items()}
    energy_l2 = {arch: data.get(layer2_name, {}) for arch, data in arch_energy_data.items()}
    df_l1 = pd.DataFrame(energy_l1).T.fillna(0)
    df_l2 = pd.DataFrame(energy_l2).T.fillna(0)

    # Use the component list and colors from the user's reference script
    component_colors = {
        'Reading Cells Current': '#d62728',
        'WL Drivers/Mults': '#ff7f0e',
        'BL Drivers/Pre-Charge/\nAddition': '#2ca02c',
        'ADCs': '#e377c2',
        'DACs': '#aec7e8',
        'Digital Logic': '#9467bd',
        'I/O Data Movement': '#1f77b4',
        'Weight Loading': '#8c564b',
    }

    energy_components = list(component_colors.keys())

    # Ensure both dataframes have all components for consistent stacking
    df_l1 = df_l1.reindex(columns=energy_components, fill_value=0)
    df_l2 = df_l2.reindex(columns=energy_components, fill_value=0)

    x_pos = np.arange(len(arch_names))
    bar_width = 0.4

    bottom_l1 = np.zeros(len(arch_names))
    bottom_l2 = np.zeros(len(arch_names))

    for component in energy_components:
        ax.bar(x_pos - bar_width / 2, df_l1[component], bar_width, bottom=bottom_l1,
               color=component_colors[component], edgecolor='black', zorder=3)
        ax.bar(x_pos + bar_width / 2, df_l2[component], bar_width, bottom=bottom_l2,
               color=component_colors[component], edgecolor='black', zorder=3)
        bottom_l1 += df_l1[component].values
        bottom_l2 += df_l2[component].values

    ax.set_title('Energy Breakdown of ReRAM and SRAM Architectures (same area)', fontsize=20, pad=20)
    ax.set_ylabel('Energy (pJ)', fontsize=18, labelpad=15)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(arch_names, rotation=45, ha="right", fontsize=14)
    ax.tick_params(axis='y', labelsize=12)
    ax.grid(True, which='major', axis='y', linestyle='--', linewidth=0.7, zorder=0)
    ax.set_ylim(0, 7.2e8)

    # Create legend
    component_legend_elements = [Patch(facecolor=color, edgecolor='black', label=comp) for comp, color in
                                 component_colors.items()]
    layer_legend_elements = [
        Patch(facecolor='dimgrey', label=f'Left Bars: {layer_short_names[0]}', alpha=0.7),
        Patch(facecolor='grey', label=f'Right Bars: {layer_short_names[1]}', alpha=0.7)
    ]

    # Place two legends inside the plot with larger fonts
    legend1 = ax.legend(handles=component_legend_elements, title='Energy Components', loc='upper right',
                        fontsize=14, title_fontsize=16)
    ax.add_artist(legend1)
    ax.legend(handles=layer_legend_elements, title='Layer of ResNet-18', loc='upper left',
              fontsize=14, title_fontsize=16)

    fig.tight_layout()
    # plt.show()
    plt.savefig('architecture_energy_breakdown_samesize.png', dpi=300)
    plt.close(fig)
    # print("\nPlot saved successfully as 'architecture_energy_breakdown.png'")


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
    # ========================================================================

    all_arch_energy_data = {}
    for arch_name, dir_path in architectures_to_compare.items():
        print(f"\nProcessing Architecture: {arch_name}")
        energy_data = get_energy_breakdown_for_layers(dir_path, TARGET_LAYER_NAMES)
        if energy_data:
            all_arch_energy_data[arch_name] = energy_data

    if all_arch_energy_data:
        plot_energy_breakdown(all_arch_energy_data, TARGET_LAYER_NAMES)
    else:
        print("\nNo valid data found for any architecture. Cannot generate plot.")
