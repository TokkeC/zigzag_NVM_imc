"""
    This validation is for Light-CIM (2024, 28 nm paper)
    The code is based on the initial validation code of the IMC validation in ZigZag.
"""

import pdb # PYTHON DEBUGGER
from nvm_aimc_cost_model import *
from nvm_dimc_cost_model import *

def nvm_aimc1_cost_estimation(nvm_aimc, cacti_value):
    # For SRAM -> For 6 Transistors
    unit_area = nvm_aimc['unit_area']
    unit_delay = nvm_aimc['unit_delay']
    unit_cap = nvm_aimc['unit_cap']

    input_channel = nvm_aimc['input_channel']
    reg_input_bitwidth = nvm_aimc['reg_input_bitwidth']  # is None right now
    input_bandwidth = input_channel * nvm_aimc['input_precision']
    output_bandwidth_per_channel = nvm_aimc['output_precision']

    unit_reg = UnitDff(unit_area, unit_delay, unit_cap) # From DIMC cost model, values from nvm_aimc dictionary

    """
        THIS IS MOST PROBABLY WRONG. THERE WILL NEED TO BE MULTIPLIERS AND ADDERS!
        If I'm correct, there are NO multipliers (happens in the analog domain on the bitlines)
        BUT the multipliers in this cost model do represent the cells of SRAM... and their cost --> Also needed for ReRAM
        Adders happen via Current Mirror Adders, with bigger 1 : 2^N-1 mirrors for weighted sums.
        
        Next to the CIM arrays, there is an Analog ReRAM array for the analog input and output data.
        It is thus low level cache for the array. There is one such array for each FANT.
    """
    """
        Multiplier array for each output channel --> ReRAM now
    """
    mults = MultiplierArray(vdd=nvm_aimc['vdd'],
                            input_precision=int(nvm_aimc['multiplier_precision']),
                            number_of_multiplier = input_channel,
                            unit_area= (1/6) * unit_area, # Due to 1 Transistor instead of 6 per cell now
                            unit_delay= 3 * unit_delay, # Due to current sensing and higher resistance
                            unit_cap= 0.71 * unit_cap)
    # I will use the SAME class as for SRAM, but the units will be SCALED for ReRAM

    # For SRAM
    # mults = MultiplierArray(vdd=nvm_aimc['vdd'], input_precision=int(nvm_aimc['multiplier_precision']),
    #                         number_of_multiplier=input_channel, unit_area=unit_area, unit_delay=unit_delay,
    #                         unit_cap=unit_cap)

    """
        Adder_tree for each output channel
    """
    adder_tree = None

    """
        Accumulator for each output channel
    """
    accumulator = None

    """
        ADC cost for each output channel
    """
    adc = ADC(resolution=nvm_aimc['adc_resolution'], ICH=nvm_aimc['input_channel'])
    # ALl channels that in 1 clk cycle should be sampled by ADC. Gives still 1 per FANT (bank)

    """
        DAC cost for each input channel
    """
    dac = DAC(resolution=nvm_aimc['dac_resolution'])

    """
        Memory Instance (delay unit: ns, energy unit: fJ, area unit: mm2)
        unitbank: sram bank, data from CACTI --> IT NEEDS TO BE A RERAM BANK, ONE PER FANT
        regs_input: input register files
        regs_output: output register files for each output channel
        regs_accumulator: register files inside accumulator for each output channel (configuration is same with regs_output)
    """
    # The Analog RRAM buffer that is present in each FANT does hold the inputs and the outputs.
    unitbank = MemoryInstance(name='AnalogReRAMBuffer',
                              size= nvm_aimc['rows'] * nvm_aimc['cols'], # storage needed per FANT, holding of BITS
                              r_bw= nvm_aimc['cols'],
                              w_bw= nvm_aimc['cols'],

                              # NEED TO BE THE ACTUAL ReRAM VALUES FOR THE Analog ReRAM BLOCK (function as cache)
                              # These are all values for SRAM!
                              # delay= cacti_value['delay'] * 0,
                              # r_energy= cacti_value['r_energy'],
                              # w_energy= cacti_value['w_energy'],
                              # area= cacti_value['area'],
                              # latency=0,
                              delay = 5, #ns WRITE
                              r_energy = 0.02, #fJ
                              w_energy = 50, #fJ
                              area = nvm_aimc['rows'] * nvm_aimc['cols'] * (10**(-7)),
                              latency = 1, #Cycles to Access -> Instant

                              r_port=1,
                              w_port=1,
                              rw_port=0
                              )

    energy_wl = 0  # per output channel
    energy_bl = (nvm_aimc['input_channel'] * (nvm_aimc['unit_cap']  ) # no opposite bitline, so no C/2
                  * nvm_aimc['vdd_read'] ** 2) ## vdd_read because we need the READ voltage not the VDD

    # per output channel (aimc['unit_cap']/2 for bitline cap/cell, *2 for 2 bitline port of 2 cells connecting together)
    energy_en = nvm_aimc['input_channel'] * nvm_aimc['unit_cap'] / 2 * nvm_aimc[
        'vdd'] ** 2
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
    area_accumulator = 0
    area_banks = nvm_aimc['banks'] * 1 * unitbank.area  # FANTS * unitbank area (unitbank being the Analog ReRAM cache)
    area_regs_accumulator = 0
    area_regs_pipeline = 0
    area_adc = nvm_aimc['banks'] * 1 * adc.calculate_area() # ONLT 1 ADC per FANT
    area_dac = nvm_aimc['banks'] * nvm_aimc['input_channel'] * dac.calculate_area() # area is 0 in function, + not really given how many there are

    # # NO SCALING NEEDED, BECAUSE Light-CIM USES THE 28NM TECHNOLOGY NODE
    # # (for beyong ADC/DAC part, scale from 28nm -> 22nm, exclude ADC/DAC, which is assumed indepedent from tech.) (assume linear)
    # area_mults = area_mults / 28 * 22
    # area_adder_tree = area_adder_tree / 28 * 22
    # area_accumulator = area_accumulator / 28 * 22
    # area_banks = area_banks  # the area is for 22 nm
    # area_regs_accumulator = area_regs_accumulator / 28 * 22
    # area_regs_pipeline = area_regs_pipeline / 28 * 22
    # area_adc = area_adc / 28 * 22
    # area_dac = area_dac / 28 * 22

    area_pred_list = [area_mults, area_adder_tree, area_accumulator, area_banks,
                      area_regs_accumulator, area_regs_pipeline, area_adc, area_dac ]
    predicted_area = 0
    for area_item in area_pred_list:
        predicted_area += area_item
    # cost of input/output regs has been taken out # (assume linear)

    ## delay
    # Important here again is that the multipliers delay is seen as the reading delay of the SRAM cells (which now are ReRAM cells)
    predicted_delay = unitbank.delay + mults.calculate_delay() + adc.calculate_delay()

    ## Energy cost breakdown per cycle
    # AGAIN mults is SRAM reading --> ReRAM READING NEEDED
    # BANKS amount of FANTS, output_channels amount of columns, needed for ReRAM reading amount of energy
    energy_mults = (1 - nvm_aimc['weight_sparsity']) * nvm_aimc['banks'] * nvm_aimc['output_channel'] * mults.calculate_energy()
    energy_adder_tree = 0
    energy_accumulator = 0
    energy_banks = ((1 - nvm_aimc['weight_sparsity'])
                    * nvm_aimc['banks']
                    * nvm_aimc['output_channel']
                    * (energy_wl + energy_bl + energy_en))
    energy_regs_accumulator = 0
    energy_regs_pipeline = 0

    energy_adc = ((1 - nvm_aimc['weight_sparsity'])
                  * nvm_aimc['banks'] # AMOUNT OF FANTS (168)
                  * nvm_aimc['output_channel'] # 128 (array BLs) x8 (Arrays per PE) x12 (PEs per FANT)
                  * adc.calculate_energy(vdd = nvm_aimc['vdd'])) # using VDD not read VDD!!!
    energy_dac = nvm_aimc['banks'] * nvm_aimc['input_channel'] * dac.calculate_energy(vdd = nvm_aimc['vdd'], k0 = nvm_aimc['dac_energy_k0'])

    ## NO SCALING NEEDED, BECAUSE Light-CIM USES THE 28NM TECHNOLOGY NODE
    # # (for beyong ADC/DAC part, scale from 28nm -> 22nm, exclude ADC/DAC, which is assumed indepedent from tech.) (assume linear)
    # energy_mults = energy_mults / 28 * 22
    # energy_adder_tree = energy_adder_tree / 28 * 22
    # energy_accumulator = energy_accumulator / 28 * 22
    # energy_banks = energy_banks / 28 * 22
    # energy_regs_accumulator = energy_regs_accumulator / 28 * 22
    # energy_regs_pipeline = energy_regs_pipeline / 28 * 22

    energy_pred_list = [energy_mults, energy_adder_tree, energy_accumulator, energy_banks,
                        energy_regs_accumulator, energy_regs_pipeline, energy_adc, energy_dac]
    predicted_energy_per_cycle = 0
    for energy_item in energy_pred_list:
        predicted_energy_per_cycle += energy_item
    # cost of input/output regs has been taken out # (assume linear)

    number_of_cycle = nvm_aimc['activation_precision'] / nvm_aimc['input_precision']
    predicted_energy = predicted_energy_per_cycle * number_of_cycle

    number_of_operations = (2 * nvm_aimc['banks']
                            * (nvm_aimc['output_channel'] / nvm_aimc['output_precision']) # without dividing we look at BITS
                            * (nvm_aimc['input_channel'] / nvm_aimc['input_precision']) # without dividing we look at BITS
                            )
    # number_of_operations = (2 * nvm_aimc['banks']
    #                         * nvm_aimc['output_channel']
    #                         * nvm_aimc['input_channel']
    #                         )
    # 1MAC = 2 Operations !!!!!

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

    print('TOPSW: ', predicted_topsw) # Should be 3.08 but is now 4.485
    print('TOPSmm2: ', nvm_aimc['TOP/s/mm^2'], predicted_topsmm2, number_of_operations ,predicted_tops, predicted_area)


    # return predicted_area, predicted_delay, energy_estimation_per_mac


    # RIGHT NOW:
    # ENERGY MISMATCH IS AROUND 1 (which means ENERGY IS HALF OF WHAT IT IS SUPPOSED TO BE)
    # The delay is around 20%, so quite close
    # The predicted area is 20.5 x bigger than it should be -> BECAUSE OF THE SRAM ARRAY WHICH IS A RERAM ARRAY

    print('Delays', [unitbank.delay, mults.calculate_delay(), adc.calculate_delay()], predicted_delay, nvm_aimc['tclk']) # --> ONLY ADC DELAY, KINDA EXPECTED!!!
    print('Areas', area_pred_list, predicted_area, nvm_aimc['area'])
    print('Energies', energy_pred_list, energy_estimation_per_mac, energy_reported_per_mac) # --> 2.62 VS 649 actually! --> FACTOR 250
    # Now already better, only 31% difference -> Still probably need to be closer

    # TO BE FAIR, I THINK I HAVE A PROBLEM WITH DEFINING WHAT 1 OPERATION IS!!!! --> Defined it as a 8x8 bit operation now

    return area_mismatch, delay_mismatch, energy_mismatch

    # pdb.set_trace()
