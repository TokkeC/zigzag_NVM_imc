"""
    This code is rewritten from NeuroSIM. What was not useful has not been used!
"""

"""
    There are multiple kind of cells in NeuroSIM. Being:
        ANALOG NVM:
        - IdealDevice
        - RealDevice
        
        DIGITAL NVM:
        - DigitalNVM
        
        
        - MeasuredDevice
        - SRAM (IS ALREADY IMPLEMENTED IN ZIGZAG)
        
        - HybridCell
        - 2T1F
"""

"""
    I will model IdealDevice,
    as it does NOT have any nonlinearities
    (which zigzag can't work with as it is not bit per bit based).
"""

"""
    Defining class with values for IdealDevice
"""
class ReRAM_IDEAL:
    """
        Global for all ReRAM
    """
    maxConductance = 5e-6  # S
    minConductance = 100e-9  # S
    # maxConductance = 3.8462e-8 #from RealDevice class in NeuroSim
    # minConductance = 3.0769e-9

    avgMaxConductance = maxConductance  # we just use the max and min values due to no non linearities taken into account
    avgMinConductance = minConductance
    conductance = None  # This is variable/dynamic
    conductancePrev = None # DEFINED IN __init__

    readVoltage = 0.5  # V, voltage to read ReRAM
    readPulseWidth = 5e-9  # s, The pulse to read, how long
    writeVoltageLTP = 2  # V, write voltage for weight increase (LTP, Long term potentiation)
    writeVoltageLTD = 2  # V, write voltage for weight decrease (LTD, Long term depression)
    # writeVoltageLTP = 3.2  #  from RealDevice class
    # writeVoltageLTD = 2.8

    # writePulseWidthLTP = 10e-9  # s
    # writePulseWidthLTD = 10e-9  # s
    writePulseWidthLTP = 300e-6 * 64  # from RealDevice class
    writePulseWidthLTD = 300e-6 * 64 # * 64 due to only seeing as binary now?


    writeEnergy = 0  # dynamic/variable
    maxNumLevelLTP = 1 #64  # Maximum number of conductance states during LTP or weight increase
    maxNumLevelLTD = 1 #64  # 4 for BINARY -> Most robust
    numPulse = 0  # dynamic/variable, In most recent write operation, number of write pulses used
    cmosAccess = True  # true for pseudo-crossbar (1T1R), false for crossbar
    # Nothing implemented for FeFET right now
    resistanceAccess = 15e3  # Ohm, resistance of transistor when turned on (if CMOSACCESS)

    nonlinearIV = False  # This is what we are modelling now!
    nonIdenticalPulse = False
    NL = 10  # The nonlinearity in write scheme

    readNoise = False  # Not considering read noise
    # They make Gaussian distribution for the noise with a certain sigmaReadNoise (0.25 on default)

    conductanceRangeVar = 0  # So for NeuroSim it can be usefull as they want to model literally everything, for us it isn't
    # not declaring other variables that have to do with it

    heightInFeatureSize = 4 if cmosAccess else 2  # Crossbar or not
    widthInFeatureSize = 4 if cmosAccess else 2

    writeLatencyLTP = 0
    writeLatencyLTD = 0

    def __init__(self):
        # All variables of the class
        self.conductance = self.minConductance  # This is variable/dynamic but initialized at the minConductance
        self.conductancePrev = self.conductance
        self.writeEnergy = 0  # dynamic/variable
        self.numPulse = 0  # dynamic/variable, In most recent write operation, number of write pulses used
        self.writeLatencyLTP = 0
        self.writeLatencyLTD = 0

    def read(self, voltage):
        if self.readNoise: #always False actually
            pass
            # nothing, not implemented
        else:
            return voltage * self.conductance

    def write(self, deltaWeightNormalized, weight, minWeight=0, maxWeight=1):
        if deltaWeightNormalized >= 0:
            deltaWeightNormalized = deltaWeightNormalized / (maxWeight-minWeight)
            deltaWeightNormalized = min(deltaWeightNormalized, self.maxNumLevelLTP) #truncating actually
            self.numPulse = deltaWeightNormalized * self.maxNumLevelLTP
        else:
            deltaWeightNormalized = deltaWeightNormalized / (maxWeight - minWeight)
            deltaWeightNormalized = min(deltaWeightNormalized, self.maxNumLevelLTD)
            self.numPulse = deltaWeightNormalized * self.maxNumLevelLTD

        conductanceNew = self.conductance + deltaWeightNormalized * (self.maxConductance - self.minConductance)
        if conductanceNew > self.maxConductance:
            conductanceNew = self.maxConductance
        elif conductanceNew < self.minConductance:
            conductanceNew = self.minConductance

        # Write latency calculation itself (before it was conductance calculations)
        # also works like this for BINARY
        if self.numPulse > 0:
            self.writeLatencyLTP = self.numPulse * self.writePulseWidthLTP
            self.writeLatencyLTD = 0
        else:
            self.writeLatencyLTP = 0
            self.writeLatencyLTD = -self.numPulse * self.writePulseWidthLTD

        self.conductancePrev = self.conductance
        self.conductance = conductanceNew


    def WriteEnergyCalculation(self, wireCapCol):
        if self.nonlinearIV:  # never happening
            pass
            # NOT IMPLEMENTED
        else:
            # first if fefet, but not implemented

            # THERE IS AN LTP AND LTD PHASE, AFTER EACH OTHER
            if self.numPulse > 0: # LTP PULSES NEEDED
                self.writeEnergy = self.writeVoltageLTP * self.writeVoltageLTP * ((self.conductancePrev + self.conductance)/2) * self.writePulseWidthLTP * self.numPulse
                self.writeEnergy += self.writeVoltageLTP * self.writeVoltageLTP * wireCapCol * self.numPulse
                if not self.cmosAccess: # Crossbar
                    #if nonIdenticalPulse, but never
                    # Half-selected during LTD phase
                    self.writeEnergy += self.writeVoltageLTD/2 * self.writeVoltageLTD/2 * self.conductance * self.writeLatencyLTD
                    self.writeEnergy += self.writeVoltageLTD/2 * self.writeVoltageLTD/2 * wireCapCol

            elif self.numPulse < 0: # LTD PULSES NEEDED
                self.writeEnergy = self.writeVoltageLTD * self.writeVoltageLTD * ((self.conductancePrev + self.conductance)/2) * self.writePulseWidthLTD * (-self.numPulse)
                self.writeEnergy += self.writeVoltageLTD * self.writeVoltageLTD * wireCapCol * (-self.numPulse)
                if not self.cmosAccess:
                    #if nonIdenticalPulse again
                    # Half-selected during LTP phase (use the old conductance value if LTP phase is before LTD phase)
                    self.writeEnergy += self.writeVoltageLTP/2 * self.writeVoltageLTP/2 * self.conductancePrev * self.writeLatencyLTP
                    self.writeEnergy += self.writeVoltageLTP/2 * self.writeVoltageLTP/2 * wireCapCol
                else: # 1T1R
                    self.writeEnergy += self.writeVoltageLTP * self.writeVoltageLTP * wireCapCol

            else: #NO WEIGHT UPDATE
                #half selected during both LTP and LTD
                if not self.cmosAccess:
                    self.writeEnergy = self.writeVoltageLTP/2 * self.writeVoltageLTP/2 * self.conductancePrev * self.writeLatencyLTP
                    self.writeEnergy += self.writeVoltageLTP / 2 * self.writeVoltageLTP / 2 * wireCapCol
                    self.writeEnergy += self.writeVoltageLTD / 2 * self.writeVoltageLTD / 2 * self.conductancePrev * self.writeLatencyLTD
                    self.writeEnergy += self.writeVoltageLTD / 2 * self.writeVoltageLTD / 2 * wireCapCol
                else: # 1T1R
                    self.writeEnergy = self.writeVoltageLTP * self.writeVoltageLTP * wireCapCol
