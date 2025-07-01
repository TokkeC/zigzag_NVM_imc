import matplotlib.pyplot as plt
import numpy as np

"""
    Plotting results from the MACRO PEAK PERFORMANCE!
    Refactored to create separate, horizontal bar charts for each metric.
"""
# --- 1. Define Your Data for Each Metric ---
# (Data is unchanged from your original code)
metrics_data_list = [
    {
        'title': 'Peak Energy',
        'unit': 'Normalised energy (%)',
        'comparisons': [
            {
                'name': '1T1R \n Wen, VLSI 2023',
                'user_breakdown': {'Cells': 54.25624615384615, 'WL Drivers': 43.25606484072191, 'BL Drivers': 0.7632468591132585, 'DACs': 0, 'ADCs': 20.74927104, 'PV Adders': 1.306367996, 'Accumulators': 0.8164799},
                'paper_reported_total': 106.1139896
            },
            {
                'name': '2T2R PC \n Yao, ESSERC 2024',
                'user_breakdown': {'Cells': 138.52800319487997, 'WL Drivers': 583.9568753497457, 'BL Drivers': 1.7090084204787814, 'DACs': 10.368000000000002, 'ADCs': 44.869386240000004, 'PV Adders': 0.0, 'Accumulators': 0},
                'paper_reported_total': 953.857 # 1667.5827 with buffer
            },
        ]
    },
    {
        'title': 'Latency',
        'unit': ' Normalised latency (%)',
        'comparisons': [
            {
                'name': '1T1R \n Wen, VLSI 2023',
                'user_breakdown': {'Cells': 0, 'WL Drivers': 0, 'BL Drivers': 0, 'DACs': 0, 'ADCs': 10.769230769230768, 'PV Adders': 1.3384, 'Accumulators': 0.8795200000000001},
                'paper_reported_total': 12.04705882
            },
            {
                'name': '2T2R PC \n Yao, ESSERC 2024',
                'user_breakdown': {'Cells': 0, 'WL Drivers': 0, 'BL Drivers': 0, 'DACs': 0, 'ADCs': 23.076923076923073, 'PV Adders': 0, 'Accumulators': 0},
                'paper_reported_total': 23.08
            },
        ]
    },
    {
        'title': 'Area',
        'unit': 'Normalised area (%)',
        'comparisons': [
            {
                'name': '1T1R \n Wen, VLSI 2023',
                'user_breakdown': {'Cells': 0, 'Access TXs': 0.411041792, 'DACs': 0, 'ADCs': 0.0029284645108206254, 'PV Adders': 0.0004597632, 'Accumulators': 0.021691391999999997, 'WL Drivers': 0.16956377417562987, 'BL Drivers': 0.04255186044762985},
                'paper_reported_total': 0.75 # scaled with 0.5 ,without scaling estimation 1.517857143 # for 4 macros 6
            },
            {
                'name': '2T2R PC \n Yao, ESSERC 2024',
                'user_breakdown': {'Cells': 0, 'Access TXs': 0.205520896, 'DACs': 0, 'ADCs': 0.13341969370468265, 'PV Adders': 0.0, 'Accumulators': 0, 'WL Drivers': 0.08478188708781494, 'BL Drivers': 0.02384945891162985},
                'paper_reported_total': 0.448 # 0.56 with buffer
            },
        ]
    }
]

# --- 2. Define Colors and Component Mapping ---
# (Unchanged from your original code)
component_colors_hex = [
    '#1f77b4', '#ff7f0e', '#d62728', '#9467bd', '#8c564b',
    '#e377c2', '#bcbd22', '#17becf', '#aec7e8', '#ffbb78', '#98df8a',
    '#ff9896', '#c5b0d5', '#c49c94'
]
paper_total_bar_color = '#7f7f7f'

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

# --- 3. Loop Through Each Metric to Create and Save a Separate Plot ---
bar_height_single = 0.4  # Height of individual bars in a group

for metric_data in metrics_data_list:
    # --- Create a new figure for each metric ---
    fig, ax = plt.subplots(figsize=(10, 6))  # Good starting size for horizontal plots

    # --- Setup plot aesthetics (axes are swapped) ---
    ax.set_title(metric_data['title'] + " Cost Model Validation ", fontsize=20, pad=20, y = 1.2, x = 0.4)
    ax.set_xlabel(metric_data['unit'], fontsize=15)
    ax.tick_params(axis='both', which='major', labelsize=10)

    comparisons_list = metric_data['comparisons']
    num_comparison_sets = len(comparisons_list)

    # Y-axis now represents the different papers/comparisons
    y_group_centers = np.arange(num_comparison_sets)
    y_group_labels = [comp_set['name'] for comp_set in comparisons_list]

    max_x_val_subplot = 0
    legend_handles_for_components = {}
    paper_total_legend_handle = None

    for k, comp_set_data in enumerate(comparisons_list):
        group_interface_y = y_group_centers[k]
        user_breakdown_dict = comp_set_data['user_breakdown']
        paper_total_value_to_normalize = float(comp_set_data['paper_reported_total']) / 100
        paper_total_value = float(comp_set_data['paper_reported_total'])

        # --- Plot Paper's Reported Total Bar (TOP bar in the pair) ---
        paper_bar_center_y = group_interface_y + bar_height_single / 2
        bar_width = paper_total_value / paper_total_value_to_normalize
        if bar_width > max_x_val_subplot: max_x_val_subplot = bar_width

        p_bar_label = "Paper Reported Total"
        p_bar = ax.barh(paper_bar_center_y, bar_width, bar_height_single,
                        color=paper_total_bar_color, label=p_bar_label)
        paper_total_legend_handle = p_bar

        # Add text label to the paper bar
        if metric_data['title'] == "Area":
            unit_added = ' mm$^2$'
        elif metric_data['title'] == "Latency":
            unit_added = ' ns'
        else:
            unit_added = ' pJ'

        ax.text(bar_width + 0.01 * (max_x_val_subplot or 1), paper_bar_center_y,
                f'{paper_total_value:.2f}' + unit_added, ha='left', va='center', fontsize=12)

        # --- Plot User's Stacked Breakdown Bar (BOTTOM bar in the pair) ---
        user_bar_center_y = group_interface_y - bar_height_single / 2
        current_left = 0
        calculated_user_total = sum(user_breakdown_dict.values())
        total_bar_width = calculated_user_total / paper_total_value_to_normalize
        if total_bar_width > max_x_val_subplot: max_x_val_subplot = total_bar_width

        for component_name, value in user_breakdown_dict.items():
            color = component_color_map.get(component_name, '#000000')
            bar_width = value / paper_total_value_to_normalize
            rect = ax.barh(user_bar_center_y, bar_width, bar_height_single, left=current_left,
                           color=color, label=component_name, edgecolor='white', linewidth=0.5)
            current_left += bar_width
            if component_name not in legend_handles_for_components:
                legend_handles_for_components[component_name] = rect

        # Add text label to the user's breakdown bar
        ax.text(total_bar_width + 0.01 * (max_x_val_subplot or 1), user_bar_center_y,
                f'{calculated_user_total:.2f}{unit_added}\n({total_bar_width:.2f}%)',
                ha='left', va='center', fontsize=12, fontweight='bold')

    # --- Finalize Axes and Grid ---
    ax.set_yticks(y_group_centers)
    ax.set_yticklabels(y_group_labels, rotation=30, ha='right', va='center', fontsize=12) # No rotation needed
    if max_x_val_subplot > 0:
        ax.set_xlim(0, max_x_val_subplot * 1.15)  # Increase padding for text
    else:
        ax.set_xlim(0, 1)
    ax.grid(axis='x', linestyle=':', alpha=0.6)  # Grid on the value axis
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    # Invert y-axis to have the first item at the top
    ax.invert_yaxis()

    # --- Create a Legend for the Current Plot ---
    all_legend_handles = []
    sorted_comp_handles = [legend_handles_for_components[name] for name in sorted_unique_component_names
                           if name in legend_handles_for_components]
    all_legend_handles.extend(sorted_comp_handles)
    if paper_total_legend_handle:
        all_legend_handles.append(paper_total_legend_handle)

    if all_legend_handles:
        num_legend_items = len(all_legend_handles)
        # Place legend above the plot
        ax.legend(handles=all_legend_handles,
                  loc='lower center',
                  bbox_to_anchor=(0.41, 1.0),  # Position above the plot area
                  ncol=num_legend_items // 2 if num_legend_items > 4 else num_legend_items,
                  fontsize=12, frameon=False)

    # --- Adjust Layout, Save, and Show the Plot ---
    plt.tight_layout(rect=[0, 0, 1, 0.9])  # Adjust rect to make space for the top legend

    # Save the figure to a file
    # filename = f"{metric_data['title']}_validation.png"
    # plt.savefig(filename, dpi=300, bbox_inches='tight')
    # print(f"Saved plot to {filename}")

    plt.show()

    # Close the figure to free up memory before the next loop
    plt.close(fig)