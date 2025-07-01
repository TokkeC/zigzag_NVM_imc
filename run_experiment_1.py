import logging
import math
import re

# from zigzag.api import get_hardware_performance_zigzag
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
logging_level = logging.INFO
logging_format = "%(asctime)s - %(name)s.%(funcName)s +%(lineno)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging_level, format=logging_format)

accelerator_list = ["zigzag/inputs/hardware/Experiment1_paper4_template.yaml", "zigzag/inputs/hardware/Experiment1_paper3_template.yaml"]
workload_rram = "zigzag/inputs/workload/resnet18.onnx"
mapping_rram = "zigzag/inputs/mapping/default_imc.yaml"
accelerator_rram = accelerator_list[0]

# parser = get_arg_parser()
# args = parser.parse_args()

hw_name = accelerator_rram.split(".")[-1]
if hw_name == "yaml":
    hw_name = re.split(r"/|\.",accelerator_rram)[-2]
workload_name = re.split(r"/|\.", workload_rram)[-1]
if workload_name == "onnx" or "yaml":
    workload_name = re.split(r"/|\.", workload_rram)[-2]
    print(workload_rram)
    print(accelerator_rram)
experiment_id = f"{hw_name}-{workload_name}"
pickle_name = f"{experiment_id}-saved_list_of_cmes"
dump_folder = f"outputs/{experiment_id}"
pickle_filename = f"outputs/{pickle_name}.pickle"

accelerator = AcceleratorParserStage.parse_accelerator(accelerator_rram)
# breakdown_results = accelerator.operational_array.print_peak_performance() # works only if it is an NVM IMC Array!

# WRITE ENERGY CODE
# SLC - 1T1R
# V_write = 2.2
# G_writeavg = 20 * (10**(-6))
# T_write = 100 * (10**(-9))
# N_pulses = 1
# M_type_dev = 1
# gamma = 0.5

# MLC - 2T2R pseudo-crossbar
V_write = 2.2
G_writeavg = 20 * (10**(-6))
T_write = 20 * (10**(-9))
N_pulses = 8
M_type_dev = 2
gamma = 0.7


E_write_dev_pulse = (V_write**2) * G_writeavg * T_write
E_write_current_dev = E_write_dev_pulse * N_pulses

weight_precision = accelerator.operational_array.weight_precision
cells_size_nvm = accelerator.operational_array.cells_size_nvm

N_dev_w_tot = math.ceil(weight_precision / cells_size_nvm) * M_type_dev

E_write_current_weight = E_write_current_dev * N_dev_w_tot * gamma
print("E_write_current_weight: ", E_write_current_weight * (10**12))

alpha = 1.0
beta = 2.0
C_WL = accelerator.operational_array.c_wl_ff * (10**-15)
C_BL = accelerator.operational_array.c_blsl_ff * (10**-15)
V_WL_SWING = accelerator.operational_array.ReRAM_param["V_wl_swing_read"]
N_BL = accelerator.operational_array.bitline_amount

E_write_WL_weight = alpha * C_WL * (V_WL_SWING**2) #/ (N_BL * M_type_dev/N_dev_w_tot)
E_write_BL_weight = beta * N_dev_w_tot * C_BL * (V_write**2)
E_write_switching_weight = E_write_WL_weight + E_write_BL_weight
print("E_write_WL_weight, E_write_BL_weight, E_write_switching_weight: ", E_write_WL_weight * (10**12), E_write_BL_weight* (10**12), E_write_switching_weight* (10**12))

E_write_tot_weight = E_write_current_weight + E_write_switching_weight
print("E_write_tot_weight: ", E_write_tot_weight * (10**12))



#Running Cacti

cacti_result = accelerator.operational_array.get_single_cell_array_cost_from_cacti(
    tech_node = 0.028,
    wordline_dim_size = 64.0,
    bitline_dim_size = 65536.0,
    cells_size = 8,
    weight_precision = 8
)
# cacti_result = accelerator.operational_array.get_single_cell_array_cost_from_cacti(
#     tech_node=0.028,
#     wordline_dim_size=65536.0,
#     bitline_dim_size=64.0,
#     cells_size=1.0,
#     weight_precision=8
# )
print(cacti_result)


#Running ZigZag
# get_hardware_performance_zigzag(
#     workload=workload_rram,
#     accelerator=accelerator_rram,
#     mapping=mapping_rram,
#     opt="latency",
#     dump_folder=f"outputs/{experiment_id}",
#     pickle_filename=f"outputs/{pickle_name}.pickle",
#     in_memory_compute = True
# )




# def get_hardware_performance_zigzag(
#     workload: str | ModelProto,
#     accelerator: str,
#     mapping: str,
#     *,
#     opt: str = "latency",
#     dump_folder: str = f"outputs/{datetime.now()}",
#     pickle_filename: str | None = None,
#     lpf_limit: int = 6,
#     nb_spatial_mappings_generated: int = 3,
#     in_memory_compute: bool = False,
#     exploit_data_locality: bool = False,
#     enable_mix_spatial_mapping: bool = False,
# )
# @param opt Optimization criterion: either `energy`, `latency` or `EDP`.


