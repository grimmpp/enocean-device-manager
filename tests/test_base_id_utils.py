import unittest

from eltakobus.message import ESP2Message, Regular4BSMessage

class TestBaseIdUtils(unittest.TestCase):
    
    def test_add_addresses(self):
        a1 = b'\xff\x00\xff\x00'
        a2 = b'\x00\xff\x00\xff'
        
        r = self.add_two_addresses(a1, a2)
        self.assertEqual(r, b'\xff\xff\xff\xff')
        
        a1 = b'\xff\x00\x00\xff'
        r = self.add_two_addresses(a1, a2)
        self.assertEqual(r, b'\xff\xff\x01\xfe')
        
    def add_two_addresses(self, a1, a2):
        # return bytes((a + b) & 0xFF for a, b in zip(a1, a2))
        return (int.from_bytes(a1, 'big') + int.from_bytes(a2, 'big')).to_bytes(4, byteorder='big')
    
    
    def test_add_base_id_to_local_message(self):
        base_id = b'\xff\x0C\x0b\x80'
        msg = Regular4BSMessage(b'\x00\x00\x00\x05', 50, b'\x08\x08\x08\x08', True)
        address = self.add_two_addresses(base_id, msg.address)
        msg2 = ESP2Message( msg.body[:8] + address + msg.body[12:] )
        
        self.assertTrue(base_id not in msg.serialize())
        self.assertTrue(base_id not in msg2.serialize())
        
        self.assertTrue(address not in msg.serialize())
        self.assertTrue(address in msg2.serialize())
        
        
    def test_address_checks(self):
        address = b'\x00\x00\x00\x08'
        self.assertEqual( address[0], 0)
        self.assertEqual( address[0:2], b'\x00\x00')
        self.assertEqual( int.from_bytes(address[0:2]), 0)