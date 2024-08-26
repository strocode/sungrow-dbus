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

# set max power output = units of 0.1%
max_output = 10
addr = 5039 # export limitation value - units of 0.1 %
#addr = 5039 # power limitation adjustment
reg = c.write_register(addr-1,max_output,unit=1)
reg = c.read_holding_registers(addr-1, 1, unit=1)
print(f'set max output to {reg.registers[0]}')




