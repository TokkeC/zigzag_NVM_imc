import math

class ReRAMArrayModel: # Placeholder for your class structure
    def __init__(self):
        # --- Core Architectural Parameters (Example Values - User should define these) ---
        self.is_aimc = True
        self.is_crossbar = False # Example: False for 1T1R or 2T2R
        self.is_1t1r = True # Assumed if not crossbar and not 2T2R
        self.is_2t2r = False # Assumed if not crossbar and not 1T1R

        self.wordline_dim_size = 128  # Number of rows (WLs activated simultaneously in AIMC)
        self.bitline_dim_size = 128   # Number of columns (BLs)
        self.weight_precision = 4     # Logical bits per weight
        self.input_precision = 8      # Bits for input activation (for DACs)
        self.bits_per_reram_cell = 2  # e.g., 1 for SLC, 2 for 2-bit MLC
        self.nb_of_banks = 1          # Number of parallel array banks

        # --- Technology & Operational Parameters (User must define these in self.tech_param) ---
        self.tech_param = {
            "vdd_read": 0.8,  # Voltage for read operations (e.g., V_WL or V_BL precharge) [V]
            "vdd_peripheral": 0.8, # Voltage for digital peripherals like adders [V]
            # Wordline Parameters
            "c_wl_per_um_length": 2e-15, # WL capacitance per um length [F/um]
            "wl_length_per_cell_um": 0.2, # Effective WL length contribution per cell [um]
            "r_wl_per_um_length": 10,    # WL resistance per um length [Ohm/um] - for delay, not directly energy here
            "t_read_cycle": 10e-9,       # Read cycle time [s]

            # Cell & Access Device Parameters (Crucial and highly technology-dependent)
            # For 1T1R / 2T2R
            "access_tx_gate_cap_per_cell": 0.1e-15, # Gate capacitance of access transistor per cell [F]
            # For all ReRAM types
            "avg_read_current_per_physical_cell": 5e-6, # Avg current through one active ReRAM element [A]
                                                       # This is a major simplification. Real current depends on V across cell and R_state.
            "voltage_drop_across_physical_cell_read": 0.3, # Avg voltage drop across the ReRAM element itself during read [V]

            # Bitline Parameters
            "c_bl_per_um_length": 1.5e-15, # BL capacitance per um length [F/um]
            "bl_length_per_cell_um": 0.5, # Effective BL length contribution per cell [um]
            "v_bl_swing_for_adc": 0.2,   # Effective voltage swing on BL that ADC needs to resolve [V]
                                         # Or, if current-sensing, this might be different.

            # DAC/ADC parameters (Can be outputs from self.get_adc_cost, self.get_dac_cost)
            "energy_per_adc_conversion": 0.1e-12, # Energy for one full ADC conversion [pJ] (example)
                                                 # This should come from a detailed ADC model like get_adc_cost()[2]
            "num_adcs_per_bitline": 1, # Typically 1. If ADCs are shared spatially (e.g., 1 ADC per 2 BLs -> 0.5)
            "energy_per_dac_conversion_bit": 0.01e-12, # Energy per bit for DAC conversion [pJ/bit] (example)

            # Digital peripheral costs (if not from superclass)
            "energy_1b_adder": 0.002e-12, # Energy for a 1-bit adder operation [pJ]
            "energy_1b_accumulator_reg": 0.001e-12, # Energy for 1-bit register in accumulator [pJ]
        }
        # --- Parameters for inherited digital components (if any) ---
        self.bit_serial_precision = 1 # Example, if used by superclass digital parts

    def get_adc_cost(self): # User's existing method, assumed to return (area, delay, energy_per_conversion)
        # This is a placeholder for the user's actual ADC model
        # Example: returns (Area, Delay_ns, Energy_pJ)
        # The energy should be for one full conversion by one ADC.
        adc_resolution = self.input_precision + math.log2(self.wordline_dim_size) # Simplified ADC resolution
        # Based on supervisor's paper (Eq 3 for energy, but simplified here)
        # E_ADC = (k1 * ADC_res + k2 * 4^ADC_res) * VDD^2
        # For this example, we'll use the fixed tech_param value
        return (100e-12, 5e-9, self.tech_param["energy_per_adc_conversion"])

    def get_dac_cost(self): # User's existing method for DACs
        # This is a placeholder for the user's actual DAC model
        # Example: returns (Area, Delay_ns, Energy_pJ_per_conversion)
        energy_total_dac = self.input_precision * self.tech_param["energy_per_dac_conversion_bit"]
        return (10e-12, 1e-9, energy_total_dac)

    # --- Dummy methods for components that might be in a superclass ---
    def get_peak_energy_digital_peripherals(self):
        """ Calculates energy for digital adders, accumulators etc.
            This would call methods similar to those in the supervisor's SRAM model
            if these components exist after the ReRAM analog part.
        """
        # Placeholder: In a real scenario, this would use detailed models
        # for adders, accumulators as in the supervisor's paper (Table I).
        # For this example, let's assume they are negligible or handled by 'super()'.
        return {
            "adders_regular": 0.0,
            "adders_pv": 0.0,
            "accumulators": 0.0,
        }

    def get_peak_energy_single_cycle_reram(self) -> dict[str, float]:
        """
        Calculates macro-level one-cycle peak energy for ReRAM AIMC arrays.
        Assumes full utilization and no weight updating.
        Energy unit: pJ
        """
        peak_energy_breakdown = {
            "wl_activation": 0.0,
            "cell_read_current_dissipation": 0.0,
            "bl_charging_summation": 0.0,
            "dacs": 0.0,
            "adcs": 0.0,
            "adders_regular": 0.0, # From digital peripherals
            "adders_pv": 0.0,      # From digital peripherals
            "accumulators": 0.0,   # From digital peripherals
            "local_bl_precharging": 0.0, # Typically for SRAM, can be 0 for ReRAM AIMC read
        }

        # --- Number of physical ReRAM cells involved ---
        # This accounts for MLC where one ReRAM cell stores multiple logical bits.
        # For peak energy, assume all logical weight bits contribute to cell activity.
        # If one weight is represented by multiple cells (e.g. for precision or differential)
        # this calculation needs to be adjusted.
        # Here, we assume one 'column' of ReRAM cells per logical weight bit if bits_per_reram_cell=1,
        # or fewer physical cells if bits_per_reram_cell > 1.
        # This interpretation might need refinement based on how weights are mapped.
        # For simplicity, let's assume weight_precision maps to activating circuitry
        # that drives `bitline_dim_size` columns, each column representing part of many weights.
        # The number of physical cells in a column that are part of one weight element is
        # num_phys_cells_per_weight_col = math.ceil(self.weight_precision / self.bits_per_reram_cell)
        # However, for array-level energy, we consider total active cells.

        num_active_rows = self.wordline_dim_size
        num_active_cols = self.bitline_dim_size # These are the bitlines where ADCs are.

        # --- DAC Energy ---
        # One DAC per active row (wordline)
        _, _, energy_per_dac_conversion = self.get_dac_cost()
        peak_energy_breakdown["dacs"] = num_active_rows * energy_per_dac_conversion

        if self.is_aimc:
            # --- 1. Wordline (WL) Activation Energy ---
            # Capacitance of one WL = N_cols * (capacitance contribution per cell on that WL)
            # For 1T1R/2T2R: capacitance contribution is gate capacitance of access Tx.
            # For Crossbar: it's coupling capacitance.
            cap_wl_per_row = 0.0
            if self.is_crossbar:
                # Simplified: WL length proportional to num_active_cols * pitch
                wl_total_length_um = num_active_cols * self.tech_param["wl_length_per_cell_um"]
                cap_wl_per_row = wl_total_length_um * self.tech_param["c_wl_per_um_length"]
            elif self.is_1t1r or self.is_2t2r: # 1T1R or 2T2R
                # Assuming WL drives gates of access transistors
                num_transistors_per_wl_cell = 1 if self.is_1t1r else 2
                cap_wl_per_row = num_active_cols * num_transistors_per_wl_cell * self.tech_param["access_tx_gate_cap_per_cell"]

            # Energy = N_rows_active * 0.5 * C_wl_total_per_row * V_wl^2
            # V_wl is typically VDD_read or a specific read voltage for WLs
            energy_wl_activation_total = num_active_rows * 0.5 * cap_wl_per_row * (self.tech_param["vdd_read"] ** 2)
            peak_energy_breakdown["wl_activation"] = energy_wl_activation_total

            # --- 2. Cell Read Current Dissipation Energy ---
            # Energy dissipated within the ReRAM elements themselves (and series access devices if any)
            # E = N_active_physical_cells * V_drop_across_cell * I_read_per_cell * t_cycle
            # Number of *physical* cells active:
            # Each of the `num_active_cols` might have multiple physical cells if a single
            # output bitline value is formed from multiple physical ReRAM cells (e.g. for MLC decoding)
            # For simplicity, assume each of the `num_active_cols` corresponds to one stream of output
            # that involved `num_active_rows` physical cells contributing to its current.
            num_total_active_physical_cells = num_active_rows * num_active_cols

            energy_dissipated_in_cells = (
                num_total_active_physical_cells
                * self.tech_param["voltage_drop_across_physical_cell_read"]
                * self.tech_param["avg_read_current_per_physical_cell"]
                * self.tech_param["t_read_cycle"]
            )
            peak_energy_breakdown["cell_read_current_dissipation"] = energy_dissipated_in_cells

            # --- 3. Bitline (BL) Charging/Summation Energy ---
            # Energy to drive the bitline capacitance due to summed currents.
            # This depends on the BL voltage swing required by the ADCs.
            # Capacitance of one BL = N_rows * (capacitance contribution per cell on that BL)
            bl_total_length_um = num_active_rows * self.tech_param["bl_length_per_cell_um"]
            cap_bl_per_col = bl_total_length_um * self.tech_param["c_bl_per_um_length"]

            # Energy = N_cols_active * 0.5 * C_bl_total_per_col * V_bl_swing^2
            # V_bl_swing is the effective voltage swing on the bitline.
            energy_bl_charging_total = num_active_cols * 0.5 * cap_bl_per_col * (self.tech_param["v_bl_swing_for_adc"] ** 2)
            peak_energy_breakdown["bl_charging_summation"] = energy_bl_charging_total

            # --- 4. ADC Energy ---
            # One ADC per effective bitline output.
            num_adcs = num_active_cols * self.tech_param["num_adcs_per_bitline"]
            _, _, energy_per_adc_conv = self.get_adc_cost() # This should be energy for one full conversion
            peak_energy_breakdown["adcs"] = num_adcs * energy_per_adc_conv

        else: # DIMC (Digital In-Memory Computing with ReRAM)
            # For DIMC, the model would be different.
            # It involves reading ReRAM cells like a memory, then digital MAC.
            # 'mults' would be energy of digital multipliers.
            # 'analog_bl_addition' would be 0. ADCs would be 0.
            # This part needs a separate detailed model if DIMC ReRAM is a focus.
            # For now, let's assume the superclass or other methods handle DIMC.
            # If your `super().get_peak_energy_single_cycle()` handles DIMC correctly,
            # you might only need to override/add ReRAM specific parts for AIMC.
            # The user's original code had a DIMC path for 'mults':
            # nb_of_1b_multiplier = (
            #     self.bit_serial_precision
            #     * self.weight_precision
            #     * self.wordline_dim_size
            #     * self.bitline_dim_size
            #     * self.nb_of_banks
            # )
            # energy_mults = self.get_1b_multiplier_energy() * nb_of_1b_multiplier
            # peak_energy_breakdown["mults"] = energy_mults # Renaming 'mults' for clarity
            # This implies `get_1b_multiplier_energy()` is for digital multipliers.
            # Let's assume this is handled by a different logic path or superclass for DIMC.
            pass


        # --- Digital Peripherals (Adders, Accumulators) ---
        # These might be used after ADCs in AIMC, or as main compute in DIMC.
        # Assuming these are mainly for post-ADC accumulation in AIMC.
        digital_peripheral_energy = self.get_peak_energy_digital_peripherals()
        peak_energy_breakdown["adders_regular"] = digital_peripheral_energy["adders_regular"]
        peak_energy_breakdown["adders_pv"] = digital_peripheral_energy["adders_pv"]
        peak_energy_breakdown["accumulators"] = digital_peripheral_energy["accumulators"]

        # Multiply all components by the number of banks for total energy
        for key in peak_energy_breakdown:
            peak_energy_breakdown[key] *= self.nb_of_banks

        # print("ReRAM Peak energy breakdown (pJ):")
        # for key, value in peak_energy_breakdown.items():
        #     print(f"  {key}: {value:.6e}")
        # print(f"  Total: {sum(peak_energy_breakdown.values()):.6e}")

        return peak_energy_breakdown

    def get_peak_energy_single_cycle(self) -> dict[str, float]:
        # This method now decides whether to call the ReRAM specific model
        # or a potential superclass model (e.g., for SRAM or generic digital parts)
        # For this example, we directly call the ReRAM model.
        # If you have a superclass:
        # peak_energy_breakdown_superclass = super().get_peak_energy_single_cycle()
        # And then modify/add ReRAM specific parts.

        # For this standalone example, we directly use the ReRAM calculation:
        if self.is_aimc: # Or other conditions to identify it as ReRAM
            reram_energies = self.get_peak_energy_single_cycle_reram()
            # The user's original code structure:
            # It seems the intention was to get a base dict from super()
            # and then overwrite/add ReRAM specific values.
            # Let's simulate that structure if the user wants to merge.
            # For now, reram_energies contains all relevant AIMC ReRAM parts.

            # If merging with a superclass's output that has different keys:
            # final_breakdown = super().get_peak_energy_single_cycle() # Get base
            # final_breakdown["mults"] = reram_energies["wl_activation"] + reram_energies["cell_read_current_dissipation"]
            # final_breakdown["analog_bl_addition"] = reram_energies["bl_charging_summation"]
            # final_breakdown["adcs"] = reram_energies["adcs"]
            # final_breakdown["dacs"] = reram_energies["dacs"]
            # # Keep other relevant parts from superclass if any
            # return final_breakdown
            return reram_energies # Returning the detailed ReRAM breakdown directly
        else:
            # Placeholder for DIMC ReRAM or if falling back to a superclass for non-ReRAM
            # return super().get_peak_energy_single_cycle()
            # For this example, return an empty dict or raise error for non-AIMC
            print("Warning: Called get_peak_energy_single_cycle for non-AIMC ReRAM without a DIMC model here.")
            return {key: 0.0 for key in [
                "wl_activation", "cell_read_current_dissipation", "bl_charging_summation",
                "dacs", "adcs", "adders_regular", "adders_pv", "accumulators", "local_bl_precharging"
            ]}


# --- Example Usage (Illustrative) ---
if __name__ == '__main__':
    reram_model = ReRAMArrayModel()

    # --- User needs to customize parameters in reram_model.tech_param and reram_model attributes ---
    # Example: Overriding some tech_param for a specific scenario
    reram_model.tech_param["vdd_read"] = 0.7
    reram_model.tech_param["avg_read_current_per_physical_cell"] = 4e-6 # 4uA
    reram_model.tech_param["energy_per_adc_conversion"] = 0.08e-12 # 0.08 pJ per ADC
    reram_model.tech_param["energy_per_dac_conversion_bit"] = 0.008e-12 # 0.008 pJ per DAC bit

    reram_model.wordline_dim_size = 256
    reram_model.bitline_dim_size = 256
    reram_model.is_crossbar = False
    reram_model.is_1t1r = True
    reram_model.is_2t2r = False


    print(f"Simulating for {'Crossbar' if reram_model.is_crossbar else ('1T1R' if reram_model.is_1t1r else '2T2R')} AIMC ReRAM Array")
    peak_energy = reram_model.get_peak_energy_single_cycle()

    print("\nCalculated Peak Energy Breakdown (pJ):")
    if peak_energy:
        total_energy = 0
        for component, energy in peak_energy.items():
            print(f"  {component}: {energy:.6e}")
            total_energy += energy
        print(f"  ------------------------------------")
        print(f"  Total Peak Energy: {total_energy:.6e} pJ")

    # --- Example for a different configuration ---
    reram_model_crossbar = ReRAMArrayModel()
    reram_model_crossbar.is_crossbar = True
    reram_model_crossbar.is_1t1r = False
    reram_model_crossbar.tech_param["vdd_read"] = 0.6
    reram_model_crossbar.tech_param["avg_read_current_per_physical_cell"] = 10e-6 # Higher for crossbar due to sneak paths (effective)
    reram_model_crossbar.tech_param["voltage_drop_across_physical_cell_read"] = 0.2 # Lower effective V_drop

    print(f"\nSimulating for {'Crossbar' if reram_model_crossbar.is_crossbar else ('1T1R' if reram_model_crossbar.is_1t1r else '2T2R')} AIMC ReRAM Array")
    peak_energy_cb = reram_model_crossbar.get_peak_energy_single_cycle()
    print("\nCalculated Peak Energy Breakdown (Crossbar) (pJ):")
    if peak_energy_cb:
        total_energy_cb = 0
        for component, energy in peak_energy_cb.items():
            print(f"  {component}: {energy:.6e}")
            total_energy_cb += energy
        print(f"  ------------------------------------")
        print(f"  Total Peak Energy (Crossbar): {total_energy_cb:.6e} pJ")

