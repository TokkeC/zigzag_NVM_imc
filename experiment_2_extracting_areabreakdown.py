import os
import json
import glob
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


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
                    breakdown["Access Transistors/Cells"] = value
                elif component == "access_tx":
                    breakdown["Access Transistors/Cells"] = value
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
                breakdown[f'L1 Cache ({tech})'] = value
                break  # Assume only one L1 cache entry is relevant

        if not breakdown:
            print(f"Warning: Could not extract any valid area breakdown components from {file_path}")
            return None

        return breakdown

    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error processing file {file_path}: {e}")
        return None


def plot_area_breakdown(arch_area_data: dict):
    """
    Generates and saves a stacked bar chart of the area breakdown for
    multiple architectures.
    """
    if not arch_area_data:
        print("No area data provided to plot.")
        return

    # Create a pandas DataFrame from the dictionary for easy plotting
    df = pd.DataFrame(arch_area_data).T.fillna(0)

    # --- Custom Component Order ---
    # Manually set the order of components to ensure L1 Cache is at the bottom.
    all_cols = list(df.columns)
    cache_cols = [col for col in all_cols if 'L1 Cache' in col]
    other_cols = sorted([col for col in all_cols if 'L1 Cache' not in col])

    # The new order for stacking: L1 caches first, then the rest alphabetically.
    component_order = cache_cols + other_cols
    df = df[component_order]

    arch_names = list(df.index)

    # --- Plotting ---
    fig, ax = plt.subplots(figsize=(18, 10))

    # Use a colormap that provides distinct colors for many categories
    colors = plt.cm.get_cmap('tab20c', len(df.columns))

    # Plot the stacked bars component by component
    bottoms = np.zeros(len(arch_names))
    for i, component in enumerate(df.columns):
        values = df[component].values
        ax.bar(arch_names, values, label=component, bottom=bottoms, color=colors(i), width=0.6)
        bottoms += values

    # --- Formatting ---
    ax.set_title('Area Breakdown Comparison Across ReRAM and SRAM Architectures (same array size)', fontsize=24, pad=25)
    ax.set_ylabel('Area (mm²)', fontsize=18, labelpad=15)
    ax.set_xlabel('Architecture', fontsize=18, labelpad=15)
    ax.tick_params(axis='x', labelsize=14, rotation=45)
    ax.tick_params(axis='y', labelsize=14)
    ax.grid(True, which='major', axis='y', linestyle='--', linewidth=0.7)
    ax.set_ylim(bottom=0)

    # --- Legend ---
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, title='Area Components', bbox_to_anchor=(0, 1), loc='upper left',
              fontsize=12, title_fontsize=14)

    # --- Total Area Labels ---
    totals = df.sum(axis=1)
    for i, total in enumerate(totals):
        ax.text(i, total, f'{total:.2f}', ha='center', va='bottom', fontsize=12, fontweight='bold')

    fig.tight_layout(rect=[0, 0, 0.85, 1])

    # Save the figure and close the plot
    plt.show()
    # plt.savefig('architecture_area_breakdown.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("\nPlot saved successfully as 'architecture_area_breakdown.png'")


if __name__ == '__main__':
    # ========================== USER CONFIGURATION ==========================
    # --- DEFINE YOUR 8 ARCHITECTURES AND THEIR DIRECTORY PATHS ---
    # IMPORTANT: Update these paths to point to your actual output directories.
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
    for arch_name, dir_path in architectures_to_compare.items():
        print(f"\nProcessing Architecture: {arch_name}")
        area_data = get_area_breakdown_for_arch(dir_path)
        if area_data:
            all_arch_areas[arch_name] = area_data

    if all_arch_areas:
        plot_area_breakdown(all_arch_areas)
    else:
        print("\nNo valid data found for any architecture. Cannot generate plot.")
