import logging
import math
import re
import os

from zigzag.api import get_hardware_performance_zigzag
from zigzag.parser.arguments import get_arg_parser
from zigzag.stages.parser.accelerator_parser import AcceleratorParserStage
from zigzag.parser.accelerator_factory import AcceleratorFactory, MemoryFactory
from zigzag.stages.evaluation.cost_model_evaluation import CostModelStage

from zigzag.utils import pickle_load # Loading in of results
from zigzag.visualization.results.print_mapping import print_mapping # Also already printed in txt file
from zigzag.visualization.results.plot_cme import bar_plot_cost_model_evaluations_breakdown # Bar plot visualizations

import matplotlib.pyplot as plt
import numpy as np



# Initialize the logger
# logging_level = logging.INFO
# logging_format = "%(asctime)s - %(name)s.%(funcName)s +%(lineno)s - %(levelname)s - %(message)s"
# logging.basicConfig(level=logging_level, format=logging_format)
#
#
# accelerator_list = ["zigzag/inputs/hardware/Experiment3_reramCiM.yaml"]
# workload_list = ["zigzag/inputs/workload/resnet18.onnx", ]
#
#
# workload_rram = "zigzag/inputs/workload/resnet18.onnx"
# mapping_rram = "zigzag/inputs/mapping/default_imc.yaml"
# for i in range(0,8):
#     accelerator_rram = accelerator_list[i]
#
#     # parser = get_arg_parser()
#     # args = parser.parse_args()
#
#     hw_name = accelerator_rram.split(".")[-1]
#     if hw_name == "yaml":
#         hw_name = re.split(r"/|\.",accelerator_rram)[-2]
#     workload_name = re.split(r"/|\.", workload_rram)[-1]
#     if workload_name == "onnx" or "yaml":
#         workload_name = re.split(r"/|\.", workload_rram)[-2]
#         print(workload_rram)
#         print(accelerator_rram)
#     experiment_id = f"{hw_name}-{workload_name}"
#     pickle_name = f"{experiment_id}-saved_list_of_cmes"
#     dump_folder = f"outputs/{experiment_id}"
#     pickle_filename = f"outputs/{pickle_name}.pickle"
#
#     accelerator = AcceleratorParserStage.parse_accelerator(accelerator_rram)
    # print(accelerator.operational_array.area)
    # Running ZigZag
    # get_hardware_performance_zigzag(
    #     workload=workload_rram,
    #     accelerator=accelerator_rram,
    #     mapping=mapping_rram,
    #     opt="energy",
    #     dump_folder=f"outputs/{experiment_id}",
    #     pickle_filename=f"outputs/{pickle_name}.pickle",
    #     in_memory_compute = True
    # )


def generate_write_energy(accelerator_path: str):
    accelerator = AcceleratorParserStage.parse_accelerator(accelerator_path)
    # # # breakdown_results = accelerator.operational_array.print_peak_performance() # works only if it is an NVM IMC Array!
    # #
    # # # WRITE ENERGY CODE
    # # SLC - 1T1R
    # V_write = 2.2
    # G_writeavg = 20 * (10**(-6))
    # T_write = 100 * (10**(-9))
    # N_pulses = 1
    # M_type_dev = 1
    # gamma = 0.5
    #
    # # # MLC - 2T2R pseudo-crossbar
    V_write = 2.2
    G_writeavg = 20 * (10 ** (-6))
    T_write = 20 * (10 ** (-9))
    N_pulses = 8
    M_type_dev = 2
    gamma = 0.7
    #
    E_write_dev_pulse = (V_write ** 2) * G_writeavg * T_write
    E_write_current_dev = E_write_dev_pulse * N_pulses

    weight_precision = accelerator.operational_array.weight_precision
    cells_size_nvm = accelerator.operational_array.cells_size_nvm

    N_dev_w_tot = math.ceil(weight_precision / cells_size_nvm) * M_type_dev
    # print(N_dev_w_tot)

    E_write_current_weight = E_write_current_dev * N_dev_w_tot * gamma
    print("E_write_current_weight: ", E_write_current_weight * (10 ** 12))

    alpha = 1.0
    beta = 2.0
    C_WL = accelerator.operational_array.c_wl_ff * (10 ** -15)
    C_BL = accelerator.operational_array.c_blsl_ff * (10 ** -15)
    V_WL_SWING = accelerator.operational_array.ReRAM_param["V_wl_swing_read"]
    N_BL = accelerator.operational_array.bitline_amount

    E_write_WL_weight = alpha * C_WL * (V_WL_SWING ** 2) * math.ceil(
        weight_precision / cells_size_nvm)  # / (N_BL * M_type_dev/N_dev_w_tot)
    E_write_BL_weight = beta * N_dev_w_tot * C_BL * (V_write ** 2)
    E_write_switching_weight = E_write_WL_weight + E_write_BL_weight
    print("E_write_WL_weight, E_write_BL_weight, E_write_switching_weight: ", E_write_WL_weight * (10 ** 12),
          E_write_BL_weight * (10 ** 12), E_write_switching_weight * (10 ** 12))

    E_write_tot_weight = E_write_current_weight + E_write_switching_weight
    print("E_write_tot_weight: ", E_write_tot_weight * (10 ** 12))
    return E_write_tot_weight



def generate_yaml_files(template_path: str, output_folder: str, configs: list[dict]):
    """
    Generates multiple YAML files from a template by filling in specified placeholders.

    Args:
        template_path (str): The file path of the YAML template.
        output_folder (str): The name of the folder to save the generated files in.
        configs (list[dict]): A list of dictionaries. Each dictionary represents one
                               file to be generated and should contain key-value pairs
                               for the placeholders, plus a 'name' for the output file.
    """
    # --- 1. Read the template file ---
    try:
        with open(template_path, 'r') as f:
            template_content = f.read()
    except FileNotFoundError:
        print(f"Error: Template file not found at '{template_path}'")
        return

    # --- 2. Create the output folder if it doesn't exist ---
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output directory: '{output_folder}'")

    # --- 3. Loop through configurations and generate files ---
    generated_files = []
    for config in configs:
        # Make a copy of the content to work on
        new_content = template_content

        # Substitute each placeholder with the value from the config dictionary
        for key, value in config.items():
            placeholder = f"{{Fill in: {key}}}"
            new_content = new_content.replace(placeholder, str(value))

        # Check if all placeholders have been filled
        if "{Fill in:" in new_content:
            print(f"Warning: Not all placeholders were filled for config '{config.get('name', 'Unnamed')}'.")
            print("Please ensure your config dictionaries contain keys for all placeholders in the template.")

        # Create the output filename and path
        file_name = f"{config.get('name', 'unnamed_config')}.yaml"
        output_path = os.path.join(output_folder, file_name)

        # Write the new content to the file
        with open(output_path, 'w') as f:
            f.write(new_content)

        generated_files.append(output_path)

    print(f"\nSuccessfully generated {len(generated_files)} YAML files in '{output_folder}'.")


if __name__ == '__main__':

    template_filepath = 'zigzag/inputs/hardware/Experiment3_reramCiM.yaml'

    output_directory = 'zigzag/inputs/hardware/Experiment3_generated'

    configurations_to_generate = []
    end_power = 13  # until 4096x496
    for i in range(4,end_power):
        configuration_dict = dict()
        w_cost = 0 #has to be calculated after
        rows = int(2**i)
        synaptic_weights = 2
        cols = int(rows / synaptic_weights)
        configuration_dict['name'] = f"Experiment3_reramCiM_{rows}"
        configuration_dict['w_cost'] = w_cost
        configuration_dict['cols'] = cols
        configuration_dict['rows'] = rows
        configurations_to_generate.append(configuration_dict)

    # Run the function to generate the files
    generate_yaml_files(
        template_path=template_filepath,
        output_folder=output_directory,
        configs=configurations_to_generate
    )

    configurations_to_generate = []
    accelerator_list = []

    for i in range(4,  end_power):  # until 2048x2048
        configuration_dict = dict()
        rows = int(2 ** i)
        w_cost = (10**12) * generate_write_energy(f"zigzag/inputs/hardware/Experiment3_generated/Experiment3_reramCiM_{rows}.yaml")
        synaptic_weight_precision = 8
        cols = int(rows / synaptic_weight_precision)
        configuration_dict['name'] = f"Experiment3_reramCiM_{rows}"
        configuration_dict['w_cost'] = w_cost
        configuration_dict['cols'] = cols
        configuration_dict['rows'] = rows
        configurations_to_generate.append(configuration_dict)
        accelerator_list.append(f"zigzag/inputs/hardware/Experiment3_generated/Experiment3_reramCiM_{rows}.yaml")

    generate_yaml_files(
        template_path=template_filepath,
        output_folder=output_directory,
        configs=configurations_to_generate
    )

    # Initialize the logger
    logging_level = logging.INFO
    logging_format = "%(asctime)s - %(name)s.%(funcName)s +%(lineno)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=logging_level, format=logging_format)

    # workload_list = ["zigzag/inputs/workload/resnet18.onnx",
    #                  "zigzag/inputs/workload/resnet50.onnx",
    #                  "zigzag/inputs/workload/mobilenetv2.onnx",
    #                  "zigzag/inputs/workload/matmul_prefill.yaml",
    #                  "zigzag/inputs/workload/matmul_decode.yaml"]
    workload_list = ["zigzag/inputs/workload/resnet18.yaml"]

    mapping_path = "zigzag/inputs/mapping/default_imc_fornvm.yaml" # standard mapping


    for accelerator_path in accelerator_list:
        for workload_path in workload_list:

            hw_name = accelerator_path.split(".")[-1]
            if hw_name == "yaml":
                hw_name = re.split(r"/|\.", accelerator_path)[-2]
            workload_name = re.split(r"/|\.", workload_path)[-1]
            if workload_name == "onnx" or "yaml":
                workload_name = re.split(r"/|\.", workload_path)[-2]
            experiment_id = f"{hw_name}-{workload_name}"
            pickle_name = f"{experiment_id}-saved_list_of_cmes"
            dump_folder = f"outputs/{experiment_id}"
            pickle_filename = f"outputs/{pickle_name}.pickle"

            # accelerator = AcceleratorParserStage.parse_accelerator(accelerator_path)
            # Running ZigZag
            get_hardware_performance_zigzag(
                workload = workload_path,
                accelerator = accelerator_path,
                mapping = mapping_path,
                opt = "energy",
                dump_folder = f"outputs/Experiment3/{experiment_id}",
                pickle_filename = f"outputs/{pickle_name}.pickle",
                in_memory_compute = True
            )


