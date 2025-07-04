import logging
import math
import re

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
logging_level = logging.INFO
logging_format = "%(asctime)s - %(name)s.%(funcName)s +%(lineno)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging_level, format=logging_format)

accelerator_list = ["zigzag/inputs/hardware/Experiment2_paper4_sram_rbuffer.yaml",
                    "zigzag/inputs/hardware/Experiment2_paper4_sram.yaml",
                    "zigzag/inputs/hardware/Experiment2_paper4_reram_rbuffer.yaml",
                    "zigzag/inputs/hardware/Experiment2_paper4_reram.yaml",
                    "zigzag/inputs/hardware/Experiment2_paper3_sram_rbuffer.yaml",
                    "zigzag/inputs/hardware/Experiment2_paper3_sram.yaml",
                    "zigzag/inputs/hardware/Experiment2_paper3_reram_rbuffer.yaml",
                    "zigzag/inputs/hardware/Experiment2_paper3_reram.yaml"]
# PEAK PERFORMANCES:
# TOP/s: 1.0378619435839938, TOP/s/W: 34.115689244707, TOP/s/mm^2: 1.1762292878967673
# TOP/s: 1.0378619435839938, TOP/s/W: 34.115689244707, TOP/s/mm^2: 1.1762292878967673
# TOP/s: 0.3153886539689881, TOP/s/W: 39.38704389366728, TOP/s/mm^2: 0.4865329060604892
# TOP/s: 0.3153886539689881, TOP/s/W: 39.38704389366728, TOP/s/mm^2: 0.4865329060604892
# TOP/s: 7.883299832677154, TOP/s/W: 120.27733397320874, TOP/s/mm^2: 1.5746335587202793
# TOP/s: 7.883299832677154, TOP/s/W: 120.27733397320874, TOP/s/mm^2: 1.5746335587202793
# TOP/s: 1.4013693669414946, TOP/s/W: 83.97625849448485, TOP/s/mm^2: 3.6728161435125863
# TOP/s: 1.4013693669414946, TOP/s/W: 83.97625849448485, TOP/s/mm^2: 3.6728161435125863


# architectures_to_compare = {
#         # --- 1T1R Architectures ---
#         "1T1R-S CiM/R Cache": "outputs/Experiment2_paper4_sram_rbuffer-resnet18",
#         "1T1R-S CiM/S Cache": "outputs/Experiment2_paper4_sram-resnet18",
#         "1T1R-R CiM/R Cache": "outputs/Experiment2_paper4_reram_rbuffer-resnet18",
#         "1T1R-R CiM/S Cache": "outputs/Experiment2_paper4_reram-resnet18",
#         # --- 2T2R Architectures ---
#         "2T2R-S CiM/R Cache": "outputs/Experiment2_paper3_sram_rbuffer-resnet18",
#         "2T2R-S CiM/S Cache": "outputs/Experiment2_paper3_sram-resnet18",
#         "2T2R-R CiM/R Cache": "outputs/Experiment2_paper3_reram_rbuffer-resnet18",
#         "2T2R-R CiM/S Cache": "outputs/Experiment2_paper3_reram-resnet18",
#     }
#
#     # --- 3. DEFINE THE PEAK PERFORMANCE DATA FOR EACH ARCHITECTURE ---
# peak_performance_data = {
#         # --- 1T1R Architectures ---
#         "1T1R-S CiM/R Cache": {"throughput_tops": 1.0378619435839938, "tops_per_watt": 34.115689244707, "tops_per_mm2": 1.1762292878967673},
#         "1T1R-S CiM/S Cache": {"throughput_tops": 1.0378619435839938, "tops_per_watt": 34.115689244707, "tops_per_mm2": 1.1762292878967673},
#         "1T1R-R CiM/R Cache": {"throughput_tops": 0.3153886539689881, "tops_per_watt": 39.38704389366728, "tops_per_mm2": 0.4865329060604892},
#         "1T1R-R CiM/S Cache": {"throughput_tops": 0.3153886539689881, "tops_per_watt": 39.38704389366728, "tops_per_mm2": 0.4865329060604892},
#         # --- 2T2R Architectures ---
#         "2T2R-S CiM/R Cache": {"throughput_tops": 7.883299832677154, "tops_per_watt": 120.27733397320874, "tops_per_mm2": 1.5746335587202793},
#         "2T2R-S CiM/S Cache": {"throughput_tops": 7.883299832677154, "tops_per_watt": 120.27733397320874, "tops_per_mm2": 1.5746335587202793},
#         "2T2R-R CiM/R Cache": {"throughput_tops": 1.4013693669414946, "tops_per_watt": 83.97625849448485, "tops_per_mm2": 6.242857967442599},
#         "2T2R-R CiM/S Cache": {"throughput_tops": 1.4013693669414946, "tops_per_watt": 83.97625849448485, "tops_per_mm2": 6.242857967442599},
#     }
# same number of ADCs
#     peak_performance_data = {
#         "1T1R-S/R": {"throughput_tops": 0.016216592868499902, "tops_per_watt": 34.115689244707, "tops_per_mm2": 1.1762292878967673},
#         "1T1R-S/S": {"throughput_tops": 0.016216592868499902, "tops_per_watt": 34.115689244707, "tops_per_mm2": 1.1762292878967673},
#         "1T1R-R/R": {"throughput_tops": 0.3153886539689881, "tops_per_watt": 39.38704389366728, "tops_per_mm2": 0.4865329060604892},
#         "1T1R-R/S": {"throughput_tops": 0.3153886539689881, "tops_per_watt": 39.38704389366728, "tops_per_mm2": 0.4865329060604892},
#         "2T2R-S/R": {"throughput_tops": 0.24635311977116106, "tops_per_watt": 55.179378762619315, "tops_per_mm2": 1.5746335587202793},
#         "2T2R-S/S": {"throughput_tops": 0.24635311977116106, "tops_per_watt": 55.179378762619315, "tops_per_mm2": 1.5746335587202793},
#         "2T2R-R/R": {"throughput_tops": 2.802738733882989, "tops_per_watt": 83.97625849448485, "tops_per_mm2": 6.242857967442599},
#         "2T2R-R/S": {"throughput_tops": 2.802738733882989, "tops_per_watt": 83.97625849448485, "tops_per_mm2": 6.242857967442599},
#     }
# same area
# peak_performance_data = {
#         "1T1R-S/R": {"throughput_tops": 0.8330528316826986, "tops_per_watt": 31.61563557103075, "tops_per_mm2": 1.3035410730646246},
#         "1T1R-S/S": {"throughput_tops": 0.8330528316826986, "tops_per_watt": 31.61563557103075, "tops_per_mm2": 1.3035410730646246},
#         "1T1R-R/R": {"throughput_tops": 0.3153886539689881, "tops_per_watt": 39.38704389366728, "tops_per_mm2": 0.4865329060604892},
#         "1T1R-R/S": {"throughput_tops": 0.3153886539689881, "tops_per_watt": 39.38704389366728, "tops_per_mm2": 0.4865329060604892},
#         "2T2R-S/R": {"throughput_tops": 0.9274418692685513, "tops_per_watt": 66.40338294500823, "tops_per_mm2": 1.4388133556426328},
#         "2T2R-S/S": {"throughput_tops": 0.9274418692685513, "tops_per_watt": 66.40338294500823, "tops_per_mm2": 1.4388133556426328},
#         "2T2R-R/R": {"throughput_tops": 4.270481552286069, "tops_per_watt": 85.14077942594498, "tops_per_mm2": 6.620280674656164},
#         "2T2R-R/S": {"throughput_tops": 4.270481552286069, "tops_per_watt": 85.14077942594498, "tops_per_mm2": 6.620280674656164},
#     }

workload_rram = "zigzag/inputs/workload/resnet18.onnx"
mapping_rram = "zigzag/inputs/mapping/default_imc.yaml"
for i in range(0,8):
    accelerator_rram = accelerator_list[i]

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

accelerator_rram = "zigzag/inputs/hardware/Experiment2_paper3_reram.yaml"
accelerator = AcceleratorParserStage.parse_accelerator(accelerator_rram)
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
G_writeavg = 20 * (10**(-6))
T_write = 20 * (10**(-9))
N_pulses = 8
M_type_dev = 2
gamma = 0.7
#
#
E_write_dev_pulse = (V_write**2) * G_writeavg * T_write
E_write_current_dev = E_write_dev_pulse * N_pulses

weight_precision = accelerator.operational_array.weight_precision
cells_size_nvm = accelerator.operational_array.cells_size_nvm

N_dev_w_tot = math.ceil(weight_precision / cells_size_nvm) * M_type_dev
# print(N_dev_w_tot)

E_write_current_weight = E_write_current_dev * N_dev_w_tot * gamma
print("E_write_current_weight: ", E_write_current_weight * (10**12))

alpha = 1.0
beta = 2.0
C_WL = accelerator.operational_array.c_wl_ff * (10**-15)
C_BL = accelerator.operational_array.c_blsl_ff * (10**-15)
V_WL_SWING = accelerator.operational_array.ReRAM_param["V_wl_swing_read"]
N_BL = accelerator.operational_array.bitline_amount

E_write_WL_weight = alpha * C_WL * (V_WL_SWING**2) * math.ceil(weight_precision / cells_size_nvm) #/ (N_BL * M_type_dev/N_dev_w_tot)
E_write_BL_weight = beta * N_dev_w_tot * C_BL * (V_write**2)
E_write_switching_weight = E_write_WL_weight + E_write_BL_weight
print("E_write_WL_weight, E_write_BL_weight, E_write_switching_weight: ", E_write_WL_weight * (10**12), E_write_BL_weight* (10**12), E_write_switching_weight* (10**12))

E_write_tot_weight = E_write_current_weight + E_write_switching_weight
print("E_write_tot_weight: ", E_write_tot_weight * (10**12))



#Running Cacti, but server out of date for python..., cacti is just shit and gives different results

# cacti_result = accelerator.operational_array.get_single_cell_array_cost_from_cacti(
#     tech_node = 0.028,
#     wordline_dim_size = 64.0,
#     bitline_dim_size = 65536.0,
#     cells_size = 8,
#     weight_precision = 8
# )
# cacti_result = accelerator.operational_array.get_single_cell_array_cost_from_cacti(
#     tech_node=0.028,
#     wordline_dim_size=65536.0,
#     bitline_dim_size=64.0,
#     cells_size=1.0,
#     weight_precision=8
# )
# print(cacti_result)







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


