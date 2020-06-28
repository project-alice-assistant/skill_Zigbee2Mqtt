from typing import Dict, Generator, Optional

from .model.ZigbeeDeviceHandler import ZigbeeDeviceHandler
from core.base.model.AliceSkill import AliceSkill
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import MqttHandler


class Zigbee2Mqtt(AliceSkill): #NOSONAR
	"""
	Author: Psychokiller1888
	Description: Have your zigbee devices communicate with alice directly over mqtt
	"""

	TOPIC_QUERY_DEVICE_LIST = 'zigbee2mqtt/bridge/config/devices'
	TOPIC_PERMIT_JOIN = 'zigbee2mqtt/bridge/config/permit_join'
	TOPIC_REMOVE_DEVICE = 'zigbee2mqtt/bridge/config/remove'
	TOPIC_RENAME_DEVICE = 'zigbee2mqtt/bridge/config/rename'


	def __init__(self):
		self._online = False
		self._devices = dict()
		self._subscribers: Dict[str: AliceSkill] = dict()
		super().__init__()


	@MqttHandler('zigbee2mqtt/bridge/state')
	def bridgeStateReport(self, session: DialogSession):
		if session.payload['state'] == b'online':
			self._online = True
			self.logInfo('Zigbee server online')
		else:
			self._online = False
			self.logInfo('Zigbee server offline')


	@MqttHandler('zigbee2mqtt/bridge/log')
	def handleMessage(self, session: DialogSession):
		logType = session.payload.get('type', None)
		if not logType:
			return

		if logType == 'devices':
			for device in session.payload['message']:
				if device['type'] != 'EndDevice':
					continue

				self._devices[device['friendly_name']] = device
		elif logType == 'device_removed':
			self._devices.pop(session.payload['message'])
		elif logType == 'device_renamed':
			device = self._devices.pop(session.payload['from'], None)

			if not device:
				return

			device['friendlyName'] = session.payload['to']
			self._devices[session.payload['to']] = device


	@MqttHandler('zigbee2mqtt/+')
	def deviceMessage(self, session: DialogSession):
		deviceName = session.intentName.split('/')[-1]
		device = self._devices.get(deviceName, None)
		if not device:
			return

		subscriber = self._subscribers.get(device['modelIID'], None)
		if not subscriber:
			return

		try:
			func = getattr(subscriber, 'onDeviceMessage')
			func(session.payload)
		except:
			self.logWarning(f'{subscriber.name} is subscribed for devices but does not implement **onDeviceMessage**')


	def getDevice(self, friendlyName: str) -> Optional[dict]:
		return self._devices.get(friendlyName, None)


	def getDevices(self) -> Generator[dict, None, None]:
		for device in self._devices.values():
			yield device


	def subscribeForDevices(self, subscriber: ZigbeeDeviceHandler, deviceType: str):
		print(subscriber)
		print(deviceType)
		self._subscribers[deviceType] = subscriber


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


	def onStart(self):
		super().onStart()
		self.Commons.runRootSystemCommand(['systemctl', 'start', 'zigbee2mqtt'])
		self.blockNewDeviceJoining()
		self.publish(topic=self.TOPIC_QUERY_DEVICE_LIST)


	def onStop(self):
		super().onStop()
		self.Commons.runRootSystemCommand(['systemctl', 'stop', 'zigbee2mqtt'])


	def onBooted(self) -> bool:
		for subscriber in self._subscribers.values():
			try:
				func = getattr(subscriber, 'onDeviceListReceived')
				func(self._devices)
			except:
				self.logWarning(f'{subscriber.name} is subscribed for devices but does not implement **onDeviceListReceived**')

		return True
