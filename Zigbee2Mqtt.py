from typing import Callable, Dict, Generator, Optional

from .model.ZigbeeDeviceHandler import ZigbeeDeviceHandler
from core.base.model.AliceSkill import AliceSkill
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import MqttHandler


class Zigbee2Mqtt(AliceSkill): #NOSONAR
	"""
	Author: Psychokiller1888
	Description: Have your zigbee devices communicate with alice directly over mqtt
	"""

	TOPIC_QUERY_DEVICE_LIST = 'zigbee2mqtt/bridge/config/devices/get'
	TOPIC_PERMIT_JOIN = 'zigbee2mqtt/bridge/config/permit_join'
	TOPIC_REMOVE_DEVICE = 'zigbee2mqtt/bridge/config/remove'
	TOPIC_RENAME_DEVICE = 'zigbee2mqtt/bridge/config/rename'


	def __init__(self):
		self._online = False
		self._devices = dict()
		self._subscribers: Dict[str: ZigbeeDeviceHandler] = dict()
		super().__init__()


	@MqttHandler('zigbee2mqtt/bridge/state')
	def bridgeStateReport(self, session: DialogSession):
		if session.payload['state'] == b'online':
			self._online = True
			self.logInfo('Zigbee server online')

			self.blockNewDeviceJoining()
			self.publish(topic=self.TOPIC_QUERY_DEVICE_LIST)
		else:
			self._online = False
			self.logInfo('Zigbee server offline')


	@MqttHandler('zigbee2mqtt/bridge/config/devices')
	def deviceList(self, session: DialogSession):
		self.logDebug(f'Received device list')
		self._devices = dict()

		for device in session.payload:
			if device['type'] != 'EndDevice':
				continue

			self._devices[device['friendly_name']] = device

		for handler in self._subscribers.values():
			handler.onDeviceListReceived(self._devices)


	@MqttHandler('zigbee2mqtt/bridge/log')
	def handleLogMessage(self, session: DialogSession):
		logType = session.payload.get('type', None)
		if not logType:
			return

		if logType == 'device_removed':
			self._devices.pop(session.payload['message'])
		elif logType == 'device_renamed':
			device = self._devices.pop(session.payload['from'], None)

			if not device:
				return

			device['friendlyName'] = session.payload['to']
			self._devices[session.payload['to']] = device


	@MqttHandler('zigbee2mqtt/abc')
	def deviceMessage(self, session: DialogSession):
		deviceName = session.intentName.split('/')[-1]
		device = self._devices.get(deviceName, None)
		if not device:
			return

		handler = self._subscribers.get(device['modelID'], None)
		if not handler:
			return

		handler(session.payload)


	def getDevice(self, friendlyName: str) -> Optional[dict]:
		return self._devices.get(friendlyName, None)


	def getDevices(self) -> Generator[dict, None, None]:
		for device in self._devices.values():
			yield device


	def subscribe(self, deviceType: str, onMessageCallback: Callable) -> ZigbeeDeviceHandler:
		handler = ZigbeeDeviceHandler(deviceType=deviceType, onMessageCallback=onMessageCallback)
		self._subscribers[deviceType] = handler
		return handler


	def renameDevice(self, friendlyName: str, newName: str) -> bool:
		if ' ' in newName:
			newName = newName.replace(' ', '_')

		if newName in self._devices:
			return False

		self.publish(
			topic=self.TOPIC_RENAME_DEVICE,
			payload={
				'old': friendlyName,
				'new': newName
			}
		)

		return True


	def removeDevice(self, friendlyName: str):
		self.publish(
			topic=self.TOPIC_REMOVE_DEVICE,
			stringPayload=friendlyName
		)


	def allowNewDeviceJoining(self):
		self.publish(
			topic=self.TOPIC_PERMIT_JOIN,
			stringPayload='true'
		)


	def blockNewDeviceJoining(self):
		self.publish(
			topic=self.TOPIC_PERMIT_JOIN,
			stringPayload='false'
		)


	def onBooted(self) -> bool:
		self.Commons.runRootSystemCommand(['systemctl', 'start', 'zigbee2mqtt'])
		return super().onBooted()


	def onStop(self):
		super().onStop()
		self.Commons.runRootSystemCommand(['systemctl', 'stop', 'zigbee2mqtt'])
