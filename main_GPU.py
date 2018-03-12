import os
import sys
from PyQt4 import QtGui, QtCore, uic
from vispy import gloo
from vispy import app
import numpy as np
import math
import qdarkstyle
from obspy import read, Stream

# load in Qt Designer UI files
seed_view_ui = "seed_view_window.ui"

MainWindowUI, MainWindowBase = uic.loadUiType(seed_view_ui)

SEED_VIEW_ITEM_TYPES = {
    "TRACE": 0,
    "STATS": 1}

VERT_SHADER = """
#version 120
attribute vec2 a_position;
attribute float a_index;
varying float v_index;
attribute vec3 a_color;
varying vec3 v_color;
uniform vec2 u_pan;
uniform vec2 u_scale;
void main() {
    vec2 position_tr = u_scale * (a_position + u_pan);
    gl_Position = vec4(position_tr, 0.0, 1.0);
    v_color = a_color;
    v_index = a_index;
}
"""

FRAG_SHADER = """
#version 120
varying vec3 v_color;
varying float v_index;
void main() {
    gl_FragColor = vec4(v_color, 1.0);
    if ((fract(v_index) > .00001) && (fract(v_index) < .99999))
        gl_FragColor.a = 0.;
}
"""

class Canvas(app.Canvas):
    def __init__(self, array):
        app.Canvas.__init__(self, keys='interactive')
        self.program = gloo.Program(VERT_SHADER, FRAG_SHADER)
        self.program.bind(gloo.VertexBuffer(array))

        self.program['u_pan'] = (0., 0.)
        self.program['u_scale'] = (1., 1.)

        gloo.set_viewport(0, 0, *self.physical_size)

        gloo.set_state(clear_color=(1, 1, 1, 1), blend=True,
                       blend_func=('src_alpha', 'one_minus_src_alpha'))

        self.show()

    def on_resize(self, event):
        gloo.set_viewport(0, 0, *event.physical_size)

    def on_draw(self, event):
        gloo.clear(color=(0.0, 0.0, 0.0, 1.0))
        self.program.draw('line_strip')

    def _normalize(self, x_y):
        x, y = x_y
        w, h = float(self.size[0]), float(self.size[1])
        return x/(w/2.)-1., y/(h/2.)-1.

    def on_mouse_move(self, event):
        if event.is_dragging:
            x0, y0 = self._normalize(event.press_event.pos)
            x1, y1 = self._normalize(event.last_event.pos)
            x, y = self._normalize(event.pos)
            dx, dy = x - x1, -(y - y1)
            button = event.press_event.button

            pan_x, pan_y = self.program['u_pan']
            scale_x, scale_y = self.program['u_scale']

            if button == 1:
                self.program['u_pan'] = (pan_x+dx/scale_x, pan_y+dy/scale_y)
            elif button == 2:
                scale_x_new, scale_y_new = (scale_x * math.exp(2.5*dx),
                                            scale_y * math.exp(2.5*dy))
                self.program['u_scale'] = (scale_x_new, scale_y_new)
                self.program['u_pan'] = (pan_x -
                                         x0 * (1./scale_x - 1./scale_x_new),
                                         pan_y +
                                         y0 * (1./scale_y - 1./scale_y_new))
            self.update()

    def on_mouse_wheel(self, event):
        dx = np.sign(event.delta[1])*.05
        scale_x, scale_y = self.program['u_scale']
        scale_x_new, scale_y_new = (scale_x * math.exp(2.5*dx),
                                    scale_y * math.exp(2.5*dx))
        self.program['u_scale'] = (scale_x_new, scale_y_new)
        self.update()

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


    def transform_data(self, tr):
        m = 1
        n = len(tr)

        # print(n,m)
        x = np.tile(np.linspace(-1., 1., n), m)

        # print(x)
        # y = .1 * np.random.randn(m, n)
        # y += np.arange(m).reshape((-1, 1))
        # print(y)
        # print(y.shape)
        y = np.asfarray(np.array([tr.data]))

        print(x.shape)
        print(y.shape)

        # print(np.zeros(n * m))
        data = np.zeros(n * m, dtype=[
            ('a_position', np.float32, 2),
            ('a_color', np.float32, 3),
            ('a_index', np.float32, 1),
        ])

        # print(data)
        print(data.shape)

        data['a_position'] = np.zeros((n * m, 2), dtype=np.float32)
        data['a_position'][:, 0] = x
        data['a_position'][:, 1] = (y.ravel() / y.max() * 2 - 1)  # .9 * (y.ravel() / y.max() * 2 - 1)

        # print(y)
        # print(y.ravel())
        # print(y.max())
        # print(y.ravel() / y.max())
        # print(.9 * (y.ravel() / y.max() * 2 - 1))
        # print((.9 * (y.ravel() / y.max() * 2 - 1)).shape)

        data['a_color'] = np.repeat(np.random.uniform(size=(m, 3), low=.1, high=.9),
                                    n, axis=0)

        data['a_index'] = np.repeat(np.arange(m), n)

        print(np.repeat(np.arange(m), n))

        # print(data)
        print(data.shape)

        self.array = data

    def seed_plot(self):

        # transform the trace
        self.transform_data(self.selected_tr)


        self.canvas = Canvas(self.array)

        self.graph_stackedWidget.addWidget(self.canvas.native)
        self.graph_stackedWidget.setCurrentWidget(self.canvas.native)



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

