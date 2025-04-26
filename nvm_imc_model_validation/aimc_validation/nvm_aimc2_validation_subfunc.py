"""
    This validation is for TL-nvSRAM-CIM (2023, 28 nm paper)
    The code is based on the initial validation code of the IMC validation in ZigZag.
"""

import pdb # PYTHON DEBUGGER
from nvm_aimc_cost_model import *
from nvm_dimc_cost_model import *
import numpy as np
import matplotlib.pyplot as plt

def nvm_aimc2_cost_estimation(nvm_aimc, cacti_value):

    # For SRAM -> For 6 Transistors
    # In this paper two 6T SRAM Cells are used per cell and some extra transistors
    # We thus need to estimate this with more than just a simple 6T cell!!!
    # 29 transistors?
    unit_area = nvm_aimc['unit_area']
    unit_delay = nvm_aimc['unit_delay']
    unit_cap = nvm_aimc['unit_cap']

    input_channel = nvm_aimc['input_channel']
    reg_input_bitwidth = nvm_aimc['reg_input_bitwidth']  # is None right now
    input_bandwidth = input_channel * nvm_aimc['input_precision'] # serially done
    output_bandwidth_per_channel = nvm_aimc['output_precision']

    unit_reg = UnitDff(unit_area, unit_delay, unit_cap) # From DIMC cost model, values from nvm_aimc dictionary

    """
        Multiplier array for each output channel
        So each cell is 1 bit times 1 trit (so 2 bits, but in reality only 1.6 bits)
    """
    mults = MultiplierArray(vdd=nvm_aimc['vdd'],
                            input_precision=int(nvm_aimc['multiplier_precision']),
                            number_of_multiplier = input_channel,
                            unit_area= (29/6) * unit_area, # Due to 29 Transistor instead of 6 per cell now
                            unit_delay= unit_delay, # Just keeping from IMC validation for now
                            unit_cap= unit_cap)
    # I will use the SAME class as for SRAM, but the units will be SCALED for the special cell

    # For SRAM standard
    # mults = MultiplierArray(vdd=nvm_aimc['vdd'], input_precision=int(nvm_aimc['multiplier_precision']),
    #                         number_of_multiplier=input_channel, unit_area=unit_area, unit_delay=unit_delay,
    #                         unit_cap=unit_cap)

    """
        Adder_tree for each output channel
        THERE IS NO ADDER TREE
    """
    adder_tree = None


    """
        Accumulator for each output channel
        THERE is a "Shift & Add" for each 5 output channels.
        They add up the results of 5 CYCLES (with shifting).
        They are thus shared over 5 output channels (time multiplexing, together with the ADCs)
    """
    accumulator = None
    shift_and_add = Adder(vdd=nvm_aimc['vdd'], input_precision=5, # 5 bit ADC --> 5 bit input
                          unit_area=unit_area, unit_delay=unit_delay,
                   unit_cap=unit_cap)

    print('shift & add:', 5* shift_and_add.calculate_energy())
    # It should be 0.3360 pJ/5col.

    """
        ADC cost for each output channel
    """
    adc = ADC(resolution=nvm_aimc['adc_resolution'], ICH=nvm_aimc['input_channel'])
    # 5 bit ADC

    """
        DAC cost for each input channel
        THERE ARE NO DACs, Only ternary encoders (kind of do the same thing)
    """
    # dac = DAC(resolution=nvm_aimc['dac_resolution'])

    """
        Memory Instance (delay unit: ns, energy unit: fJ, area unit: mm2)
        unitbank: sram bank, data from CACTI --> IT NEEDS TO BE A RERAM BANK
        regs_input: input register files
        regs_output: output register files for each output channel
        regs_accumulator: register files inside accumulator for each output channel (configuration is same with regs_output)
    """
    # The Analog RRAM buffer stores the WEIGHTS as trits, with HRS/LRS/MRS (1 cell per trit).
    #
    # that is present in each FANT does hold the inputs and the outputs.
    unitbank = MemoryInstance(name='AnalogReRAMBuffer',
                              size=nvm_aimc['rows'] * nvm_aimc['cols'],  # storage needed per FANT, holding of BITS
                              r_bw=nvm_aimc['cols'],
                              w_bw=nvm_aimc['cols'],

                              # NEED TO BE THE ACTUAL ReRAM VALUES FOR THE Analog ReRAM BLOCK (function as cache)
                              # These are all values for SRAM!
                              # delay= cacti_value['delay'] * 0,
                              # r_energy= cacti_value['r_energy'],
                              # w_energy= cacti_value['w_energy'],
                              # area= cacti_value['area'],
                              # latency=0,

                              delay=5,  # ns WRITE
                              r_energy=nvm_aimc['rows'] * nvm_aimc['cols'] * 8.57, #0.02
                              # fJ # should be energy to restore the whole array to SRAM (without conversion circuits taken into account)
                              w_energy=nvm_aimc['rows'] * nvm_aimc['cols'] * 69.2,  # fJ # 50
                              area = 0, # PHYSICALLY ON TOP OF THE SRAM --> NO EXTRA AREA
                              # area = nvm_aimc['rows'] * nvm_aimc['cols']
                              #      * 4 * 60  # per cell actually 4x60 ReRAMM CELLS
                              #      * (10 ** (-7)),  # size of a single ReRAM Cell,
                              latency=1,  # Cycles to Access -> Instant

                              r_port=1,
                              w_port=1,
                              rw_port=0
                              )



    """
        Pre-charging CBL to VDD, nothing said about BLs
    """

    energy_wl = 0 # FOR EVERY WL


    # Pre charging of CBL to VDD
    energy_bl = (nvm_aimc['input_channel'] * (1/1) # 16 CBs, so 256/16=16 rows at once, BUT PRECHARGING NEEDS TO HAPPEN AGAIN AND AGAIN
                 * (nvm_aimc['unit_cap']/2  )
                 * nvm_aimc['vdd'] ** 2)
    # per output channel (aimc['unit_cap']/2 for bitline cap/cell, *2 for 2 bitline port of 2 cells connecting together)

    energy_en = 0

    # energy_en = nvm_aimc['input_channel'] * nvm_aimc['unit_cap'] / 2 * nvm_aimc[
    #     'vdd'] ** 2
    # per output channel (energy cost on "csbias" enable signal)


    """
    calculate result
    :predicted_area:                The area cost for entire CIM core (unit: mm2) --> A single FANT, or all at once (1 bank is 1 FANT)
    :predicted_delay:               The minimum delay of single clock period (unit: ns)
    :predicted_energy_per_cycle:    The energy cost each time the IMC core is activated (unit: fJ)
    :number_of_cycle:               The number of cycle for computing entire input
    :predicted_energy:              The energy cost for computing entire input (unit: fJ)
    :number_of_operations:          The number of operations executed when computing entire input
    :predicted_tops:                Peak TOP/s
    :predicted_topsw:               Peak TOP/s/W    (EE, Energy Efficiency)
    :predicted_topsmm2:             Peak TOP/s/mm^2 (AE, Area Efficiency)
    """

    ## Area cost breakdown
    area_mults = nvm_aimc['banks'] * nvm_aimc['output_channel'] * mults.calculate_area()
    area_adder_tree = 0

    amount_of_adcs = nvm_aimc['output_channel'] * (1/5) # shared over 5 CBLs

    area_accumulator = nvm_aimc['banks'] * amount_of_adcs * shift_and_add.calculate_area()
    area_banks = nvm_aimc['banks'] * 1 * unitbank.area  # ReRAM L1 cache
    area_regs_accumulator = 0
    area_regs_pipeline = 0

    area_adc = nvm_aimc['banks'] * amount_of_adcs * adc.calculate_area() # ADCs shared per 5 CBLs

    # area_dac = nvm_aimc['banks'] * nvm_aimc['input_channel'] * dac.calculate_area()
    area_dac = 0 # It's the ternary encoder, but no area is given for it --> Approximate as not that important


    # # NO SCALING NEEDED, BECAUSE the paper USES THE 28NM TECHNOLOGY NODE

    area_pred_list = [area_mults, area_adder_tree, area_accumulator, area_banks,
                      area_regs_accumulator, area_regs_pipeline, area_adc, area_dac ]
    predicted_area = sum(area_pred_list)
    # cost of input/output regs has been taken out # (assume linear)



    ## Delay
    # Important here again is that the multipliers delay is seen as the reading delay of the SRAM cells
    delay_pred_list = [unitbank.delay, mults.calculate_delay(), adc.calculate_delay()]
    predicted_delay = sum(delay_pred_list)



    ## Energy cost breakdown per cycle
    # AGAIN mults is SRAM reading
    energy_mults = ((1 - nvm_aimc['weight_sparsity'])
                    * nvm_aimc['banks']
                    * nvm_aimc['output_channel']
                    * mults.calculate_energy()
                    * (1/1) * (1/5)) # amortized over the cycles (multiplexing ADCs, but not actually over 16 CBs)

    energy_bitlines = ((1 - nvm_aimc['weight_sparsity'])
                       * nvm_aimc['banks']
                       * nvm_aimc['output_channel']
                       * (energy_wl
                          + energy_bl
                          + energy_en)
                        * (1 / 5)) # amortized over the cycles (multiplexing ADCs, not over the CBs!)

    print('Energy BL precharging:', energy_bl, '| Energy BL discharging:', mults.calculate_energy(),' Energy of <<CiM>>: 96 fJ/CBL')
    energy_adder_tree = 0

    energy_accumulator = (shift_and_add.calculate_energy()
                          * nvm_aimc['banks']
                          * amount_of_adcs)

    energy_banks = 0
    energy_regs_accumulator = 0 # No registers included for now, but technically they are probably there
    energy_regs_pipeline = 0

    energy_adc = ((1 - nvm_aimc['weight_sparsity'])
                  * nvm_aimc['banks']
                  * amount_of_adcs
                  * adc.calculate_energy(vdd = nvm_aimc['vddl']))
    # I chose VDDL (because it exists on the chip according to the paper)
    # And the reported power consumption of the ADC is 0.188 pJ, so this gives a very close match (0.180 pJ)

    # print("adc energies:", adc.calculate_energy(vdd = nvm_aimc['vddl']))

    energy_dac = (nvm_aimc['banks']
                  * nvm_aimc['input_channel']
                  * 13.1 # From paper per conversion for DAC
                  * (1/5) ) #to 5 trits but over 5 cycles, could be even less possibly, but this is already really low
                  # * dac.calculate_energy(vdd = nvm_aimc['vdd'], k0 = nvm_aimc['dac_energy_k0']))
    # per output channel (13.1 fJ/conversion for the Ternary Encoder (the DAC))


    energy_pred_list = [energy_mults, energy_bitlines, energy_adder_tree, energy_accumulator, energy_banks,
                        energy_regs_accumulator, energy_regs_pipeline, energy_adc, energy_dac]
    predicted_energy_per_cycle = sum(energy_pred_list)
    # cost of input/output regs has been taken out # (assume linear)

    # number_of_cycle = nvm_aimc['activation_precision'] / nvm_aimc['input_precision']
    number_of_cycle = (nvm_aimc['input_precision'] # inputs shared over 5 cycles
                       * 16 # Compute Blocks something is 16 in paper --> If diagram is actually correct
                       * 5) # ADC needs to do 5 cycles as well --> Shared over 5 columns


    predicted_energy = predicted_energy_per_cycle * number_of_cycle


    number_of_operations = int(2 * nvm_aimc['banks']
                            * nvm_aimc['input_precision'] # 5t IN
                            * 1.6 # trit to bit
                            * nvm_aimc['input_channel'] # 256t Weights
                            * 1.6 # trit to bit
                            # THIS IS FOR ONE COLUMN

                            * (nvm_aimc['output_channel'] )
                            # THIS IS FOR THE WHOLE ARRAY
                            )

    # number_of_operations = (2 * nvm_aimc['banks']
    #                         * nvm_aimc['output_channel']
    #                         * nvm_aimc['input_channel']
    #                         )
    # 1MAC = 2 Operations !!!!!

    predicted_ops_cycle = number_of_operations/number_of_cycle
    print("Predicted ops per cycle: ", predicted_ops_cycle/nvm_aimc['banks']/2, "From graph:", 2800, "Operation  = MAC here I think")

    predicted_tops = number_of_operations / (predicted_delay * number_of_cycle) / (10 ** 3)
    predicted_topsw = number_of_operations / predicted_energy * 10 ** 3
    predicted_topsmm2 = number_of_operations / predicted_area

    ## Energy breakdown per MAC
    number_of_mac = number_of_operations / 2
    energy_mults_mac = energy_mults * number_of_cycle / number_of_mac
    energy_adder_tree_mac = 0
    energy_accumulator_mac = 0
    energy_banks_mac = energy_banks * number_of_cycle / number_of_mac
    energy_regs_accumulator_mac = 0
    energy_regs_pipeline_mac = 0
    energy_adc_mac = energy_adc * number_of_cycle / number_of_mac
    energy_dac_mac = energy_dac * number_of_cycle / number_of_mac
    energy_estimation_per_mac = predicted_energy / number_of_mac

    energy_reported_per_mac = 2000 / nvm_aimc['TOP/s/W'] # transforming into energy/MAC

    area_mismatch = abs(predicted_area / nvm_aimc['area'] -1) # Area is actually unknown

    delay_mismatch = abs(predicted_delay / nvm_aimc['tclk'] - 1)

    energy_mismatch = abs(energy_estimation_per_mac / energy_reported_per_mac - 1)

    print('TOPSW: ', predicted_topsw, nvm_aimc['TOP/s/W']) # 230 but is now 94.17
    print('TOPSmm2: ', nvm_aimc['TOP/s/mm^2'], predicted_topsmm2, number_of_operations ,predicted_tops, predicted_area)


    # return predicted_area, predicted_delay, energy_estimation_per_mac


    # RIGHT NOW:
    # ENERGY MISMATCH IS AROUND 1 (which means ENERGY IS HALF OF WHAT IT IS SUPPOSED TO BE)
    # The delay is around 20%, so quite close
    # The predicted area is 20.5 x bigger than it should be -> BECAUSE OF THE SRAM ARRAY WHICH IS A RERAM ARRAY

    print('Areas', area_pred_list, predicted_area, nvm_aimc['area'])
    # The area is DOMINATED by the CiM array. This is because the SRAM cells are huge. And the cache is very small (reram)
    # The final area is however what it should be!
    print('Delays', [unitbank.delay, mults.calculate_delay(), adc.calculate_delay()], predicted_delay, nvm_aimc['tclk'])
    print('Energies', energy_pred_list, energy_estimation_per_mac, energy_reported_per_mac) #





    ###############################################################################################
    # Sample data
    categories = ['CIM energy (mult + BL)', 'Accumulator (after ADC)', 'Banks (Cache,New weights)', 'ADCs', 'DACs (here Ternary Encoder)']  # Labels for the bars
    values1 = [energy_mults + energy_bitlines, energy_accumulator, energy_banks,
                        energy_adc, energy_dac]

    # Create the figure and axes
    fig, ax = plt.subplots(figsize=(8, 5))

    # Plot bars
    x = np.arange(len(categories))  # Positions for bars
    ax.bar(x, values1, width=0.6, color='b', alpha=0.7)

    # Labels and formatting
    ax.set_xlabel('Categories')
    ax.set_ylabel('Values')
    ax.set_title('Energies')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)

    # Show plot
    plt.show()

    ###############################################################################################

    # Sample data
    categories = ['mults(Cim)', 'accumulator', 'banks', 'adc', 'dac']  # Labels for the bars
    values2 = [area_mults, area_accumulator, area_banks,
                    area_adc, area_dac ]

    # Create the figure and axes
    fig, ax = plt.subplots(figsize=(8, 5))

    # Plot bars
    x = np.arange(len(categories))  # Positions for bars
    ax.bar(x, values2, width=0.6, color='b', alpha=0.7)

    # Labels and formatting
    ax.set_xlabel('Categories')
    ax.set_ylabel('Values')
    ax.set_title('Area')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)

    # Show plot
    plt.show()


    return area_mismatch, delay_mismatch, energy_mismatch

    # pdb.set_trace()
