import os
import json
import glob
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch


def get_area_breakdown_for_arch(directory_path: str) -> dict | None:
    """
    Parses the first available ZigZag JSON output file in a directory
    to extract the detailed area breakdown. The area is assumed to be
    the same for all layers of a given architecture.
    """
    if not os.path.isdir(directory_path):
        print(f"Error: Directory not found at '{directory_path}'. Please update the path.")
        return None

    json_files = glob.glob(os.path.join(directory_path, '_layer*.json'))
    if not json_files:
        print(f"Warning: No ZigZag layer output files found in directory: {directory_path}")
        return None

    # Take the first layer file found, as area is constant across layers for an arch
    file_path = json_files[0]

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        area_data = data.get('outputs', {}).get('area (mm^2)', {})
        if not area_data:
            print(f"Warning: No area information in {file_path}")
            return None

        breakdown = {}
        breakdown["Digital Logic"] = 0
        # Extract IMC and Memory area breakdowns from the 'total_area_breakdown_further' key
        imc_breakdown = area_data.get('total_area_breakdown_further', {}).get('imc_area_breakdown', {})
        mem_breakdown = area_data.get('total_area_breakdown_further', {}).get('mem_area_breakdown', {})

        # Add all IMC components to the breakdown dictionary
        for component, value in imc_breakdown.items():
            if value > 0:  # Only include components with non-zero area
                if component == "wl_drivers":
                    breakdown["WL Drivers"] = value
                elif component == "bl_drivers":
                    breakdown["BL Drivers"] = value
                elif component == "adcs":
                    breakdown["ADCs"] = value
                elif component == "mults":
                    breakdown["Access TXs"] = value
                elif component == "access_tx":
                    breakdown["Access TXs"] = value
                elif component == "adders_pv":
                    breakdown["Digital Logic"] = breakdown["Digital Logic"] + value
                elif component == "accumulators":
                    breakdown["Digital Logic"] = breakdown["Digital Logic"] + value
                else:
                    breakdown[component] = value

        # Find the L1 cache entry (SRAM or ReRAM) and add it to the breakdown
        for component, value in mem_breakdown.items():
            if 'L1_' in component and value > 0:
                # Standardize the name for a cleaner legend
                tech = "SRAM" if "SRAM" in component else "ReRAM"
                breakdown[f'L1 {tech}'] = value
                break  # Assume only one L1 cache entry is relevant

        if not breakdown:
            print(f"Warning: Could not extract any valid area breakdown components from {file_path}")
            return None

        return breakdown

    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error processing file {file_path}: {e}")
        return None


def get_latency_breakdown_for_layers(directory_path: str, target_layer_names: list[str]) -> dict:
    """
    Parses ZigZag JSON output files in a directory to find the target layers
    and extract their detailed latency breakdowns.
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

            latency_data = data.get('outputs', {}).get('latency', {})
            clock_data = data.get('outputs', {}).get('clock', {})
            tclk_ns = clock_data.get('tclk (ns)', 0)
            tclk_breakdown_ns = clock_data.get('tclk_breakdown (ns)', {})

            if not latency_data or tclk_ns == 0:
                print(f"Warning: No latency/clock information in {file_path}")
                continue

            mac_computation_cycles = latency_data.get('computation_breakdown', {}).get('mac_computation', 0)
            onloading_cycles = latency_data.get('data_onloading', 0)
            offloading_cycles = latency_data.get('data_offloading', 0)
            stalling_cycles = latency_data.get('computation_breakdown', {}).get('memory_stalling', 0)
            ns_to_ms = 1e-6
            scaling_factor = tclk_ns * ns_to_ms

            breakdown = {
                'Data On-loading': onloading_cycles * scaling_factor,
                'Data Off-loading': offloading_cycles * scaling_factor,
                'Memory Stalling': stalling_cycles * scaling_factor
            }

            for component, time_ns in tclk_breakdown_ns.items():
                if time_ns > 0:
                    comp_name = component.replace('_', ' ').replace('pv', 'PV').capitalize()
                    if comp_name == "Accumulators":
                        comp_name = "Acc"
                    elif comp_name == "Adders pv":
                        comp_name = "Add PV"
                    if 'Adcs' in comp_name: comp_name = 'ADCs'
                    breakdown[f'Comp - {comp_name} '] = mac_computation_cycles * time_ns * ns_to_ms

            layer_results[target_layer_name] = breakdown
            found_layers.add(target_layer_name)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error processing latency in file {file_path}: {e}")
            continue

    if len(found_layers) != len(target_layer_names):
        missing = set(target_layer_names) - found_layers
        print(f"Warning: Could not find latency data for all target layers in {directory_path}. Missing: {missing}")

    return layer_results


def plot_final_breakdowns(arch_area_data: dict, arch_latency_data: dict, target_layer_names: list[str]):
    """
    Generates and saves a figure with two charts:
    1. Area breakdown (one stacked bar per architecture).
    2. Latency breakdown (two grouped stacked bars per architecture for two layers).
    """
    if not arch_area_data or not arch_latency_data:
        print("No area or latency data provided to plot.")
        return

    # Use the figsize from the user's code, but with slightly more height for the top legend
    fig, axes = plt.subplots(1, 2, figsize=(15, 8))
    fig.suptitle('Area/Latency Breakdowns of ReRAM and SRAM Architectures (same area)', fontsize=22)

    arch_names = list(arch_area_data.keys())

    # =================================================================
    # Plot 1: Area Breakdown (axes[0])
    # =================================================================
    df_area = pd.DataFrame(arch_area_data).T.fillna(0)
    all_cols_area = list(df_area.columns)
    cache_cols = [col for col in all_cols_area if 'L1' in col]
    other_cols = sorted([col for col in all_cols_area if 'L1' not in col])
    component_order_area = cache_cols + other_cols
    df_area = df_area[component_order_area]

    colors_area = plt.get_cmap('tab20c', len(df_area.columns))
    bottoms_area = np.zeros(len(arch_names))
    for i, component in enumerate(df_area.columns):
        values = df_area.loc[arch_names, component].values
        axes[0].bar(arch_names, values, label=component, bottom=bottoms_area, color=colors_area(i), width=0.7)
        bottoms_area += values

    axes[0].set_title('Area Breakdown', fontsize=20, pad=105) # Increased pad for legend space
    axes[0].set_ylabel('Area (mm²)', fontsize=16, labelpad=0)
    axes[0].tick_params(axis='y', labelsize=12)
    axes[0].tick_params(axis='x', rotation=45, labelsize=12)
    plt.setp(axes[0].get_xticklabels(), ha="right", rotation_mode="anchor")
    axes[0].grid(True, which='major', axis='y', linestyle='--', linewidth=0.7)
    handles_area, labels_area = axes[0].get_legend_handles_labels()
    # Place legend above the plot, below the title
    axes[0].legend(handles_area, labels_area, title='Area Components', loc='lower center',
                   bbox_to_anchor=(0.5, 1.025), ncol=3, fontsize=12, title_fontsize=14)
    totals_area = df_area.sum(axis=1)
    for i, total in enumerate(totals_area):
        axes[0].text(i, total, f'{total:.2f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

    # =================================================================
    # Plot 2: Grouped and Stacked Latency Breakdown (axes[1])
    # =================================================================
    layer1_name, layer2_name = target_layer_names
    layer_short_names = ["L1.0 C1", "L4.1 C2"]

    # Prepare dataframes for each layer
    latency_l1 = {arch: data.get(layer1_name, {}) for arch, data in arch_latency_data.items()}
    latency_l2 = {arch: data.get(layer2_name, {}) for arch, data in arch_latency_data.items()}
    df_l1 = pd.DataFrame(latency_l1).T.fillna(0)
    df_l2 = pd.DataFrame(latency_l2).T.fillna(0)

    # Combine all possible components to ensure consistent ordering and coloring
    all_latency_components = sorted(list(set(df_l1.columns) | set(df_l2.columns)))
    df_l1 = df_l1.reindex(columns=all_latency_components, fill_value=0)
    df_l2 = df_l2.reindex(columns=all_latency_components, fill_value=0)

    x_pos = np.arange(len(arch_names))
    bar_width = 0.4
    colors_latency = plt.get_cmap('tab10', len(all_latency_components))
    color_map = {comp: colors_latency(i) for i, comp in enumerate(all_latency_components)}

    bottom_l1 = np.zeros(len(arch_names))
    bottom_l2 = np.zeros(len(arch_names))

    for component in all_latency_components:
        axes[1].bar(x_pos - bar_width / 2, df_l1[component], bar_width, bottom=bottom_l1, color=color_map[component])
        axes[1].bar(x_pos + bar_width / 2, df_l2[component], bar_width, bottom=bottom_l2, color=color_map[component])
        bottom_l1 += df_l1[component].values
        bottom_l2 += df_l2[component].values

    axes[1].set_title('Latency Breakdown', fontsize=20, pad=105) # Increased pad for legend space
    axes[1].set_ylabel('Time (ms)', fontsize=16, labelpad=0)
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels(arch_names)
    axes[1].tick_params(axis='y', labelsize=12)
    axes[1].tick_params(axis='x', rotation=45, labelsize=12)
    plt.setp(axes[1].get_xticklabels(), ha="right", rotation_mode="anchor")
    axes[1].grid(True, which='major', axis='y', linestyle='--', linewidth=0.7)

    # Create legend
    legend_patches = [Patch(color=color_map[comp], label=comp) for comp in all_latency_components]
    legend_patches.insert(0, Patch(facecolor='dimgrey', label=f'Left: {layer_short_names[0]}', alpha=0.7))
    legend_patches.insert(0, Patch(facecolor='grey', label=f'Right: {layer_short_names[1]}', alpha=0.7))
    # Place legend above the plot, below the title
    axes[1].legend(handles=legend_patches, title='Latency Components', loc='lower center',
                   bbox_to_anchor=(0.5, 1.025), ncol=3, fontsize=12, title_fontsize=14)

    # The following block for adding numbers on top of the bars has been removed.
    # totals_l1 = df_l1.sum(axis=1)
    # totals_l2 = df_l2.sum(axis=1)
    # for i in range(len(arch_names)):
    #     axes[1].text(x_pos[i] - bar_width / 2, totals_l1.iloc[i], f'{totals_l1.iloc[i]:.3f}', ha='center', va='bottom',
    #                  fontsize=11, fontweight='bold')
    #     axes[1].text(x_pos[i] + bar_width / 2, totals_l2.iloc[i], f'{totals_l2.iloc[i]:.3f}', ha='center', va='bottom',
    #                  fontsize=11, fontweight='bold')

    # --- Final Figure Adjustments ---
    # Use subplots_adjust to manually set the spacing to prevent overlap
    fig.subplots_adjust(top=0.72, bottom=0.10, wspace=0.15)
    # plt.show()
    plt.savefig('architecture_breakdowns_combined_samearea.png', dpi=300)
    plt.close(fig)
    print("\nPlot saved successfully as 'architecture_breakdowns_combined.png'")


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

    all_arch_areas = {}
    all_arch_latencies = {}
    for arch_name, dir_path in architectures_to_compare.items():
        print(f"\nProcessing Architecture: {arch_name}")
        area_data = get_area_breakdown_for_arch(dir_path)
        if area_data:
            all_arch_areas[arch_name] = area_data

        latency_data = get_latency_breakdown_for_layers(dir_path, TARGET_LAYER_NAMES)
        if latency_data:
            all_arch_latencies[arch_name] = latency_data

    if all_arch_areas and all_arch_latencies:
        plot_final_breakdowns(all_arch_areas, all_arch_latencies, TARGET_LAYER_NAMES)
    else:
        print("\nNo valid data found for all architectures. Cannot generate plot.")
