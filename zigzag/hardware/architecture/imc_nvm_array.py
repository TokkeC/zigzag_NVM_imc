import logging
import math

from zigzag.datatypes import OADimension
# from zigzag.hardware.architecture.imc_unit import ImcUnit
from zigzag.hardware.architecture.imc_array import ImcArray
from zigzag.mapping.mapping import Mapping
from zigzag.utils import json_repr_handler
from zigzag.workload.layer_node import LayerNode


class ImcNvmArray(ImcArray):
    """
     Class for an NVM-CiM Array. The cells are NVM (ReRAM).
    constraint:
        -- activation precision must be in the power of 2.
        -- bit_serial_precision must be in the power of 2.
    """

    def __init__(
        self,
        is_analog_imc: bool,
        is_crossbar: bool,
        bit_serial_precision: int,
        input_precision: list[int],
        adc_resolution: int,
        cells_size: int,
        cells_area: float | None,
        dimension_sizes: dict[OADimension, int],
        auto_cost_extraction: bool = False,
    ):
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
        self.is_crossbar = is_crossbar
        self.get_area()
        self.get_tclk()
        (
            self.tops_peak,
            self.topsw_peak,
            self.topsmm2_peak,
        ) = self.get_macro_level_peak_performance()

    """
    ADC/DAC COST CAN STAY THE SAME FOR RERAM -> JUST USING NORMAL ADCs
    """

    def get_area(self):
        # First running from superclass, so from imc_array.py
        super().get_area()
        """
            This is now made, but for SRAM -> mults is different
            self.area_breakdown = {
                "cells": area_cells,
                "dacs": area_dacs,
                "adcs": area_adcs,
                "mults": area_mults,
                "adders_regular": area_adders_regular,
                "adders_pv": area_adders_pv,
                "accumulators": area_accumulators,
            }
        """

        """
            IMPORTANT
            The cell area need to be changed in the yaml file (hardware declaration).
            For the rest, area calculation of the cells should be fine.
            CELLS AREA IS FOR THE CELL * SIZE -> FULL CELL (full weight)
        """

        """
            NVM and non NVM the same
            self.bitline_dim_size is the size of the dimension which is chosen as the inputs (wordlines, how many per bitline)
            
        """

        """
          The multipliers for AIMC are the transistors to access the cells.  
          For 1T1R, the ReRAM cell is usually put physically ON TOP of the Transistor (so no extra area).
        """
        # area of multiplier array -> Extra transistors for access into cells!
        if self.is_aimc:
            if self.is_crossbar: # CROSSBAR
                nb_of_1b_multiplier = 0
            else: # 1T1R/ Pseudo-Crossbar
                nb_of_1b_multiplier = (
                    self.weight_precision
                    * self.wordline_dim_size
                    * self.bitline_dim_size
                    * self.nb_of_banks
                )
        else: # DIMC -> 1T1R (no crossbar possible)
            nb_of_1b_multiplier = (
                self.bit_serial_precision # Having to check this
                * self.weight_precision # How many bits are actually saved in each cell
                * self.wordline_dim_size
                * self.bitline_dim_size
                * self.nb_of_banks
            )
        area_mults = (self.get_1b_multiplier_area()  # AND gate
                      * nb_of_1b_multiplier)

        # total logic area of imc macros (exclude cells)
        # The other parts of the dictionary are calculated in the super class.
        self.area_breakdown["mults"] = area_mults

        self.area = sum([v for v in self.area_breakdown.values()])
        # Just adding up the whole breakdown to 1 number

    def get_tclk(self):
        # First running from superclass, so from imc_array.py
        super().get_tclk()
        """
            This is now made, but for SRAM CIM
            self.tclk_breakdown = {
                "cells": dly_cells,
                "dacs": dly_dacs,
                "adcs": dly_adcs,
                "mults": dly_mults,
                "adders_regular": dly_adders_regular,
                "adders_pv": dly_adders_pv,
                "accumulators": dly_accumulators,
            }
        """

        """worst path: dacs -> mults -> adcs -> adders -> accumulators)"""
        # delay of cells
        # might be needed to model for ReRAM
        dly_cells = 0  # cells are not on critical paths

        # delay of multipliers
        dly_mults = self.get_1b_multiplier_dly() * 3

        # Changing some of the things in the dictionary
        self.tclk_breakdown["cells"] = dly_cells
        self.tclk_breakdown["mults"] = dly_mults

        self.tclk = sum([v for v in self.tclk_breakdown.values()])
        # Just summed up the breakdown

    def get_peak_energy_single_cycle(self) -> dict[str, float]:
        """! macro-level one-cycle energy of imc arrays (fully utilization, no weight updating)
        (components: cells, mults, adders, adders_pv, accumulators. Not include input/output regs)
        """

        # First running from superclass again -> So from normal CiM Array
        peak_energy_breakdown = super().get_peak_energy_single_cycle()
        """
        peak_energy_breakdown
        = {  # unit: pJ (the unit is borrowed from CACTI)
            "local_bl_precharging": energy_local_bl_precharging, # -> 0 because peak energy
            "dacs": energy_dacs, # -> Same as normal IMC
            "adcs": energy_adcs, # temporary # -> Same as normal IMC
            "mults": energy_mults, # BASICALLY THE CELL ACCESS/Multiplications
            "analog_bl_addition": energy_analog_bl_addition, # The actual bitline addition
            "adders_regular": energy_adders_regular, # Same as normal IMC
            "adders_pv": energy_adders_pv, # Same as normal IMC
            "accumulators": energy_accumulators, # Same as normal IMC
        }
        """

        # energy of multiplier array
        if self.is_aimc: # AIMC
            if self.is_crossbar: # CROSSBAR
                nb_of_1b_multiplier = 0 # No access Transistors -> But not sure whether I can just do this
            else: # 1T1R -> Pseudo Crossbar
                nb_of_1b_multiplier = (
                    self.weight_precision
                    * self.wordline_dim_size
                    * self.bitline_dim_size
                    * self.nb_of_banks
                    * 0.5 # Because only 1 access transistor, so just reducing the amount of multipliers (SRAM would be around 2)
                )
        else: # DIMC 1T1R -> The 'actual' multipliers that are needed again
            nb_of_1b_multiplier = (
                self.bit_serial_precision
                * self.weight_precision
                * self.wordline_dim_size
                * self.bitline_dim_size
                * self.nb_of_banks
            )
        energy_mults = self.get_1b_multiplier_energy() * nb_of_1b_multiplier


        # energy of analog bitline addition, type: voltage-based
        vdd_read = self.tech_param["vdd"] # For ReRAM arrays
        vdd_write = 1.2 # For ReRAM arrays
        nonlinearity_factor = 0
        if self.is_aimc: # AIMC
            if self.is_crossbar: # CROSSBAR
                energy_analog_bl_addition = ((self.tech_param["bl_cap"] * 0.25
                                             * (vdd_read **2)
                                             * self.weight_precision) # amount of bits in a cell (actual cell)
                                             * self.wordline_dim_size
                                             * self.bitline_dim_size
                                             * self.nb_of_banks
                                             )
            else: # 1T1R -> Pseudo-Crossbar
                energy_analog_bl_addition = ((self.tech_param["bl_cap"] * 0.5
                                             * (vdd_read ** 2)
                                             * self.weight_precision
                                             )
                                             * self.wordline_dim_size
                                             * self.bitline_dim_size
                                             * self.nb_of_banks
                                             )
        else: # DIMC 1T1R
            energy_analog_bl_addition = 0

        peak_energy_breakdown["mults"] = energy_mults
        peak_energy_breakdown["analog_bl_addition"] = energy_analog_bl_addition

        return peak_energy_breakdown

    def get_macro_level_peak_performance(self) -> tuple[float, float, float]:
        """! macro-level peak performance of imc arrays (fully utilization, no weight updating)"""
        nb_of_macs_per_cycle = (
            self.wordline_dim_size
            * self.bitline_dim_size
            / (self.activation_precision / self.bit_serial_precision) # this is the output and input precision
            * self.nb_of_banks
        )

        clock_cycle_period = self.tclk  # unit: ns
        peak_energy_per_cycle = sum([v for v in self.get_peak_energy_single_cycle().values()])  # unit: pJ
        imc_area = self.area  # unit: mm^2

        # Times 2 is for the operations (a MAC is 2 operations)
        tops_peak = nb_of_macs_per_cycle * 2 / clock_cycle_period / 1000
        topsw_peak = nb_of_macs_per_cycle * 2 / peak_energy_per_cycle
        topsmm2_peak = tops_peak / imc_area

        logger = logging.getLogger(__name__)
        imc_type_info = f"Current macro-level peak performance ({'analog' if self.is_aimc else 'digital'} {'crossbar' if self.is_crossbar else '1T1R'} NVM IMC):"
        peak_performance_info = f"TOP/s: {tops_peak}, TOP/s/W: {topsw_peak}, TOP/s/mm^2: {topsmm2_peak}"
        logger.info(imc_type_info)
        logger.info(peak_performance_info)

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
