from typing import Callable, Dict, Union
from core.base.model.ProjectAliceObject import ProjectAliceObject


class ZigbeeDeviceHandler(ProjectAliceObject):

	def __init__(self, deviceType: str, onMessageCallback: Callable):
		super().__init__()
		self._deviceType = deviceType
		self._onMessage = onMessageCallback
		self._devices: Dict[str, dict] = dict()


	def onDeviceMessage(self, message: Union[str, Dict]):
		self._onMessage(message)


	def onDeviceListReceived(self, listing: dict):
		self._devices = {name: device for name, device in listing.items() if f'{device.get("vendor", "")}_{device.get("model", "")}' == self._deviceType}


	def removeDevice(self, name: str):
		self._devices.pop(name, None)
