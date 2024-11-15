else if (cell.memCellType == Type::RRAM || cell.memCellType == Type::FeFET) {
			// Array only
			heightArray = lengthCol;
			widthArray = lengthRow;
			areaArray = heightArray * widthArray;
			
			if (conventionalSequential) {  
				wlDecoder.CalculateArea(heightArray, NULL, NONE);
				if (cell.accessType == CMOS_access) {
					wlNewDecoderDriver.CalculateArea(heightArray, NULL, NONE);
				} else {
					wlDecoderDriver.CalculateArea(heightArray, NULL, NONE);
				}
				slSwitchMatrix.CalculateArea(NULL, widthArray, NONE);
				
				if (numColMuxed > 1) {
					mux.CalculateArea(NULL, widthArray, NONE);
					muxDecoder.CalculateArea(NULL, NULL, NONE);
					double minMuxHeight = MAX(muxDecoder.height, mux.height);
					mux.CalculateArea(minMuxHeight, widthArray, OVERRIDE);
				}
				if (SARADC) {
					sarADC.CalculateUnitArea();
					sarADC.CalculateArea(NULL, widthArray, NONE);
				} else {
					multilevelSenseAmp.CalculateArea(NULL, widthArray, NONE);
					if (avgWeightBit > 1) {
						multilevelSAEncoder.CalculateArea(NULL, widthArray, NONE);
					}
				}

				dff.CalculateArea(NULL, widthArray, NONE);
				adder.CalculateArea(NULL, widthArray, NONE);
				if (numReadPulse > 1) {
					shiftAddInput.CalculateArea(NULL, widthArray, NONE);
				}
				if (numCellPerSynapse > 1) {
					shiftAddWeight.CalculateArea(NULL, widthArray, NONE);
				}
				height = slSwitchMatrix.height + heightArray + mux.height + multilevelSenseAmp.height + multilevelSAEncoder.height + adder.height + dff.height + shiftAddInput.height + shiftAddWeight.height + sarADC.height;
				width = MAX(wlDecoder.width + wlNewDecoderDriver.width + wlDecoderDriver.width, muxDecoder.width) + widthArray;
				usedArea = areaArray + wlDecoder.area + wlDecoderDriver.area + wlNewDecoderDriver.area + slSwitchMatrix.area + mux.area + multilevelSenseAmp.area + multilevelSAEncoder.area + muxDecoder.area + adder.area + dff.area + shiftAddInput.area + shiftAddWeight.area + sarADC.area;
				
				areaADC = multilevelSenseAmp.area + multilevelSAEncoder.area + sarADC.area;
				areaAccum = adder.area + dff.area + shiftAddInput.area + shiftAddWeight.area;
				areaOther = wlDecoder.area + wlNewDecoderDriver.area + wlDecoderDriver.area + slSwitchMatrix.area + mux.area + muxDecoder.area;
				
				/* Transpose Peripheral for BP */
				/* TRAINING -> NOT IMPORTANT? */
				if (trainingEstimation) {
					if (numRowMuxedBP>1) {
						muxBP.CalculateArea(heightArray, NULL, NONE);
						muxDecoderBP.CalculateArea(NULL, NULL, NONE);
						double minMuxWidth = MAX(muxDecoderBP.width, muxBP.width);
						muxBP.CalculateArea(heightArray, minMuxWidth, OVERRIDE);
					}
					if (SARADC) {
						sarADCBP.CalculateUnitArea();
						sarADCBP.CalculateArea(heightArray, NULL, NONE);
					} else {
						multilevelSenseAmpBP.CalculateArea(heightArray, NULL, NONE);
						if (avgWeightBit > 1) {
							multilevelSAEncoderBP.CalculateArea(heightArray, NULL, NONE);
						}
					}

					dffBP.CalculateArea(heightArray, NULL, NONE);
					adderBP.CalculateArea(heightArray, NULL, NONE);
					if (numReadPulseBP > 1) {
						shiftAddBPInput.CalculateArea(heightArray, NULL, NONE);
					}
					if (numCellPerSynapse > 1) {
						shiftAddBPWeight.CalculateArea(heightArray, NULL, NONE);
					}
					width += muxBP.width + multilevelSenseAmpBP.width + multilevelSAEncoderBP.width + dffBP.width + adderBP.width + shiftAddBPInput.width + shiftAddBPWeight.width + sarADCBP.width;
					areaAG = muxBP.area + muxDecoderBP.area + multilevelSenseAmpBP.area + multilevelSAEncoderBP.area + dffBP.area + adderBP.area + shiftAddBPInput.area + shiftAddBPWeight.area + sarADCBP.area;
					usedArea += areaAG;
					areaADC += multilevelSenseAmpBP.area + multilevelSAEncoderBP.area + sarADCBP.area;
					areaAccum += dffBP.area + adderBP.area + shiftAddBPInput.area + shiftAddBPWeight.area;
					areaOther += muxBP.area + muxDecoderBP.area;
					
				}
				
				area = height * width;
				emptyArea = area - usedArea;
				
			} else if (conventionalParallel) { 
				if (cell.accessType == CMOS_access) {
					wlNewSwitchMatrix.CalculateArea(heightArray, NULL, NONE);
				} else {
					wlSwitchMatrix.CalculateArea(heightArray, NULL, NONE);
				}
				slSwitchMatrix.CalculateArea(NULL, widthArray, NONE);
				if (numColMuxed > 1) {
					mux.CalculateArea(NULL, widthArray, NONE);
					muxDecoder.CalculateArea(NULL, NULL, NONE);
					double minMuxHeight = MAX(muxDecoder.height, mux.height);
					mux.CalculateArea(minMuxHeight, widthArray, OVERRIDE);
				}
				if (SARADC) {
					sarADC.CalculateUnitArea();
					sarADC.CalculateArea(NULL, widthArray, NONE);
				} else {
					multilevelSenseAmp.CalculateArea(NULL, widthArray, NONE);
					multilevelSAEncoder.CalculateArea(NULL, widthArray, NONE);
				}
				
				if (numReadPulse > 1) {
					shiftAddInput.CalculateArea(NULL, widthArray, NONE);
				}
				if (numCellPerSynapse > 1) {
					shiftAddWeight.CalculateArea(NULL, widthArray, NONE);
				}
				
				height = slSwitchMatrix.height + heightArray + mux.height + multilevelSenseAmp.height + multilevelSAEncoder.height + shiftAddInput.height + shiftAddWeight.height + sarADC.height;
				width = MAX(wlNewSwitchMatrix.width + wlSwitchMatrix.width, muxDecoder.width) + widthArray;
				usedArea = areaArray + wlSwitchMatrix.area + wlNewSwitchMatrix.area + slSwitchMatrix.area + mux.area + multilevelSenseAmp.area + muxDecoder.area + multilevelSAEncoder.area + shiftAddInput.area + shiftAddWeight.area + sarADC.area;
				
				areaADC = multilevelSenseAmp.area + multilevelSAEncoder.area + sarADC.area;
				areaAccum = shiftAddInput.area + shiftAddWeight.area;
				areaOther = wlNewSwitchMatrix.area + wlSwitchMatrix.area + slSwitchMatrix.area + mux.area + muxDecoder.area;
				
				/* Transpose Peripheral for BP */
				/* TRAINING -> NOT IMPORTANT? */	
				if (trainingEstimation) {
					if (numRowMuxedBP>1) {
						muxBP.CalculateArea(heightArray, NULL, NONE);
						muxDecoderBP.CalculateArea(NULL, NULL, NONE);
						double minMuxWidth = MAX(muxDecoderBP.width, muxBP.width);
						muxBP.CalculateArea(heightArray, minMuxWidth, OVERRIDE);
					}
					
					if (parallelBP) {
						if (SARADC) {
							sarADCBP.CalculateUnitArea();
							sarADCBP.CalculateArea(heightArray, NULL, NONE);
						} else {
							multilevelSenseAmpBP.CalculateArea(heightArray, NULL, NONE);
							multilevelSAEncoderBP.CalculateArea(heightArray, NULL, NONE);
						}

						if (numReadPulseBP > 1) {
							shiftAddBPInput.CalculateArea(heightArray, NULL, NONE);
						}
						if (numCellPerSynapse > 1) {
							shiftAddBPWeight.CalculateArea(heightArray, NULL, NONE);
						}
						width += muxBP.width + multilevelSenseAmpBP.width + multilevelSAEncoderBP.width + shiftAddBPInput.width + shiftAddBPWeight.width + sarADCBP.width;
						areaAG = muxBP.area + muxDecoderBP.area + multilevelSenseAmpBP.area + multilevelSAEncoderBP.area + shiftAddBPInput.area + shiftAddBPWeight.area + sarADCBP.area;
						usedArea += areaAG;
						areaADC += multilevelSenseAmpBP.area + multilevelSAEncoderBP.area + sarADCBP.area;
						areaAccum += shiftAddBPInput.area + shiftAddBPWeight.area;
						areaOther += muxBP.area + muxDecoderBP.area;
					} else {
						if (SARADC) {
							sarADCBP.CalculateUnitArea();
							sarADCBP.CalculateArea(heightArray, NULL, NONE);
						} else {
							multilevelSenseAmpBP.CalculateArea(heightArray, NULL, NONE);
							if (avgWeightBit > 1) {
								multilevelSAEncoderBP.CalculateArea(heightArray, NULL, NONE);
							}
						}

						dffBP.CalculateArea(heightArray, NULL, NONE);
						adderBP.CalculateArea(heightArray, NULL, NONE);
						
						if (numReadPulseBP > 1) {
							shiftAddBPInput.CalculateArea(heightArray, NULL, NONE);
						}
						if (numCellPerSynapse > 1) {
							shiftAddBPWeight.CalculateArea(heightArray, NULL, NONE);
						}
						width += muxBP.width + multilevelSenseAmpBP.width + multilevelSAEncoderBP.width + dffBP.width + adderBP.width + shiftAddBPInput.width + shiftAddBPWeight.width + sarADCBP.width;
						areaAG = muxBP.area + muxDecoderBP.area + multilevelSenseAmpBP.area + multilevelSAEncoderBP.area + dffBP.area + adderBP.area + shiftAddBPInput.area + shiftAddBPWeight.area + sarADCBP.area;
						usedArea += areaAG;
						areaADC += multilevelSenseAmpBP.area + multilevelSAEncoderBP.area + sarADCBP.area;
						areaAccum += dffBP.area + adderBP.area + shiftAddBPInput.area + shiftAddBPWeight.area;
						areaOther += muxBP.area + muxDecoderBP.area;
					}
				}
				
				
				
				
				
				area = height * width;
				emptyArea = area - usedArea;
				
				
				
			} else if (BNNsequentialMode || XNORsequentialMode) {       
				wlDecoder.CalculateArea(heightArray, NULL, NONE);
				if (cell.accessType == CMOS_access) {
					wlNewDecoderDriver.CalculateArea(heightArray, NULL, NONE);
				} else {
					wlDecoderDriver.CalculateArea(heightArray, NULL, NONE);
				}
				slSwitchMatrix.CalculateArea(NULL, widthArray, NONE);
				if (numColMuxed > 1) {
					mux.CalculateArea(NULL, widthArray, NONE);
					muxDecoder.CalculateArea(NULL, NULL, NONE);
					double minMuxHeight = MAX(muxDecoder.height, mux.height);
					mux.CalculateArea(minMuxHeight, widthArray, OVERRIDE);
				}
				rowCurrentSenseAmp.CalculateUnitArea();
				rowCurrentSenseAmp.CalculateArea(widthArray);
				
				dff.CalculateArea(NULL, widthArray, NONE);
				adder.CalculateArea(NULL, widthArray, NONE);
				
				height = slSwitchMatrix.height + heightArray + mux.height + rowCurrentSenseAmp.height + adder.height + dff.height;
				width = MAX(wlDecoder.width + wlNewDecoderDriver.width + wlDecoderDriver.width, muxDecoder.width) + widthArray;
				area = height * width;
				usedArea = areaArray + wlDecoder.area + wlDecoderDriver.area + wlNewDecoderDriver.area + slSwitchMatrix.area + mux.area + rowCurrentSenseAmp.area + muxDecoder.area + adder.area + dff.area;
				emptyArea = area - usedArea;
			} else if (BNNparallelMode || XNORparallelMode) {      
				if (cell.accessType == CMOS_access) {
					wlNewSwitchMatrix.CalculateArea(heightArray, NULL, NONE);
				} else {
					wlSwitchMatrix.CalculateArea(heightArray, NULL, NONE);
				}
				slSwitchMatrix.CalculateArea(NULL, widthArray, NONE);
				if (numColMuxed > 1) {
					mux.CalculateArea(NULL, widthArray, NONE);
					muxDecoder.CalculateArea(NULL, NULL, NONE);
					double minMuxHeight = MAX(muxDecoder.height, mux.height);
					mux.CalculateArea(minMuxHeight, widthArray, OVERRIDE);
				}
				if (SARADC) {
					sarADC.CalculateUnitArea();
					sarADC.CalculateArea(NULL, widthArray, NONE);
				} else {
					multilevelSenseAmp.CalculateArea(NULL, widthArray, NONE);
					multilevelSAEncoder.CalculateArea(NULL, widthArray, NONE);
				}
				
				height = slSwitchMatrix.height + heightArray + mux.height + multilevelSenseAmp.height + multilevelSAEncoder.height + sarADC.height;
				width = MAX(wlNewSwitchMatrix.width + wlSwitchMatrix.width, muxDecoder.width) + widthArray;
				area = height * width;
				usedArea = areaArray + wlSwitchMatrix.area + wlNewSwitchMatrix.area + slSwitchMatrix.area + mux.area + multilevelSenseAmp.area + muxDecoder.area + multilevelSAEncoder.area + sarADC.area;
				emptyArea = area - usedArea;
			} else {   
				if (cell.accessType == CMOS_access) {
					wlNewSwitchMatrix.CalculateArea(heightArray, NULL, NONE);
				} else {
					wlSwitchMatrix.CalculateArea(heightArray, NULL, NONE);
				}
				slSwitchMatrix.CalculateArea(NULL, widthArray, NONE);
				if (numColMuxed > 1) {
					mux.CalculateArea(NULL, widthArray, NONE);
					muxDecoder.CalculateArea(NULL, NULL, NONE);
					double minMuxHeight = MAX(muxDecoder.height, mux.height);
					mux.CalculateArea(minMuxHeight, widthArray, OVERRIDE);
				}
				if (SARADC) {
					sarADC.CalculateUnitArea();
					sarADC.CalculateArea(NULL, widthArray, NONE);
				} else {
					multilevelSenseAmp.CalculateArea(NULL, widthArray, NONE);
					multilevelSAEncoder.CalculateArea(NULL, widthArray, NONE);
				}
				
				height = slSwitchMatrix.height + heightArray + mux.height + multilevelSenseAmp.height + multilevelSAEncoder.height + sarADC.height;
				width = MAX(wlNewSwitchMatrix.width + wlSwitchMatrix.width, muxDecoder.width) + widthArray;
				area = height * width;
				usedArea = areaArray + wlSwitchMatrix.area + wlNewSwitchMatrix.area + slSwitchMatrix.area + mux.area + multilevelSenseAmp.area + muxDecoder.area + multilevelSAEncoder.area + sarADC.area;
				emptyArea = area - usedArea;
			}
			
		} 