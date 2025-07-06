import logging
import math
from typing import Any

from zigzag.datatypes import OADimension
from zigzag.hardware.architecture.imc_array import ImcArray
from zigzag.hardware.architecture.imc_unit import ImcUnit
from zigzag.mapping.mapping import Mapping
from zigzag.utils import json_repr_handler
from zigzag.workload.layer_node import LayerNode

# Define NVM array types
NVM_ARRAY_TYPE_CROSSBAR = "crossbar"
NVM_ARRAY_TYPE_1T1R = "1T1R"
NVM_ARRAY_TYPE_1T1R_PSEUDO_CROSSBAR = "1T1R_pseudo_crossbar"
NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR = "2T2R_pseudo_crossbar"
NVM_ARRAY_TYPE_2T2R = "2T2R"

class ImcNvmArray(ImcArray):
    """
     Class for a Non-Volatile Memory (NVM) Compute-in-Memory (CiM) Array, specifically focusing on ReRAM.
    """

    def __init__(
        self,
        is_analog_imc: bool,
        bit_serial_precision: int,
        input_precision: list[int],
        adc_resolution: int,
        cells_size: int,
        cells_area: float | None,
        dimension_sizes: dict[OADimension, int],
        nvm_param_dict: dict[str, Any],
        auto_cost_extraction: bool = False,
    ):
        """
            Initializing of object of type ImcNvmArray
            Which has the cost model for CiM macros, focused on NVM/ReRAM.
        """
        # Just initializing so that python knows these attributes exist
        # Performance characteristics
        self.tclk_breakdown = None
        self.tclk = None
        self.area_breakdown = None
        self.area = None
        self.peak_energy_breakdown = None
        self.peak_energy = None
        self.tops_peak_bits = None
        self.topsw_peak_bits = None
        self.topsmm2_peak_bits = None
        self.tops_peak = None
        self.topsw_peak = None
        self.topsmm2_peak = None

        # Capacitance WLs and BLSLs
        # These are put as attributes so no recalculating
        self.c_wl_ff = None
        self.c_blsl_ff = None

        # Initializing from the inputs
        # ReRAM Specific
        self.ReRAM_param = nvm_param_dict
        self.nvm_array_type = self.ReRAM_param["nvm_array_type"]
        self.adc_share_factor = self.ReRAM_param["ADC_share_factor"]
        self.cells_size_nvm = self.ReRAM_param["size_nvm"]
        self.is_nvm = True

        # Grandparent class function, ImcUnit.__init__()
        ImcUnit.__init__(self,
            is_analog_imc=is_analog_imc,
            bit_serial_precision=bit_serial_precision,
            input_precision=input_precision,
            adc_resolution=adc_resolution,
            cells_size=cells_size,
            cells_area=cells_area,
            dimension_sizes=dimension_sizes,
            auto_cost_extraction=auto_cost_extraction,
        )

        # self.wordline_amount is the amount of rows, self.bitline_amount is the amount of columns
        # To avoid confusion, the amount of wordlines are the bitline_dim_size, and vice versa
        # This means that in the .yaml hardware configuration file, D1 refers to the amount of columns
        self.wordline_amount = self.bitline_dim_size
        num_physical_reram_devices_per_synaptic_weight = math.ceil(self.weight_precision / self.cells_size_nvm)
        self.bitline_amount = self.wordline_dim_size * num_physical_reram_devices_per_synaptic_weight
        # This last thing is done in this way, to still get the right array size,
        # but such that the mapping still does what it is expected to do

        # Getting the performance characteristics
        self.get_tclk()
        self.get_area()
        (
            self.tops_peak,
            self.topsw_peak,
            self.topsmm2_peak,
        ) = self.get_macro_level_peak_performance()

    def print_peak_performance(self):
        """
           Function to print the peak performance.
           It does it in terms of operations, and in terms of bit-operations.
           Finally, it also gives the numbers for latency, area, and (peak) energy consumption, with all their breakdowns.
        """
        print("---------------- Printing peak performance of NVM-IMC Array Macro: ----------------")
        print(f"Current macro-level peak performance ({'analog' if self.is_aimc else 'digital'} {self.nvm_array_type} NVM IMC):")
        print(f"TOP/s: {self.tops_peak}, TOP/s/W: {self.topsw_peak}, TOP/s/mm^2: {self.topsmm2_peak}")
        print(f"TOP/s/bit: {self.tops_peak_bits}, TOP/s/W/bit: {self.topsw_peak_bits}, TOP/s/mm^2/bit: {self.topsmm2_peak_bits}")
        print(f"Latency/clock period: {self.tclk} ns, Macro area: {self.area} mm^2, Energy consumption (single output cycle): {self.peak_energy} pJ")
        print("Latency breakdown: ", self.tclk_breakdown)
        print("Area breakdown: ", self.area_breakdown)
        print("Peak energy breakdown: ", self.peak_energy_breakdown)
        print("----------------------------------------------------------------------------------")
        return self.tclk, self.area, self.peak_energy, self.tclk_breakdown, self.area_breakdown, self.peak_energy_breakdown


    def get_area_access_device(self) -> float:
        """
            Returns the area of a single access device (transistor) in mm^2.
            Either it takes the value given in the ReRAM_params dictionary, or otherwise it estimates it with F (tech_node).
        """
        if self.nvm_array_type in [NVM_ARRAY_TYPE_1T1R, NVM_ARRAY_TYPE_1T1R_PSEUDO_CROSSBAR,
                                   NVM_ARRAY_TYPE_2T2R, NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR]:
            area_t = self.ReRAM_param.get("area_access_transistor_mm2", None)
            if area_t is None:
                f_um = self.ReRAM_param.get("tech_node")
                f_mm = f_um * (10**(-3))
                if f_mm:
                    area_t_estimate = (self.ReRAM_param["cell_area_F_multiplier"] * (f_mm ** 2))
                    return area_t_estimate
                print(
                    "ReRAM_param 'area_access_transistor_mm2' and 'tech_node' not found! Cannot estimate access device area.")
            return 0
        return 0.0  # No separate access device for pure crossbar (area assumed in cell)

    def calculate_driver_info(
            self,
            # Capacitance parameters, defaults are the estimates for 28nm
            c_gate_per_tx_ff: float = 4.0, # Gate capacitance of one access TX (fF)
            c_junction_per_tx_ff: float = 0.91, # Junction cap of one access TX to BL/SL (fF)
            cw_per_unit_length_ff_um: float = 0.2,  # Wire capacitance (fF/µm)
            # Buffer/Driver and minimum inverter parameters
            a_inv_min_f2: float = 10.0,  # Area of minimum sized inverter (F^2)
            c_in_inv_min_ff: float = 0.2,  # Input capacitance of minimum inverter (fF)
    ) -> dict:
        """
            Calculates estimated areas for Word Line (WL) and Bit Line/Source Line (BL/SL) drivers
            in a ReRAM array. Only valid for 1T1R, 2T2R and pseudo-crossbar, NOT crossbar.

            Returns a dictionary containing the capacitance of the WLs and BLSLs.
            Besides it also calculates the area of the drivers for those lines, a single one and the total area!
        """
        # General parameters
        num_rows = self.wordline_amount
        num_cols = self.bitline_amount
        f_um = self.ReRAM_param["tech_node"]  # Feature size in µm
        number_transistors_per_cell = (2 if (self.nvm_array_type == NVM_ARRAY_TYPE_2T2R or
                                             self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR)
                                       else 1) #2 for 2T2R, 1 for 1T1R
        # Cell pitches
        cell_pitch_width_f_multiplier = math.sqrt(self.ReRAM_param["cell_area_F_multiplier"])
        cell_pitch_height_f_multiplier = math.sqrt(self.ReRAM_param["cell_area_F_multiplier"])
        pitch_cell_width_um = cell_pitch_width_f_multiplier * f_um
        pitch_cell_height_um = cell_pitch_height_f_multiplier * f_um

        # 1. Word Line Load Capacitance (C_WL) for one WL
        length_wl_um = num_cols * number_transistors_per_cell * pitch_cell_width_um
        c_wire_wl_ff = cw_per_unit_length_ff_um * length_wl_um
        c_transistors_on_wl_ff = number_transistors_per_cell * num_cols * c_gate_per_tx_ff
        c_wl_ff = c_transistors_on_wl_ff + c_wire_wl_ff

        # 2. Bit Line / Source Line Load Capacitance (C_BLSL) for one BL/SL
        length_blsl_um = num_rows * pitch_cell_height_um
        c_transistors_on_blsl_ff = num_rows * c_junction_per_tx_ff
        if (self.nvm_array_type == NVM_ARRAY_TYPE_1T1R_PSEUDO_CROSSBAR or
            self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR):
            # BLs are in the same direction as WLs (they need the drivers), but SLs in general direction!
            # When the arrays are square, the calculations give the same!
            length_blsl_um = length_wl_um
            c_transistors_on_blsl_ff = num_cols * c_junction_per_tx_ff
        c_wire_blsl_ff = cw_per_unit_length_ff_um * length_blsl_um
        c_blsl_ff = c_transistors_on_blsl_ff + c_wire_blsl_ff

        # 3. Driver Area Calculation
        # Area of minimum inverter in um^2
        a_inv_min_um2 = a_inv_min_f2 * (f_um ** 2)

        # WL Driver Area
        s_wl_driver = max(1.0, c_wl_ff / c_in_inv_min_ff)
        area_one_wl_driver_um2 = a_inv_min_um2 * s_wl_driver
        area_total_wl_drivers_um2 = num_rows * area_one_wl_driver_um2

        # BL/SL Driver Area
        s_blsl_driver = max(1.0, c_blsl_ff / c_in_inv_min_ff)
        area_one_blsl_driver_um2 = a_inv_min_um2 * s_blsl_driver
        area_total_blsl_drivers_um2 = number_transistors_per_cell * num_cols * area_one_blsl_driver_um2
        if (self.nvm_array_type == NVM_ARRAY_TYPE_1T1R_PSEUDO_CROSSBAR or
                self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR):
            area_total_blsl_drivers_um2 = number_transistors_per_cell * num_rows * area_one_blsl_driver_um2

        results = {
            "C_WL_total_fF": c_wl_ff,
            "C_BLSL_total_fF": c_blsl_ff,
            "S_WL_driver": s_wl_driver,
            "S_BLSL_driver": s_blsl_driver,
            "Area_one_WL_driver_um2": area_one_wl_driver_um2,
            "Area_total_WL_drivers_um2": area_total_wl_drivers_um2,
            "Area_one_BLSL_driver_um2": area_one_blsl_driver_um2,
            "Area_total_BLSL_drivers_um2": area_total_blsl_drivers_um2
        }
        self.c_wl_ff = c_wl_ff
        self.c_blsl_ff = c_blsl_ff
        return results

    def get_adc_cost(self) -> tuple[float, float, float]:
        """
            Single ADC area, delay and energy but for ReRAM-based CiMs
            The delay was different compared to SRAM-CiMs, probably because the ADC designs are custom.
        """
        # Area (mm^2)
        if self.adc_resolution == 0 or self.adc_resolution == 1:
            adc_area: float = 0
        else:  # Empirical formula taken over from the (SRAM) IMC model
            k1 = -0.0369
            k2 = 1.206
            adc_area = 10 ** (k1 * self.adc_resolution + k2) * 2**self.adc_resolution * (10**-6)  # unit: mm^2

        # delay (ns)
        if self.adc_resolution == 0:
            adc_delay: float = 0
        else:
            fast_internal_clk_mhz = 650 # JOS paper
            clk_period_ns = 1.0/(fast_internal_clk_mhz * 10**(-3))

            (adc_setup_cycles, adc_cycles_per_bit_avg_first_chunk,
             first_chunk_max_bits, adc_cycles_per_bit_avg_second_chunk) = (3, 1, 4 ,2)
            total_adc_cycles_first_chunk = (adc_setup_cycles +
                    ((first_chunk_max_bits if self.adc_resolution >= first_chunk_max_bits else self.adc_resolution)
                     * adc_cycles_per_bit_avg_first_chunk))
            total_adc_cycles_second_chunk = (
                    (0 if self.adc_resolution <= first_chunk_max_bits else self.adc_resolution - first_chunk_max_bits)
                     * adc_cycles_per_bit_avg_second_chunk)

            total_adc_cycles = total_adc_cycles_first_chunk + total_adc_cycles_second_chunk
            adc_delay = total_adc_cycles * clk_period_ns

        # energy (fJ)
        if self.adc_resolution == 0:
            adc_energy: float = 0
        else:
            k5 = 100  # fF
            k6 = 0.001  # fF
            adc_energy = (k5 * self.adc_resolution + k6 * 4**self.adc_resolution) * self.tech_param["vdd"] ** 2
            adc_energy = adc_energy / 1000  # unit: pJ
        return adc_area, adc_delay, adc_energy

    def get_dac_cost(self) -> tuple[float, float, float]:
        """single DAC cost calculation"""
        # area (mm^2)
        dac_area = 0  # neglected
        # delay (ns)
        dac_delay = 0  # neglected
        # energy (fJ)
        if self.bit_serial_precision == 1:
            dac_energy = 0
        else:
            k0 = 50e-3  # pF
            dac_energy = k0 * self.bit_serial_precision * self.tech_param["vdd"] ** 2  # unit: pJ
        return dac_area, dac_delay, dac_energy

    def get_area(self):
        """
           Calculates the total area of the NVM CiM macro, breaking it down into components.
           Overrides the base ImcArray.get_area().
        """
        self.area_breakdown = dict()

        # 1. Area of the ReRAM cells themselves (the ReRAM material/stack)
        total_physical_reram_devices = self.wordline_amount * self.bitline_amount * self.nb_of_banks
        if self.nvm_array_type == NVM_ARRAY_TYPE_2T2R or self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR:
            total_physical_reram_devices = total_physical_reram_devices * 2 # Two ReRAM devices for 2T2R
        area_reram_devices_total = total_physical_reram_devices * self.cells_area  # self.cells_area from YAML
        self.area_breakdown["cells"] = area_reram_devices_total # often 0 (3D stacking often)

        # 2. Area of Access Devices (Transistors)
        area_single_access_device = self.get_area_access_device()
        total_access_devices = (total_physical_reram_devices
                                * (1 if not self.nvm_array_type == NVM_ARRAY_TYPE_CROSSBAR else 0))
        # `total_physical_reram_devices` already accounts for how many R devices are there in 2T2R.
        area_access_devices = total_access_devices * area_single_access_device
        self.area_breakdown["access_tx"] = area_access_devices

        # 3. Area of DACs (Digital-to-Analog Converters) for inputs
        area_dacs = 0
        if self.is_aimc:  # Analog IMC needs DACs for inputs
            # Assuming DACs are applied to wordlines for inputs.
            num_dacs = self.wordline_amount * self.nb_of_banks
            area_dacs = num_dacs * self.get_dac_cost()[0]
        self.area_breakdown["dacs"] = area_dacs

        # 4. Area of ADCs (Analog-to-Digital Converters) for outputs
        area_adcs = 0
        if self.is_aimc:  # Analog IMC needs ADCs for outputs
            # ADCs are typically along the bitline dimension.
            amount_of_adc_bitlines = math.ceil(self.bitline_amount / (self.weight_precision/self.cells_size_nvm))
            num_adcs = math.ceil( amount_of_adc_bitlines / self.adc_share_factor) * self.nb_of_banks
            area_adcs = num_adcs * self.get_adc_cost()[0]
        self.area_breakdown["adcs"] = area_adcs

        # 5. Area of Digital Adders and Accumulators (if any, from base class)
        self.area_breakdown["adders_regular"] = 0 # Only for DIMC
        total_sharing_factor = (self.adc_share_factor * (self.weight_precision / self.cells_size_nvm))

        # area of adder trees with place values (type: RCA)
        nb_inputs_of_adder_pv = self.weight_precision / self.cells_size_nvm  # amount of bitlines that give input
        input_precision_pv = self.adc_resolution
        if nb_inputs_of_adder_pv == 1:
            nb_of_1b_adder_per_tree_pv = 0
        else:
            adder_depth_pv = math.log2(nb_inputs_of_adder_pv)
            assert (adder_depth_pv % 1 == 0), f"[weight_precision/self.cells_size_nvm] is not in the power of 2."
            adder_depth_pv = int(adder_depth_pv)  # float -> int for simplicity
            nb_of_1b_adder_per_tree_pv = input_precision_pv * (nb_inputs_of_adder_pv - 1) + nb_inputs_of_adder_pv * (
                    adder_depth_pv - 0.5)  # nb of 1b adders in a single place-value adder tree
        nb_of_adder_trees_pv = self.bitline_amount * self.nb_of_banks / total_sharing_factor / nb_inputs_of_adder_pv # amount of ADCs/ how many inputs
        area_adders_pv = self.get_1b_adder_area() * nb_of_1b_adder_per_tree_pv * nb_of_adder_trees_pv
        self.area_breakdown["adders_pv"] = area_adders_pv  # Place-value adders after ADCs

        # area of accumulators (adder type: RCA)
        if self.bit_serial_precision == self.activation_precision: # No accumulator needed if no accumulation needs to happen (just 1 input cycle)
            area_accumulators = 0
        else:
            accumulator_output_precision = self.activation_precision + self.adc_resolution + self.weight_precision
            # output precision from adders_pv + required shifted bits
            # more accumulators needed, for every possible output, not just for amount of adders_pv
            nb_of_1b_adder_accumulator = (accumulator_output_precision * self.nb_of_banks
                                          * self.bitline_amount / (self.weight_precision / self.cells_size_nvm ))
            nb_of_1b_reg_accumulator = nb_of_1b_adder_accumulator  # number of regs in an accumulator
            area_accumulators = (
                    self.get_1b_adder_area() * nb_of_1b_adder_accumulator
                    + self.get_1b_reg_area() * nb_of_1b_reg_accumulator
            )
        self.area_breakdown["accumulators"] = area_accumulators

        # 6. Area of Peripheral Drivers (Wordline drivers, Bitline/Sourceline drivers)
        driver_areas_dict = self.calculate_driver_info() # via seperate function
        self.area_breakdown["wl_drivers"] = self.nb_of_banks * driver_areas_dict.get("Area_total_WL_drivers_um2", 0)/(10**6)
        self.area_breakdown["bl_drivers"] = self.nb_of_banks * driver_areas_dict.get("Area_total_BLSL_drivers_um2", 0)/(10**6)

        self.area = sum(self.area_breakdown.values())

    def get_tclk(self):
        """
           Calculates the latency of the NVM CiM macro, breaking it down into components.
           Overrides the base ImcArray.get_tclk().
        """
        self.tclk_breakdown = dict()

        """worst path for AIMC: adcs -> adders -> accumulators"""
        """worst path for DIMC: cells -> adders -> accumulators"""
        # Some parts do not contribute, as they execute while ADCs are quantizising (during its setup cycles)

        # --- 1. ReRAM Cells Reading Latency (but at same time as ADC) ---
        dly_cells = 0
        if not self.is_aimc:
            dly_cells = 10 # no ADC decide how long pulse, so a certain time (10 ns)
        self.tclk_breakdown["cells"] = dly_cells

        # --- 2. Line Driver Latency -----
        self.tclk_breakdown["wl_drivers"] = 0  # Put to 0 -> Driving WLs during ADC setup
        self.tclk_breakdown["bl_drivers"] = 0  # Put to 0 -> Driving BLs during ADC setup

        # --- 3. DAC Latency ---
        if self.is_aimc:
            dly_dacs = self.get_dac_cost()[1]
        else:
            dly_dacs = 0
        self.tclk_breakdown["dacs"] = dly_dacs

        # --- 4. ADC Latency ---
        # ADCs are by far the most important in the whole breakdown (for AIMC)
        if self.is_aimc:
            dly_adcs = self.get_adc_cost()[1]
        else:
            dly_adcs = 0
        self.tclk_breakdown["adcs"] = dly_adcs

        # --- 5. Digital Logic Latency (Adders, Accumulators etc.) ---
        self.tclk_breakdown["adders_regular"] = 0 # Only needed for DIMC, which is not modeled

        # delay of adder trees with place value (type: RCA)
        # worst path: in-to-sum -> in-to-sum -> ... -> in-to-cout -> cin-to-cout -> ... -> cin-to-cout
        nb_inputs_of_adder_pv = self.weight_precision/self.cells_size_nvm
        input_precision_pv = self.adc_resolution
        if nb_inputs_of_adder_pv == 1:
            adder_pv_output_precision = input_precision_pv
            dly_adders_pv = 0
        else:
            adder_depth_pv = math.log2(nb_inputs_of_adder_pv)
            adder_depth_pv = int(adder_depth_pv)  # float -> int for simplicity
            adder_pv_output_precision = nb_inputs_of_adder_pv + input_precision_pv  # output precision from adders_pv
            dly_adders_pv = ( (adder_depth_pv - 1) * self.get_1b_adder_dly_in2sum()
                            + self.get_1b_adder_dly_in2cout()
                            + (adder_pv_output_precision - input_precision_pv - 1) * self.get_1b_adder_dly_cin2cout() )
        self.tclk_breakdown["adders_pv"] = dly_adders_pv

        # delay of accumulators (adder type: RCA)
        if self.bit_serial_precision == self.activation_precision:  # No accumulator needed if no accumulation needs to happen (just 1 input cycle)
            dly_accumulators = 0
        else:
            accumulator_input_precision = adder_pv_output_precision
            accumulator_output_precision = (self.activation_precision + self.adc_resolution + self.weight_precision)  # output precision from adders_pv + required shifted bits
            assert accumulator_input_precision < accumulator_output_precision
            dly_accumulators = (self.get_1b_adder_dly_in2cout() +
                                (accumulator_output_precision - accumulator_input_precision - 1)
                                * self.get_1b_adder_dly_cin2cout())
        self.tclk_breakdown["accumulators"] = dly_accumulators

        self.tclk = sum([v for v in self.tclk_breakdown.values()])

        # 'Pulse' for reading (how long current through) ReRAM cells is:
        #   - how long ADCs are working for AIMC
        #   - how long current through cells for DIMC
        # This function (self.get_tclk()) always needs to be run before energy functions do!
        self.ReRAM_param["t_read_pulse"] = self.tclk_breakdown["adcs"] * 1e-9
        if not self.is_aimc:
            self.ReRAM_param["t_read_pulse"] = self.tclk_breakdown["cells"]

    def get_peak_energy_single_cycle(self) -> dict[str, float]:
        """
           Calculates macro-level one-cycle peak energy for ReRAM CiM array read operation.
           Assumes full utilization of activated components and no weight updating.
           One cycle here is not a full array readout, but rather a 'cycle' with one time ADC quantization.
           This function is ONLY valid for AIMC, not for DIMC, as it doesn't make much sense for ReRAM and no validation was done.
           Energies in dictionary are returned in picoJoules (pJ).
       """
        # --- 0. Getting General Parameters ---
        self.peak_energy_breakdown = dict() # Initializing dict

        # Rows and Columns activated: Peak energy -> Complete macro
        num_rows_activated = self.wordline_amount
        num_cols_activated = ((self.bitline_amount /
                               (self.adc_share_factor * (self.weight_precision / self.cells_size_nvm) ))
                              ) # During one quantization cycle
        num_all_active_cells_in_op = num_rows_activated * num_cols_activated
        if (self.nvm_array_type == NVM_ARRAY_TYPE_2T2R
                or self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR):  # 2 reram per cell
            num_all_active_cells_in_op = 2 * num_all_active_cells_in_op

        # WLs and BLs that need to be driven (BLs in this are along the dimension of the ADCs (sometimes called SLs))
        num_wl_to_drive = (num_rows_activated
                          / (self.adc_share_factor * (self.weight_precision / self.cells_size_nvm)) )
        # Different compare to num_rows_activated, as the WLs active stay active over multiple quantization cycles
        # We need to divide by how many quantization cycles happen (total sharing factor of ADCs)!
        num_bl_to_drive = num_cols_activated # Same as activated amount
        if (self.nvm_array_type == NVM_ARRAY_TYPE_1T1R_PSEUDO_CROSSBAR
                or self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR): # BLs to drive along wl direction
            num_bl_to_drive = num_wl_to_drive
        if (self.nvm_array_type == NVM_ARRAY_TYPE_2T2R
                or self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR): # 2 BLs per cell column/row
            num_bl_to_drive = 2 * num_bl_to_drive

        # self.calculated_driver_info() has already been run (in self.get_area()) during initialization.
        # Not needed to run again to get the average wl and bl capacitances
        c_wl_avg_f = self.c_wl_ff * (10**(-15)) # unit: F
        c_bl_avg_f = self.c_blsl_ff * (10**(-15)) # unit: F

        # --- 1. ReRAM Array Read Current Energy ---
        # Energy from current flowing through selected ReRAM cells during read

        # Energy for one cell to be read (in Joules)
        # Calculate average cell current for read if not pre-calculated
        i_cell_avg_read = 0
        if "G_LRS" in self.ReRAM_param and "G_HRS" in self.ReRAM_param:
            if not (self.ReRAM_param["G_LRS"] is None or self.ReRAM_param["G_HRS"] is None):
                avg_conductance = (self.ReRAM_param["G_LRS"] + self.ReRAM_param["G_HRS"]) / 2.0
                i_cell_avg_read = avg_conductance * self.ReRAM_param["V_read"]
        elif "I_LRS" in self.ReRAM_param and "I_HRS" in self.ReRAM_param:
            if not (self.ReRAM_param["I_LRS"] is None or self.ReRAM_param["I_HRS"] is None):
                i_cell_avg_read = (self.ReRAM_param["I_LRS"] + self.ReRAM_param["I_HRS"]) / 2.0
        else:
            raise ValueError("Missing LRS/HRS current or conductance in reram_params")

        e_read_one_cell_j = (self.ReRAM_param["V_read"] * i_cell_avg_read * self.ReRAM_param["t_read_pulse"])

        # Total energy for all active cells (in Joules)
        total_array_cell_current_energy_j = num_all_active_cells_in_op * e_read_one_cell_j
        self.peak_energy_breakdown["cells"] = total_array_cell_current_energy_j * 1e12 * self.nb_of_banks  # Convert J to pJ

        # --- 2. Line Driver Energy (Dynamic CV^2) ---
        # For peak energy, typically one significant transition is considered.
        alpha_switching = 0.5 * 2 #charging and discharging after full computation
        if ((self.nvm_array_type == NVM_ARRAY_TYPE_1T1R_PSEUDO_CROSSBAR
            or self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR)\
                and (self.bit_serial_precision > 1)):
            alpha_switching = 0.75*2 #bitlines do most weighting rather than the wordlines
        beta_switching = 1.0 * 2 #charging and discharging after one cycle

        # WL Driver Energy
        e_wl_drivers_j = (alpha_switching * num_wl_to_drive *
                          c_wl_avg_f * (self.ReRAM_param["V_wl_swing_read"] ** 2))
        self.peak_energy_breakdown["wl_drivers"] = e_wl_drivers_j * 1e12 * self.nb_of_banks
        # BL Driver Energy, the energy delivered during holding of the voltage duringthe cycle is taken care of by the cell reading energy
        e_bl_drivers_j = (beta_switching * num_bl_to_drive *
                           c_bl_avg_f * (self.ReRAM_param["V_bl_swing_read"] ** 2))
        self.peak_energy_breakdown["bl_drivers"] = e_bl_drivers_j * 1e12 * self.nb_of_banks

        # --- 3. DAC Energy ---
        total_dac_energy_pj = (self.get_dac_cost()[2] * num_rows_activated) / (self.adc_share_factor * (self.weight_precision / self.cells_size_nvm) )
        self.peak_energy_breakdown["dacs"] = total_dac_energy_pj * self.nb_of_banks

        # --- 4. ADC Energy ---
        total_adc_energy_pj = self.get_adc_cost()[2] * num_cols_activated
        self.peak_energy_breakdown["adcs"] = total_adc_energy_pj * self.nb_of_banks

        # --- 5. Digital Logic Energy (Adders, Accumulators etc.) ---
        self.peak_energy_breakdown["adders_regular"] = 0 # Only needed for DIMC, which is not modeled
        total_sharing_factor = (self.adc_share_factor * (self.weight_precision / self.cells_size_nvm))

        # energy of adder trees with place values (type: RCA) (AIMC case)
        nb_inputs_of_adder_pv = self.weight_precision/self.cells_size_nvm # amount of bitlines that give input
        input_precision_pv = self.adc_resolution
        if nb_inputs_of_adder_pv == 1: # No adders_pv needed if no combining because of no multiple bitlines make a single output
            nb_of_1b_adder_per_tree_pv = 0
        else:
            nb_of_1b_adder_per_tree_pv = input_precision_pv *(nb_inputs_of_adder_pv - 1) + nb_inputs_of_adder_pv * (
                                        math.log2(nb_inputs_of_adder_pv) - 0.5)
        nb_of_adder_trees_pv = num_cols_activated / nb_inputs_of_adder_pv * self.nb_of_banks # amount of ADCs
        # Assumption: adders_pv are placed after ADCs and before accumulators, combining multiple ADC outputs to one!
        energy_adders_pv = self.get_1b_adder_energy() * nb_of_1b_adder_per_tree_pv * nb_of_adder_trees_pv
        self.peak_energy_breakdown["adders_pv"] = energy_adders_pv

        # energy of accumulators (adder type: RCA)
        if self.bit_serial_precision == self.activation_precision: # No accumulator needed if no accumulation needs to happen (just 1 input cycle)
            energy_accumulators = 0
        else:
            accumulator_output_precision = self.activation_precision + self.adc_resolution + self.weight_precision
            # output precision from adders_pv + required shifted bits
            # more accumulators needed, for every possible output, not just for amount of adders_pv
            # but only the same amount as adder_pv trees do actually switch
            nb_of_1b_adder_accumulator = accumulator_output_precision * self.nb_of_banks * num_cols_activated / (self.weight_precision / self.cells_size_nvm)
            # Assumption: accumulator is placed behind the adders_pv and accumulates for multiple input cycles!
            nb_of_1b_reg_accumulator = nb_of_1b_adder_accumulator  # number of regs in an accumulator
            energy_accumulators = ( self.get_1b_adder_energy() * nb_of_1b_adder_accumulator
                                    + self.get_1b_reg_energy() * nb_of_1b_reg_accumulator)
        self.peak_energy_breakdown["accumulators"] = energy_accumulators

        self.peak_energy = sum(self.peak_energy_breakdown.values())
        return self.peak_energy_breakdown

    def get_macro_level_peak_performance(self) -> tuple[float, float, float]:
        """
            Macro-level peak performance of imc arrays (fully utilization, no weight updating)
        """
        # Amount of MACs and bit-operations
        nb_of_macs_per_cycle = (
            self.wordline_amount * self.bitline_amount
            / (self.activation_precision / self.bit_serial_precision) # how many cycles for a mac on inputs -> wl dimension sharing
            / (self.weight_precision / self.cells_size_nvm) # cells together to make weight precision -> bl dimension sharing
            / (self.weight_precision / self.cells_size_nvm) # This with the adc share factor is the total adc share factor
            / self.adc_share_factor # ADCs shared over how many synaptic cells (stores self.weight_precision) -> bl dimension sharing
            * self.nb_of_banks) # amount of macros/banks
        nb_of_operations_per_cycle = nb_of_macs_per_cycle * 2 # 1 MAC is an addition and a multiplication
        nb_of_bit_macs_per_cycle = nb_of_macs_per_cycle * self.weight_precision * self.activation_precision # times input and weight precisions
        nb_of_bit_operations_per_cycle = nb_of_bit_macs_per_cycle * 2 # 1 MAC is an addition and a multiplication

        # latency and energy calculations from other functions (saved as attributes)
        clock_cycle_period = self.tclk  # unit: ns
        self.get_peak_energy_single_cycle() # Actually calculating energies
        peak_energy_per_cycle = self.peak_energy  # unit: pJ
        imc_area = self.area  # unit: mm^2

        # Performance characteristics calculations, both in terms of operations and bit-operations
        tops_peak = nb_of_operations_per_cycle / clock_cycle_period / 1000
        tops_peak_bits = nb_of_bit_operations_per_cycle / clock_cycle_period / 1000
        topsw_peak = nb_of_operations_per_cycle / peak_energy_per_cycle
        topsw_peak_bits = nb_of_bit_operations_per_cycle / peak_energy_per_cycle
        topsmm2_peak = tops_peak / (imc_area)
        topsmm2_peak_bits = tops_peak_bits / imc_area
        self.tops_peak_bits = tops_peak_bits
        self.topsw_peak_bits = topsw_peak_bits
        self.topsmm2_peak_bits = topsmm2_peak_bits

        # Logging peak performance characteristics
        logger = logging.getLogger(__name__)
        imc_type_info = f"Current macro-level peak performance ({'analog' if self.is_aimc else 'digital'} {self.nvm_array_type} NVM IMC):"
        peak_performance_info = f"TOP/s: {tops_peak}, TOP/s/W: {topsw_peak}, TOP/s/mm^2: {topsmm2_peak}"
        peak_performance_bits_info = f"TOP/s/bit: {tops_peak_bits}, TOP/s/W/bit: {topsw_peak_bits}, TOP/s/mm^2/bit: {topsmm2_peak_bits}"
        logger.info(imc_type_info)
        logger.info(peak_performance_info)
        logger.info(peak_performance_bits_info)

        return tops_peak, topsw_peak, topsmm2_peak

    def get_energy_for_a_layer(self, layer: LayerNode, mapping: Mapping) -> dict[str, float]:
        """
           Calculates macro-level one-cycle energy for ReRAM CiM array read operation.
           One cycle here is not a full array readout, but rather a 'cycle' with one time ADC quantization.
           This is similar to how it is done in the self.get_peak_energy_single_cycle() function,
           but it will be scaled to support the whole layer.
           This function is ONLY valid for AIMC, not for DIMC, as it doesn't make much sense for ReRAM and no validation was done.
           Energies in dictionary are returned in picoJoules (pJ).
       """
        # --- 0. Getting General Parameters ---
        self.energy_breakdown = dict()

        # Workload Parameters Extraction
        (   mapped_rows_total_per_macro,
            _,
            mapped_cols_per_macro,
            macro_activation_times,  # normalized to only one imc macro
        ) = self.get_mapped_oa_dim(layer, self.wl_dim, self.bl_dim)
        self.mapped_rows_total_per_macro = mapped_rows_total_per_macro
        amount_of_repeating_macro = macro_activation_times * (self.activation_precision / self.bit_serial_precision)
        mapped_cols_per_macro_real = mapped_cols_per_macro * (self.weight_precision / self.cells_size_nvm)

        # Rows and Columns activated:
        num_rows_activated = mapped_rows_total_per_macro
        num_cols_activated_max = ((self.bitline_amount /
                               (self.adc_share_factor * (self.weight_precision / self.cells_size_nvm)))
                               )  # During one quantization cycle
        reading_array_full_amount = math.floor(mapped_cols_per_macro_real / num_cols_activated_max)
        num_cols_activated_partly = mapped_cols_per_macro_real % num_cols_activated_max
        reading_array_partly_amount = (1 if num_cols_activated_partly != 0 else 0)
        num_all_active_cells_in_op_full = num_rows_activated * num_cols_activated_max
        num_all_active_cells_in_op_partly = num_rows_activated * num_cols_activated_partly

        if (self.nvm_array_type == NVM_ARRAY_TYPE_2T2R
                or self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR):  # 2 devices per cell
            num_all_active_cells_in_op_full = 2 * num_all_active_cells_in_op_full
            num_all_active_cells_in_op_partly = 2 * num_all_active_cells_in_op_partly

        self.number_of_cycles_for_layer = reading_array_partly_amount  +  reading_array_full_amount

        # WLs and BLs that need to be driven (BLs in this are along the dimension of the ADCs (sometimes called SLs))
        num_wl_to_drive = num_rows_activated
        num_bl_to_drive_full = num_cols_activated_max
        num_bl_to_drive_partly = num_cols_activated_partly
        if (self.nvm_array_type == NVM_ARRAY_TYPE_1T1R_PSEUDO_CROSSBAR
                or self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR):  # BLs to drive along wl direction
            num_bl_to_drive_full = num_wl_to_drive / float((reading_array_full_amount + reading_array_partly_amount))
            num_bl_to_drive_partly = num_wl_to_drive / float((reading_array_full_amount + reading_array_partly_amount))
        if (self.nvm_array_type == NVM_ARRAY_TYPE_2T2R
                or self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR):  # 2 BLs per cell column/row
            num_bl_to_drive_full = 2 * num_bl_to_drive_full
            num_bl_to_drive_partly = 2 * num_bl_to_drive_partly

        # self.calculated_driver_info() has already been run (in self.get_area()) during initialization.
        # Not needed to run again to get the average wl and bl capacitances
        c_wl_avg_f = self.c_wl_ff * (10 ** (-15))  # unit: F
        c_bl_avg_f = self.c_blsl_ff * (10 ** (-15))  # unit: F

        # --- 1. ReRAM Array Read Current Energy ---
        # Energy from current flowing through selected ReRAM cells during read

        # Energy for one cell to be read (in Joules)
        # Calculate average cell current for read if not pre-calculated
        i_cell_avg_read = 0
        if "G_LRS" in self.ReRAM_param and "G_HRS" in self.ReRAM_param:
            if not (self.ReRAM_param["G_LRS"] is None or self.ReRAM_param["G_HRS"] is None):
                avg_conductance = (self.ReRAM_param["G_LRS"] + self.ReRAM_param["G_HRS"]) / 2.0
                i_cell_avg_read = avg_conductance * self.ReRAM_param["V_read"]
        elif "I_LRS" in self.ReRAM_param and "I_HRS" in self.ReRAM_param:
            if not (self.ReRAM_param["I_LRS"] is None or self.ReRAM_param["I_HRS"] is None):
                i_cell_avg_read = (self.ReRAM_param["I_LRS"] + self.ReRAM_param["I_HRS"]) / 2.0
        else:
            raise ValueError("Missing LRS/HRS current or conductance in reram_params")

        e_read_one_cell_j = (self.ReRAM_param["V_read"] * i_cell_avg_read * self.ReRAM_param["t_read_pulse"])

        # Total energy for all active cells (in Joules)
        total_array_cell_current_energy_j = ((num_all_active_cells_in_op_full * e_read_one_cell_j
                                             * reading_array_full_amount)
                                            + (num_all_active_cells_in_op_partly * e_read_one_cell_j
                                             * reading_array_partly_amount))
        self.energy_breakdown["cells"] = total_array_cell_current_energy_j * 1e12 * amount_of_repeating_macro  # Convert J to pJ

        # --- 2. Line Driver Energy (Dynamic CV^2) ---
        alpha_switching = 0.5 * 2  # charging and discharging after full computation
        if ((self.nvm_array_type == NVM_ARRAY_TYPE_1T1R_PSEUDO_CROSSBAR
             or self.nvm_array_type == NVM_ARRAY_TYPE_2T2R_PSEUDO_CROSSBAR) and
            (self.bit_serial_precision > 1)):
            alpha_switching = 0.75 * 2  # bitlines do most weighting rather than the wordlines
        beta_switching = 1.0 * 2  # charging and discharging after one cycle

        # WL Driver Energy -> Once at the start energy
        e_wl_drivers_j = (alpha_switching * num_wl_to_drive *
                          c_wl_avg_f * (self.ReRAM_param["V_wl_swing_read"] ** 2)) # just once until new inputs
        self.energy_breakdown["wl_drivers"] = e_wl_drivers_j * 1e12 * amount_of_repeating_macro
        # BL Driver Energy -> Every time a new BL will be used
        e_bl_drivers_j_full = (beta_switching * num_bl_to_drive_full *
                          c_bl_avg_f * (self.ReRAM_param["V_bl_swing_read"] ** 2))
        e_bl_drivers_j_partly = (beta_switching * num_bl_to_drive_partly *
                               c_bl_avg_f * (self.ReRAM_param["V_bl_swing_read"] ** 2))
        e_bl_drivers_j = (e_bl_drivers_j_full * reading_array_full_amount +
                          e_bl_drivers_j_partly * reading_array_partly_amount)
        self.energy_breakdown["bl_drivers"] = e_bl_drivers_j * 1e12 * amount_of_repeating_macro

        # --- 3. DAC Energy ---
        total_dac_energy_pj = self.get_dac_cost()[2] * num_rows_activated
        self.energy_breakdown["dacs"] = total_dac_energy_pj * amount_of_repeating_macro

        # --- 4. ADC Energy ---
        total_adc_energy_pj_full = self.get_adc_cost()[2] * num_cols_activated_max
        total_adc_energy_pj_partly = self.get_adc_cost()[2] * num_cols_activated_partly
        total_adc_energy_pj = (total_adc_energy_pj_full  * reading_array_full_amount
                            + total_adc_energy_pj_partly * reading_array_partly_amount)
        self.energy_breakdown["adcs"] = total_adc_energy_pj * amount_of_repeating_macro

        # --- 5. Digital Logic Energy (Adders, Accumulators etc.) ---
        self.energy_breakdown["adders_regular"] = 0

        # energy of adder trees with place values (type: RCA) (AIMC case)
        nb_inputs_of_adder_pv = self.weight_precision / self.cells_size_nvm  # amount of bitlines that give input
        input_precision_pv = self.adc_resolution
        if nb_inputs_of_adder_pv == 1:  # No adders_pv needed if no combining because of no multiple bitlines make a single output
            nb_of_1b_adder_per_tree_pv = 0
        else:
            nb_of_1b_adder_per_tree_pv = input_precision_pv * (nb_inputs_of_adder_pv - 1) + nb_inputs_of_adder_pv * (
                    math.log2(nb_inputs_of_adder_pv) - 0.5)
        # Assumption: adders_pv are placed after ADCs and before accumulators, combining multiple ADC outputs to one!
        energy_adders_pv_full = (self.get_1b_adder_energy() * nb_of_1b_adder_per_tree_pv
                                * (num_cols_activated_max / nb_inputs_of_adder_pv)  * reading_array_full_amount)
        energy_adders_pv_partly = (self.get_1b_adder_energy() * nb_of_1b_adder_per_tree_pv
                                * (math.ceil(num_cols_activated_partly / float(nb_inputs_of_adder_pv))) * reading_array_partly_amount)
        energy_adders_pv = energy_adders_pv_full + energy_adders_pv_partly
        self.energy_breakdown["adders_pv"] = energy_adders_pv * amount_of_repeating_macro

        # energy of accumulators (adder type: RCA)
        if self.bit_serial_precision == self.activation_precision:  # No accumulator needed if no accumulation needs to happen (just 1 input cycle)
            energy_accumulators = 0
        else:
            accumulator_output_precision = self.activation_precision + self.adc_resolution + self.weight_precision
            # output precision from adders_pv + required shifted bits
            # but only the same amount as adder_pv trees do actually switch
            nb_of_1b_adder_accumulator = (accumulator_output_precision
                * ((num_cols_activated_max / (self.weight_precision/self.cells_size_nvm) )
                    * reading_array_full_amount
                +   math.ceil((num_cols_activated_partly / float(self.weight_precision/self.cells_size_nvm)))
                    * reading_array_partly_amount))
            # Assumption: accumulator is placed behind the adders_pv and accumulates for multiple input cycles!
            nb_of_1b_reg_accumulator = nb_of_1b_adder_accumulator  # number of regs in an accumulator
            energy_accumulators = (self.get_1b_adder_energy() * nb_of_1b_adder_accumulator
                                   + self.get_1b_reg_energy() * nb_of_1b_reg_accumulator)
        self.peak_energy_breakdown["accumulators"] = energy_accumulators * amount_of_repeating_macro

        self.energy = sum([v for v in self.energy_breakdown.values()])
        return self.energy_breakdown

    def __jsonrepr__(self):
        return json_repr_handler({"operational_unit: ImcNvmArray, dimensions": self.dimension_sizes})