"""
"""
from __future__ import with_statement
import sys
import os
import posixpath
import gc
import re
from operator import itemgetter

try:
    from PyMca import PyMcaQt as qt
    safe_str = qt.safe_str
except ImportError:
    # for people using this widget without PyMca installed
    import PyQt4.Qt as qt
    safe_str = str

if hasattr(qt, 'QStringList'):
    MyQVariant = qt.QVariant
else:
    def MyQVariant(x=None):
        return x

import h5py
phynx = h5py
import weakref

DEBUG = 0

#sorting method
def h5py_sorting(object_list):
    sorting_list = ['start_time', 'end_time', 'name']
    n = len(object_list)
    if n < 2:
        return object_list

    # This implementation only sorts entries
    if posixpath.dirname(object_list[0].name) != "/":
        return object_list

    names = list(object_list[0].keys())

    sorting_key = None
    for key in sorting_list:
        if key in names:
            sorting_key = key
            break
        
    if sorting_key is None:
        if 'name' in sorting_list:
            sorting_key = 'name'
        else:
            return object_list

    try:
        if sorting_key != 'name':
            sorting_list = [(o[sorting_key].value, o)
                           for o in object_list]
            sorted_list = sorted(sorting_list, key=itemgetter(0))
            return [x[1] for x in sorted_list]

        if sorting_key == 'name':
            sorting_list = [(_get_number_list(o.name),o)
                           for o in object_list]
            sorting_list.sort()
            return [x[1] for x in sorting_list]
    except:
        #The only way to reach this point is to have different
        #structures among the different entries. In that case
        #defaults to the unfiltered case
        print("WARNING: Default ordering")
        print("Probably all entries do not have the key %s" % sorting_key)
        return object_list

def _get_number_list(txt):
    rexpr = '[/a-zA-Z:-]'
    nbs= [float(w) for w in re.split(rexpr, txt) if w not in ['',' ']]
    return nbs

class QRLock(qt.QMutex):

    """
    """

    def __init__(self):
        qt.QMutex.__init__(self, qt.QMutex.Recursive)

    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, type, value, traceback):
        self.unlock()


class RootItem(object):

    @property
    def children(self):
        return self._children

    @property
    def hasChildren(self):
        if len(self._children):
            return True
        else:
            return False

    @property
    def header(self):
        return self._header

    @property
    def parent(self):
        return None

    def __init__(self, header):
        self._header = header
        self._children = []
        self._identifiers = []

    def __iter__(self):
        def iter_files(files):
            for f in files:
                yield f
        return iter_files(self.children)

    def __len__(self):
        return len(self.children)

    def appendChild(self, item):
        self.children.append(H5FileProxy(item, self))
        self._identifiers.append(id(item))

    def deleteChild(self, child):
        idx = self._children.index(child)
        del self._children[idx]
        del self._identifiers[idx]

class H5NodeProxy(object):
    @property
    def children(self):
        if not self.hasChildren:
            return []

        if not self._children:
            # obtaining the lock here is necessary, otherwise application can
            # freeze if navigating tree while data is processing
            if 1: #with self.file.plock:
                tmpList = list(self.getNode(self.name).values())
                try:
                    finalList = h5py_sorting(tmpList)
                except:
                    #one cannot afford any error
                    if DEBUG:
                        raise
                    else:
                        finalList = tmpList
                self._children = [H5NodeProxy(self.file, i, self)
                                  for i in finalList]
        return self._children

    @property
    def file(self):
        return self._file

    @property
    def hasChildren(self):
        return self._hasChildren

    @property
    def name(self):
        return self._name

    @property
    def row(self):
        if 1:#with self.file.plock:
            try:
                return self.parent.children.index(self)
            except ValueError:
                return
    @property
    def type(self):
        return self._type

    @property
    def shape(self):
        if type(self._shape) == type(""):
            return self._shape
        if len(self._shape) == 1:
            return "%d" % self._shape[0]
        elif len(self._shape) > 1:
            text = "%d" % self._shape[0]
            for a in range(1, len(self._shape)):
                text += " x %d" % self._shape[a]
            return text
        else:
            return ""
        
    @property
    def dtype(self):
        return self._dtype

    @property
    def parent(self):
        return self._parent


    def __init__(self, ffile, node, parent=None):
        if 1:#with ffile.plock:
            self._file = ffile
            self._parent = parent
            self._name = node.name
            """
            if hasattr(node, "_sourceName"):
                self._name = node._sourceName
            else:
                self._name = posixpath.basename(node.name)
            """
            self._type = type(node).__name__
            self._hasChildren = isinstance(node, h5py.Group)
            if hasattr(node, 'attrs'):
                attrs = list(node.attrs)
                for cname in ['class', 'NX_class']:
                    if cname in attrs:
                        if sys.version <'3.0':
                            _type = "%s" % node.attrs[cname]
                        else:
                            _type = node.attrs[cname].decode('utf=8')
                        self._type = _type
                        break
                        #self._type = _type[2].upper() + _type[3:]
            self._children = []
            if hasattr(node, 'dtype'):
                self._dtype = safe_str(node.dtype)
            else:
                self._dtype = ""
            if hasattr(node, 'shape'):
                if 0:
                    self._shape = safe_str(node.shape)
                else:
                    self._shape = node.shape
            else:
                self._shape = ""

    def clearChildren(self):
        self._children = []
        self._hasChildren = False

    def getNode(self, name=None):
        if not name:
            name = self.name
        return self.file[name]

    def __len__(self):
        return len(self.children)


class H5FileProxy(H5NodeProxy):

    @property
    def name(self):
        return '/'

    @property
    def filename(self):
        return self._filename

    def __init__(self, ffile, parent=None):
        super(H5FileProxy, self).__init__(ffile, ffile, parent)
        self._name = ffile.name
        self._filename = self.file.name

    def close(self):
        with self.file.plock:
            return self.file.close()

    def __getitem__(self, path):
        if path == '/':
            return self
        else:
            return H5NodeProxy(self.file, self.file[path], self)


class FileModel(qt.QAbstractItemModel):

    """
    """

    def __init__(self, parent=None):
        qt.QAbstractItemModel.__init__(self, parent)
        self.rootItem = RootItem(['File/Group/Dataset', 'Description', 'Shape', 'DType'])
        self._idMap = {qt.QModelIndex().internalId(): self.rootItem}

    def clearRows(self, index):
        self.getProxyFromIndex(index).clearChildren()

    def close(self):
        for item in self.rootItem:
            item.close()
        self._idMap = {}

    def columnCount(self, parent):
        return 4

    def data(self, index, role):
        if role != qt.Qt.DisplayRole:
            return MyQVariant()
        item = self.getProxyFromIndex(index)
        column = index.column()
        if column == 0:
            if isinstance(item, H5FileProxy):
                return MyQVariant(os.path.basename(item.file.filename))
            else:
                return MyQVariant(posixpath.basename(item.name))
        if column == 1:
            showtitle = True
            if showtitle:
                if hasattr(item, 'type'):
                    if item.type in ["Entry", "NXentry"]:
                        children = item.children
                        names = [posixpath.basename(o.name) for o in children]
                        if "title" in names:
                            idx = names.index("title")
                            if len(children[idx].getNode().shape):
                                #stored as an array of strings!!!
                                #return just the first item
                                return MyQVariant("%s" % children[idx].getNode().value[0])
                            else:
                                #stored as a string
                                return MyQVariant("%s" % children[idx].getNode().value)
            return MyQVariant(item.type)
        if column == 2:
            return MyQVariant(item.shape)
        if column == 3:
            return MyQVariant(item.dtype)
        return MyQVariant()

    def getNodeFromIndex(self, index):
        try:
            return self.getProxyFromIndex(index).getNode()
        except AttributeError:
            return None
        
    def getProxyFromIndex(self, index):
        try:
            return self._idMap[index.internalId()]        
        except KeyError:
            try:
                #Linux 32-bit problem
                return self._idMap[index.internalId() & 0xFFFFFFFF]
            except KeyError:
                return self.rootItem

    def hasChildren(self, index):
        return self.getProxyFromIndex(index).hasChildren

    def headerData(self, section, orientation, role):
        if orientation == qt.Qt.Horizontal and \
                role == qt.Qt.DisplayRole:
            return MyQVariant(self.rootItem.header[section])

        return MyQVariant()

    def hasIndex(self, row, column, parent):
        parentItem = self.getProxyFromIndex(parent)
        if row >= len(parentItem.children):
            return False
        return True

    def index(self, row, column, parent):
        parentItem = self.getProxyFromIndex(parent)
        if row >= len(parentItem.children):
            return qt.QModelIndex()
        child = parentItem.children[row]
        #force a pointer to child and not use id(child)
        index = self.createIndex(row, column, child)
        self._idMap.setdefault(index.internalId(), child)
        return index

    def parent(self, index):
        child = self.getProxyFromIndex(index)
        parent = child.parent
        if parent == self.rootItem:
            return qt.QModelIndex()
        if parent is None:
            return qt.QModelIndex()
        if parent.row is None:
            return qt.QModelIndex()
        else:
            return self.createIndex(parent.row, 0, parent)

    def rowCount(self, index):
        return len(self.getProxyFromIndex(index))

    def openFile(self, filename, weakreference=False):
        gc.collect()
        for item in self.rootItem:
            if item.file.filename == filename:
                ddict = {}
                ddict['event'] = "fileUpdated"
                ddict['filename'] = filename
                self.emit(qt.SIGNAL('fileUpdated'), ddict)
                return item.file
        phynxFile = phynx.File(filename, 'r')
        if weakreference:
            def phynxFileInstanceDistroyed(weakrefObject):
                idx = self.rootItem._identifiers.index(id(weakrefObject))
                child = self.rootItem._children[idx]
                child.clearChildren()
                del self._idMap[id(child)]
                self.rootItem.deleteChild(child)
                if not self.rootItem.hasChildren:
                    self.clear()
                return
            refProxy = weakref.proxy(phynxFile, phynxFileInstanceDistroyed)
            self.rootItem.appendChild(refProxy)
        else:
            self.rootItem.appendChild(phynxFile)
        ddict = {}
        ddict['event'] = "fileAppended"
        ddict['filename'] = filename
        self.emit(qt.SIGNAL('fileAppended'), ddict)
        return phynxFile

    def appendPhynxFile(self, phynxFile, weakreference=True):
        """
        I create a weak reference to a phynx file instance, get informed when
        the instance disappears, and delete the entry from the view
        """
        if hasattr(phynxFile, "_sourceName"):
            name = phynxFile._sourceName
        else:
            name = phynxFile.name
        gc.collect()
        present = False
        for child in self.rootItem:
            if child.file.filename == name:
                #already present
                present = True
                break

        if present:
            ddict = {}
            ddict['event'] = "fileUpdated"
            ddict['filename'] = name
            self.emit(qt.SIGNAL('fileUpdated'), ddict)
            return
            
        if weakreference:
            def phynxFileInstanceDistroyed(weakrefObject):
                idx = self.rootItem._identifiers.index(id(weakrefObject))
                child = self.rootItem._children[idx]
                child.clearChildren()
                del self._idMap[id(child)]
                self.rootItem.deleteChild(child)
                if not self.rootItem.hasChildren:
                    self.clear()
                return
            phynxFileProxy = weakref.proxy(phynxFile, phynxFileInstanceDistroyed)
            self.rootItem.appendChild(phynxFileProxy)
        else:
            self.rootItem.appendChild(phynxFile)
        ddict = {}
        ddict['event'] = "fileAppended"
        ddict['filename'] = name
        self.emit(qt.SIGNAL('fileAppended'), ddict)

    def clear(self):
        self.reset()


class FileView(qt.QTreeView):
    def __init__(self, fileModel, parent=None):
        qt.QTreeView.__init__(self, parent)
        self.setModel(fileModel)
        self.setColumnWidth(0, 250)
        #This removes the children after a double click
        #with no possibility to recover them
        #self.connect(
        #    self,
        #    qt.SIGNAL('collapsed(QModelIndex)'),
        #    fileModel.clearRows
        #)
        self.connect(
            fileModel,
            qt.SIGNAL('fileAppended'),
            self.fileAppended
        )

        self.connect(
            fileModel,
            qt.SIGNAL('fileUpdated'),
            self.fileUpdated
        )

    def fileAppended(self, ddict=None):
        self.doItemsLayout()
        if ddict is None:
            return
        self.fileUpdated(ddict)
            

    def fileUpdated(self, ddict):
        rootModelIndex = self.rootIndex()
        if self.model().hasChildren(rootModelIndex):
            rootItem = self.model().getProxyFromIndex(rootModelIndex)
            for row in range(len(rootItem)):
                if self.model().hasIndex(row, 0, rootModelIndex):
                    modelIndex = self.model().index(row, 0, rootModelIndex)
                    item = self.model().getProxyFromIndex(modelIndex)
                    if item.name == ddict['filename']:            
                        self.selectionModel().setCurrentIndex(modelIndex,
                                              qt.QItemSelectionModel.NoUpdate)
                        self.scrollTo(modelIndex,
                                      qt.QAbstractItemView.PositionAtTop)
                        break
        self.doItemsLayout()
                    
class HDF5Widget(FileView):
    def __init__(self, model, parent=None):
        FileView.__init__(self, model, parent)
        self.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self._adjust()
        if 0:
            qt.QObject.connect(self,
                     qt.SIGNAL('activated(QModelIndex)'),
                     self.itemActivated)

        qt.QObject.connect(self,
                     qt.SIGNAL('clicked(QModelIndex)'),
                     self.itemClicked)

        qt.QObject.connect(self,
                     qt.SIGNAL('doubleClicked(QModelIndex)'),
                     self.itemDoubleClicked)

        qt.QObject.connect(
            self,
            qt.SIGNAL('collapsed(QModelIndex)'),
            self._adjust)

        qt.QObject.connect(
            self,
            qt.SIGNAL('expanded(QModelIndex)'),
            self._adjust)

    def _adjust(self, modelIndex=None):
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)
        self.resizeColumnToContents(2)
        self.resizeColumnToContents(3)
        
    def mousePressEvent(self, e):
        button = e.button()
        if button == qt.Qt.LeftButton:
            self._lastMouse = "left"
        elif button == qt.Qt.RightButton:
            self._lastMouse = "right"
        elif button == qt.Qt.MidButton:
            self._lastMouse = "middle"
        else:
            #Should I set it to no button?
            self._lastMouse = "left"
        qt.QTreeView.mousePressEvent(self, e)

    def itemActivated(self, modelIndex):
        event ="itemActivated"
        self.emitSignal(event, modelIndex)

    def itemClicked(self, modelIndex):
        event ="itemClicked"
        self.emitSignal(event, modelIndex)

    def itemDoubleClicked(self, modelIndex):
        event ="itemDoubleClicked"
        self.emitSignal(event, modelIndex)

    def emitSignal(self, event, modelIndex):
        if self.model() is None:
            return
        ddict = {}
        item  = self.model().getProxyFromIndex(modelIndex)        
        ddict['event'] = event
        ddict['file']  = item.file.filename
        ddict['name']  = item.name
        ddict['type']  = item.type
        ddict['dtype'] = item.dtype
        ddict['shape'] = item.shape
        ddict['mouse'] = self._lastMouse * 1
        self.emit(qt.SIGNAL("HDF5WidgetSignal"), ddict)

    def getSelectedEntries(self):
        modelIndexList = self.selectedIndexes()
        entryList = []
        analyzedPaths = []
        for modelIndex in modelIndexList:
            item = self.model().getProxyFromIndex(modelIndex)
            path = item.name * 1
            if path in analyzedPaths:
                continue
            else:
                analyzedPaths.append(path)
            if item.type in ["weakproxy", "File"]:
                continue
            entry = "/" + path.split("/")[1]
            if entry not in entryList:
                entryList.append((entry, item.file.filename))
        return entryList


if __name__ == "__main__":
    app = qt.QApplication(sys.argv)
    if len(sys.argv) < 2:
        print("Usage:")
        print("python HDF5Widget.py path_to_hdf5_file_name")
        sys.exit(0)
    fileModel = FileModel()
    fileView = HDF5Widget(fileModel)
    #fileModel.openFile('/home/darren/temp/PSI.hdf')
    phynxFile = fileModel.openFile(sys.argv[1])
    def mySlot(ddict):
        print(ddict)
        if ddict['type'].lower() in ['dataset']:
            print(phynxFile[ddict['name']].dtype, phynxFile[ddict['name']].shape)
    qt.QObject.connect(fileView, qt.SIGNAL("HDF5WidgetSignal"), mySlot)
    fileView.show()
    sys.exit(app.exec_())
