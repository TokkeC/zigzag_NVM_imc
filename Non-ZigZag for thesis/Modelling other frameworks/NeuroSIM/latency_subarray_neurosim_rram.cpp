else if (cell.memCellType == Type::RRAM || cell.memCellType == Type::FeFET) {
			if (conventionalSequential) {
				double capBL = lengthCol * 0.2e-15/1e-6;
				double colRamp = 0;
				double tau = (capCol)*(cell.resMemCellAvg);
				colDelay = horowitz(tau, 0, 1e20, &colRamp);	// Just to generate colRamp
				colDelay = tau * 0.2 * numColMuxed;  // assume the 15~20% voltage drop is enough for sensing
				int numWriteOperationPerRow = (int)ceil((double)numCol*activityColWrite/numWriteCellPerOperationNeuro);
				
				wlDecoder.CalculateLatency(1e20, capRow2, NULL, numRow*activityRowRead*numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				if (cell.accessType == CMOS_access) {
					wlNewDecoderDriver.CalculateLatency(wlDecoder.rampOutput, capRow2, resRow, numRow*activityRowRead*numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);	
				} else {
					wlDecoderDriver.CalculateLatency(wlDecoder.rampOutput, capRow1, capRow1, resRow, numRow*activityRowRead*numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				}
				slSwitchMatrix.CalculateLatency(1e20, capCol, resCol, 0, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				if (numColMuxed > 1) {
					mux.CalculateLatency(colRamp, 0, numColMuxed);
					muxDecoder.CalculateLatency(1e20, mux.capTgGateN*ceil(numCol/numColMuxed), mux.capTgGateP*ceil(numCol/numColMuxed), numColMuxed, 0);
				}
				if (SARADC) {
					sarADC.CalculateLatency(numColMuxed*numRow*activityRowRead);
				} else {
					multilevelSenseAmp.CalculateLatency(columnResistance, numColMuxed, numRow*activityRowRead);
					if (avgWeightBit > 1) {
						multilevelSAEncoder.CalculateLatency(1e20, numColMuxed*numRow*activityRowRead);
					}
				}
				
				adder.CalculateLatency(1e20, dff.capTgDrain, numColMuxed*numRow*activityRowRead);
				dff.CalculateLatency(1e20, numColMuxed*numRow*activityRowRead);
				if (numCellPerSynapse > 1) {				 
					shiftAddWeight.CalculateLatency(numColMuxed);							// There are numReadPulse times of shift-and-add
				}																								
				if (numReadPulse > 1) {
					shiftAddInput.CalculateLatency(ceil(numColMuxed/numCellPerSynapse));	// There are numReadPulse times of shift-and-add
				}
				
				// Read
				readLatency = 0;
				readLatency += MAX(wlDecoder.readLatency + wlNewDecoderDriver.readLatency + wlDecoderDriver.readLatency, ( ((numColMuxed > 1)==true? (mux.readLatency+muxDecoder.readLatency):0) )/numReadPulse);
				readLatency += multilevelSenseAmp.readLatency;
				readLatency += multilevelSAEncoder.readLatency;
				readLatency += adder.readLatency;
				readLatency += dff.readLatency;
				readLatency += shiftAddInput.readLatency + shiftAddWeight.readLatency;
				readLatency += colDelay/numReadPulse;
				readLatency += sarADC.readLatency;
				
				readLatencyADC = multilevelSenseAmp.readLatency + multilevelSAEncoder.readLatency + sarADC.readLatency;
				readLatencyAccum = adder.readLatency + dff.readLatency + shiftAddInput.readLatency + shiftAddWeight.readLatency;
				readLatencyOther = MAX(wlDecoder.readLatency + wlNewDecoderDriver.readLatency + wlDecoderDriver.readLatency, ( ((numColMuxed > 1)==true? (mux.readLatency+muxDecoder.readLatency):0) )/numReadPulse) + colDelay/numReadPulse;
				
				// Write
				writeLatency = 0;
				writeLatencyArray = 0;
				writeLatencyArray += totalNumWritePulse * cell.writePulseWidth;
				writeLatency += MAX(wlDecoder.writeLatency + wlNewDecoderDriver.writeLatency + wlDecoderDriver.writeLatency, slSwitchMatrix.writeLatency);
				writeLatency += writeLatencyArray;
				
				/* Transpose Peripheral for BP */
				if (trainingEstimation) {
					readLatencyAG = 0;
					if (layerNumber != 0) {
						double capRow = lengthRow * 0.2e-15/1e-6 + CalculateDrainCap(cell.widthAccessCMOS * tech.featureSize, NMOS, cell.widthInFeatureSize * tech.featureSize, tech) * numCol;
						tau = (capRow)*(cell.resMemCellAvg);
						double rowDelay = tau * 0.2 * numRowMuxedBP;  // assume the 15~20% voltage drop is enough for sensing
						
						slSwitchMatrix.CalculateLatency(1e20, capCol, resCol, numRowMuxedBP*numCol*activityBPColRead, 2*numWriteOperationPerRow*numRow*activityRowWrite);
						if (numRowMuxedBP>1) {
							muxBP.CalculateLatency(colRamp, 0, numRowMuxedBP);
							muxDecoderBP.CalculateLatency(1e20, muxBP.capTgGateN*ceil(numRow/numRowMuxedBP), muxBP.capTgGateP*ceil(numRow/numRowMuxedBP), numRowMuxedBP, 0);
						}
						if (SARADC) {
							sarADCBP.CalculateLatency(numRowMuxedBP*numCol*activityBPColRead);
						} else {
							multilevelSenseAmpBP.CalculateLatency(columnResistance, numRowMuxedBP, numCol*activityBPColRead);
							if (avgWeightBit > 1) {
								multilevelSAEncoderBP.CalculateLatency(1e20, numRowMuxedBP*numCol*activityBPColRead);
							}
						}
						
						dffBP.CalculateLatency(1e20, numRowMuxedBP*numCol*activityBPColRead);
						adderBP.CalculateLatency(1e20, dffBP.capTgDrain, numRowMuxedBP*numCol*activityBPColRead);
						
						if (numCellPerSynapse > 1) {				 
							shiftAddBPWeight.CalculateLatency(numRowMuxedBP);							// There are numReadPulse times of shift-and-add
						}																								
						if (numReadPulseBP > 1) {
							shiftAddBPInput.CalculateLatency(ceil(numRowMuxedBP/numCellPerSynapse));	// There are numReadPulse times of shift-and-add
						}

						readLatencyAG += MAX(slSwitchMatrix.readLatency, ( ((numRowMuxedBP > 1)==true? (muxBP.readDynamicEnergy + muxDecoderBP.readDynamicEnergy):0) )/numReadPulseBP);
						readLatencyAG += multilevelSenseAmpBP.readLatency;
						readLatencyAG += multilevelSAEncoderBP.readLatency;
						readLatencyAG += adderBP.readLatency;
						readLatencyAG += dffBP.readLatency;
						readLatencyAG += shiftAddBPInput.readLatency + shiftAddBPWeight.readLatency;
						readLatencyAG += rowDelay/numReadPulseBP;
						readLatencyAG += sarADCBP.readLatency;
						
						readLatencyADC += multilevelSenseAmpBP.readLatency + multilevelSAEncoderBP.readLatency + sarADCBP.readLatency;
						readLatencyAccum += adderBP.readLatency + dffBP.readLatency + shiftAddBPInput.readLatency + shiftAddBPWeight.readLatency;
						readLatencyOther += MAX(slSwitchMatrix.readLatency, ( ((numRowMuxedBP > 1)==true? (muxBP.readDynamicEnergy + muxDecoderBP.readDynamicEnergy):0) )/numReadPulseBP) + rowDelay/numReadPulseBP;
					}
				}
				
			} else if (conventionalParallel) {
				double capBL = lengthCol * 0.2e-15/1e-6;
				int numWriteOperationPerRow = (int)ceil((double)numCol*activityColWrite/numWriteCellPerOperationNeuro);
				double colRamp = 0;
				double tau = (capCol)*(cell.resMemCellAvg/(numRow/2));
				colDelay = horowitz(tau, 0, 1e20, &colRamp);
				colDelay = tau * 0.2 * numColMuxed;  // assume the 15~20% voltage drop is enough for sensing
				
				if (cell.accessType == CMOS_access) {
					wlNewSwitchMatrix.CalculateLatency(1e20, capRow2, resRow, numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				} else {
					wlSwitchMatrix.CalculateLatency(1e20, capRow1, resRow, numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				}
				slSwitchMatrix.CalculateLatency(1e20, capCol, resCol, 0, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				if (numColMuxed>1) {
					mux.CalculateLatency(colRamp, 0, numColMuxed);
					muxDecoder.CalculateLatency(1e20, mux.capTgGateN*ceil(numCol/numColMuxed), mux.capTgGateP*ceil(numCol/numColMuxed), numColMuxed, 0);
				}
				if (SARADC) {
					sarADC.CalculateLatency(numColMuxed);
				} else {
					multilevelSenseAmp.CalculateLatency(columnResistance, numColMuxed, 1);
					multilevelSAEncoder.CalculateLatency(1e20, numColMuxed);
				}
				
				if (numCellPerSynapse > 1) {
					shiftAddWeight.CalculateLatency(numColMuxed);	
				}
				if (numReadPulse > 1) {
					shiftAddInput.CalculateLatency(ceil(numColMuxed/numCellPerSynapse));		
				}
				
				// Read
				readLatency = 0;
				readLatency += MAX(wlNewSwitchMatrix.readLatency + wlSwitchMatrix.readLatency, ( ((numColMuxed > 1)==true? (mux.readLatency+muxDecoder.readLatency):0) )/numReadPulse);
				readLatency += multilevelSenseAmp.readLatency;
				readLatency += multilevelSAEncoder.readLatency;
				readLatency += shiftAddInput.readLatency + shiftAddWeight.readLatency;
				readLatency += colDelay/numReadPulse;
				readLatency += sarADC.readLatency;
				
				readLatencyADC = multilevelSenseAmp.readLatency + multilevelSAEncoder.readLatency + sarADC.readLatency;
				readLatencyAccum = shiftAddInput.readLatency + shiftAddWeight.readLatency;
				readLatencyOther = MAX(wlNewSwitchMatrix.readLatency + wlSwitchMatrix.readLatency, ( ((numColMuxed > 1)==true? (mux.readLatency+muxDecoder.readLatency):0) )/numReadPulse) + colDelay/numReadPulse;

				// Write
				writeLatency = 0;
				writeLatencyArray = 0;
				writeLatencyArray += totalNumWritePulse * cell.writePulseWidth;
				writeLatency += MAX(wlNewSwitchMatrix.writeLatency + wlSwitchMatrix.writeLatency, slSwitchMatrix.writeLatency);
				writeLatency += writeLatencyArray;
				
				/* Transpose Peripheral for BP */
				if (trainingEstimation) {
					readLatencyAG = 0;
					if (layerNumber != 0) {
						double capRow = lengthRow * 0.2e-15/1e-6 + CalculateDrainCap(cell.widthAccessCMOS * tech.featureSize, NMOS, cell.widthInFeatureSize * tech.featureSize, tech) * numCol;
						tau = (capRow)*(cell.resMemCellAvg/(numCol/2));
						double rowDelay = tau * 0.2 * numRowMuxedBP;  // assume the 15~20% voltage drop is enough for sensing
						if (parallelBP) {
							slSwitchMatrix.CalculateLatency(1e20, capCol, resCol, numRowMuxedBP, 2*numWriteOperationPerRow*numRow*activityRowWrite);
							if (numRowMuxedBP>1) {
								muxBP.CalculateLatency(colRamp, 0, numRowMuxedBP);
								muxDecoderBP.CalculateLatency(1e20, muxBP.capTgGateN*ceil(numRow/numRowMuxedBP), muxBP.capTgGateP*ceil(numRow/numRowMuxedBP), numRowMuxedBP, 0);
							}
							if (SARADC) {
								sarADCBP.CalculateLatency(numRowMuxedBP);
							} else {
								multilevelSenseAmpBP.CalculateLatency(columnResistance, numRowMuxedBP, 1);
								multilevelSAEncoderBP.CalculateLatency(1e20, numRowMuxedBP);
							}
							
							if (numCellPerSynapse > 1) {
								shiftAddBPWeight.CalculateLatency(numRowMuxedBP);	
							}
							if (numReadPulseBP > 1) {
								shiftAddBPInput.CalculateLatency(ceil(numRowMuxedBP/numCellPerSynapse));		
							}
							
							readLatencyAG += MAX(slSwitchMatrix.readLatency, ( ((numRowMuxedBP > 1)==true? (muxBP.readDynamicEnergy + muxDecoderBP.readDynamicEnergy):0) )/numReadPulseBP);
							readLatencyAG += multilevelSenseAmpBP.readLatency;
							readLatencyAG += multilevelSAEncoderBP.readLatency;
							readLatencyAG += shiftAddBPInput.readLatency + shiftAddBPWeight.readLatency;
							readLatencyAG += rowDelay/numReadPulseBP;
							readLatencyAG += sarADCBP.readLatency;
							
							readLatencyADC += multilevelSenseAmpBP.readLatency + multilevelSAEncoderBP.readLatency + sarADCBP.readLatency;
							readLatencyAccum += shiftAddBPInput.readLatency + shiftAddBPWeight.readLatency;
							readLatencyOther += MAX(slSwitchMatrix.readLatency, ( ((numRowMuxedBP > 1)==true? (muxBP.readDynamicEnergy + muxDecoderBP.readDynamicEnergy):0) )/numReadPulseBP) + rowDelay/numReadPulseBP;
						} else {
							slSwitchMatrix.CalculateLatency(1e20, capCol, resCol, numRowMuxedBP*numCol*activityBPColRead, 2*numWriteOperationPerRow*numRow*activityRowWrite);
							if (numRowMuxedBP>1) {
								muxBP.CalculateLatency(colRamp, 0, numRowMuxedBP);
								muxDecoderBP.CalculateLatency(1e20, muxBP.capTgGateN*ceil(numRow/numRowMuxedBP), muxBP.capTgGateP*ceil(numRow/numRowMuxedBP), numRowMuxedBP, 0);
							}
							if (SARADC) {
								sarADCBP.CalculateLatency(numRowMuxedBP*numCol*activityBPColRead);
							} else {
								multilevelSenseAmpBP.CalculateLatency(columnResistance, numRowMuxedBP, numCol*activityBPColRead);
								if (avgWeightBit > 1) {
									multilevelSAEncoderBP.CalculateLatency(1e20, numRowMuxedBP*numCol*activityBPColRead);
								}
							}

							dffBP.CalculateLatency(1e20, numRowMuxedBP*numCol*activityBPColRead);
							adderBP.CalculateLatency(1e20, dffBP.capTgDrain, numRowMuxedBP*numCol*activityBPColRead);
							
							if (numCellPerSynapse > 1) {
								shiftAddBPWeight.CalculateLatency(numRowMuxedBP);	
							}
							if (numReadPulseBP > 1) {
								shiftAddBPInput.CalculateLatency(ceil(numRowMuxedBP/numCellPerSynapse));		
							}
							
							readLatencyAG += MAX(slSwitchMatrix.readLatency, ( ((numRowMuxedBP > 1)==true? (muxBP.readDynamicEnergy + muxDecoderBP.readDynamicEnergy):0) )/numReadPulseBP);
							readLatencyAG += multilevelSenseAmpBP.readLatency;
							readLatencyAG += multilevelSAEncoderBP.readLatency;
							readLatencyAG += adderBP.readLatency;
							readLatencyAG += dffBP.readLatency;
							readLatencyAG += shiftAddBPInput.readLatency + shiftAddBPWeight.readLatency;
							readLatencyAG += rowDelay/numReadPulseBP;
							readLatencyAG += sarADCBP.readLatency;
							
							readLatencyADC += multilevelSenseAmpBP.readLatency + multilevelSAEncoderBP.readLatency + sarADCBP.readLatency;
							readLatencyAccum += adderBP.readLatency + dffBP.readLatency + shiftAddBPInput.readLatency + shiftAddBPWeight.readLatency;
							readLatencyOther += MAX(slSwitchMatrix.readLatency, ( ((numRowMuxedBP > 1)==true? (muxBP.readDynamicEnergy + muxDecoderBP.readDynamicEnergy):0) )/numReadPulseBP) + rowDelay/numReadPulseBP;
						}
					}
				}
				
			} else if (BNNsequentialMode || XNORsequentialMode) {
				double capBL = lengthCol * 0.2e-15/1e-6;
				double colRamp = 0;
				double tau = (capCol)*(cell.resMemCellAvg);
				colDelay = horowitz(tau, 0, 1e20, &colRamp);	// Just to generate colRamp
				colDelay = tau * 0.2 * numColMuxed;  // assume the 15~20% voltage drop is enough for sensing
				int numWriteOperationPerRow = (int)ceil((double)numCol*activityColWrite/numWriteCellPerOperationNeuro);
				
				wlDecoder.CalculateLatency(1e20, capRow2, NULL, numRow*activityRowRead*numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				if (cell.accessType == CMOS_access) {
					wlNewDecoderDriver.CalculateLatency(wlDecoder.rampOutput, capRow2, resRow, numRow*activityRowRead*numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);	
				} else {
					wlDecoderDriver.CalculateLatency(wlDecoder.rampOutput, capRow1, capRow1, resRow, numRow*activityRowRead*numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				}
				slSwitchMatrix.CalculateLatency(1e20, capCol, resCol, 0, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				if (numColMuxed > 1) {
					mux.CalculateLatency(colRamp, 0, numColMuxed);
					muxDecoder.CalculateLatency(1e20, mux.capTgGateN*ceil(numCol/numColMuxed), mux.capTgGateP*ceil(numCol/numColMuxed), numColMuxed, 0);
				}
				rowCurrentSenseAmp.CalculateLatency(columnResistance, numColMuxed, numRow*activityRowRead);
				adder.CalculateLatency(1e20, dff.capTgDrain, numColMuxed*numRow*activityRowRead);
				dff.CalculateLatency(1e20, numColMuxed*numRow*activityRowRead);
				
				// Read
				readLatency = 0;
				readLatency += MAX(wlDecoder.readLatency + wlNewDecoderDriver.readLatency + wlDecoderDriver.readLatency, ( ((numColMuxed > 1)==true? (mux.readLatency+muxDecoder.readLatency):0) )/numReadPulse);
				readLatency += rowCurrentSenseAmp.readLatency;
				readLatency += adder.readLatency;
				readLatency += dff.readLatency;
				readLatency += colDelay/numReadPulse;
				
				// Write
				
				writeLatency = 0;
				writeLatencyArray = 0;
				writeLatencyArray += totalNumWritePulse * cell.writePulseWidth;
				writeLatency += MAX(wlDecoder.writeLatency + wlNewDecoderDriver.writeLatency + wlDecoderDriver.writeLatency, slSwitchMatrix.writeLatency);
				writeLatency += writeLatencyArray;
				
			} else if (BNNparallelMode || XNORparallelMode) {
				double capBL = lengthCol * 0.2e-15/1e-6;
				int numWriteOperationPerRow = (int)ceil((double)numCol*activityColWrite/numWriteCellPerOperationNeuro);
				double colRamp = 0;
				double tau = (capCol)*(cell.resMemCellAvg/(numRow/2));
				colDelay = horowitz(tau, 0, 1e20, &colRamp);
				colDelay = tau * 0.2 * numColMuxed;  // assume the 15~20% voltage drop is enough for sensing
				
				if (cell.accessType == CMOS_access) {
					wlNewSwitchMatrix.CalculateLatency(1e20, capRow2, resRow, numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				} else {
					wlSwitchMatrix.CalculateLatency(1e20, capRow1, resRow, numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				}
				slSwitchMatrix.CalculateLatency(1e20, capCol, resCol, 0, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				if (numColMuxed > 1) {
					mux.CalculateLatency(colRamp, 0, numColMuxed);
					muxDecoder.CalculateLatency(1e20, mux.capTgGateN*ceil(numCol/numColMuxed), mux.capTgGateP*ceil(numCol/numColMuxed), numColMuxed, 0);
				}
				if (SARADC) {
					sarADC.CalculateLatency(numColMuxed);
				} else {
					multilevelSenseAmp.CalculateLatency(columnResistance, numColMuxed, 1);
					multilevelSAEncoder.CalculateLatency(1e20, numColMuxed);
				}

				// Read
				readLatency = 0;
				readLatency += MAX(wlNewSwitchMatrix.readLatency + wlSwitchMatrix.readLatency, ( ((numColMuxed > 1)==true? (mux.readLatency+muxDecoder.readLatency):0) )/numReadPulse);
				readLatency += multilevelSenseAmp.readLatency;
				readLatency += multilevelSAEncoder.readLatency;
				readLatency += colDelay/numReadPulse;
				readLatency += sarADC.readLatency;
				// Write
				
				writeLatency = 0;
				writeLatencyArray = 0;
				writeLatencyArray += totalNumWritePulse * cell.writePulseWidth;
				writeLatency += MAX(wlNewSwitchMatrix.writeLatency + wlSwitchMatrix.writeLatency, slSwitchMatrix.writeLatency);
				writeLatency += writeLatencyArray;
				
			} else {
				double capBL = lengthCol * 0.2e-15/1e-6;
				int numWriteOperationPerRow = (int)ceil((double)numCol*activityColWrite/numWriteCellPerOperationNeuro);
				double colRamp = 0;
				double tau = (capCol)*(cell.resMemCellAvg/(numRow/2));
				colDelay = horowitz(tau, 0, 1e20, &colRamp);
				colDelay = tau * 0.2 * numColMuxed;  // assume the 15~20% voltage drop is enough for sensing
				
				if (cell.accessType == CMOS_access) {
					wlNewSwitchMatrix.CalculateLatency(1e20, capRow2, resRow, numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				} else {
					wlSwitchMatrix.CalculateLatency(1e20, capRow1, resRow, numColMuxed, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				}
				slSwitchMatrix.CalculateLatency(1e20, capCol, resCol, 0, 2*numWriteOperationPerRow*numRow*activityRowWrite);
				if (numColMuxed > 1) {
					mux.CalculateLatency(colRamp, 0, numColMuxed);
					muxDecoder.CalculateLatency(1e20, mux.capTgGateN*ceil(numCol/numColMuxed), mux.capTgGateP*ceil(numCol/numColMuxed), numColMuxed, 0);
				}
				if (SARADC) {
					sarADC.CalculateLatency(numColMuxed);
				} else {
					multilevelSenseAmp.CalculateLatency(columnResistance, numColMuxed, 1);
					multilevelSAEncoder.CalculateLatency(1e20, numColMuxed);
				}
				if (numCellPerSynapse > 1) {
					shiftAddWeight.CalculateLatency(numColMuxed);	
				}
				if (numReadPulse > 1) {
					shiftAddInput.CalculateLatency(ceil(numColMuxed/numCellPerSynapse));		
				}

				// Read
				readLatency = 0;
				readLatency += MAX(wlNewSwitchMatrix.readLatency + wlSwitchMatrix.readLatency, ( ((numColMuxed > 1)==true? (mux.readLatency+muxDecoder.readLatency):0) )/numReadPulse);
				readLatency += multilevelSenseAmp.readLatency;
				readLatency += multilevelSAEncoder.readLatency;
				readLatency += shiftAddInput.readLatency + shiftAddWeight.readLatency;
				readLatency += colDelay/numReadPulse;
				readLatency += sarADC.readLatency;
				// Write
				
				writeLatency = 0;
				writeLatencyArray = 0;
				writeLatencyArray += totalNumWritePulse * cell.writePulseWidth;
				writeLatency += MAX(wlNewSwitchMatrix.writeLatency + wlSwitchMatrix.writeLatency, slSwitchMatrix.writeLatency);
				writeLatency += writeLatencyArray;
				
			}
		}