import atexit
from threading import Thread, Event

_THREADS = set()
_TCount = 0



stop_thread = False

def _shutdown():
    while _THREADS:
        for t in _THREADS.copy():
            print("Threads Shutdown",t.name)
            t.stop()

def _Inc_TCount():
    _TCount=1
    return _TCount

def _has_name(name):
    for t in _THREADS.copy():
        if t.name == name:
            return t
    return None

atexit.register(_shutdown)


class WrapThread(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
        if name is None:
            name = 'BattMon'
        self.stopping = Event()
        kwargs['stopping']=self.stopping
        super(WrapThread, self).__init__(group, target, name, args, kwargs)
        self.daemon = True
        # only have one thread with same name - kill existing ...
        t = _has_name(self.name)
        if t :
            print("Killing thread",self.name)
            t.stop()

    def start(self):
        self.stopping.clear()
        _THREADS.add(self)
        print("Starting Thread",self.name)
        super(WrapThread, self).start()

    def kill(self):
        self.stop()

    def stop(self):
        self.stopping.set()
        self.join()

    def join(self):
        super(WrapThread, self).join(1)
        _THREADS.discard(self)
