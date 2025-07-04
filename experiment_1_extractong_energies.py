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
    """
    if 'conv1' in s and 'layer' not in s:
        return [0]
    if 'fc' in s.lower() or 'gemm' in s.lower():
        return [999]

    numbers = [int(x) for x in re.findall(r'\d+', s)]
    is_downsample = 1 if 'ds' in get_short_layer_name(s).lower() else 0
    return numbers + [is_downsample]


def get_short_layer_name(long_name: str) -> str:
    """
    Converts a long, path-like layer name from the JSON file into a short,
    descriptive label for plotting.
    """
    if 'fc' in long_name.lower() or 'gemm' in long_name.lower():
        return 'FC'
    if 'conv1/Conv' in long_name and 'layer' not in long_name:
        return 'Initial C'

    match = re.search(r'layer(\d+)/layer\d+\.(\d+)/conv(\d+)', long_name)
    if match:
        return f"L{match.group(1)}.{match.group(2)} C{match.group(3)}"

    match_ds = re.search(r'layer(\d+)/layer\d+\.(\d+)/downsample.*conv', long_name, re.IGNORECASE)
    if match_ds:
        return f"L{match_ds.group(1)}.{match_ds.group(2)} DS"

    return os.path.basename(long_name).replace('_complete.json', '')


def extract_energy_breakdown(directory_path: str) -> dict:
    """
    Parses all ZigZag JSON output files to extract a detailed energy breakdown for each layer.
    """
    json_files = glob.glob(os.path.join(directory_path, '_*.json'))
    if not json_files:
        print(f"Warning: No ZigZag layer output files found in directory: {directory_path}")
        return {}

    energy_results = {}

    for file_path in json_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            layer_name = data.get('inputs', {}).get('layer', {}).get('name', os.path.basename(file_path))

            op_energy_breakdown = data.get('outputs', {}).get('energy', {}).get('operational_energy_breakdown', {})
            cells_energy = op_energy_breakdown.get('cells', 0)
            drivers_energy = op_energy_breakdown.get('wl_drivers', 0) + op_energy_breakdown.get('bl_drivers', 0)
            adcs_dacs_energy = op_energy_breakdown.get('adcs', 0) + op_energy_breakdown.get('dacs', 0)
            digital_energy = op_energy_breakdown.get('adders_pv', 0) + op_energy_breakdown.get('accumulators', 0)

            mem_energy_breakdown = data.get('outputs', {}).get('energy', {}).get('memory_energy_breakdown_per_level',
                                                                                 {})

            weight_loading_energy = sum(mem_energy_breakdown.get('W', [0]))
            io_data_movement_energy = sum(mem_energy_breakdown.get('I', [0])) + sum(mem_energy_breakdown.get('O', [0]))

            energy_results[layer_name] = {
                'Reading Cells': cells_energy,
                'Drivers': drivers_energy,
                'ADCs/DACs': adcs_dacs_energy,
                'Digital Logic': digital_energy,
                'I/O Data Movement': io_data_movement_energy,
                'Weight Loading': weight_loading_energy,
            }
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error processing file {file_path}: {e}")
            continue

    return energy_results


def plot_energy_breakdown(all_results: dict):
    """
    Generates a single stacked bar chart comparing the detailed energy breakdown of different architectures.
    """
    if not all_results:
        print("No results to plot.")
        return

    all_layer_names = set()
    for res in all_results.values():
        all_layer_names.update(res.keys())

    sorted_layer_names = sorted(list(all_layer_names), key=natural_sort_key)
    short_layer_names = [get_short_layer_name(name) for name in sorted_layer_names]

    x = np.arange(len(short_layer_names))
    width = 0.4
    num_archs = len(all_results)

    fig, ax = plt.subplots(figsize=(20, 8))

    component_colors = {
        'Reading Cells': '#d62728',
        'WL/BL Drivers': '#ff7f0e',
        'ADCs/DACs': '#2ca02c',
        'Digital Logic': '#9467bd',
        'I/O Data Movement': '#1f77b4',
        'Weight Loading': '#8c564b',
    }
    energy_components = list(component_colors.keys())

    for i, (arch_name, results) in enumerate(all_results.items()):
        bottoms = np.zeros(len(sorted_layer_names))
        bar_pos = x - width / 2 + i * width

        for component in energy_components:
            values = [results.get(layer, {}).get(component, 0) for layer in sorted_layer_names]
            ax.bar(bar_pos, values, width, bottom=bottoms,
                   color=component_colors[component],
                   edgecolor='black',
                   zorder=3)
            bottoms += np.array(values)

    ax.set_ylabel('Energy (pJ)', fontsize=19)
    ax.set_title('Detailed Energy Breakdown per Layer for ResNet-18', fontsize=26, pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(short_layer_names, rotation=45, ha="right", fontsize=17)
    ax.tick_params(axis='y', labelsize=14)

    ax.grid(True, which='both', axis='y', linestyle='--', linewidth=0.7, zorder=0)
    ax.set_yscale('linear')
    ax.set_ylim(0, 2.5e8)

    # --- Create two separate legends for clarity ---
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D

    # Legend 1: For the energy components (colors)
    component_legend_elements = [Patch(facecolor=color, edgecolor='black', label=component) for component, color in
                                 component_colors.items()]
    legend1 = ax.legend(handles=component_legend_elements, loc='upper right', fontsize=20, title='Energy Components',
                        title_fontsize=16)
    ax.add_artist(legend1)

    # Legend 2: For the architecture bar groups
    # Create dummy artists to label the bar groups without affecting the plot
    arch_legend_elements = [Line2D([0], [0], color='black', lw=4, label=f'Left Bars: {list(all_results.keys())[0]}'),
                            Line2D([0], [0], color='black', lw=4, label=f'Right Bars: {list(all_results.keys())[1]}')]
    # This second legend creation will overwrite the first one if not handled correctly.
    # The ax.add_artist(legend1) call ensures the first one is drawn.
    ax.legend(handles=arch_legend_elements, loc='upper left', fontsize=20, title='Architectures', title_fontsize=16)

    fig.tight_layout()
    plt.savefig('energy_breakdown_detailed.png', dpi=300)
    print("Saved detailed energy breakdown plot to energy_breakdown_detailed.png")
    plt.close(fig)


if __name__ == '__main__':
    architectures_to_compare = {
        "1T1R": "outputs/Experiment1_paper4_template-resnet18",
        "2T2R Pseudo-Crossbar": "outputs/Experiment1_paper3_template-resnet18",
    }

    all_arch_results = {}
    for arch_name, dir_path in architectures_to_compare.items():
        print(f"\nProcessing Architecture: {arch_name}")
        if not os.path.isdir(dir_path):
            print(f"Error: Directory not found at '{dir_path}'. Please update the path.")
            continue

        results = extract_energy_breakdown(dir_path)
        if results:
            all_arch_results[arch_name] = results

    plot_energy_breakdown(all_arch_results)
