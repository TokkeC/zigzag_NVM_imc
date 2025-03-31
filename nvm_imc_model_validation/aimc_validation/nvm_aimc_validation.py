import pdb # PYTHON DEBUGGER
from nvm_aimc1_validation_subfunc import * # The actual validation function for the first paper
from nvm_aimc2_validation_subfunc import * # Second paper

"""
Light-CIM 2024 (28 nm technology) 
(Assume 100% input toggle rate, 0% weight sparsity)
"""
nvm_aimc1 = {  # https://ieeexplore.ieee.org/document/10614392 (28nm)
    'paper_idx': 'LightCIM2024',


    'input_toggle_rate': 1,  # Assuming full usage all the time
    'weight_sparsity': 0,  # Assuming no sparsity


    'activation_precision': 16, # 'Analog' (Means 16 bit for calculation on bitlines (says so in table))
    'weight_precision': 8, # 1-8
    'output_precision': 8,  # Output/Sensing precision (Reading of bitlines for results)
    'input_precision': 8, # Input precision (wordlines into array)


    'input_channel': 128*8*12,  # how many input in parallel (per bank) --> GIVEN IN BITS NOW
    'output_channel': 128*8*12,  # how many output in parallel (per bank) --> GIVEN IN BITS NOW
    # sizes: [1, 196608, 1]
    # #128x128(SubArray is 128x128 cells) x8(Sub-Arrays per PE) x12(PEs per FANT, only 1 ADC per FANT......) x168(FANTS per chip)
    # Each cell can hold 1 bit, but we see it as 8 bits per cell.
    # D1 =8* 168 /8 (precision ADCs), D2 = 128x16x96
    # Right now the BANKS are seen as the FANTs


    'adc_resolution': 1, # NEED to recheck, because they are not super clear about it
                         # But they mention '1-bit SAs can effectively replace all the ADCs'
    'dac_resolution': 8, # Same I guess? NO??? -> Made 8 such that we have an 8 bit input that needs to be translated to 8 actual wordlines

    'booth_encoding': False, # In all examples for IMC it is set to 'False'
                             # it does stand for a specific bit scheme to store values to do faster multiplication

    # NOT SURE ABOUT ALL THESE!
    'multiplier_precision': 2,
    'adder_input_precision': None,
    'accumulator_precision': None,
    'reg_accumulator_precision': None,
    'reg_input_bitwidth': None,

    # I don't see any pipelining, but could be in the controller...
    'pipeline': False,

    'vdd': 1.8,  # V
    'vdd_read': 1.0, # V
    # Read voltage is 0.5 or 1.0 V
    # Source voltage (VDD) is 0.9 or 1.8 V


    # the rows, cols, NOT SAME AS INPUT AND OUTPUTS! But it is valid for EACH FANTS ANALOG RRAM
    'rows': 128*8*12,
    'cols': 128*8*12,

    'banks': 168,  # number of cores (FANTS)
    # Per chip there are 168 FANTs

    'compact_rule': False,  # NOT SURE WHAT THIS IS!


    'area': 850,  # mm2
    # RIGHT NOW, NOT SURE...
    # In the paper, there actually is no area mentioned, only Area Efficiency... (AE = 3.91 TOPS/mm^2)
    #

    'tclk': 1000 / 10,  # ns (assume tclk doesn't scale with technology)
    # 10 MHz --> 100 ns (1000 / fclk in MHz)

    # TOPS and TOP/s is the same
    # EE: TOP/s/W
    # AE : TOP/s/mm^2
    # For this paper, also 'normalized' numbers for this are available.
    # This means they are normalized to 1-bit activation and 1-bit weights. While 'Analog' is calculated as 16 bits
    'TOP/s': None,
    'TOP/s/W': 3.08,
    'TOP/s/mm^2': 3.91,

    # FOR NOW NOT CHANGED, but probably not these
    # BUT THEY WERE NOT PAPER SPECIFIC AND THE SAME FOR ALL THE IMC VALIDATIONS
    'unit_area': 0.614,  # um2 # THIS IS FOR A SINGLE SRAM CELL -> 6 Transistors in 25 nm node
    # APPROXIMATION FOR ReRAM -> 1 Transistor -> 1/6th of this -> Done in code

    'unit_delay': 0.0478,  # ns
    # As a for APPROXIMATION, this value will be 3 times more for ReRAM sensing.

    'unit_cap': 0.7,  # fF
    # Approximation for ReRAM 0.71 * unit_cap, there are less transistors thus lower capacitances

    'dac_energy_k0': 50
    # fF (energy validation fitting parameter, which is taken directly from the value in TinyML paper)
}

# NOT changed compared to IMC VALIDATION!!!
cacti1 = {  # 131072B, bw: 1024
    'delay': 0.106473,  # ns
    'r_energy': None,  # not used
    'w_energy': None,  # not used
    'area': 0.24496704  # mm2
}


"""
TL-nvSRAM-CIM 2023 (28 nm technology) 
(Assume 100% input toggle rate, 0% weight sparsity)

This work does integrate nvm (ReRAM) as the first level cache and leaves the CIM as an SRAM array.
"""
nvm_aimc2 = {  # https://ieeexplore.ieee.org/document/10323889 (28nm)
    'paper_idx': 'TLnvSRAMCIM2023',


    'input_toggle_rate': 1,  # Assuming full usage all the time
    'weight_sparsity': 0,  # Assuming no sparsity

    #####################
    # The precisions are in terms of trits (+1, -1, 0) instead of bits... --> Converting to bits
    # Base 3 instead of Base 2 -> 8 Bits is +- 5 trits
    # THE CONVERSION ALSO NEEDS TO HAPPEN IN HARDWARE, AND THUS HAS AN ENERGY IMPACT!!
    'activation_precision': 5, # On bitline? 16 bit?
    'weight_precision': 5,  # 5 trit --> 8 bit W
    'output_precision': 5,  # Output/Sensing precision (Reading of bitlines for results) --> IN BITS
    'input_precision': 5, # 5 Trits in (time multiplexed serially)
    #####################

    # 256x320 macro, activating max 16 rows (the Compute Blocks), 1 row read at a time (so total cycles calculation)
    'input_channel': 256,  # how many input in parallel (per bank) --> GIVEN IN BITS NOW
    'output_channel': 320,  # how many output in parallel (per bank) --> GIVEN IN BITS NOW


    'adc_resolution': 5, # 5 BIT ADCs, shared by every 5 CBLs (10 columns of SRAM) --> Single array should be 32 ADCs (320/10)
    'dac_resolution': 5, # 5 TRIT DACs --> Converting bits to trits (Ternary Encoder)

    'booth_encoding': False, # In all examples for IMC it is set to 'False'
                             # it does stand for a specific bit scheme to store values to do faster multiplication

    # NOT SURE ABOUT ALL THESE!
    'multiplier_precision': 1,
    'adder_input_precision': None,
    'accumulator_precision': None,
    'reg_accumulator_precision': None,
    'reg_input_bitwidth': None,

    # I don't see any pipelining, but could be in the controller...
    'pipeline': False,

    'vdd': 0.9, # Used for the precharging of the bitlines (of SRAM CiM)
    'vddh': 1.5,
    'vddl': 0.6,
    'vstr': 0.31,

    # the rows, cols, NOT SAME AS INPUT AND OUTPUTS! But it is valid for EACH FANTS ANALOG RRAM
    'rows': 256, # 60 TL-ReRAM and 4 such clusters per CELL!!!!
    'cols': 320,

    'banks': 6,  # number of macros --> 6 subarrays, BUT they give array level throughput etc, so think I should just do a single Macro
    # I think they evaluate just a single macro (to keep it easy)

    'compact_rule': False,  # NOT SURE WHAT THIS IS!


    'area': 1.7 ,  # mm2
    # Total area, FROM GRAPH (Fig. 11 b)
    # Also given is the 'Cell Area' which is 6.35 µm^2

    'tclk': 1000 / 10,  # ns (assume tclk doesn't scale with technology)
    # Unknown, not given in the paper

    # TOPS and TOP/s is the same
    # EE: TOP/s/W
    # AE : TOP/s/mm^2
    # For this paper, also 'normalized' numbers for this are available.
    # This means they are normalized to 1-bit activation and 1-bit weights. While 'Analog' is calculated as 16 bits
    'TOP/s': None, # OPS/cycle is known (either with the multiplexing, or full array usage)
    'TOP/s/W': 230,
    'TOP/s/mm^2': None, # Not known
    'TOP/s/W/mm^2': 2.2,


    # In this paper we use an SRAM CiM ARRAY at 28 nm node --> These values should be suited exactly for that
    # FOR NOW NOT CHANGED, but probably not these
    # BUT THEY WERE NOT PAPER SPECIFIC AND THE SAME FOR ALL THE IMC VALIDATIONS
    'unit_area': 0.614,  # um2 # THIS IS FOR A SINGLE SRAM CELL -> 6 Transistors in 25 nm node
    # APPROXIMATION FOR ReRAM -> 1 Transistor -> 1/6th of this -> Done in code

    'unit_delay': 0.0478,  # ns
    # As a for APPROXIMATION, this value will be 3 times more for ReRAM sensing.

    'unit_cap': 0.7,  # fF
    # Approximation for ReRAM 0.71 * unit_cap, there are less transistors thus lower capacitances

    'dac_energy_k0': 50
    # fF (energy validation fitting parameter, which is taken directly from the value in TinyML paper)
}

# NOT changed compared to IMC VALIDATION!!!
# These are for SRAM caches, while we actually will use ReRAM cache --> Doing this in the code
cacti2 = {  # 131072B, bw: 1024
    'delay': 0.106473,  # ns
    'r_energy': None,  # not used
    'w_energy': None,  # not used
    'area': 0.24496704  # mm2
}

# """
# JSSC2023 (Assume 100% input toggle rate, 0% weight sparsity)
# """
# aimc2 = {  # https://ieeexplore.ieee.org/document/9896828/ (28nm)
#     'paper_idx': 'JSSC2023',
#     'input_toggle_rate': 1,  # assumption
#     'weight_sparsity': 0,  # assumption
#     'activation_precision': 8,
#     'weight_precision': 8,
#     'output_precision': 20,  # output precision (unit: bit)
#     'input_precision': 8,
#     'input_channel': 16,  # how many input in parallel (per bank)
#     'output_channel': 12,  # how many output in parallel (per bank)
#     'adc_resolution': 5,
#     'dac_resolution': 2,
#     'booth_encoding': False,
#     'multiplier_precision': 2,
#     'adder_input_precision': 12,
#     'accumulator_input_precision': 16,
#     'accumulator_precision': 20,
#     'reg_accumulator_precision': 20,
#     'reg_input_bitwidth': None,
#     'pipeline': True,
#     'vdd': 0.9,  # V
#     'rows': 32 * 16,  # equal to the number of input channels
#     'cols': 8 * 2 * 12,  # *2 for column MUX
#     'banks': 4,  # number of cores
#     'compact_rule': True,
#     'area': 0.468,  # mm2
#     'tclk': 7.2,  # ns
#     'TOP/s': None,
#     'TOP/s/W': 15.02,
#     'unit_area': 0.614,  # um2
#     'unit_delay': 0.0478,  # ns
#     'unit_cap': 0.7,  # fF
#     'dac_energy_k0': 50  # fF
# }
# cacti2 = {  # 98304b , bw: 96
#     'delay': 0.16111872,  # ns
#     'r_energy': None,  # fJ @ 0.9V # not used
#     'w_energy': None,  # fJ @ 0.9V # not used
#     'area': 0.0360450648  # mm2
# }
#
# """
# ISSCC2023, 7.8 (Assume 37.5% input toggle rate, 50% weight sparsity)
# """
# aimc3 = {  # https://ieeexplore.ieee.org/document/10067289 (22nm)
#     'paper_idx': 'ISSCC2023, 7.8',
#     'input_toggle_rate': 0.375,  # assumption
#     'weight_sparsity': 0.5,  # assumption
#     'activation_precision': 8,
#     'weight_precision': 8,
#     'output_precision': 24,  # output precision (unit: bit)
#     'input_precision': 1,
#     'input_channel': 8,  # how many input in parallel (per bank)
#     'output_channel': 256,  # how many output in parallel (per bank)
#     'adc_resolution': 3,
#     'dac_resolution': 0,
#     'booth_encoding': False,
#     'multiplier_precision': 1,
#     'adder_input_precision': None,
#     'accumulator_precision': None,
#     'reg_accumulator_precision': None,
#     'reg_input_bitwidth': None,
#     'pipeline': False,
#     'vdd': 0.8,  # V @ 22nm
#     'rows': 64,
#     'cols': 256,
#     'banks': 8,  # number of cores
#     'compact_rule': True,
#     'area': 1.88,  # mm2 (in code, the area will scale from 28nm -> 22nm)
#     'tclk': 1000 / 364,  # ns
#     'TOP/s': None,
#     'TOP/s/W': 18.7,  # (in code, the area will scale from 28nm -> 22nm)
#     'unit_area': 0.614,  # um2
#     'unit_delay': 0.0478,  # ns
#     'unit_cap': 0.7,  # fF
#     'dac_energy_k0': 50  # fF
# }
# cacti3 = {  # 64*256, bw: 256
#     'delay': 0.0722227,  # ns not used # delay of array will be merged into ADC delay
#     'r_energy': None,  # fJ @ 0.9V # not used
#     'w_energy': None,  # fJ @ 0.9V # not used
#     'area': 0.004505472  # mm2
# }

"""
    Main function, runs the comparison
"""
if __name__ == '__main__':
    """
        For energy fitting, fit: dac_energy_k0
        For area fitting, fit: cell scaling factor (2 for now), constant in ADC formula
        For delay fitting, fit: constant in ADC formula
    """
    # print(nvm_aimc1_cost_estimation(nvm_aimc1, cacti1) ) # nvm_aimc1
    print(nvm_aimc2_cost_estimation(nvm_aimc2, cacti2) ) # nvm_aimc2
    # print(aimc3_cost_estimation(aimc3, cacti3))  # aimc3