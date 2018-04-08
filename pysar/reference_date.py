#!/usr/bin/env python3
############################################################
# Program is part of PySAR v2.0                            #
# Copyright(c) 2013, Zhang Yunjun, Heresh Fattahi          #
# Author:  Zhang Yunjun, Heresh Fattahi                    #
############################################################

import os, sys
import argparse
import shutil
import string
import h5py
import numpy as np
import matplotlib as mpl; mpl.use('Agg')
import matplotlib.pyplot as plt
from pysar.utils import readfile, datetime as ptime, utils as ut, network as pnet


##################################################################
def ref_date_attribute(atr_in, ref_date, date_list):
    '''Update attribute dictionary for reference date'''
    ref_date = ptime.yyyymmdd(ref_date)
    date_list = ptime.yyyymmdd(date_list)
    ref_index = date_list.index(ref_date)

    atr = dict()
    for key, value in iter(atr_in.items()):
        atr[key] = str(value)

    # Update ref_date
    atr['REF_DATE'] = ref_date
    print('update ref_date')

    # Update Bperp time series
    try:
        pbase = np.array([float(i) for i in atr['P_BASELINE_TIMESERIES'].split()])
        pbase -= pbase[ref_index]
        pbaseStr = str(pbase.tolist()).translate(str.maketrans('[],','   ')).strip()
        atr['P_BASELINE_TIMESERIES'] = pbaseStr
        print('update P_BASELINE_TIMESERIES')
    except:
        pass

    try:
        pbase_top    = np.array([float(i) for i in atr['P_BASELINE_TOP_TIMESERIES'].split()])
        pbase_bottom = np.array([float(i) for i in atr['P_BASELINE_BOTTOM_TIMESERIES'].split()])
        pbase_top    -= pbase_top[ref_index]
        pbase_bottom -= pbase_bottom[ref_index]
        pbase_topStr = str(pbase_top.tolist()).translate(str.maketrans('[],','   ')).strip()
        pbase_bottomStr = str(pbase_bottom.tolist()).translate(str.maketrans('[],','   ')).strip()
        atr['P_BASELINE_TOP_TIMESERIES']    = pbase_topStr
        atr['P_BASELINE_BOTTOM_TIMESERIES'] = pbase_bottomStr
        print('update P_BASELINE_TOP/BOTTOM_TIMESERIES')
    except:
        pass

    return atr


def ref_date_file(inFile, ref_date, outFile=None):
    '''Change input file reference date to a different one.'''
    if not outFile:
        outFile = os.path.splitext(inFile)[0]+'_refDate.h5'

    # Input file type 
    atr = readfile.read_attribute(inFile)
    k = atr['FILE_TYPE']
    if not k in ['timeseries']:
        print('Input file is '+k+', only timeseries is supported.')
        return None

    # Input reference date
    h5 = h5py.File(inFile, 'r')
    date_list = sorted(h5[k].keys())
    h5.close()
    date_num = len(date_list)
    try:    ref_date_orig = atr['REF_DATE']
    except: ref_date_orig = date_list[0]

    ref_date = ptime.yyyymmdd(ref_date)
    print('input reference date: '+ref_date)
    if not ref_date in date_list:
        print('Input reference date was not found!\nAll dates available: '+str(date_list))
        return None
    if ref_date == ref_date_orig:
        print('Same reference date chosen as existing reference date.')
        print('Copy %s to %s' % (inFile, outFile))
        shutil.copy2(inFile, outFile)
        return outFile

    # Referencing in time
    h5 = h5py.File(inFile, 'r')
    ref_data = h5[k].get(ref_date)[:]

    print('writing >>> '+outFile)
    h5out = h5py.File(outFile,'w')
    group = h5out.create_group(k)
    prog_bar = ptime.progress_bar(maxValue=date_num)
    for i in range(date_num):
        date = date_list[i]
        data = h5[k].get(date)[:]
        dset = group.create_dataset(date, data=data-ref_data)
        prog_bar.update(i+1, suffix=date)
    prog_bar.close()
    h5.close()

    ## Update attributes
    atr = ref_date_attribute(atr, ref_date, date_list)
    for key,value in iter(atr.items()):
        group.attrs[key] = str(value)
    h5out.close()

    return outFile


def read_template2inps(templateFile, inps=None):
    '''Update inps with options from templateFile'''
    if not inps:
        inps = cmdLineParse()

    template = readfile.read_template(templateFile)

    key = 'pysar.reference.date'
    if key in template.keys():
        inps.ref_date = template[key]

    prefix = 'pysar.residualStd.'
    key = prefix+'maskFile'
    if key in template.keys():
        value = template[key]
        if value == 'auto':
            inps.mask_file = 'maskTempCoh.h5'
        elif value == 'no':
            inps.mask_file = None
        else:
            inps.mask_file = value

    key = prefix+'ramp'
    if key in template.keys():
        value = template[key]
        if value == 'auto':
            inps.ramp_type = 'quadratic'
        else:
            inps.ramp_type = 'no'

    return inps


##################################################################
TEMPLATE='''
## 8.1 Phase Residual Root Mean Square
## calculate the deramped Root Mean Square (RMS) for each epoch of timeseries residual from DEM error inversion
## To get rid of long wavelength component in space, a ramp is removed for each epoch.
## Recommendation: quadratic for whole image, plane for local/small area
pysar.residualRms.maskFile        = auto  #[file name / no], auto for maskTempCoh.h5, mask for ramp estimation
pysar.residualRms.ramp            = auto  #[quadratic / plane / no], auto for quadratic
pysar.residualRms.threshold       = auto  #[0.0-inf], auto for 0.02, minimum RMS in meter for exclude date(s)
pysar.residualRms.saveRefDate     = auto  #[yes / no], auto for yes, save date with min RMS to txt/pdf file.
pysar.residualRms.saveExcludeDate = auto  #[yes / no], auto for yes, save date(s) with RMS > minStd to txt/pdf file.


## 9. Reference in Time
## reference all timeseries to one date in time
## auto - choose date with minimum residual RMS using value from step 8.1
## no   - do not change reference date, keep the defaut one (1st date usually) and skip this step
pysar.reference.date = auto   #[auto / reference_date.txt / 20090214 / no]
'''

EXAMPLE='''example:
  reference_date.py timeseries_ECMWF_demErr.h5  --ref-date 20050107
  reference_date.py timeseries_ECMWF_demErr.h5  --ref-date auto
  reference_date.py timeseries_ECMWF_demErr.h5  --template KujuAlosAT422F650.template
'''

def cmdLineParse():
    parser = argparse.ArgumentParser(description='Change reference date of timeseries.',\
                                     formatter_class=argparse.RawTextHelpFormatter,\
                                     epilog=EXAMPLE)

    parser.add_argument('timeseries_file', help='Timeseries File')
    parser.add_argument('--ref-date', dest='ref_date', default='auto',\
                        help='reference date or method, default: auto. e.g.\n'+\
                             '20101120\n'+\
                             'reference_date.txt - text file with date in YYYYMMDD format in it\n'+\
                             'auto               - choose date with min residual standard deviation')
    parser.add_argument('--template', dest='template_file',\
                        help='template file with options below:\n'+TEMPLATE+'\n')

    auto = parser.add_argument_group('Auto referencing in time based on max phase residual coherence')
    auto.add_argument('--residual-file', dest='resid_file',\
                      help='timeseries of phase residual file from DEM error inversion.\n'+\
                           'Deramped Residual RMS')
    auto.add_argument('--deramp', dest='ramp_type', default='quadratic',\
                      help='ramp type to remove for each epoch from phase residual\n'+\
                           'default: quadratic\n'+\
                           'no - do not remove ramp')
    auto.add_argument('--mask', dest='mask_file', default='maskTempCoh.h5',\
                      help='mask file used for ramp estimation\n'+'default: maskTempCoh.h5')
    parser.add_argument('-o','--outfile', help='Output file name.')

    inps = parser.parse_args()
    return inps


##################################################################
def main(argv):
    inps = cmdLineParse()
    if inps.template_file:
        inps = read_template2inps(inps.template_file)

    if inps.ref_date == 'no':
        print('No reference date input, skip this step.')
        return inps.timeseries_file

    elif inps.ref_date.lower() in ['auto']:
        print('------------------------------------------------------------')
        print('auto choose reference date based on minimum residual RMS')
        if not inps.resid_file:
            inps.resid_file = os.path.join(os.path.dirname(inps.timeseries_file), 'timeseriesResidual.h5')
        rms_list, date_list = ut.get_residual_rms(inps.resid_file, inps.mask_file, inps.ramp_type)[0:2]
        ref_idx = np.argmin(rms_list)
        inps.ref_date = date_list[ref_idx]
        print('date with minimum residual RMS: %s - %.4f' % (inps.ref_date, rms_list[ref_idx]))
        print('------------------------------------------------------------')

    elif os.path.isfile(inps.ref_date):
        print('read reference date from file: '+inps.ref_date)
        inps.ref_date = ptime.read_date_list(inps.ref_date)[0]

    # Referencing input file
    if not inps.outfile:
        inps.outfile = os.path.splitext(inps.timeseries_file)[0]+'_refDate.h5'
    try:    ref_date_comp = readfile.read_attribute(inps.outfile)['REF_DATE']
    except: ref_date_comp = readfile.read_attribute(inps.timeseries_file)['REF_DATE']
    if inps.ref_date != ref_date_comp or ut.update_file(inps.outfile, inps.timeseries_file):
        inps.outfile = ref_date_file(inps.timeseries_file, inps.ref_date, inps.outfile)

    return inps.outfile


##################################################################
if __name__ == '__main__':
    main(sys.argv[1:])


