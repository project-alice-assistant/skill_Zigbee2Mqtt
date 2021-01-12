from typing import Callable, Generator, Optional

from core.base.model.AliceSkill import AliceSkill
from core.commons import constants
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import MqttHandler
from core.device.model.Device import Device
from core.device.model.DeviceAbility import DeviceAbility


class Zigbee2Mqtt(AliceSkill):
	"""
	Author: Psychokiller1888
	Description: Have your zigbee devices communicate with alice directly over mqtt
	"""

	TOPIC_QUERY_DEVICE_LIST = 'zigbee2mqtt/bridge/config/devices/get'
	TOPIC_PERMIT_JOIN = 'zigbee2mqtt/bridge/config/permit_join'
	TOPIC_REMOVE_DEVICE = 'zigbee2mqtt/bridge/config/remove'
	TOPIC_FORCE_REMOVE_DEVICE = 'zigbee2mqtt/bridge/config/force_remove'
	TOPIC_RENAME_DEVICE = 'zigbee2mqtt/bridge/config/rename'

	TOPIC_BRIDGE_STATE = 'zigbee2mqtt/bridge/state'
	TOPIC_DEVICES_CONFIG = 'zigbee2mqtt/bridge/config/devices'
	TOPIC_BRIDGE_LOGS = 'zigbee2mqtt/bridge/log'
	TOPIC_BRIDGE_CONFIGS = 'zigbee2mqtt/bridge/config'


	DEVICES = {
		'Zigbee': {
			'deviceTypeName'    : 'Zigbee',
			'perLocationLimit'  : 0,
			'totalDeviceLimit'  : 0,
			'allowLocationLinks': True,
			'heartbeatRate'     : 0,
			'deviceSettings'    : { 'storeTelemetry': True,
									'excludedTelmetry': ''
									},
			'abilities'         : [DeviceAbility.NONE]
		}
	}


	def __init__(self):
		self._online = False
		self._lastMessage = ''
		self._limitToOne = False
		self._currentlyPairing = None
		super().__init__(devices=self.DEVICES)


	@MqttHandler('zigbee2mqtt/#')
	def zigbeeMessage(self, session: DialogSession):
		if session.intentName == self.TOPIC_BRIDGE_STATE:
			self.bridgeStateReport(session)

		if not self._online:
			return
		elif session.intentName == self.TOPIC_DEVICES_CONFIG:
			self.deviceList(session)
		elif session.intentName == self.TOPIC_BRIDGE_LOGS:
			self.handleLogMessage(session)
		else:
			return self.deviceMessage(session)


	def deviceMessage(self, session: DialogSession):
		# ignore double messages - zigbee sends just multiple messages and hopes one arrives
		if session.payload == self._lastMessage:
			return
		else:
			self._lastMessage = session.payload
		deviceName = session.intentName.split('/')[-1]
		device = self.DeviceManager.getDeviceByName(name=deviceName)

		if not device:
			return False

		device.deviceType.onZigbeeMessage(device, session.payload)
		return True


	def bridgeStateReport(self, session: DialogSession):
		if session.payload['state'].decode() == 'online':
			self._online = True
			self.logInfo('Zigbee server online')


			def later():
				self.blockNewDeviceJoining()
				self.publish(topic=self.TOPIC_QUERY_DEVICE_LIST)


			self.ThreadManager.doLater(interval=1, func=later)

		elif session.payload['state'].decode() == 'offline':
			self._online = False
			self.logInfo('Zigbee server offline')


	def deviceList(self, session: DialogSession):
		self.logDebug(f'Received device list, checking for new devices')

		for devicePayload in session.payload:
			if devicePayload.get('type', '') != 'EndDevice':
				continue

			device = self.DeviceManager.getDevice(uid=devicePayload['ieeeAddr'])
			if not device:
				devices = self.DeviceManager.getDevicesBySkill(skillName=self.name)
				for search in devices:
					if search.uid == '-1':
						device = search
						break
				if device:
					device.pairingDone(uid=devicePayload['ieeeAddr'])
				else:
					if self.getConfig('createDeviceViaZigbee'):
						defLocation = self.DeviceManager.getMainDevice().getLocation()
						self.logInfo(f'Creating device for {devicePayload["friendly_name"]} in {defLocation.name} ')

						device = self.DeviceManager.addNewDevice(locationId=defLocation.id,
						                                         skillName=self.name,
						                                         deviceType='Zigbee',
						                                         uid=devicePayload['ieeeAddr'])
						device.changeName(devicePayload['friendly_name'])
					else:
						self.logWarning(f'device {devicePayload["friendly_name"]} not existing!\n {devicePayload}')
					pass


	def handleLogMessage(self, session: DialogSession):
		logType = session.payload.get('type', None)
		if not logType:
			return

		if logType == 'device_removed':
			deviceName = session.payload['message'] if not 'meta' in session.payload else session.payload['meta']['friendly_name']
			self._removeDevice(name=deviceName)

		elif logType == 'device_renamed':
			device = self.DeviceManager.getDeviceByName(name=session.payload['message']['from'])
			if not device:
				return
			device.changeName(session.payload['message']['to'])

		elif logType == 'device_removed_failed':
			self.publish(topic=self.TOPIC_FORCE_REMOVE_DEVICE, stringPayload=session.payload['message'])

		elif logType == 'device_force_removed':
			self._removeDevice(name=session.payload['message'])

		elif logType == 'pairing':
			#todo interview_started vs interview_successful
			if not self._currentlyPairing:
				#todo check if device was existing
				pass
			if session.payload['message'] != 'interview_successful':
				return
			#session.payload['message']['meta']['friendly_name']

			self._currentlyPairing = None

			self.broadcast(method=constants.EVENT_DEVICE_ADDED, exceptions=[self.name], propagateToSkills=True)
			if self._limitToOne:
				self.blockNewDeviceJoining()


	def _removeDevice(self, name: str):
		"""
		Stricly internal, only called once the server has confirmed the deletion
		:param name: device friend name
		"""
		#todo determine behaviour: delete device? unlink device?
		pass


	def removeDevice(self, friendlyName: str):
		self.publish(
			topic=self.TOPIC_REMOVE_DEVICE,
			stringPayload=friendlyName
		)


	def allowNewDeviceJoining(self, limitToOne: bool = False, device: Device = None):
		if self._currentlyPairing and self._currentlyPairing != device:
			raise Exception('already Pairing another device!')
		self._limitToOne = limitToOne
		self._currentlyPairing = device
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
