import logging
import math
from typing import Any


from zigzag.datatypes import OADimension
# from zigzag.hardware.architecture.imc_unit import ImcUnit
from zigzag.hardware.architecture.imc_array import ImcArray
from zigzag.mapping.mapping import Mapping
from zigzag.utils import json_repr_handler
from zigzag.workload.layer_node import LayerNode


# Define NVM array types (as constants or an Enum)
NVM_ARRAY_TYPE_CROSSBAR = "crossbar"
NVM_ARRAY_TYPE_1T1R = "1T1R"
NVM_ARRAY_TYPE_PSEUDO_CROSSBAR = "pseudo_crossbar" # May be similar to 1T1R in core logic
NVM_ARRAY_TYPE_2T2R = "2T2R"

class ImcNvmArray(ImcArray):
    """
     Class for a Non-Volatile Memory (NVM) Compute-in-Memory (CiM) Array, specifically focusing on ReRAM.

    constraints (for SRAM CiM as well):
        -- activation precision must be in the power of 2.
        -- bit_serial_precision must be in the power of 2.
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

        # ReRAM-specific ReRAM_param:
        # e.g., area_access_transistor_mm2, area_wordline_driver_mm2,
        # area_bitline_driver_mm2, ADC_share_factor, tech_node (for F_mm)
        # For example, in your YAML for ReRAM_param:
        # tech_node: 28 #nm
        # F_mm: 0.000028 # Feature size in mm (28nm)
        # area_access_transistor_mm2: 0.00000000784 # Example: 10 * (F_mm^2) for a 28nm transistor
        # area_wordline_driver_mm2: 0.00001 # Placeholder for area of one WL driver
        # area_bitline_driver_mm2: 0.00001  # Placeholder for area of one BL driver
        # ADC_share_factor: 8 # Example: From Liu et al. [cite: 481] or Yao et al. [cite: 663] papers for 512cols/64ADCs
        # To capture other args for ImcUnit/ImcArray like auto_cost_extraction
    ):
        # Just initializing so that python knows these attributes exist
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


        self.ReRAM_param = nvm_param_dict
        self.nvm_array_type = self.ReRAM_param["nvm_array_type"]
        self.adc_share_factor = self.ReRAM_param["ADC_share_factor"]

        # print ("adc share factor", self.adc_share_factor)
        if not isinstance(self.adc_share_factor, int) or self.adc_share_factor < 1:
            print(f"Invalid ADC_share_factor ({self.adc_share_factor}), defaulting to 1.")
            self.adc_share_factor = 1  # defaulting to 1

        super().__init__(
            is_analog_imc=is_analog_imc,
            bit_serial_precision=bit_serial_precision,
            input_precision=input_precision,
            adc_resolution=adc_resolution,
            cells_size=cells_size,
            cells_area=cells_area,
            dimension_sizes=dimension_sizes,
            auto_cost_extraction=auto_cost_extraction,
        )

    def print_peak_performance(self):
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

    def _get_area_access_device(self) -> float:
        """
        Returns the area of a single access device (transistor) in mm^2.
        This value MUST be set realistically in your tech_param.
        """
        if self.nvm_array_type in [NVM_ARRAY_TYPE_1T1R, NVM_ARRAY_TYPE_PSEUDO_CROSSBAR, NVM_ARRAY_TYPE_2T2R]:
            area_t = self.ReRAM_param.get("area_access_transistor_mm2", None)
            if area_t is None:
                # Fallback to a very rough estimation if not provided, with a warning.
                f_um = self.ReRAM_param.get("tech_node")  # Feature size in um (e.g., 28e-3 for 28nm)
                f_mm = f_um * (10**(-3))
                if f_mm:
                    area_t_estimate = (self.ReRAM_param["cell_area_F_multiplier"]
                                       * (f_mm ** 2))
                    print(
                        f"ReRAM_param 'area_access_transistor_mm2' not found! Using rough estimate: {area_t_estimate:.3e} mm^2. Please define it in hardware YAML for accuracy.")
                    return area_t_estimate
                else:
                    print(
                        "ReRAM_param 'area_access_transistor_mm2' and 'tech_node' not found! Cannot estimate access device area.")
                    return 0.0
            return area_t
        return 0.0  # No separate access device for pure crossbar (area assumed in cell or peripheral)

    def _get_num_access_devices_per_logical_cell(self) -> int:
        """
        Returns the number of access devices (transistors) per logical ReRAM cell
        (a logical cell stores 'self.cells_size' bits using one or more ReRAM devices,
        and for 2T2R, a logical weight cell uses two ReRAM devices, each with a transistor).
        This method counts transistors associated with the ReRAM elements forming one 'weight_precision' unit.

        If one 'weight_precision' unit is stored across (self.weight_precision / self.cells_size) physical ReRAM devices.
        And each physical ReRAM device has 'N' transistors.
        """
        num_physical_reram_devices_per_weight = math.ceil(self.weight_precision / self.cells_size)

        if self.nvm_array_type == NVM_ARRAY_TYPE_1T1R or self.nvm_array_type == NVM_ARRAY_TYPE_PSEUDO_CROSSBAR:
            return 1 * num_physical_reram_devices_per_weight  # 1 Transistor per physical ReRAM device
        if self.nvm_array_type == NVM_ARRAY_TYPE_2T2R:
            # A 2T2R logical cell for one weight uses two 1T1R-like structures.
            # So, 2 transistors for the pair of ReRAM devices that form one effective signed weight.
            # If multi-bit weight_precision is achieved by multiple 2T2R cells, then multiply.
            return 2 * num_physical_reram_devices_per_weight  # 2 Transistors per pair of ReRAM devices making a logical unit
        return 0  # Crossbar

    def calculate_driver_info(
            self,
            # Capacitance parameters (Estimates for 28nm)
            C_gate_per_TX_fF: float = 4.0, #was 0.12 # Gate capacitance of one access TX (fF)
            C_junction_per_TX_fF: float = 0.91, #was 0.06 # Junction cap of one access TX to BL/SL (fF)
            Cw_per_unit_length_fF_um: float = 0.2,  # Wire capacitance (fF/µm)

            # Cell pitch assumptions (can be derived from cell_area_F2 if needed)
            # cell_pitch_width_F_multiplier: float = math.sqrt(300), #was 3.16 = sqrt(10)
            # Effective cell width as multiplier of F
            # cell_pitch_height_F_multiplier: float = math.sqrt(300),  # Effective cell height as multiplier of F

            # Buffer/Driver and minimum inverter parameters
            A_inv_min_F2: float = 10.0,  # Area of minimum sized inverter in F^2 (e.g., ~6-10 F^2 for logic)
            C_in_inv_min_fF: float = 0.2,  # Input capacitance of minimum inverter (fF)
    ) -> dict:
        """
        Calculates estimated areas for Word Line (WL) and Bit Line/Source Line (BL/SL) drivers
        in a ReRAM array.

        Returns:
            A dictionary containing:
                'F_um': Feature size in µm,
                'C_WL_fF': Total load capacitance of one Word Line (fF),
                'C_BLSL_fF': Total load capacitance of one Bit/Source Line (fF),
                'Area_one_WL_driver_um2': Area of a single WL driver (µm^2),
                'Area_total_WL_drivers_um2': Total area of all WL drivers (µm^2),
                'Area_one_BLSL_driver_um2': Area of a single BL/SL driver/interface circuit (µm^2),
                'Area_total_BLSL_drivers_um2': Total area of all BL/SL drivers (µm^2).
        """
        num_rows = self.wordline_dim_size
        num_cols = self.bitline_dim_size
        F_um = self.ReRAM_param["tech_node"]  # Feature size in µm
        number_transistors_per_cell = (2 if self.nvm_array_type == NVM_ARRAY_TYPE_2T2R else 1) #2 for 2T2R, 1 for pseudo crossbar and 1T1

        cell_pitch_width_F_multiplier = math.sqrt(self.ReRAM_param["cell_area_F_multiplier"])
        cell_pitch_height_F_multiplier = math.sqrt(self.ReRAM_param["cell_area_F_multiplier"])
        # Calculate cell pitches in µm
        pitch_cell_width_um = cell_pitch_width_F_multiplier * F_um
        pitch_cell_height_um = cell_pitch_height_F_multiplier * F_um

        # 1. Word Line Load Capacitance (C_WL) for one WL
        length_WL_um = num_cols * pitch_cell_width_um
        C_wire_WL_fF = Cw_per_unit_length_fF_um * length_WL_um
        C_transistors_on_WL_fF = number_transistors_per_cell * num_cols * C_gate_per_TX_fF
        C_WL_fF = C_transistors_on_WL_fF + C_wire_WL_fF

        # 2. Bit Line / Source Line Load Capacitance (C_BLSL) for one BL/SL
        length_BLSL_um = num_rows * pitch_cell_height_um
        C_wire_BLSL_fF = Cw_per_unit_length_fF_um * length_BLSL_um
        C_transistors_on_BLSL_fF = num_rows * C_junction_per_TX_fF
        C_BLSL_fF = C_transistors_on_BLSL_fF + C_wire_BLSL_fF

        # 3. Driver Area Calculation
        # Area of minimum inverter in µm^2
        A_inv_min_um2 = A_inv_min_F2 * (F_um ** 2)

        # WL Driver Area
        # Scaling factor S_driver = C_load / C_in_inv_min
        # Ensure scaling factor is at least 1 (driver is at least min size)
        S_WL_driver = max(1.0, C_WL_fF / C_in_inv_min_fF)
        Area_one_WL_driver_um2 = A_inv_min_um2 * S_WL_driver
        Area_total_WL_drivers_um2 = num_rows * Area_one_WL_driver_um2

        # BL/SL Driver Area (assuming similar driver structure for estimation)
        S_BLSL_driver = max(1.0, C_BLSL_fF / C_in_inv_min_fF)
        Area_one_BLSL_driver_um2 = A_inv_min_um2 * S_BLSL_driver
        Area_total_BLSL_drivers_um2 = number_transistors_per_cell * num_cols * Area_one_BLSL_driver_um2

        results = {
            "C_WL_total_fF": C_WL_fF,
            "C_BLSL_total_fF": C_BLSL_fF,
            "S_WL_driver": S_WL_driver,
            "S_BLSL_driver": S_BLSL_driver,
            "Area_one_WL_driver_um2": Area_one_WL_driver_um2,
            "Area_total_WL_drivers_um2": Area_total_WL_drivers_um2,
            "Area_one_BLSL_driver_um2": Area_one_BLSL_driver_um2,
            "Area_total_BLSL_drivers_um2": Area_total_BLSL_drivers_um2
        }
        # print(results)
        return results

    """
        Overriding, because the delays seem quite different for me :((
    """
    def get_adc_cost(self) -> tuple[float, float, float]:
        """single ADC BUT FOR ReRAM"""
        # area (mm^2)
        if self.adc_resolution == 0:
            adc_area: float = 0
        elif self.adc_resolution == 1:
            adc_area: float = 0
        else:  # formula extracted and validated against 3 AIMC papers on 28nm
            k1 = -0.0369
            k2 = 1.206 #+ 0.6096 # was trying for 40 nm x
            adc_area = 10 ** (k1 * self.adc_resolution + k2) * 2**self.adc_resolution * (10**-6)  # unit: mm^2

        # delay (ns)
        if self.adc_resolution == 0:
            adc_delay: float = 0
        else:
            #FROM SRAM IMC MODEL
            # k3 = 0.00653  # ns
            # k4 = 0.640  # ns
            # adc_delay = self.adc_resolution * (k3 * self.bitline_dim_size + k4)  # unit: ns

            #FROM RERAM PAPER YAO
            fast_internal_clk_Mhz = 650 # example from the paper JOS
            # fast_internal_clk_Mhz = 200

            clk_period_ns = 1.0/(fast_internal_clk_Mhz * 10**(-3))
            adc_setup_cycles = 3
            adc_cycles_per_bit_avg_first_chunk = 1
            first_chunk_max_bits = 4
            adc_cycles_per_bit_avg_second_chunk = 2

            total_adc_cycles_first_chunk = (adc_setup_cycles +
                    ((first_chunk_max_bits if self.adc_resolution >= first_chunk_max_bits else self.adc_resolution)
                     * adc_cycles_per_bit_avg_first_chunk)
                    )

            total_adc_cycles_second_chunk = (
                    (0 if self.adc_resolution <= first_chunk_max_bits else self.adc_resolution - first_chunk_max_bits)
                     * adc_cycles_per_bit_avg_second_chunk
                     )

            total_adc_cycles = total_adc_cycles_first_chunk + total_adc_cycles_second_chunk
            adc_latency_ns = total_adc_cycles * clk_period_ns
            adc_delay = adc_latency_ns

        # energy (fJ)
        if self.adc_resolution == 0:
            adc_energy: float = 0
        else:
            k5 = 100  # fF
            k6 = 0.001  # fF
            # unit: fJ
            adc_energy = (k5 * self.adc_resolution + k6 * 4**self.adc_resolution) * self.tech_param["vdd"] ** 2
            adc_energy = adc_energy / 1000  # unit: pJ
        return adc_area, adc_delay, adc_energy


    def get_area(self):
        """
       Calculates the total area of the NVM IMC array, breaking it down into components.
       Overrides the base ImcArray.get_area().
       """
        # print(f"Calculating area for NVM IMC array with type: {self.nvm_array_type}")

        # First running from superclass, so from imc_array.py
        super().get_area()

        # 1. Area of the ReRAM cells themselves (the ReRAM material/stack)
        # self.cells_area (from YAML) is the area of ONE physical ReRAM device.
        # self.cells_size is bits stored per ONE physical ReRAM device.
        # self.weight_precision is the total bits for a synaptic weight.
        # Number of physical ReRAM devices needed per synaptic weight:
        num_physical_reram_devices_per_synaptic_weight = math.ceil(self.weight_precision / self.cells_size)
        # Total number of synaptic weight locations in the array:
        num_synaptic_weights_locations = self.wordline_dim_size * self.bitline_dim_size * self.nb_of_banks
        # Total number of physical ReRAM CELLS:
        total_physical_reram_devices = num_synaptic_weights_locations * num_physical_reram_devices_per_synaptic_weight

        if self.nvm_array_type == NVM_ARRAY_TYPE_2T2R:
            total_physical_reram_devices = total_physical_reram_devices * 2 # I do this to make sure cells_size takes into account the two cells of the 2T2R together (so 2 ReRAMs needed)

        area_reram_devices_stack = total_physical_reram_devices * self.cells_area  # self.cells_area from YAML
        self.area_breakdown["cells"] = area_reram_devices_stack # GIVES THE ACTUAL ReRAM MATERIAL!!!


        ######### JOS 0.2548 mm^2 total
        ######### JOS 0.000000864 mm^2 = 0.864 um^2 is the array per 2T2R ccell -> instead of multiplier of 10 -> 550
        # 2. Area of Access Devices (Transistors) (Mults)
        area_single_access_device = self._get_area_access_device()
        # The number of access devices depends on the total physical ReRAM devices and nvm_array_type
        num_transistors_per_physical_reram_device = 0
        if self.nvm_array_type == NVM_ARRAY_TYPE_1T1R or self.nvm_array_type == NVM_ARRAY_TYPE_PSEUDO_CROSSBAR:
            num_transistors_per_physical_reram_device = 1
        elif self.nvm_array_type == NVM_ARRAY_TYPE_2T2R:
            num_transistors_per_physical_reram_device = 1  # Each of the two ReRAMs in a 2T2R unit has one T.
            # So effectively, 2 transistors per logical 2T2R weight cell if that cell maps to one weight_precision unit directly.
            # If weight_precision requires multiple such 2T2R cells, then it scales.
            # The `total_physical_reram_devices` already accounts for how many R devices are there.
            # So, just multiply by 1 if it's one T per R.

        total_access_devices = total_physical_reram_devices * num_transistors_per_physical_reram_device
        area_access_devices = total_access_devices * area_single_access_device
        self.area_breakdown["mults"] = area_access_devices

        # 3. Area of DACs (Digital-to-Analog Converters) for inputs
        area_dacs = 0
        if self.is_aimc:  # Analog IMC needs DACs for inputs
            # Assuming DACs are applied to wordlines for inputs.
            # Number of DACs = number of wordlines that can take distinct analog inputs.
            num_dacs = self.wordline_dim_size * self.nb_of_banks
            # get_dac_cost()[0] from base class. Ensure this model is suitable.
            # The Light-CIM paper aims for ADC/DAC-fewer tiles, DACs might only be at tile interface[cite: 7, 56].
            # However, for a general AIMC macro, inputs are often from DACs.
            area_one_dac = self.get_dac_cost()[0]  # Area of a single DAC unit
            area_dacs = num_dacs * area_one_dac
        self.area_breakdown["dacs"] = area_dacs


        ######### JOS 0.882 mm^2 total ADCs
        ######### JOS 0.01378125 mm^2 per adc -> 0.882 mm^2 for all ADCs
        # 4. Area of ADCs (Analog-to-Digital Converters) for outputs
        area_adcs = 0
        if self.is_aimc:  # Analog IMC needs ADCs for outputs
            # Number of physical ADCs considering sharing
            # ADCs are typically along the bitline dimension.
            amount_of_adc_bitlines = math.ceil(self.bitline_dim_size / (self.weight_precision/self.cells_size))
            if self.nvm_array_type == NVM_ARRAY_TYPE_PSEUDO_CROSSBAR: # ADCs in other direction
                amount_of_adc_bitlines = math.ceil(self.wordline_dim_size / (self.weight_precision / self.cells_size))
            if self.adc_share_factor > 0:
                num_adcs = math.ceil( amount_of_adc_bitlines / self.adc_share_factor) * self.nb_of_banks
            else:  # Should not happen if adc_share_factor is validated
                num_adcs =  amount_of_adc_bitlines * self.nb_of_banks

            area_one_adc = self.get_adc_cost()[0]  # Area of a single ADC unit from base class
            # print("num_adcs", num_adcs)
            area_adcs = num_adcs * area_one_adc
            # The Light-CIM paper states ADCs are only 2.5% of total power, implying their area might also be managed[cite: 8].
            # Fig 7b in Light-CIM shows ADC area for their "Light-CIM" vs "ISAAC". It's small for Light-CIM.
            # Liu et al. (JOS 2025) Fig 9b: DSDC ADCs are 45% of area. This is significant.
            # Yao et al. (ESSERC 2024) Fig 9a: "ADC&DAC&I/O" is a large portion.
            # This shows ADC area contribution can vary wildly based on design and sharing.
        self.area_breakdown["adcs"] = area_adcs

        # 5. Area of Digital Adders and Accumulators (if any, from base class)
        # These are calculated by super().get_area() if it was called and ImcArray has them.
        # For a clean NVM override, we might want to call specific sub-functions from ImcArray
        # or recalculate them here if their assumptions change for NVM.
        # For now, assume super().get_area() populated these if it was called, or initialize.
        self.area_breakdown["adders_regular"] = self.area_breakdown.get("adders_regular", 0.0)
        self.area_breakdown["adders_pv"] = self.area_breakdown.get("adders_pv", 0.0)  # Place-value adders after ADCs
        self.area_breakdown["accumulators"] = self.area_breakdown.get("accumulators", 0.0)


        # 6. Area of Peripheral Drivers (Wordline drivers, Bitline/Sourceline drivers)
        #trying with seperate function now

        driver_areas_dict = self.calculate_driver_info()
        # print("driver_areas_dict",driver_areas_dict)

        # These are often substantial for large arrays.
        # Values should come from ReRAM_param.
        # area_wl_drivers = self.wordline_dim_size * self.nb_of_banks * \
        #                   self.ReRAM_param.get("area_wordline_driver_mm2", 1e-5)  # Placeholder value
        # self.area_breakdown["wl_drivers"] = area_wl_drivers
        #
        # area_bl_drivers = self.bitline_dim_size * self.nb_of_banks * \
        #                   self.ReRAM_param.get("area_bitline_driver_mm2", 1e-5)  # Placeholder value
        # self.area_breakdown["bl_drivers"] = area_bl_drivers

        # For 2T2R, Source Line (SL) drivers might also be distinct.
        # if self.nvm_array_type == NVM_ARRAY_TYPE_2T2R:
        #     # possibly sometimes bitline_dim_size
        #     area_sl_drivers = self.wordline_dim_size * self.nb_of_banks * \
        #                       self.ReRAM_param.get("area_sourceline_driver_mm2", 1e-5)  # Placeholder
        #     self.area_breakdown["sl_drivers"] = area_sl_drivers


        self.area_breakdown["wl_drivers"] = driver_areas_dict.get("Area_total_WL_drivers_um2",0)/(10**6)
        self.area_breakdown["bl_drivers"] = driver_areas_dict.get("Area_total_BLSL_drivers_um2",0)/(10**6)

        # print ("area_breakdown",self.area_breakdown)
        self.area = sum(self.area_breakdown.values())
        # print("total_area:", self.area)

    def get_tclk(self):
        # First running from superclass, so from imc_array.py
        super().get_tclk()

        """worst path: adcs -> adders -> accumulators)"""
        # delay of cells
        # might be needed to model for ReRAM
        dly_cells = 0  # cells are not on critical paths

        # ReRAM Array Read Operation Latency
        #    This is the core time current flows and is summed.
        # t_reram_read_pulse_s = self.ReRAM_param.get("t_read_pulse", 5e-9)  # Default 5ns
        # t_reram_read_pulse_ns = t_reram_read_pulse_s * 1e9
        # dly_cells = t_reram_read_pulse_ns # not in the crithical path

        # delay of multipliers
        dly_mults = 0

        # Changing some of the things in the dictionary
        self.tclk_breakdown["cells"] = dly_cells
        self.tclk_breakdown["mults"] = dly_mults
        self.tclk_breakdown["wl_drivers"] = 0
        self.tclk_breakdown["bl_drivers"] = 0
        self.tclk = sum([v for v in self.tclk_breakdown.values()])

        self.ReRAM_param["t_read_pulse"] = self.tclk_breakdown["adcs"] * 1e-9 # reading pulse dependent on how long adcs work!


    def get_peak_energy_single_cycle(self) -> dict[str, float]:
        """
           Calculates macro-level one-cycle peak energy for ReRAM CiM array read operation.
           Assumes full utilization of activated components and no weight updating.
           Energies are returned in picoJoules (pJ).
       """
        peak_energy_breakdown_super = super().get_peak_energy_single_cycle()
        self.peak_energy_breakdown = dict()

        num_rows_actived = (self.wordline_dim_size * self.nb_of_banks)
        num_cols_activated = (self.bitline_dim_size /(self.adc_share_factor * (self.weight_precision / self.cells_size) ))  * self.nb_of_banks # only so many columns actually active
        num_all_active_cells_in_op = num_rows_actived * num_cols_activated

        num_wl_to_drive = (num_rows_actived
                          / (self.adc_share_factor * (self.weight_precision / self.cells_size))
                          # / (self.activation_precision / self.bit_serial_precision)
                          )
        # the division is because the rows activating is shared over all the outputting cycles, so how many FULL ADC cycles are needed for all the outputs for a single part of the wl activated, cause after again the energy needed!

        num_bl_driven = num_cols_activated

        driver_info = self.calculate_driver_info()
        C_wl_avg_F = driver_info["C_WL_total_fF"] * (10**(-15))
        C_bl_avg_F = driver_info["C_BLSL_total_fF"] * (10**(-15))

        # --- 1. ReRAM Array Read Current Energy ---
        # Energy from current flowing through selected ReRAM cells during read pulse
        # N_active_cells = self.num_rows_activated * self.num_cols_read_by_adcs
        # (Assuming current flows in all cells of the sub-array slice defined by active rows and cols read by ADCs)


        # Energy for one cell to be read (in Joules)
        # Calculate average cell current for read if not pre-calculated
        # Assuming G_LRS and G_HRS are conductances in Siemens
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


        e_read_one_cell_J = (self.ReRAM_param["V_read"] * i_cell_avg_read * self.ReRAM_param["t_read_pulse"])

        # Total energy for all active cells (in Joules)
        total_array_cell_current_energy_J = num_all_active_cells_in_op * e_read_one_cell_J
        # THE RERAM ARRAY READ CURRENT
        self.peak_energy_breakdown["cells"] = total_array_cell_current_energy_J * 1e12  # Convert J to pJ
        self.peak_energy_breakdown["mults"] = 0 # seen as NOT using any energy, the energy usage is included in the drivers

        # print("energies etc for array currents", num_all_active_cells_in_op, e_read_one_cell_J, total_array_cell_current_energy_J)




        # --- 2. Line Driver Energy (Dynamic CV^2) ---
        # Assuming alpha = 0.5 for one transition (e.g., 0 -> Vdd or Vdd -> 0)
        # If V_swing already implies full swing for C*Vswing^2, then alpha=1 for energy of a full cycle 0-V-0.
        # For peak energy, typically one significant transition is considered.
        # Let's use 0.5 C V_swing^2 per transition.
        alpha_switching = 1.0
        beta_switching = 1.0

        # WL Driver Energy
        e_wl_drivers_J = (alpha_switching *
                          num_wl_to_drive *
                          C_wl_avg_F *
                          (self.ReRAM_param["V_wl_swing_read"] ** 2))
        self.peak_energy_breakdown["wl_drivers"] = e_wl_drivers_J * 1e12

        # BL Driver Energy (for DACs applying inputs, if not part of DAC energy itself)
        # This assumes DACs output voltages onto bitlines which are then driven.
        # If DACs have their own output stage energy, this might be double counting or need refinement.
        e_bl_drivers_J = (beta_switching *
                           num_bl_driven *
                           C_bl_avg_F *
                           (self.ReRAM_param["V_bl_swing_read"] ** 2))
        self.peak_energy_breakdown["bl_drivers"] = e_bl_drivers_J * 1e12

        # Energy for dynamic swing on summation lines (if precharged/discharged beyond cell current effects)
        # This could be your "analog_bl_addition" if it represents dynamic energy.
        # Often, for current-based summation, this explicit charging might be minimal if lines are held at virtual ground
        # or if the swing is small. If it's large and actively driven, it's:
        # e_sum_lines_dynamic_J = (alpha_switching *
        #                          self.num_bl_summation_lines *
        #                          self.C_sum_line_avg_F *
        #                          (self.reram_params.get("V_bl_sum_swing", 0) ** 2))  # Default swing 0 if not defined
        # self.peak_energy_breakdown["summation_lines_dynamic"] = e_sum_lines_dynamic_J * 1e12



        # --- 3. DAC Energy ---
        self.peak_energy_breakdown["dacs"] = peak_energy_breakdown_super["dacs"]




        # --- 4. ADC Energy ---
        total_adc_energy_pJ = (
                            self.get_adc_cost()[2]
                            * num_cols_activated
        )

        self.peak_energy_breakdown["adcs"] = total_adc_energy_pJ

        # --- 5. Digital Logic Energy (Adders, Accumulators etc.) ---

        self.peak_energy_breakdown["adders_regular"] = peak_energy_breakdown_super["adders_regular"]
        self.peak_energy_breakdown["adders_pv"] = peak_energy_breakdown_super["adders_pv"]
        self.peak_energy_breakdown["accumulators"] = peak_energy_breakdown_super["accumulators"]

        self.peak_energy = sum(self.peak_energy_breakdown.values())

        # print("Peak energy breakdown", self.peak_energy_breakdown)
        # print("total energy peak", self.peak_energy)

        return self.peak_energy_breakdown

    def get_macro_level_peak_performance(self) -> tuple[float, float, float]:
        """! macro-level peak performance of imc arrays (fully utilization, no weight updating)"""
        """
            A cycle is a whole quantization of the outputs.
        """
        nb_of_macs_per_cycle = (
            self.wordline_dim_size
            * self.bitline_dim_size
            / (self.activation_precision / self.bit_serial_precision) # this is the input precision and how much on a WL at once
            / (self.weight_precision / self.cells_size) # how many cells need to be put together to actually do the input output precision
            * self.nb_of_banks
            / self.adc_share_factor
        )

        nb_of_bit_operations_per_cycle = (
            nb_of_macs_per_cycle
            * 2
            * self.weight_precision
            * self.activation_precision
            )

        # IN NANOSECONDS, VERY VERY IMPORTANT
        clock_cycle_period = self.tclk  # unit: ns
        # print("tclk info", self.tclk_breakdown)
        # print("tclk", self.tclk)

        # clock_cycle_period_paper2 = 1/ 0.01886792 #0.02 Hz, so 53 seconds????
        # clock_cycle_period_paper3 = 10**(3) / 650 #650 MHz, with quantization 43.3 Mhz (factor 15 from ADC quantization)
        # clock_cycle_period_paper4 = 10**(3) / 200 #200 MHz -> 5 ns (MY CALCULATION GIVES 8.26)
        # clock_cycle_period = clock_cycle_period_paper3 * 15
        # clock_cycle_period = clock_cycle_period_paper4
        # print("Clock cycle period", clock_cycle_period)

        #pJ (10**-12 J) VERY IMPORTANT
        peak_energy_per_cycle = sum([v for v in self.get_peak_energy_single_cycle().values()])  # unit: pJ
        # print("peak energy per cycle", peak_energy_per_cycle)
        # print("energy single cycle", self.get_peak_energy_single_cycle())
        # peak_energy_per_cycle = 26681.323/4/4 #1667.5526
        # print("what I need", peak_energy_per_cycle)

        imc_area = self.area  # unit: mm^2
        # print("IMC AREA", imc_area)

        # Times 2 is for the operations (a MAC is 2 operations)

        # print("NEEDED", nb_of_macs_per_cycle * 2)
        tops_peak = nb_of_macs_per_cycle * 2 / clock_cycle_period / 1000
        tops_peak_bits = nb_of_bit_operations_per_cycle / clock_cycle_period / 1000

        topsw_peak = nb_of_macs_per_cycle * 2 / peak_energy_per_cycle
        print(nb_of_macs_per_cycle)
        topsw_peak_bits = nb_of_bit_operations_per_cycle / peak_energy_per_cycle

        topsmm2_peak = tops_peak / imc_area
        topsmm2_peak_bits = tops_peak_bits / imc_area

        self.tops_peak_bits = tops_peak_bits
        self.topsw_peak_bits = topsw_peak_bits
        self.topsmm2_peak_bits = topsmm2_peak_bits

        logger = logging.getLogger(__name__)
        imc_type_info = f"Current macro-level peak performance ({'analog' if self.is_aimc else 'digital'} {self.nvm_array_type} NVM IMC):"
        peak_performance_info = f"TOP/s: {tops_peak}, TOP/s/W: {topsw_peak}, TOP/s/mm^2: {topsmm2_peak}"
        peak_performance_bits_info = f"TOP/s/bit: {tops_peak_bits}, TOP/s/W/bit: {topsw_peak_bits}, TOP/s/mm^2/bit: {topsmm2_peak_bits}"

        logger.info(imc_type_info)
        logger.info(peak_performance_info)
        logger.info(peak_performance_bits_info)

        return tops_peak, topsw_peak, topsmm2_peak

    def get_energy_for_a_layer(self, layer: LayerNode, mapping: Mapping) -> dict[str, float]:
        # # First this function from the superclass.
        # energy_breakdown = super().get_energy_for_a_layer(layer, mapping) # should be saved in self.energy_breakdown as well

        """
            self.energy_breakdown = {  # unit: pJ (the unit borrowed from CACTI)
                "local_bl_precharging": energy_local_bl_precharging,
                "dacs": energy_dacs,
                "adcs": energy_adcs,
                "mults": energy_mults,
                "analog_bl_addition": energy_analog_bl_addition,
                "adders_regular": energy_adders_regular,
                "adders_pv": energy_adders_pv,
                "accumulators": energy_accumulators,
            }
        """

        """
            WORKLOAD PARAMETERS
        """
        # parameter extraction
        (
            mapped_rows_total_per_macro,
            _,
            mapped_cols_per_macro,
            macro_activation_times,  # normalized to only one imc macro (bank)
        ) = self.get_mapped_oa_dim(layer, self.wl_dim, self.bl_dim)
        self.mapped_rows_total_per_macro = mapped_rows_total_per_macro

        """
            LOCAL BITLINE PRECHARGING PARAMETERS
        """
        # energy of local bitline precharging during weight stationary in cells
        # This is only being done if the group_depth is bigger than 1
        # If the cells size is the same as the weight precision, this is not a problem
        (
            energy_local_bl_precharging,
            self.mapped_group_depth,
        ) = self.get_precharge_energy(self.tech_param, layer, mapping)
        # Should be (0,1)

        # energy of DACs, same for NVM
        # Activation precision is the INPUT precision
        # Bit serial precision is the amount of input precision that can be put on a Wordline at once
        # The ratio is thus how many cycles are needed for the input precisions
        if self.is_aimc:
            energy_dacs = (
                self.get_dac_cost()[2]
                * mapped_rows_total_per_macro
                * (self.activation_precision / self.bit_serial_precision)
                * macro_activation_times
            )
        else:
            energy_dacs = 0

        # energy of ADCs, same for NVM
        if self.is_aimc:
            energy_adcs = (
                self.get_adc_cost()[2]
                * self.weight_precision # extra bitlines (cause so many per cell) -> weight precision can be seen as cells next to each other with seperate bitlines
                * mapped_cols_per_macro
                * (self.activation_precision / self.bit_serial_precision)
                * macro_activation_times
            )
        else:
            energy_adcs = 0

        # energy of multiplier array, access transistors
        if self.is_aimc: # AIMC
            if self.is_crossbar:  # CROSSBAR
                nb_of_active_1b_multiplier_per_macro = 0
            else: # 1T1R -> Pseudo Crossbar
                nb_of_active_1b_multiplier_per_macro = (
                        self.weight_precision * self.wordline_dim_size # amount of bitlines
                        * mapped_rows_total_per_macro # with active rows
                        * 0.5 # Because only 1 access transistor, so just reducing the amount of multipliers (SRAM would be around 2)
                )
        else: # DIMC
            nb_of_active_1b_multiplier_per_macro = (
                self.bit_serial_precision # how many per wordline, so need multiple bit mult
                * self.weight_precision * self.wordline_dim_size # amount of columns
                * self.bitline_dim_size # For DIMC all cells seen as actively multiplying
            )

        energy_mults = (
            self.get_1b_multiplier_energy()
            * nb_of_active_1b_multiplier_per_macro
            * (self.activation_precision / self.bit_serial_precision) # cycles for a certain input
            * macro_activation_times # this has the amount of banks in it
        )

        # energy of analog bitline addition, type: voltage-based
        vdd_read = self.tech_param["vdd"]  # For ReRAM arrays
        vdd_write = 1.2  # For ReRAM arrays
        nonlinearity_factor = 0
        if self.is_aimc: # AIMC
            if self.is_crossbar: # CROSSBAR
                energy_analog_bl_addition = (
                        (self.tech_param["bl_cap"] * 0.25
                        * (vdd_read ** 2)
                        * self.weight_precision)
                        * self.wordline_dim_size # * mapped_cols_per_macro # because for crossbar everything is always working, you cannot do it seperately
                        * self.bitline_dim_size # amount of wordlines -> amount of dimension on one bitline/column
                        * (self.activation_precision / self.bit_serial_precision)
                        * macro_activation_times
                )
            else: # 1T1R -> Pseudo-Crossbar
                energy_analog_bl_addition = (
                        (self.tech_param["bl_cap"] * 0.5
                        * (vdd_read ** 2)
                        * self.weight_precision)
                        * mapped_cols_per_macro
                        * self.bitline_dim_size
                        * (self.activation_precision / self.bit_serial_precision)
                        * macro_activation_times
                )
        else: # DIMC 1T1R
            energy_analog_bl_addition = 0

        # energy of regular adder trees without place values (type: RCA)
        if self.is_aimc:
            adder_output_precision_regular = 0
            energy_adders_regular = 0
        else:
            adder_input_precision_regular = self.weight_precision
            nb_inputs_of_adder_regular = self.bitline_dim_size  # the number of inputs of the adder tree
            adder_depth_regular = math.log2(nb_inputs_of_adder_regular)
            adder_depth_regular = int(adder_depth_regular)  # float -> int for simplicity
            adder_output_precision_regular = adder_input_precision_regular + adder_depth_regular

            nb_of_active_adder_trees_per_macro = self.bit_serial_precision * mapped_cols_per_macro
            energy_adders_per_tree_regular = self.get_regular_adder_trees_energy(
                adder_input_precision=adder_input_precision_regular,
                active_inputs_number=mapped_rows_total_per_macro,
                physical_inputs_number=self.bitline_dim_size,
            )
            energy_adders_regular = (
                energy_adders_per_tree_regular
                * nb_of_active_adder_trees_per_macro
                * (self.activation_precision / self.bit_serial_precision)
                * macro_activation_times
            )

        # energy of adder trees with place values (type: RCA)
        if self.is_aimc:
            nb_inputs_of_adder_pv = self.weight_precision
            input_precision_pv = self.adc_resolution
        else:
            nb_inputs_of_adder_pv = self.bit_serial_precision
            input_precision_pv = adder_output_precision_regular

        if nb_inputs_of_adder_pv == 1:
            nb_of_1b_adder_per_tree_pv = 0
        else:
            nb_of_1b_adder_per_tree_pv = input_precision_pv * (nb_inputs_of_adder_pv - 1) + nb_inputs_of_adder_pv * (
                math.log2(nb_inputs_of_adder_pv) - 0.5
            )
        energy_adders_pv = (
            self.get_1b_adder_energy()
            * nb_of_1b_adder_per_tree_pv
            * mapped_cols_per_macro
            * (self.activation_precision / self.bit_serial_precision)
            * macro_activation_times
        )

        # energy of accumulators (adder type: RCA)
        if self.bit_serial_precision == self.activation_precision:
            energy_accumulators = 0
        else:
            if self.is_aimc:
                accumulator_output_precision = (
                    self.activation_precision + self.adc_resolution + self.weight_precision
                )  # output precision from adders_pv + required shifted bits
            else:
                accumulator_output_precision = (
                    self.activation_precision + math.log2(self.bitline_dim_size) + self.weight_precision
                )  # output precision from adders_pv + required shifted bits

            energy_accumulators = (
                (self.get_1b_adder_energy() + self.get_1b_reg_energy())
                * accumulator_output_precision
                * mapped_cols_per_macro
                * (self.activation_precision / self.bit_serial_precision)
                * macro_activation_times
            )

        self.energy_breakdown = {  # unit: pJ (the unit borrowed from CACTI)
            "local_bl_precharging": energy_local_bl_precharging,
            "dacs": energy_dacs,
            "adcs": energy_adcs,
            "mults": energy_mults,
            "analog_bl_addition": energy_analog_bl_addition,
            "adders_regular": energy_adders_regular,
            "adders_pv": energy_adders_pv,
            "accumulators": energy_accumulators,
        }
        self.energy = sum([v for v in self.energy_breakdown.values()])
        return self.energy_breakdown

    def __jsonrepr__(self):
        return json_repr_handler({"operational_unit: ImcNvmArray, dimensions": self.dimension_sizes})
