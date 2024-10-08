from pymodbus.client.sync import ModbusTcpClient
import pymodbus
import logging
log = logging.getLogger('pymodbus')
log.setLevel(logging.DEBUG)
logging.basicConfig(level='DEBUG')

print('modbus version', pymodbus.__version__)

c = ModbusTcpClient('192.168.20.23')
c.connect()
rstart = 5030
n = 10 # can't be too big
#reg = c.read_input_registers(rstart-1,n,unit=1)
reg = c.read_holding_registers(rstart-1,n,unit=1)
for i in range(n):
    addr = rstart + i
    v = reg.registers[i]
    print(f'addr {addr}={v:d} 0x{v:x}')


