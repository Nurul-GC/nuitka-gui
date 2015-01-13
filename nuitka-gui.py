#!/usr/bin/env python3
# -*- coding: utf-8 -*-


#     Copyright 2013, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.


# metadata
"""Nuitka GUI."""
__version__ = ' 0.5.8 '
__license__ = ' Apache '
__author__ = ' JuanCarlos '
__email__ = ' juancarlospaco@gmail.com '
__url__ = 'https://github.com/juancarlospaco/nuitka-gui#nuitka-gui'
__source__ = ('https://raw.githubusercontent.com/juancarlospaco/'
              'nuitka-gui/master/nuitka-gui.py')


# imports
import logging as log
import os
import re
import signal
import sys
import time
from copy import copy
from ctypes import byref, cdll, create_string_buffer
from datetime import datetime
from doctest import testmod
from getopt import getopt
from multiprocessing import cpu_count
from subprocess import call, check_output
from tempfile import gettempdir
from urllib import request
from webbrowser import open_new_tab

from PyQt5.QtCore import QDir, QProcess, Qt, QUrl
from PyQt5.QtGui import QIcon
from PyQt5.QtNetwork import (QNetworkAccessManager, QNetworkProxyFactory,
                             QNetworkRequest)
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QCompleter,
                             QDialogButtonBox, QDirModel, QFileDialog,
                             QFontDialog, QGridLayout, QGroupBox, QLabel,
                             QLineEdit, QMainWindow, QMessageBox,
                             QProgressDialog, QPushButton, QShortcut, QSpinBox,
                             QVBoxLayout, QWidget)


NUITKA = "nuitka" if not sys.platform.startswith(
    "win") else r'"C:\Python27\Scripts\nuitka"'
HELP = """<h3>Nuitka GUI</h3><b>Python Binary Compiler App !</b><br>
Version {}, licence {}<br>
Python compiler compatible with Python 2.6, 2.7, 3.2, 3.3 and 3.4.
You feed it your Python app, it does a lot of clever things,
and spits out an executable or extension module. Free license (Apache).<br>
DEV: <a href=https://github.com/juancarlospaco>JuanCarlos</a>
""".format(__version__, __license__)


###############################################################################


class Downloader(QProgressDialog):

    """Downloader Dialog with complete informations and progress bar."""

    def __init__(self, parent=None):
        """Init class."""
        super(Downloader, self).__init__(parent)
        self.setWindowTitle(__doc__)
        if not os.path.isfile(__file__) or not __source__:
            return
        if not os.access(__file__, os.W_OK):
            error_msg = ("Destination file permission denied (not Writable)! "
                         "Try again to Update but as root or administrator.")
            log.critical(error_msg)
            QMessageBox.warning(self, __doc__.title(), error_msg)
            return
        self._time, self._date = time.time(), datetime.now().isoformat()[:-7]
        self._url, self._dst = __source__, __file__
        log.debug("Downloading from {} to {}.".format(self._url, self._dst))
        if not self._url.lower().startswith("https:"):
            log.warning("Unsecure Download over plain text without SSL.")
        self.template = """<h3>Downloading</h3><hr><table>
        <tr><td><b>From:</b></td>      <td>{}</td>
        <tr><td><b>To:  </b></td>      <td>{}</td> <tr>
        <tr><td><b>Started:</b></td>   <td>{}</td>
        <tr><td><b>Actual:</b></td>    <td>{}</td> <tr>
        <tr><td><b>Elapsed:</b></td>   <td>{}</td>
        <tr><td><b>Remaining:</b></td> <td>{}</td> <tr>
        <tr><td><b>Received:</b></td>  <td>{} MegaBytes</td>
        <tr><td><b>Total:</b></td>     <td>{} MegaBytes</td> <tr>
        <tr><td><b>Speed:</b></td>     <td>{}</td>
        <tr><td><b>Percent:</b></td>     <td>{}%</td></table><hr>"""
        self.manager = QNetworkAccessManager(self)
        self.manager.finished.connect(self.save_downloaded_data)
        self.manager.sslErrors.connect(self.download_failed)
        self.progreso = self.manager.get(QNetworkRequest(QUrl(self._url)))
        self.progreso.downloadProgress.connect(self.update_download_progress)
        self.show()
        self.exec_()

    def save_downloaded_data(self, data):
        """Save all downloaded data to the disk and quit."""
        log.debug("Download done. Update Done.")
        with open(os.path.join(self._dst), "wb") as output_file:
            output_file.write(data.readAll())
        data.close()
        QMessageBox.information(self, __doc__.title(),
                                "<b>You got the latest version of this App!")
        del self.manager, data
        return self.close()

    def download_failed(self, download_error):
        """Handle a download error, probable SSL errors."""
        log.error(download_error)
        QMessageBox.warning(self, __doc__.title(), str(download_error))

    def seconds_time_to_human_string(self, time_on_seconds=0):
        """Calculate time, with precision from seconds to days."""
        minutes, seconds = divmod(int(time_on_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        human_time_string = ""
        if days:
            human_time_string += "%02d Days " % days
        if hours:
            human_time_string += "%02d Hours " % hours
        if minutes:
            human_time_string += "%02d Minutes " % minutes
        human_time_string += "%02d Seconds" % seconds
        return human_time_string

    def update_download_progress(self, bytesReceived, bytesTotal):
        """Calculate statistics and update the UI with them."""
        downloaded_MB = round(((bytesReceived / 1024) / 1024), 2)
        total_data_MB = round(((bytesTotal / 1024) / 1024), 2)
        downloaded_KB, total_data_KB = bytesReceived / 1024, bytesTotal / 1024
        # Calculate download speed values, with precision from Kb/s to Gb/s
        elapsed = time.clock()
        if elapsed > 0:
            speed = round((downloaded_KB / elapsed), 2)
            if speed > 1024000:  # Gigabyte speeds
                download_speed = "{} GigaByte/Second".format(speed // 1024000)
            if speed > 1024:  # MegaByte speeds
                download_speed = "{} MegaBytes/Second".format(speed // 1024)
            else:  # KiloByte speeds
                download_speed = "{} KiloBytes/Second".format(int(speed))
        if speed > 0:
            missing = abs((total_data_KB - downloaded_KB) // speed)
        percentage = int(100.0 * bytesReceived // bytesTotal)
        self.setLabelText(self.template.format(
            self._url.lower()[:99], self._dst.lower()[:99],
            self._date, datetime.now().isoformat()[:-7],
            self.seconds_time_to_human_string(time.time() - self._time),
            self.seconds_time_to_human_string(missing),
            downloaded_MB, total_data_MB, download_speed, percentage))
        self.setValue(percentage)


###############################################################################


def get_nuitka_version():
    """Try to return Nuitka version if fails return the default docstring.

    >>> isinstance(get_nuitka_version(), str)
    True
    """
    try:
        ver = check_output(NUITKA + " --version", shell=True).splitlines()[0]
        ver = str(ver).strip().lower()
    except:
        ver = __doc__.strip().lower()
    finally:
        log.info(ver)
        return ver


class MainWindow(QMainWindow):

    """Main window class."""

    def __init__(self, parent=None):
        """Init class."""
        super(MainWindow, self).__init__()
        QNetworkProxyFactory.setUseSystemConfiguration(True)
        self.statusBar().showMessage(__doc__ + get_nuitka_version())
        self.setWindowTitle(__doc__.strip().capitalize())
        self.setMinimumSize(480, 400)
        self.setMaximumSize(1024, 800)
        self.resize(self.minimumSize())
        self.setWindowIcon(QIcon.fromTheme("python"))
        self.center()
        QShortcut("Ctrl+q", self, activated=lambda: self.close())
        self.menuBar().addMenu("&File").addAction("Exit", lambda: self.close())
        windowMenu = self.menuBar().addMenu("&Window")
        windowMenu.addAction("Minimize", lambda: self.showMinimized())
        windowMenu.addAction("Maximize", lambda: self.showMaximized())
        windowMenu.addAction("Restore", lambda: self.showNormal())
        windowMenu.addAction("FullScreen", lambda: self.showFullScreen())
        windowMenu.addAction("Center", lambda: self.center())
        windowMenu.addAction("Top-Left", lambda: self.move(0, 0))
        windowMenu.addAction("To Mouse", lambda: self.move_to_mouse_position())
        windowMenu.addSeparator()
        windowMenu.addAction(
            "Increase size", lambda:
            self.resize(self.size().width() * 1.4, self.size().height() * 1.4))
        windowMenu.addAction("Decrease size", lambda: self.resize(
            self.size().width() // 1.4, self.size().height() // 1.4))
        windowMenu.addAction("Minimum size", lambda:
                             self.resize(self.minimumSize()))
        windowMenu.addAction("Maximum size", lambda:
                             self.resize(self.maximumSize()))
        windowMenu.addAction("Horizontal Wide", lambda: self.resize(
            self.maximumSize().width(), self.minimumSize().height()))
        windowMenu.addAction("Vertical Tall", lambda: self.resize(
            self.minimumSize().width(), self.maximumSize().height()))
        windowMenu.addSeparator()
        windowMenu.addAction("Disable Resize", lambda:
                             self.setFixedSize(self.size()))
        windowMenu.addAction("Set Interface Font...", lambda:
                             self.setFont(QFontDialog.getFont()[0]))
        windowMenu.addAction(
            "Load .qss Skin", lambda: self.setStyleSheet(self.skin()))
        helpMenu = self.menuBar().addMenu("&Help")
        helpMenu.addAction("About Qt 5", lambda: QMessageBox.aboutQt(self))
        helpMenu.addAction("About Python 3",
                           lambda: open_new_tab('https://www.python.org'))
        helpMenu.addAction("About " + __doc__,
                           lambda: QMessageBox.about(self, __doc__, HELP))
        helpMenu.addSeparator()
        helpMenu.addAction(
            "Keyboard Shortcut",
            lambda: QMessageBox.information(self, __doc__, "<b>Quit = CTRL+Q"))
        if sys.platform.startswith('linux'):
            helpMenu.addAction("View Source Code", lambda:
                               call('xdg-open ' + __file__, shell=True))
        helpMenu.addAction("View GitHub Repo", lambda: open_new_tab(__url__))
        helpMenu.addAction("Check Updates", lambda: Downloader(self))
        # process
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.readyReadStandardError.connect(self._read_errors)
        self.process.finished.connect(self._process_finished)
        self.process.error.connect(self._process_failed)
        # widgets
        self.group0, self.group1 = QGroupBox("Options"), QGroupBox("Paths")
        self.group4, self.group5 = QGroupBox("Details"), QGroupBox("Miscs")
        g0grid, g1vlay = QGridLayout(self.group0), QGridLayout(self.group1)
        g5vlay, g4vlay = QVBoxLayout(self.group5), QVBoxLayout(self.group4)
        # group 0 the options
        self.module = QCheckBox("Create compiled extension module")
        self.standalone = QCheckBox("Standalone executable binary output")
        self.nofreeze = QCheckBox("No freeze all modules of standard library")
        self.python_debug = QCheckBox("Use Python Debug")
        self.warning = QCheckBox("Warnings for implicit exceptions at compile")
        self.recurse_std = QCheckBox("Recursive compile the standard library")
        self.recurse_not = QCheckBox("Force No recursive compiling")
        self.execute = QCheckBox("Execute the created binary after compiling")
        self.pythonpath = QCheckBox("Keep pythonpath when executing")
        self.enhaced = QCheckBox("Enhaced compile, Not CPython compatible")
        self.nolineno = QCheckBox("No Statements line numbers on compile")
        self.rmbuilddir = QCheckBox("Remove build directory after compile.")
        self.nuitka_debug = QCheckBox("Use Nuitka Debug")
        self.keep_debug = QCheckBox("Keep debug info on compile for GDB")
        self.traced = QCheckBox("Traced execution output")
        self.plusplus = QCheckBox("Compile C++ Only on generated source files")
        self.experimental = QCheckBox("Experimental features")
        self.force_clang = QCheckBox("Force use of CLang")
        self.force_mingw = QCheckBox("Force use of MinGW on MS Windows")
        self.force_lto = QCheckBox("Use link time optimizations LTO")
        self.show_scons = QCheckBox("Show Scons executed commands")
        self.show_progress = QCheckBox("Show progress info and statistics")
        self.show_summary = QCheckBox("Show final summary of included modules")
        self.disable_console = QCheckBox("Disable the Console on MS Windows")
        for i, widget in enumerate((
            self.module, self.standalone, self.nofreeze, self.python_debug,
            self.warning, self.recurse_std, self.recurse_not, self.execute,
            self.pythonpath, self.enhaced, self.nolineno, self.rmbuilddir,
            self.nuitka_debug, self.keep_debug, self.traced, self.plusplus,
            self.experimental, self.force_clang, self.force_mingw,
            self.force_lto, self.show_scons, self.show_progress,
                self.show_summary, self.disable_console)):
            widget.setToolTip(widget.text())
            g0grid.addWidget(widget, i if i < i + 1 else i - (i - 1), i % 2)
        # group 1 paths
        self.target = QLineEdit()
        self.outdir = QLineEdit(os.path.expanduser("~"))
        self.t_icon = QLineEdit()
        self.target.setToolTip("Python App file you want to Compile to Binary")
        self.outdir.setToolTip("Folder to write Compiled Output Binary files")
        self.t_icon.setToolTip("Icon image file to embed for your Python App")
        self.target.setPlaceholderText("/full/path/to/target/python_app.py")
        self.outdir.setPlaceholderText("/full/path/to/output/folder/")
        self.t_icon.setPlaceholderText("/full/path/to/python_app/icon.png")
        self.completer, self.dirs = QCompleter(self), QDirModel(self)
        self.completer.setModel(self.dirs)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.popup().setStyleSheet("border: 1px solid gray")
        self.completer.popup().setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff)
        self.outdir.setCompleter(self.completer)
        self.t_icon.setCompleter(self.completer)
        self.target.setCompleter(self.completer)
        self.clear_1 = QPushButton(QIcon.fromTheme("edit-clear"), "", self,
                                   clicked=lambda: self.target.clear())
        self.clear_2 = QPushButton(QIcon.fromTheme("edit-clear"), "", self,
                                   clicked=lambda: self.t_icon.clear())
        self.clear_3 = QPushButton(QIcon.fromTheme("edit-clear"), "", self,
                                   clicked=lambda: self.outdir.clear())
        self.open_1 = QPushButton(
            QIcon.fromTheme("folder-open"), "", self, clicked=lambda:
                self.target.setText(str(QFileDialog.getOpenFileName(
                self, __doc__, os.path.expanduser("~"),
                "Python (*.py);;Python for Windows (*.pyw);;All (*.*)")[0])))
        self.open_2 = QPushButton(
            QIcon.fromTheme("folder-open"), "", self, clicked=lambda:
                self.t_icon.setText(str(QFileDialog.getOpenFileName(
                self, __doc__, os.path.expanduser("~"),
                "PNG (*.png);;JPG (*.jpg);;ICO (*.ico);;All (*.*)")[0])))
        self.open_3 = QPushButton(
            QIcon.fromTheme("folder-open"), "", self, clicked=lambda:
                self.outdir.setText(str(QFileDialog.getExistingDirectory(
                self, __doc__, os.path.expanduser("~")))))
        self.l_icon = QLabel("Target Icon")
        g1vlay.addWidget(QLabel("<b>Target Python"), 0, 0)
        g1vlay.addWidget(self.target, 0, 1)
        g1vlay.addWidget(self.clear_1, 0, 2)
        g1vlay.addWidget(self.open_1, 0, 3)
        g1vlay.addWidget(self.l_icon, 1, 0)
        g1vlay.addWidget(self.t_icon, 1, 1)
        g1vlay.addWidget(self.clear_2, 1, 2)
        g1vlay.addWidget(self.open_2, 1, 3)
        g1vlay.addWidget(QLabel("<b>Output Folder"), 2, 0)
        g1vlay.addWidget(self.outdir, 2, 1)
        g1vlay.addWidget(self.clear_3, 2, 2)
        g1vlay.addWidget(self.open_3, 2, 3)

        # group 4 the dome view mode
        self.jobs = QSpinBox()
        self.jobs.setRange(1, cpu_count())
        self.jobs.setValue(cpu_count())
        self.jobs.setToolTip("Backend Worker Jobs Processes")
        self.python_version = QComboBox()
        self.python_version.addItems(["2.7", "3.2", "3.3", "3.4"])
        self.python_version.setToolTip("Python version to use with Nuitka")
        self.display_tree = QPushButton("Display Tree")
        self.display_tree.clicked.connect(
            lambda: call(NUITKA + " --display-tree {}".format(
                self.target.text()), shell=True))
        self.dump_tree = QPushButton(
            "View Docs", clicked=lambda:
                open_new_tab("http://nuitka.net/doc/user-manual.html"))
        self.open_log = QPushButton("View Logs")
        _log = os.path.join(gettempdir(), "nuitka-gui.log")
        _open = "xdg-open " if sys.platform.startswith("lin") else "open "
        self.open_log.clicked.connect(lambda: call(_open + _log, shell=True))
        self.open_folder = QPushButton("Open Build Folder")
        self.open_folder.clicked.connect(lambda: call(
            _open + str(self.outdir.text()).strip(), shell=True))

        # self.display_tree.clicked.connect(self._display_tree)
        g4vlay.addWidget(QLabel("<b>Worker Jobs"))
        g4vlay.addWidget(self.jobs)
        g4vlay.addWidget(QLabel("<b>Python Version"))
        g4vlay.addWidget(self.python_version)
        g4vlay.addWidget(QLabel("<b>Actions"))
        g4vlay.addWidget(self.display_tree)
        g4vlay.addWidget(self.dump_tree)
        g4vlay.addWidget(self.open_log)
        g4vlay.addWidget(self.open_folder)

        # group 5 miscelaneous stuff
        self.debug, self.scr = QCheckBox("Use Debug"), QCheckBox("Make Script")
        self.chrt, self.ionice = QCheckBox("Slow CPU"), QCheckBox("Slow HDD")
        self.minimi = QCheckBox("Auto Minimize")
        self.chrt.setToolTip("Use Low CPU speed priority (Linux only)")
        self.ionice.setToolTip("Use Low HDD speed priority (Linux only)")
        self.scr.setToolTip("Generate a Bash Script to Compile with Nuitka")
        self.debug.setToolTip("Use Debug Verbose mode")
        self.minimi.setToolTip("Automatically Minimize when compiling starts")
        self.scr.setChecked(True)
        self.chrt.setChecked(True)
        self.ionice.setChecked(True)
        self.minimi.setChecked(True)
        g5vlay.addWidget(self.debug)
        g5vlay.addWidget(self.scr)
        g5vlay.addWidget(self.chrt)
        g5vlay.addWidget(self.ionice)
        g5vlay.addWidget(self.minimi)

        # option to show or hide some widgets on the gui
        self.guimode = QComboBox()
        self.guimode.addItems(('Full UX / UI', 'Simple UX / UI'))
        self.guimode.setCurrentIndex(1)
        self._set_guimode()
        self.guimode.setStyleSheet("""QComboBox{background:transparent;
            margin-left:25px;color:gray;text-decoration:underline;border:0}""")
        self.guimode.currentIndexChanged.connect(self._set_guimode)

        # buttons from bottom to close or proceed
        self.bt = QDialogButtonBox(self)
        self.bt.setStandardButtons(
            QDialogButtonBox.Ok | QDialogButtonBox.Close)
        self.bt.rejected.connect(self.close)
        self.bt.accepted.connect(self.run)

        if not sys.platform.startswith('lin'):
            self.scr.setChecked(False)
            self.chrt.setChecked(False)
            self.ionice.setChecked(False)
            self.scr.hide()
            self.chrt.hide()
            self.ionice.hide()
        if not sys.platform.startswith('win'):
            self.l_icon.hide()
            self.t_icon.hide()
            self.clear_2.hide()
            self.open_2.hide()
        if sys.platform.startswith('win'):
            self.display_tree.hide()

        # container for all groups of widgets
        container = QWidget()
        container_layout = QGridLayout(container)  # Y, X
        container_layout.addWidget(self.guimode, 0, 1)
        container_layout.addWidget(self.group0, 1, 1)
        container_layout.addWidget(self.group1, 2, 1)
        container_layout.addWidget(self.group4, 1, 2)
        container_layout.addWidget(self.group5, 2, 2)
        container_layout.addWidget(self.bt, 3, 1)
        self.setCentralWidget(container)

    def check_paths(self):
        """Check that the paths are valid."""
        if not os.path.isfile(self.target.text()):
            log.error("Target File not found or not valid.")
            QMessageBox.warning(self, __doc__.title(),
                                "Target File not found or not valid.")
            return False
        if not str(self.target.text()).endswith((".py", ".pyw")):
            log.error("Target File not valid.")
            QMessageBox.warning(self, __doc__.title(),
                                "Target File not valid.")
            return False
        if not os.path.isdir(self.outdir.text()):
            log.error("Target Folder not found or not valid.")
            QMessageBox.warning(self, __doc__.title(),
                                "Target Folder not found or not valid.")
            return False
        if self.t_icon.text() and not os.path.isfile(self.t_icon.text()):
            log.warning("Target Icon File not found or not valid.")
            QMessageBox.warning(self, __doc__.title(),
                                "Target Icon File not found or not valid.")
            return True
        else:
            return True

    def generate_build_command(self):
        """Generate a build command."""
        return re.sub(r"\s+", " ", " ".join((
            'chrt --verbose --idle 0' if self.chrt.isChecked() else '',
            'ionice --ignore --class 3' if self.ionice.isChecked() else '',
            NUITKA,
            '--debug --verbose' if self.debug.isChecked() else '',
            '--show-progress' if self.show_progress.isChecked() else '',
            '--show-scons --show-modules' if self.show_scons.isChecked() else '',
            '--unstriped' if self.keep_debug.isChecked() else '',
            '--trace-execution' if self.traced.isChecked() else '',
            '--remove-output' if self.rmbuilddir.isChecked() else '',
            '--code-gen-no-statement-lines' if self.nolineno.isChecked() else '',
            '--execute' if self.execute.isChecked() else '',
            '--recurse-none' if self.recurse_not.isChecked() else '--recurse-all',
            '--recurse-stdlib' if self.recurse_std.isChecked() else '',
            '--clang' if self.force_clang.isChecked() else '',
            '--lto' if self.force_lto.isChecked() else '',
            '--c++-only' if self.plusplus.isChecked() else '',
            '--windows-disable-console' if self.disable_console.isChecked() else '',
            '--experimental' if self.experimental.isChecked() else '',
            '--python-debug' if self.python_debug.isChecked() else '',
            '--module' if self.module.isChecked() else '--standalone',
            '--nofreeze-stdlib' if self.nofreeze.isChecked() else '',
            '--mingw' if self.force_mingw.isChecked() else '',
            '--warn-implicit-exceptions' if self.warning.isChecked() else '',
            '--execute-with-pythonpath' if self.pythonpath.isChecked() else '',
            '--enhanced' if self.enhaced.isChecked() else '',
            '--icon="{}"'.format(self.t_icon.text()) if self.t_icon.text() else '',
            '--python-version={}'.format(self.python_version.currentText()),
            '--jobs={}'.format(self.jobs.value()),
            '--output-dir="{}"'.format(self.outdir.text()),
            '"{}"'.format(self.target.text()))))

    def run(self):
        """Run the main method and run Nuitka."""
        self.statusBar().showMessage('Working...')
        log.debug("Working...")
        if not self.check_paths():
            return
        command_to_run_nuitka = self.generate_build_command()
        log.debug(command_to_run_nuitka)
        self.process.start(command_to_run_nuitka)
        if not self.process.waitForStarted():
            log.error(self._read_errors())
            return  # ERROR
        if self.scr.isChecked() and sys.platform.startswith("lin"):
            script_file = str(self.target.text()).replace(".py",
                                                          "-nuitka-compile.sh")
            log.debug("Writing Script {}".format(script_file))
            with open(script_file, "w", encoding="utf-8") as script:
                script.write("#!/usr/bin/env bash\n" + command_to_run_nuitka)
                os.chmod(script_file, 0o755)
        self.statusBar().showMessage(__doc__.title())

    def _process_finished(self):
        """Finished sucessfuly."""
        log.debug("Finished.")
        self.showNormal()

    def _read_output(self):
        """Read and return output."""
        return str(self.process.readAllStandardOutput()).strip()

    def _read_errors(self):
        """Read and return errors."""
        log.debug(self.process.readAllStandardError())
        return str(self.process.readAllStandardError()).strip()

    def _process_failed(self):
        """Read and return errors."""
        self.showNormal()
        self.statusBar().showMessage(" ERROR: Failed ! ")
        log.warning(str(self.process.readAllStandardError()).strip().lower())
        return str(self.process.readAllStandardError()).strip().lower()

    def _set_guimode(self):
        """Switch between simple and full UX."""
        for widget in (self.group0, self.group4,
                       self.group5, self.statusBar(), self.menuBar()):
            widget.hide() if self.guimode.currentIndex() else widget.show()
        self.resize(self.minimumSize()
                    if self.guimode.currentIndex() else self.maximumSize())
        self.center()

    def skin(self, filename=None):
        """Open QSS from filename,if no QSS return None,if no filename ask."""
        if not filename:
            filename = str(QFileDialog.getOpenFileName(
                self, __doc__ + "-Open QSS Skin file", os.path.expanduser("~"),
                "CSS Cascading Style Sheet for Qt 5 (*.qss);;All (*.*)")[0])
        if filename and os.path.isfile(filename):
            log.debug(filename)
            with open(filename, 'r') as file_to_read:
                text = file_to_read.read().strip()
        if text:
            log.debug(text)
            return text

    def center(self):
        """Center the Window on the Current Screen,with Multi-Monitor support.

        >>> MainWindow().center()
        True
        """
        window_geometry = self.frameGeometry()
        mousepointer_position = QApplication.desktop().cursor().pos()
        screen = QApplication.desktop().screenNumber(mousepointer_position)
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        window_geometry.moveCenter(centerPoint)
        return bool(not self.move(window_geometry.topLeft()))

    def move_to_mouse_position(self):
        """Center the Window on the Current Mouse position.

        >>> MainWindow().move_to_mouse_position()
        True
        """
        window_geometry = self.frameGeometry()
        window_geometry.moveCenter(QApplication.desktop().cursor().pos())
        return bool(not self.move(window_geometry.topLeft()))

    def closeEvent(self, event):
        """Ask to Quit."""
        the_conditional_is_true = QMessageBox.question(
            self, __doc__.title(), 'Quit ?.', QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No) == QMessageBox.Yes
        event.accept() if the_conditional_is_true else event.ignore()


###############################################################################


def main():
    """Main Loop."""
    APPNAME = str(__package__ or __doc__)[:99].lower().strip().replace(" ", "")
    if not sys.platform.startswith("win") and sys.stderr.isatty():
        def add_color_emit_ansi(fn):
            """Add methods we need to the class."""
            def new(*args):
                """Method overload."""
                if len(args) == 2:
                    new_args = (args[0], copy(args[1]))
                else:
                    new_args = (args[0], copy(args[1]), args[2:])
                if hasattr(args[0], 'baseFilename'):
                    return fn(*args)
                levelno = new_args[1].levelno
                if levelno >= 50:
                    color = '\x1b[31m'  # red
                elif levelno >= 40:
                    color = '\x1b[31m'  # red
                elif levelno >= 30:
                    color = '\x1b[33m'  # yellow
                elif levelno >= 20:
                    color = '\x1b[32m'  # green
                elif levelno >= 10:
                    color = '\x1b[35m'  # pink
                else:
                    color = '\x1b[0m'  # normal
                try:
                    new_args[1].msg = color + str(new_args[1].msg) + '\x1b[0m'
                except Exception as reason:
                    print(reason)  # Do not use log here.
                return fn(*new_args)
            return new
        # all non-Windows platforms support ANSI Colors so we use them
        log.StreamHandler.emit = add_color_emit_ansi(log.StreamHandler.emit)
    log.basicConfig(
        level=-1, format="%(levelname)s:%(asctime)s %(message)s", filemode="w",
        filename=os.path.join(gettempdir(), "nuitka-gui.log"))
    log.getLogger().addHandler(log.StreamHandler(sys.stderr))
    try:
        os.nice(19)  # smooth cpu priority
        libc = cdll.LoadLibrary('libc.so.6')  # set process name
        buff = create_string_buffer(len(APPNAME) + 1)
        buff.value = bytes(APPNAME.encode("utf-8"))
        libc.prctl(15, byref(buff), 0, 0, 0)
    except Exception as reason:
        log.debug(reason)
    log.debug("Nuitka path is: {}".format(NUITKA))
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # CTRL+C work to quit app
    application = QApplication(sys.argv)
    application.setApplicationName(__doc__.strip().lower())
    application.setOrganizationName(__doc__.strip().lower())
    application.setOrganizationDomain(__doc__.strip())
    application.setWindowIcon(QIcon.fromTheme("python"))
    try:
        opts, args = getopt(sys.argv[1:], 'hvt', ('version', 'help', 'tests'))
    except:
        pass
    for o, v in opts:
        if o in ('-h', '--help'):
            print(''' Usage:
                  -h, --help        Show help informations and exit.
                  -v, --version     Show version information and exit.
                  -t, --tests       Run Unit Tests on DocTests if any.''')
            return sys.exit(0)
        elif o in ('-v', '--version'):
            print(__version__)
            return sys.exit(0)
        elif o in ('-t', '--tests'):
            testmod(verbose=True, report=True, exclude_empty=True)
            exit(0)
    mainwindow = MainWindow()
    mainwindow.show()
    sys.exit(application.exec_())


if __name__ in '__main__':
    main()
