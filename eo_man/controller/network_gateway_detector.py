import time
import threading
from esp2_gateway_adapter.esp3_tcp_com import TCP2SerialCommunicator, detect_lan_gateways

class NetworkGatewayDetector(threading.Thread):


    def __init__(self, callback_esp3_gw, callback_esp2_gw):
        self._running = False
        self.callback_esp3_gw = callback_esp3_gw
        self.callback_esp2_gw = callback_esp2_gw

    def stop(self):
        self._running = False
        self.join()

    def run(self):
        if not self._running:
            self._running = True

            while self._running:

                esp3_gw_list = detect_lan_gateways()
                for gw in esp3_gw_list:
                    self.callback_esp3_gw(gw)


                time.sleep(5)
