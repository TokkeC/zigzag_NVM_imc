import logging
import re

from zigzag.api import get_hardware_performance_zigzag_imc_nvm
from zigzag.stages.parser.accelerator_parser import AcceleratorParserStage
from zigzag.parser.accelerator_factory import AcceleratorFactory, MemoryFactory
from zigzag.stages.evaluation.cost_model_evaluation import CostModelStage

from zigzag.utils import pickle_load # Loading in of results
from zigzag.visualization.results.print_mapping import print_mapping # Also already printed in txt file
from zigzag.visualization.results.plot_cme import bar_plot_cost_model_evaluations_breakdown # Bar plot visualizations

import matplotlib.pyplot as plt
import numpy as np

# Initialize the logger
logging_level = logging.INFO
logging_format = "%(asctime)s - %(name)s.%(funcName)s +%(lineno)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging_level, format=logging_format)

accelerator_list = ["zigzag/inputs/hardware/nvm_aimc_test_paper4.yaml", "zigzag/inputs/hardware/nvm_aimc_test_paper3.yaml"]
for accelerator_rram in accelerator_list:
    workload_rram = "zigzag/inputs/workload/resnet18.onnx"
    mapping_rram = "zigzag/inputs/mapping/default_imc.yaml"

    hw_name = accelerator_rram.split(".")[-1]
    if hw_name == "yaml":
        hw_name = re.split(r"/|\.",accelerator_rram)[-2]
    workload_name = re.split(r"/|\.", workload_rram)[-1]
    if workload_name == "onnx" or "yaml":
        workload_name = re.split(r"/|\.", workload_rram)[-2]
    experiment_id = f"{hw_name}-{workload_name}"
    pickle_name = f"{experiment_id}-saved_list_of_cmes"
    dump_folder = f"outputs/{experiment_id}"
    pickle_filename = f"outputs/{pickle_name}.pickle"

    accelerator = AcceleratorParserStage.parse_accelerator(accelerator_rram)
    breakdown_results = accelerator.operational_array.print_peak_performance() # works only if it is an NVM IMC Array!

    """
        Plotting results from the ZigZag hardware performance estimation
    """
    # cmes = pickle_load(pickle_filename)
    # print_mapping(cmes[0])
    # bar_plot_cost_model_evaluations_breakdown(cmes[0:5], save_path = f"outputs/{experiment_id}/plot_breakdown.png")
    # # Only plotting 6 layers to have a good plot!

"""
    Plotting results from the MACRO PEAK PERFORMANCE!
"""
# --- 1. Define Your Data for Each Metric ---
# IMPORTANT: For "the same amount of papers/breakdowns on each subplot",
# ensure the 'comparisons' list for each metric has entries
# for the same set of contexts/papers you want to compare.
metrics_data_list = [
    {
        'title': 'Energy',
        'unit': 'Normalized energy (pJ/pJ)',
        'comparisons': [
            {
                'name': 'Paper 4 (T.-H. Wen, et al.)',
                'user_breakdown':{'cells': 72.34166153846154, 'mults': 0, 'wl_drivers': 42.96010466825452, 'bl_drivers': 0.6599441417659073, 'dacs': 0, 'adcs': 5.18731776, 'adders_regular': 0, 'adders_pv': 2.6127359999999995, 'accumulators': 1.6329599999999997},
                'paper_reported_total': 125
            },
            {
                'name': 'Paper 3 (P. Yao, et al.)',
                'user_breakdown': {'cells': 385.65415384615386, 'mults': 0, 'wl_drivers': 215.66023412807732, 'bl_drivers': 1.3568833050902378, 'dacs': 82.94400000000002, 'adcs': 44.869386240000004, 'adders_regular': 0, 'adders_pv': 6.531839999999998, 'accumulators': 0},
                'paper_reported_total': 1667.5827 # 953.857
            },
        ]
    },
    {
        'title': 'Latency',
        'unit': ' Normalized latency (ns/ns)',
        'comparisons': [
            {
                'name': 'Paper 4 (T.-H. Wen, et al.)',
                'user_breakdown': {'cells': 0, 'dacs': 0, 'adcs': 10.769230769230768, 'mults': 0, 'adders_regular': 0, 'adders_pv': 1.3384, 'accumulators': 0.8795200000000001, 'wl_drivers': 0, 'bl_drivers': 0},
                'paper_reported_total': 12.04705882
            },
            {
                'name': 'Paper 3 (P. Yao, et al.)',
                'user_breakdown': {'cells': 0, 'dacs': 0, 'adcs': 23.076923076923073, 'mults': 0, 'adders_regular': 0, 'adders_pv': 0.7265600000000001, 'accumulators': 0, 'wl_drivers': 0, 'bl_drivers': 0},
                'paper_reported_total': 23.08
            },
        ]
    },
    {
        'title': 'Area',
        'unit': 'Normalized area (mm$^2$/mm$^2$)',
        'comparisons': [
            {
                'name': 'Paper 4 (T.-H. Wen, et al.)',
                'user_breakdown': {'IO pads (rough estimate)': 4,'cells': 0, 'dacs': 0, 'adcs': 0.0029284645108206254, 'mults': 0.9865003008, 'adders_regular': 0, 'adders_pv': 0.2353987584, 'accumulators': 0.17353113599999997, 'wl_drivers': 0.16840361029955775, 'bl_drivers': 0.041391696571557696},
                'paper_reported_total': 6.071428571
            },
            {
                'name': 'Paper 3 (P. Yao, et al.)',
                'user_breakdown': {'cells': 0, 'dacs': 0, 'adcs': 0.13341969370468265, 'mults': 0.205520896, 'adders_regular': 0, 'adders_pv': 0.073562112, 'accumulators': 0, 'wl_drivers': 0.08349512274390747, 'bl_drivers': 0.021275930223814923},
                'paper_reported_total': 0.56
            },
        ]
    }
]

# --- 2. Define Colors ---
component_colors_hex = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b',
    '#e377c2', '#bcbd22', '#17becf', '#aec7e8', '#ffbb78', '#98df8a',
    '#ff9896', '#c5b0d5', '#c49c94'
]
paper_total_bar_color = '#7f7f7f'

# --- 3. Prepare Unique Component Names and Color Mapping ---
all_component_names_set = set()
for metric_data in metrics_data_list:
    for comp_set in metric_data['comparisons']:
        for component_name in comp_set['user_breakdown'].keys():
            all_component_names_set.add(component_name)

sorted_unique_component_names = sorted(list(all_component_names_set))
component_color_map = {
    name: component_colors_hex[i % len(component_colors_hex)]
    for i, name in enumerate(sorted_unique_component_names)
}

# --- 4. Create the Plot with Subplots (HORIZONTALLY) ---
num_metrics = len(metrics_data_list)
subplot_width = 5
subplot_height = 6
fig, axes = plt.subplots(nrows=1, ncols=num_metrics,
                         figsize=(subplot_width * num_metrics, subplot_height + 1.5),
                         # Increased height for top legend/suptitle
                         squeeze=False)
axes = axes.flatten()

legend_handles_for_components = {}
paper_total_legend_handle = None

bar_width_single = 0.4

for i, metric_data in enumerate(metrics_data_list):
    ax = axes[i]
    ax.set_title(metric_data['title'], fontsize=14, pad=15)
    ax.set_ylabel(metric_data['unit'], fontsize=11)
    ax.tick_params(axis='both', which='major', labelsize=9)

    comparisons_list = metric_data['comparisons']
    num_comparison_sets = len(comparisons_list)

    x_group_centers = np.arange(num_comparison_sets)
    x_group_labels = [comp_set['name'] for comp_set in comparisons_list]

    max_y_val_subplot = 0

    for k, comp_set_data in enumerate(comparisons_list):
        group_interface_x = x_group_centers[k]
        user_breakdown_dict = comp_set_data['user_breakdown']
        paper_total_value_to_normalize = float(comp_set_data['paper_reported_total']) / 100
        paper_total_value = float(comp_set_data['paper_reported_total'])

        # --- BAR ORDER SWAPPED ---
        # --- Plot Paper's Reported Total Bar (Single, LEFT bar in the pair) ---
        paper_bar_center_x = group_interface_x - bar_width_single / 2
        if paper_total_value/paper_total_value_to_normalize > max_y_val_subplot: max_y_val_subplot = paper_total_value/paper_total_value_to_normalize

        p_bar_label = "Paper Reported Total" if not paper_total_legend_handle else None
        p_bar = ax.bar(paper_bar_center_x, paper_total_value/paper_total_value_to_normalize, bar_width_single,
                       color=paper_total_bar_color, label=p_bar_label)
        if not paper_total_legend_handle: paper_total_legend_handle = p_bar

        ax.text(paper_bar_center_x, paper_total_value/paper_total_value_to_normalize + 0.02 * (max_y_val_subplot or 1),
                f'{paper_total_value:.2f}', ha='center', va='bottom', fontsize=8)

        # --- Plot User's Stacked Breakdown Bar (Stacked, RIGHT bar in the pair) ---
        user_bar_center_x = group_interface_x + bar_width_single / 2
        current_bottom = 0
        calculated_user_total = sum(user_breakdown_dict.values())
        if calculated_user_total/paper_total_value_to_normalize > max_y_val_subplot: max_y_val_subplot = calculated_user_total/paper_total_value_to_normalize

        for component_name, value in user_breakdown_dict.items():
            color = component_color_map.get(component_name, '#000000')
            rect = ax.bar(user_bar_center_x, value/paper_total_value_to_normalize, bar_width_single, bottom=current_bottom,
                          color=color, label=component_name, edgecolor='white', linewidth=0.5)
            current_bottom += value/paper_total_value_to_normalize
            if component_name not in legend_handles_for_components:
                legend_handles_for_components[component_name] = rect

        ax.text(user_bar_center_x, calculated_user_total/paper_total_value_to_normalize + 0.02 * (max_y_val_subplot or 1),
                f'{calculated_user_total:.2f}\n{calculated_user_total/paper_total_value_to_normalize:.2f}%', ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_xticks(x_group_centers)
    ax.set_xticklabels(x_group_labels, rotation=30, ha='right', fontsize=9)
    if max_y_val_subplot > 0:
        ax.set_ylim(0, max_y_val_subplot * 1.1)
    else:
        ax.set_ylim(0, 1)
    ax.grid(axis='y', linestyle=':', alpha=0.6)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

# --- 5. Create a Single Figure-Level Legend (Placed at the TOP) ---
all_legend_handles = []
if legend_handles_for_components:
    sorted_comp_handles = [legend_handles_for_components[name] for name in sorted_unique_component_names
                           if name in legend_handles_for_components]
    all_legend_handles.extend(sorted_comp_handles)
if paper_total_legend_handle:
    all_legend_handles.append(paper_total_legend_handle)

if all_legend_handles:
    # Calculate a reasonable number of columns for the legend
    num_legend_items = len(all_legend_handles)
    ncol_legend = num_legend_items if num_legend_items <= 8 else (
        num_legend_items // 2 if num_legend_items <= 16 else 8)  # Adjust as needed

    fig.legend(handles=all_legend_handles,  # title="Legend Key",
               loc='lower center',  # Anchored at its bottom-center
               bbox_to_anchor=(0.5, 0.85),  # Positioned relative to figure: 0.5 is fig center-x, 0.95 is near fig top
               ncol=ncol_legend,
               fontsize=9, title_fontsize=10, frameon=False)  # frameon=False can look cleaner for top legends

# --- 6. Add Super Title and Adjust Layout ---
# Super title will be below the legend if legend's bbox_to_anchor y is high enough, or adjust y here
fig.suptitle("Model validation ReRAM-CiMs: Paper numbers - Calculated breakdowns", fontsize=16,
             y=1.00)  # Lowered y to be below top legend

# Adjust subplot parameters to make space for top legend and subtitle
# Increase 'top' to push subplots down, making space. Adjust 'wspace' for horizontal gaps.
plt.subplots_adjust(left=0.06, right=0.98, bottom=0.15, top=0.78, wspace=0.3)

# plt.show()