import logging
import re

from zigzag.api import get_hardware_performance_zigzag #Actual ZigZag API
from zigzag.utils import pickle_load # Loading in of results
from zigzag.visualization.results.print_mapping import print_mapping # Also already printed in txt file
from zigzag.visualization.results.plot_cme import bar_plot_cost_model_evaluations_breakdown # Bar plot visualizations



accelerator_rram = "zigzag/inputs/hardware/aimc_rram_lightcim_2.yaml"
workload_rram = "zigzag/inputs/workload/resnet18.onnx"
mapping_rram = "zigzag/inputs/mapping/default_imc.yaml"

# Initialize the logger
logging_level = logging.INFO
logging_format = "%(asctime)s - %(name)s.%(funcName)s +%(lineno)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging_level, format=logging_format)


hw_name = accelerator_rram.split(".")[-1]
if hw_name == "yaml":
    hw_name = re.split(r"/|\.",accelerator_rram)[-2]
workload_name = re.split(r"/|\.", workload_rram)[-1]
if workload_name == "onnx" or "yaml":
    workload_name = re.split(r"/|\.", workload_rram)[-2]
experiment_id = f"RRAM_tests_{hw_name}-{workload_name}"
pickle_name = f"{experiment_id}-saved_list_of_cmes"


dump_folder = f"outputs/{experiment_id}"
pickle_filename = f"outputs/{pickle_name}.pickle"


get_hardware_performance_zigzag(
    accelerator=accelerator_rram,
    workload=workload_rram,
    mapping=mapping_rram,
    opt="latency",
    dump_folder=f"outputs/{experiment_id}",
    pickle_filename=f"outputs/{pickle_name}.pickle",
    # lpf_limit = 6,
    # nb_spatial_mappings_generated = 3,
    in_memory_compute = True,
    # exploit_data_locality = False,
    # enable_mix_spatial_mapping = False,
    # The outcommented ones are the defaults
)

"""
    Plotting results from the ZigZag hardware performance estimation
"""
cmes = pickle_load(pickle_filename)
print_mapping(cmes[0])
bar_plot_cost_model_evaluations_breakdown(cmes[0:5], save_path = f"outputs/{experiment_id}/plot_breakdown.png")
# Only plotting 6 layers to have a good plot!
