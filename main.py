import os
import sys
from PyQt4 import QtGui, QtCore, uic
import numpy as np
import pyqtgraph
import qdarkstyle
from obspy import read, Stream, UTCDateTime
from MyMultiPlotWidget import MyMultiPlotWidget
from DateAxisItem import DateAxisItem


# load in Qt Designer UI files
seed_view_ui = "seed_view_window.ui"

MainWindowUI, MainWindowBase = uic.loadUiType(seed_view_ui)

SEED_VIEW_ITEM_TYPES = {
    "TRACE": 0,
    "STATS": 1}


class MainWindow(MainWindowBase, MainWindowUI):
    def __init__(self, parent=None):
        MainWindowBase.__init__(self, parent)
        self.setupUi(self)

        self.seed_load_pushButton.released.connect(self.open_seed_file)

        # Add right clickability to station view
        self.station_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.station_view.customContextMenuRequested.connect(self.station_view_rightClicked)

        QtCore.QObject.connect(self.station_view, QtCore.SIGNAL("dropped"), self.file_dropped)

    def file_dropped(self, l):
        for url in l:
            if os.path.exists(url):
                self.seed_filename = url

                self.read_seed()

    def open_seed_file(self):
        self.seed_filename = str(QtGui.QFileDialog.getOpenFileName(
            parent=self, caption="Choose MiniSEED File",
            directory=os.path.expanduser("~"),
            filter="MiniSEED Files (*.mseed)"))
        if not self.seed_filename:
            return

        self.read_seed()

    def read_seed(self):

        temp_st = read(self.seed_filename)

        self.st = Stream()

        print(".....Seis Data.....")

        for tr in temp_st:
            if len(tr) > 0:
                self.st.append(tr)

        print(self.st)

        self.build_trace_list()


    def build_trace_list(self):

        self.station_view.clear()

        items = []

        # iterate through traces in stream and add them to the list view
        for index, tr in enumerate(self.st):
            item = QtGui.QTreeWidgetItem([str(index) + ": " + tr.id], type=SEED_VIEW_ITEM_TYPES["TRACE"])

            keys_list = ["starttime", "endtime", "sampling_rate", "npts"]

            for key in keys_list:
                # add stats as child elements
                stats_item = QtGui.QTreeWidgetItem([key + ": " + str(tr.stats[key])], type=SEED_VIEW_ITEM_TYPES["STATS"])
                item.addChild(stats_item)

            items.append(item)

        self.station_view.insertTopLevelItems(0, items)

    def station_view_rightClicked(self, position):
        item = self.station_view.selectedItems()[0]

        t = item.type()

        if t == SEED_VIEW_ITEM_TYPES["TRACE"]:
            print(item.text(0))

            self.selected_tr = self.st[int(item.text(0).split(":")[0])]

        elif t == SEED_VIEW_ITEM_TYPES["STATS"]:
            # print(item.parent().text(0))
            # print(item.text(0))
            # print(item.parent().text(0).split(":")[0])
            # print(self.st[int(item.parent().text(0).split(":")[0])])

            self.selected_tr = self.st[int(item.parent().text(0).split(":")[0])]

        self.trace_item_menu = QtGui.QMenu(self)
        select_action = QtGui.QAction('Plot Trace', self)
        select_action.triggered.connect(self.seed_plot)
        self.trace_item_menu.addAction(select_action)
        self.trace_item_menu.exec_(self.station_view.viewport().mapToGlobal(position))



    def seed_plot(self):

        # use a custom multiplot class to create waveform plotting region (allows scrollbar and minimum height of plots)
        self.waveform_graph = MyMultiPlotWidget()

        self.graph_stackedWidget.addWidget(self.waveform_graph)
        self.graph_stackedWidget.setCurrentWidget(self.waveform_graph)

        self.update_waveform_graph()

    def dispMousePos(self, pos):
        # Display current mouse coords if over the scatter plot area as a tooltip

        x_coord = UTCDateTime(self.active_plot.vb.mapSceneToView(pos).toPoint().x())
        time_tool = self.active_plot.setToolTip(x_coord.ctime())

    def update_waveform_graph(self):

        tr = self.selected_tr.copy()

        print(tr)

        self.waveform_graph.clear()
        self.waveform_graph.setMinimumPlotHeight(200)

        plot = self.waveform_graph.addPlot(
            0, 0, title=tr.id,
            axisItems={'bottom': DateAxisItem(orientation='bottom',
                                              utcOffset=0)})
        plot.plot(tr.times() + tr.stats.starttime.timestamp, tr.data)
        plot.show()

        self.active_plot = plot

        self.waveform_graph.scene().sigMouseMoved.connect(self.dispMousePos)


def main():
    app = QtGui.QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(pyside=False))
    form = MainWindow()
    form.setMinimumSize(800, 600)
    form.show()
    form.raise_()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()