from pymodbus.client.sync import ModbusTcpClient
import pymodbus
import logging
log = logging.getLogger('pymodbus')
log.setLevel(logging.DEBUG)
logging.basicConfig(level='DEBUG')

print('modbus version', pymodbus.__version__)

c = ModbusTcpClient('192.168.20.23')
c.connect()
reg = c.read_input_registers(5000-1,20,unit=1)
print(reg)
