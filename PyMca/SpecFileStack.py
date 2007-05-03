#/*##########################################################################
# Copyright (C) 2004-2007 European Synchrotron Radiation Facility
#
# This file is part of the PyMCA X-ray Fluorescence Toolkit developed at
# the ESRF by the Beamline Instrumentation Software Support (BLISS) group.
#
# This toolkit is free software; you can redistribute it and/or modify it 
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option) 
# any later version.
#
# PyMCA is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# PyMCA; if not, write to the Free Software Foundation, Inc., 59 Temple Place,
# Suite 330, Boston, MA 02111-1307, USA.
#
# PyMCA follows the dual licensing model of Trolltech's Qt and Riverbank's PyQt
# and cannot be used as a free plugin for a non-free program. 
#
# Please contact the ESRF industrial unit (industry@esrf.fr) if this license 
# is a problem to you.
#############################################################################*/
import DataObject
import specfilewrapper as specfile
import SpecFileDataSource
import numpy.oldnumeric as Numeric
import sys
import os
SOURCE_TYPE = "SpecFileStack"
DEBUG = 0

X_AXIS=0
Y_AXIS=1
Z_AXIS=2

class SpecFileStack(DataObject.DataObject):
    def __init__(self, filelist = None):
        DataObject.DataObject.__init__(self)
        self.incrProgressBar=0
        self.__keyList = []
        if filelist is not None:
            if type(filelist) != type([]):
                filelist = [filelist]
            if len(filelist) == 1:
                self.loadIndexedStack(filelist)
            else:
                self.loadFileList(filelist)

    def loadFileList(self, filelist, fileindex=0):
        if type(filelist) == type(''):filelist = [filelist]
        self.__keyList = []
        self.sourceName = filelist
        self.__indexedStack = True
        self.sourceType = SOURCE_TYPE
        self.info = {}
        self.nbFiles=len(filelist)

        #read first file
        #get information
        tempInstance=SpecFileDataSource.SpecFileDataSource(filelist[0])
        keylist = tempInstance.getSourceInfo()['KeyList']
        nscans = len(keylist)        #that is the number of scans
        nmca = 0
        for key in keylist:
            info = tempInstance.getKeyInfo(key)
            numberofdetectors = info['NbMcaDet']
            numberofmca       = info['NbMca']
            scantype          = info["ScanType"]
            if numberofmca:
                nmca += numberofmca
        #get last mca of first point
        key = "%s.1.%s" % (keylist[-1], numberofmca)
        dataObject = tempInstance._getMcaData(key)
        self.info.update(dataObject.info)
        arrRet = dataObject.data
        self.onBegin(self.nbFiles*numberofmca/numberofdetectors)
        
        self.data = Numeric.zeros((self.nbFiles,
                                   numberofmca/numberofdetectors,
                                   arrRet.shape[0]),
                                   arrRet.dtype.char)
        self.incrProgressBar= 0
        if info['NbMcaDet'] > 1:
            iterlist = range(info['NbMcaDet'],info['NbMca'],info['NbMcaDet']) 
        else:
            iterlist = [1]
        filecounter         = 0
        for tempFileName in filelist:
            tempInstance=specfile.Specfile(tempFileName)
            scan = tempInstance.select(keylist[-1])
            for i in iterlist:
                #mcadata = scan_obj.mca(i)
                self.data[filecounter,
                          0,
                          :] = scan.mca(i)[:]
                self.incrProgressBar += 1
                self.onProgress(self.incrProgressBar)
            filecounter += 1
        self.onEnd()

        """
        # Scan types
        # ----------    
        #SF_EMPTY       = 0        # empty scan
        #SF_SCAN        = 1        # non-empty scan
        #SF_MESH        = 2        # mesh scan
        #SF_MCA         = 4        # single mca
        #SF_NMCA        = 8        # multi mca (more than 1 mca per acq)

        case = None
        if scantype == (SpecFileDataSource.SF_MESH + \
                        SpecFileDataSource.SF_MCA):
            # SINGLE MESH + SINGLE MCA
            # nfiles  = 1
            # nscans  = 1
            # nmca    = 1
            # there is a danger if it can be considered an indexed file ...
            pass

        elif scantype == (SpecFileDataSource.SF_MESH + \
                        SpecFileDataSource.SF_NMCA):
            # SINGLE MESH + MULTIPLE MCA
            # nfiles  = 1
            # nscans  = 1
            # nmca    > 1
            # there is a danger if it can be considered an indexed file ...
            #for the time being I take last mca
            pass

        elif scantype == (SpecFileDataSource.SF_SCAN+ \
                          SpecFileDataSource.SF_MCA):
            #Assumed scans containing always 1 detector
            pass
        
        elif scantype == (SpecFileDataSource.SF_MCA):
            #Assumed scans containing always 1 detector
            pass

        elif scantype == (SpecFileDataSource.SF_SCAN+ \
                          SpecFileDataSource.SF_NMCA):
            #Assumed scans containing the same number of detectors
            #for the time being I take last mca
            pass
        
        elif scantype == (SpecFileDataSource.SF_NMCA):
            #Assumed scans containing the same number of detectors
            #for the time being I take last mca
            pass

        else:
            raise "ValueError", "Unhandled scan type = %s" % scantype

        """

        self.__nFiles         = self.nbFiles
        self.__nImagesPerFile = 1
        shape = self.data.shape
        for i in range(len(shape)):
            key = 'Dim_%d' % (i+1,)
            self.info[key] = shape[i]
        self.info["SourceType"] = SOURCE_TYPE
        self.info["SourceName"] = self.sourceName
        self.info["Size"]       = self.__nFiles * self.__nImagesPerFile
        self.info["NumberOfFiles"] = self.__nFiles * 1
        self.info["FileIndex"] = fileindex

    def onBegin(self, n):
        pass

    def onProgress(self, n):
        pass

    def onEnd(self):
        pass

    def loadIndexedStack(self,filename,begin=None,end=None, skip = None, fileindex=0):
        #if begin is None: begin = 0
        if type(filename) == type([]):
            filename = filename[0]
        if not os.path.exists(filename):
            raise "IOError","File %s does not exists" % filename
        name = os.path.basename(filename)
        n = len(name)
        i = 1
        numbers = ['0', '1', '2', '3', '4', '5',
                   '6', '7', '8','9']
        while (i <= n):
            c = name[n-i:n-i+1]
            if c in ['0', '1', '2',
                                '3', '4', '5',
                                '6', '7', '8',
                                '9']:
                break
            i += 1
        suffix = name[n-i+1:]
        if len(name) == len(suffix):
            #just one file, one should use standard widget
            #and not this one.
            self.loadFileList(filename, fileindex=fileindex)
        else:
            nchain = []
            while (i<=n):
                c = name[n-i:n-i+1]
                if c not in ['0', '1', '2',
                                    '3', '4', '5',
                                    '6', '7', '8',
                                    '9']:
                    break
                else:
                    nchain.append(c)
                i += 1
            number = ""
            nchain.reverse()
            for c in nchain:
                number += c
            format = "%" + "0%dd" % len(number)
            if (len(number) + len(suffix)) == len(name):
                prefix = ""
            else:
                prefix = name[0:n-i+1]
            prefix = os.path.join(os.path.dirname(filename),prefix)
            if not os.path.exists(prefix + number + suffix):
                print "Internal error in EDFStack"
                print "file should exist:",prefix + number + suffix
                return
            i = 0
            if begin is None:
                begin = 0
                testname = prefix+format % begin+suffix
                while not os.path.exists(prefix+format % begin+suffix):
                    begin += 1
                    testname = prefix+format % begin+suffix
                    if len(testname) > len(filename):break
                i = begin
            else:
                i = begin
            if not os.path.exists(prefix+format % i+suffix):
                raise "ValueError","Invalid start index file = %s" % \
                      prefix+format % i+suffix
            f = prefix+format % i+suffix
            filelist = []
            while os.path.exists(f):
                filelist.append(f)
                i += 1
                if end is not None:
                    if i > end:
                        break
                f = prefix+format % i+suffix
            self.loadFileList(filelist, fileindex=fileindex)

    def getSourceInfo(self):
        sourceInfo = {}
        sourceInfo["SourceType"]=SOURCE_TYPE
        if self.__keyList == []:
            for i in range(1, self.__nFiles + 1):
                for j in range(1, self.__nImages + 1):
                    self.__keyList.append("%d.%d" % (i,j))
        sourceInfo["KeyList"]= self.__keyList

    def getKeyInfo(self, key):
        print "Not implemented"
        return {}

    def isIndexedStack(self):
        return self.__indexedStack
    
    def getZSelectionArray(self,z=0):
        return (self.data[:,:,z]).astype(Numeric.Float)
        
    def getXYSelectionArray(self,coord=(0,0)):
        x,y=coord    
        return (self.data[y,x,:]).astype(Numeric.Float)

if __name__ == "__main__":
    import time
    import sys
    t0= time.time()
    stack = SpecFileStack()
    #stack.loadIndexedStack("Z:\COTTE\ch09\ch09__mca_0005_0000_0070.edf")
    if len(sys.argv) > 1:
        stack.loadIndexedStack(sys.argv[1])
    else:
        stack.loadIndexedStack("..\..\mca3\c449b01_001.mca")
    shape = stack.data.shape
    print "elapsed = ", time.time() - t0
    #guess the MCA
    imax = 0
    for i in range(len(shape)):
        if shape[i] > shape[imax]:
            imax = i

    print "selections ",
    print "getZSelectionArray  shape = ", stack.getZSelectionArray().shape
    print "getXYSelectionArray shape = ", stack.getXYSelectionArray().shape

    try:
        import PyQt4.Qt as qt
    except:
        import qt
    app = qt.QApplication([])
    qt.QObject.connect(app, qt.SIGNAL("lastWindowClosed()"),
                       app, qt.SLOT("quit()"))
    if 1:
        import RGBCorrelatorGraph
        w = RGBCorrelatorGraph.RGBCorrelatorGraph()
        graph = w.graph
    else:
        import QtBlissGraph
        w = QtBlissGraph.QtBlissGraph()
        graph = w
    print "shape sum 0 = ",Numeric.sum(stack.data, 0).shape
    print "shape sum 1 = ",Numeric.sum(stack.data, 1).shape
    print "shape sum 2 = ",Numeric.sum(stack.data, 2).shape
    a = Numeric.sum(stack.data, imax)
    print a.shape
    graph.setX1AxisLimits(0, a.shape[0])
    if 0:
        w.setY1AxisLimits(0, a.shape[1])
        w.setY1AxisInverted(True)
    else:
        graph.setY1AxisInverted(True)
        graph.setY1AxisLimits(0, a.shape[1])
    graph.imagePlot(a, ymirror=0)
    if imax == 0:
        graph.x1Label('Column Number')
    else:
        graph.x1Label('Row Number')
    graph.ylabel('File Number')
    w.show()

    if imax == 0:
        mcaData0 = Numeric.sum(Numeric.sum(stack.data, 2),1)
    else:
        mcaData0 = Numeric.sum(Numeric.sum(stack.data, 2),0)

    import McaWindow
    mca = McaWindow.McaWidget()
    sel = {}
    sel['SourceName'] = "Specfile Stack"
    sel['Key']        = "SUM"
    sel['legend']     = "EDF Stack SUM"
    mcaData = DataObject.DataObject()
    mcaData.info = {'McaCalib': [0 , 2.0 ,0],
                    "selectiontype":"1D",
                    "SourceName":"Specfile Stack",
                    "Key":"SUM"}
    mcaData.x = [Numeric.arange(len(mcaData0)).astype(Numeric.Float)]
    mcaData.y = [mcaData0]
    sel['dataobject'] = mcaData
    mca.show()
    mca._addSelection([sel])
    graph.enableSelection(True)
    def graphSlot(ddict):
        if ddict['event'] == "MouseSelection":
            ix1 = int(ddict['xmin'])
            ix2 = int(ddict['xmax'])+1
            iy1 = int(ddict['xmin'])
            iy2 = int(ddict['xmax'])+1
            if imax == 0:
                selectedData = Numeric.sum(Numeric.sum(stack.data[:,ix1:ix2, iy1:iy2], 2),1)
            else:
                selectedData = Numeric.sum(Numeric.sum(stack.data[ix1:ix2,:, iy1:iy2], 2),0)
            sel = {}
            sel['SourceName'] = "Specfile Stack"
            sel['Key'] = "Selection"
            sel["selectiontype"] = "1D"
            sel['legend'] = "EDF Stack Selection"
            selDataObject = DataObject.DataObject()
            selDataObject.info={'McaCalib': [100 , 2.0 ,0],
                                "selectiontype":"1D",
                                "SourceName":"EDF Stack Selection",
                                "Key":"Selection"}
            selDataObject.x = [Numeric.arange(len(mcaData0)).astype(Numeric.Float)]
            selDataObject.y = [selectedData]
            sel['dataobject'] = selDataObject
            mca._addSelection([sel])
    qt.QObject.connect(graph, qt.SIGNAL('QtBlissGraphSignal'),
                       graphSlot)
    #w.replot()
    if qt.qVersion() < '4.0.0':
        app.exec_loop()
    else:
        app.exec_()
