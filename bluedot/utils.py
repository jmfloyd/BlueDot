from __future__ import unicode_literals

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

import time
import sys
import os

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)


SERVICE_NAME = "org.bluez"
ADAPTER_INTERFACE = SERVICE_NAME + ".Adapter1"
DEVICE_INTERFACE = SERVICE_NAME + ".Device1"
PROFILE_MANAGER = SERVICE_NAME + ".ProfileManager1"

def get_managed_objects():
    bus = dbus.SystemBus()
    manager = dbus.Interface(bus.get_object(SERVICE_NAME, "/"), "org.freedesktop.DBus.ObjectManager")
    return manager.GetManagedObjects()

def find_adapter(pattern=None):
    return find_adapter_in_objects(get_managed_objects(), pattern)

def find_adapter_in_objects(objects, pattern=None):
    bus = dbus.SystemBus()
    for path, ifaces in objects.items():
        adapter = ifaces.get(ADAPTER_INTERFACE)
        if adapter is None:
            continue
        if not pattern or pattern == adapter["Address"] or path.endswith(pattern):
            obj = bus.get_object(SERVICE_NAME, path)
            return dbus.Interface(obj, ADAPTER_INTERFACE)
    raise Exception("Bluetooth adapter {} not found".format(pattern))

def get_adapter_property(device_name, prop):
    bus = dbus.SystemBus()
    adapter_path = find_adapter(device_name).object_path
    adapter = dbus.Interface(bus.get_object(SERVICE_NAME, adapter_path),"org.freedesktop.DBus.Properties")
    return adapter.Get(ADAPTER_INTERFACE, prop)

def get_mac(device_name):
    return get_adapter_property(device_name, "Address")

def get_adapter_powered_status(device_name):
    powered = get_adapter_property(device_name, "Powered")
    return bool(powered)

def get_adapter_discoverable_status(device_name):
    discoverable = get_adapter_property(device_name, "Discoverable")
    return bool(discoverable)

def get_adapter_pairable_status(device_name):
    pairable = get_adapter_property(device_name, "Pairable")
    return bool(pairable)

def find_device(device_name,adapter='hci0'):
    bus = dbus.SystemBus()
#    dpath='/'.join((find_adapter(adapter).object_path,device_name))
#    print('dpath',dpath)
    device_object = bus.get_object(SERVICE_NAME, device_name)
    device = dbus.Interface(device_object, DEVICE_INTERFACE)
#    print('find_device',device)
    return device

def get_device_property(device, prop, ptype=ascii):
    device_properties = dbus.Interface(device, "org.freedesktop.DBus.Properties")
    return ptype(device_properties.Get(DEVICE_INTERFACE, prop))

def get_device_connected_status(device_name):
    value = get_adapter_property(device_name, "Connected")
    return bool(value)

def get_paired_devices(device_name):
    paired_devices = []

    bus = dbus.SystemBus()
    adapter_path = find_adapter(device_name).object_path
    om = dbus.Interface(bus.get_object(SERVICE_NAME, "/"), "org.freedesktop.DBus.ObjectManager")
    objects = om.GetManagedObjects()

    for path, interfaces in objects.items():
        if DEVICE_INTERFACE not in interfaces:
            continue
        properties = interfaces[DEVICE_INTERFACE]
        if properties["Adapter"] != adapter_path:
            continue

        paired_devices.append((str(properties["Address"]), str(properties["Alias"])))

    return paired_devices

def device_discoverable(device_name, discoverable):
    bus = dbus.SystemBus()
    adapter_path = find_adapter(device_name).object_path
    adapter = dbus.Interface(bus.get_object(SERVICE_NAME, adapter_path),"org.freedesktop.DBus.Properties")
    if discoverable:
        value = dbus.Boolean(1)
    else:
        value = dbus.Boolean(0)
    adapter.Set(ADAPTER_INTERFACE, "Discoverable", value)

def device_pairable(device_name, pairable):
    bus = dbus.SystemBus()
    adapter_path = find_adapter(device_name).object_path
    adapter = dbus.Interface(bus.get_object(SERVICE_NAME, adapter_path),"org.freedesktop.DBus.Properties")
    if pairable:
        value = dbus.Boolean(1)
    else:
        value = dbus.Boolean(0)
    adapter.Set(ADAPTER_INTERFACE, "Pairable", value)

def device_powered(device_name, powered):
    bus = dbus.SystemBus()
    adapter_path = find_adapter(device_name).object_path
    adapter = dbus.Interface(bus.get_object(SERVICE_NAME, adapter_path),"org.freedesktop.DBus.Properties")
    if powered:
        value = dbus.Boolean(1)
    else:
        value = dbus.Boolean(0)
    adapter.Set(ADAPTER_INTERFACE, "Powered", value)

def register_spp(port):

    service_record = """
    <?xml version="1.0" encoding="UTF-8" ?>
    <record>
      <attribute id="0x0001">
        <sequence>
          <uuid value="0x1101"/>
        </sequence>
      </attribute>

      <attribute id="0x0004">
        <sequence>
          <sequence>
            <uuid value="0x0100"/>
          </sequence>
          <sequence>
            <uuid value="0x0003"/>
            <uint8 value="{}" name="channel"/>
          </sequence>
        </sequence>
      </attribute>

      <attribute id="0x0100">
        <text value="Serial Port" name="name"/>
      </attribute>
    </record>
    """.format(port)

    bus = dbus.SystemBus()

    manager = dbus.Interface(bus.get_object(SERVICE_NAME, "/org/bluez"),
                             PROFILE_MANAGER)

    print("Setting up Profile")

    path = "/bluez"
    uuid = "00001101-0000-1000-8000-00805f9b34fb"
    opts = {
#        "AutoConnect" : True,
        "ServiceRecord" : service_record
    }

    try:
        manager.RegisterProfile(path, uuid, opts)
    except dbus.exceptions.DBusException as e:
        #the spp profile has already been registered, ignore
        if str(e) != "org.bluez.Error.AlreadyExists: Already Exists":
            raise(e)

'''
Creates a profile class with call backs and dbus methods
SPP class creates the profile and runs in its own thread till killed
'''


class Profile(dbus.service.Object):
    fd = -1

    def __init__(self, bus, path, read_cb=None, debug=False):
        self.read_io_cb = read_cb
        self.conn_device = None
        self.debug=debug
        dbus.service.Object.__init__(self, bus, path)

    @dbus.service.method('org.bluez.Profile1',
                         in_signature='',
                         out_signature='')
    def Release(self):
        print('Release')
        mainloop.quit()

    @dbus.service.method('org.bluez.Profile1',
                         in_signature='oha{sv}',
                         out_signature='')
    def NewConnection(self, path, fd, properties):
        self.fd = fd.take()
#        print('NewConnection(dev %s, fh %d)' % (path, self.fd))
        self.conn_device = path
        io_id = GLib.io_add_watch(self.fd,
                                     GLib.PRIORITY_DEFAULT,
                                     GLib.IO_IN | GLib.IO_PRI,
                                     self.io_cb)


    @dbus.service.method('org.bluez.Profile1',
                         in_signature='o',
                         out_signature='')
    def RequestDisconnection(self, path):
        print('RequestDisconnection(%s)' % (path))

        if self.fd > 0:
            os.close(self.fd)
            self.fd = -1

    def io_cb(self, fd, conditions):
        try:
            if self.fd>-1:
                data = os.read(fd, 1024)
                self.read_io_cb(data.decode('ascii'))
                if self.debug:
                    print('reading',data)
                return True
        except ConnectionResetError:
            print("Disconnect found on read")
            self.fd = -1
            self.conn_device = None

    def write_io(self, value):
        try:
            if self.fd>-1:
                os.write(self.fd, value.encode('utf8'))
            else:
                raise ConnectionResetError
        except ConnectionResetError:
            print("Disconnect found on send")
            self.fd = -1
            self.conn_device = None


class SPP:

    def __init__(self, read_cb=None, debug=False):
        self.profile = None
        self.debug=debug
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object(SERVICE_NAME,
                                                '/org/bluez'),
                                 PROFILE_MANAGER)

        self.mainloop = GLib.MainLoop()
        adapter_props = dbus.Interface(bus.get_object(SERVICE_NAME,
                                                      '/org/bluez/hci0'),
                                       'org.freedesktop.DBus.Properties')
        adapter_props.Set(ADAPTER_INTERFACE, 'Powered', dbus.Boolean(1))
        profile_path = '/bluez'
        server_uuid = '00001101-0000-1000-8000-00805f9b34fb'
        opts = {
            'AutoConnect': True,
            'Role': 'server',
            'Channel': dbus.UInt16(1),
            'Name': 'BattMon'
        }

        print('Starting Serial Port Profile...')

        if read_cb is None:
            self.profile = Profile(bus, profile_path, self.read_cb,
                                   debug=False)
        else:
            self.profile = Profile(bus, profile_path, read_cb,
                                   debug=False)

        manager.RegisterProfile(profile_path, server_uuid, opts)

    def read_cb(self, value):
        print(value)

    def send(self, value):
        self.profile.write_io(value)

    def fd_available(self):
        if self.profile.fd > 0:
            return True
        else:
            return False

    def get_conn_device(self):

        return self.profile.conn_device

    def start(self, stopping=False):
        self.mainloop.run()

