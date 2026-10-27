"""Small Qt worker wrapper; all widget updates remain on the GUI thread."""
from PySide6.QtCore import QObject,QRunnable,Signal
class TaskSignals(QObject):
    done=Signal(str)
class BackupTask(QRunnable):
    def __init__(self,callback):super().__init__();self.callback=callback;self.signals=TaskSignals()
    def run(self):
        import logging
        error=''
        try:self.callback()
        except Exception as exception:error=str(exception);logging.exception('Background backup failed')
        self.signals.done.emit(error)
