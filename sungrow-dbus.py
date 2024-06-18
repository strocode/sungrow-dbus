#!/usr/bin/env python3

"""
A class to put a simple service on the dbus, according to victron standards, with constantly updating
paths. See example usage below. It is used to generate dummy data for other processes that rely on the
dbus. See files in dbus_vebus_to_pvinverter/test and dbus_vrm/test for other usage examples.

To change a value while testing, without stopping your dummy script and changing its initial value, write
to the dummy data via the dbus. See example.

https://github.com/victronenergy/dbus_vebus_to_pvinverter/tree/master/test
"""
from gi.repository import GLib
import platform
import argparse
import logging
import sys
import os
import dbus
# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '../ext/velib_python'))
sys.path.insert(1, '/opt/victronenergy')
sys.path.insert(1, '/opt/victronenergy/dbus-mqtt/ext/velib_python/')
from vedbus import VeDbusService
from pymodbus.client.sync import ModbusTcpClient

def twos_comp(val, bits=16):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value

    return val

def read(client, addr, n=1):
    reg = client.read_input_registers(addr-1,n,unit=1).registers
    reg = list(map(twos_comp, reg))
    if n == 1:
        reg = reg[0]
    return reg

# Need to make independent system busses otherwise you can't have multiple devices per process
# https://community.victronenergy.com/questions/46675/venus-os-driver-for-fronius-smart-meter.html
class SystemBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SYSTEM)
    

class Reg:
    def __init__(self, path, address):
        pass

class SungrowProduct:
    def __init__(self, client, productname, servicename, deviceinstance):
        self._dbusservice = VeDbusService(servicename, bus=SystemBus())
        self._client = client
        self._paths = []
        self._interval_ms = 1000

        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))
        connection=str(self._client)
        productid=self.read(5000)

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', productid)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/FirmwareVersion', 0)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)

    def __iadd__(self, d):
        path = d[0]
        initial_value= 0
        self._dbusservice.add_path(path, initial_value)
        return self

    def read(self, addr, n=1):
        return read(self._client, addr, n)



class SungrowInverter(SungrowProduct):
    def __init__(self, client, servicename, deviceinstance):
        super().__init__(client, 'Sungrow Inverter', servicename, deviceinstance)
    
        # Fixed values
        maxpower = 10 # self.read(XXX)
        self._dbusservice.add_path('/Ac/MaxPower', maxpower)
        position = 1 # where it's connected to the inverter. 0=AC input 1; 1=AC output; 2=AC input 2
        self._dbusservice.add_path('/Position', position)

        self += '/Ac/Energy/Forward', 'kWh', 5004 #Total produced energy over all phases = Total power yields
        self += '/Ac/Power', 'W', 5009 # Total apparent power
        #        self += '/Ac/PowerLimit', 'W' # writeable # TODO
        self += '/StatusCode', ''
        self += '/FroniusDeviceType',''

        for phase in range (0,3):
            p = phase + 1
            self += f'/Ac/L{p}/Current', 'A AC', 5022+phase, 0.1
            self += f'/Ac/L{p}/Energy/Forward', 'kWh'
            self += f'/Ac/L{p}/Power', 'W'
            self += f'/Ac/L{p}/Voltage', 'V AC', 5019+phase, 0.1

        #for path, settings in self._paths.items():
        #    self._dbusservice.add_path(
        #        path, settings['initial'], writeable=True, onchangecallback=self._handlechangedvalue)

        self.phase_energies = [0,0,0]            

        GLib.timeout_add(self._interval_ms, self._update)


    def _update(self):
        interval_sec = self._interval_ms/1000.0
        with self._dbusservice as s:
            s['/Ac/Power'] = self.read(5009)
            s['/Ac/Energy/Forward'] = self.read(5004)
            d = self.read(5019, 6)
            for phase in range(3):
                p = phase + 1
                v = d[phase]*0.1 # Volts
                i = d[phase + 3]*0.1 # Amps
                phase_power =  v * i*0.001 # KW
                self.phase_energies[phase] += phase_power * interval_sec/3600.0 # kWh

                s[f'/Ac/L{p}/Voltage'] = round(v, 1)
                s[f'/Ac/L{p}/Current'] = round(i, 1)
                s[f'/Ac/L{p}/Power'] = round(phase_power, 1)
                s[f'/Ac/L{p}/Energy/Forward'] =  round(self.phase_energies[phase],1)



        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True # accept the change
    
class SungrowMeter(SungrowProduct):
    def __init__(self, client, servicename, deviceinstance):
        super().__init__(client, 'Sungrow Meter', servicename, deviceinstance)    
        # Fixed values

        self._dbusservice.add_path('/DeviceType', 'Internal meter')

        self += '/Ac/Energy/Forward', 'kWh', 5004 # Bought energy
        self += '/Ac/Energy/Reverse', 'kWh', 5004 # Sold energy
        self += '/Ac/Power', 'W', 5009 # Total apparent power
        #        self += '/Ac/PowerLimit', 'W' # writeable # TODO
        self += '/StatusCode', ''

        for phase in range (0,3):
            p = phase + 1
            self += f'/Ac/L{p}/Current', 'A AC', 5022+phase, 0.1
            self += f'/Ac/L{p}/Energy/Forward', 'kWh'
            self += f'/Ac/L{p}/Power', 'W'
            self += f'/Ac/L{p}/Voltage', 'V AC', 5019+phase, 0.1

        self.phase_energies = [0,0,0]            

        GLib.timeout_add(self._interval_ms, self._update)


    def _update(self):
        interval_sec = self._interval_ms/1000.0
        with self._dbusservice as s:
            d = self.read(5083, n=5104-5083)
            # Every second one is rubbish
            d = d[::2]
            s['/Ac/Power'] = round(d[0],1) # W
            s['/Ac/Energy/Forward'] = round(d[8]*0.1,1) # Total import energy - kWh
            s['/Ac/Energy/Reverse'] = round(d[6]*0.1,1) # total export energy - kWh

            dvolts = self.read(5019, 6)
            pd = d[1:] # phase data
            for phase in range(3):
                p = phase + 1
                v = 0 # not supplied
                i = 0 # not supplied
                phase_power = pd[phase]/1e3

                s[f'/Ac/L{p}/Voltage'] = round(v, 1)
                s[f'/Ac/L{p}/Current'] = round(i, 1)
                s[f'/Ac/L{p}/Power'] = round(phase_power, 1)
                s[f'/Ac/L{p}/Energy/Forward'] =  round(self.phase_energies[phase],1)



        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True # accept the change


# === All code below is to simply run it from the commandline for debugging purposes ===

# It will created a dbus service called com.victronenergy.pvinverter.output.
# To try this on commandline, start this program in one terminal, and try these commands
# from another terminal:
# dbus com.victronenergy.pvinverter.output
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward GetValue
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward SetValue %20
#
# Above examples use this dbus client: http://code.google.com/p/dbus-tools/wiki/DBusCli
# See their manual to explain the % in %20



def main():
    logging.basicConfig(level=logging.INFO)

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)
    client = ModbusTcpClient('192.168.20.23')
    client.connect()

    inverter = SungrowInverter(
        client,
        servicename='com.victronenergy.pvinverter.sungrow01',
        deviceinstance=0,
    )
    meter = SungrowMeter(
        client,
        servicename='com.victronenergy.grid.sungrow01',
        deviceinstance=0,
    )


    #o2 = SungrowInverter(
	#servicename='com.victronenergy.dummyservice2.tty02',
    #    deviceinstance=1,
    ##    paths={
     #       '/Ac/Energy/Forward': {'initial': 0, 'update': 1},
    #        '/Position': {'initial': 0, 'update': 0},
    #        '/Nonupdatingvalue/UseForTestingWritesForExample': {'initial': None},
    #        '/DbusInvalid': {'initial': None}
    #   	})

    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
