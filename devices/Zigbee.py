import sqlite3
from core.device.model.Device import Device
from core.device.model.DeviceAbility import DeviceAbility
from core.device.model.DeviceType import DeviceType
from core.dialog.model.DialogSession import DialogSession
from core.util.model.TelemetryType import TelemetryType
from core.webui.model.DeviceClickReactionAction import DeviceClickReactionAction
from core.webui.model.OnDeviceClickReaction import OnDeviceClickReaction
from pathlib import Path
from typing import Dict, Union


class Zigbee(Device):

	def __init__(self, data: Union[sqlite3.Row, Dict]):
		super().__init__(data)


	@classmethod
	def getDeviceTypeDefinition(cls) -> dict:
		return {
			'deviceTypeName'             : 'Zigbee',
		         'perLocationLimit'      : 0,
		         'totalDeviceLimit'      : 0,
		         'allowLocationLinks'    : True,
		         'allowHeartbeatOverride': True,
		         'heartbeatRate'         : 2700,
		         'abilities'             : [DeviceAbility.NONE]
		}

	def onUIClick(self) -> dict:
		"""
		Called whenever a device's icon is clicked on the UI
		:return:
		"""
		if not self.paired:
			self.discover()
			return OnDeviceClickReaction(
				action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
				data='notifications.info.pleasePlugDevice'
			).toDict()

		if self.zigbeeType == 'switch':
			self.skillInstance.publish(topic=f'zigbee2mqtt/{self._deviceConfigs["displayName"]}/set', payload={'state': 'TOGGLE'})
		elif self.zigbeeType == 'environment':
			return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
			                             data={'body': f'Temperatur: {self.getParam("temperature", "unknown")} \n Luftfeuchte: {self.getParam("humidity", "unknown")}'})

		return OnDeviceClickReaction(action=DeviceClickReactionAction.NONE.value).toDict()


	def getDeviceIcon(self) -> Path:
		"""
		Return the path of the icon representing the current status of the device
		e.g. a light bulb can be on or off and display its status
		:return: the icon file path
		"""
		base = self._typeName
		type = self.zigbeeType
		status = self.zigbeeStatus
		return Path(f'{self.Commons.rootDir()}/skills/{self.skillName}/devices/img/{base}'
		            f'{f"_{type}" if type else ""}'
		            f'{f"_{status}" if status else ""}.png')


	def discover(self, replyOnSiteId: str = "", session: DialogSession = None) -> bool:
		self.skillInstance.allowNewDeviceJoining(limitToOne=True, device=self)


		def later():
			self.skillInstance.blockNewDeviceJoining()
			self.skillInstance.publish(topic=self.skillInstance.TOPIC_QUERY_DEVICE_LIST)


		self.ThreadManager.doLater(interval=60, func=later)
		return True

	def toggle(self, device: Device):
		pass


	def onZigbeeMessage(self, payload):
		if self.zigbeeType == 'switch':
			self.updateParamFromPayload(payload, 'state')
		elif self.zigbeeType == 'window':
			self.updateParamFromPayload(payload, 'contact')
		elif self.zigbeeType == 'environment':
			self.updateParamFromPayload(payload, 'temperature')
			self.updateParamFromPayload(payload, 'humidity')

		if True or self.getConfig('storeTelemetry'):
			# exploded = [excl.strip() for excl in device.devSettings['excludedTelemetry'].split(',')]
			for key, val in payload.items():
				# if not key in exploded:
				try:
					ttype = TelemetryType(key)
					self.TelemetryManager.storeData(deviceId=self.id, locationId=self.getLocation().id, service='Zigbee', ttype=ttype, value=val)
				except ValueError:
					pass
		else:
			self.parentSkillInstance.logInfo("not Storing any telemetry for that device")


	def onRename(self, device: Device, newName: str) -> bool:
		if ' ' in newName:
			newName = newName.replace(' ', '_')

		self.parentSkillInstance.publish(topic=self.parentSkillInstance.TOPIC_RENAME_DEVICE,
		                                 payload={
			                                 'old': device.name,
			                                 'new': newName
		                                 })

		# todo wait for rename done message

		return True


	@property
	def zigbeeType(self) -> str:
		exposes = self.getParam('exposes')
		if not exposes:
			return ""
		for exposure in exposes:
			if exposure['type'] in ['light', 'switch', 'fan', 'cover', 'lock', 'climate']:
				return exposure['type']
			elif exposure['type'] == 'binary' and exposure['property'] == 'contact':
				return "window"
			elif exposure['type'] == 'numeric' and exposure['property'] == 'temperature':
				hasTemp = True
			elif exposure['type'] == 'numeric' and exposure['property'] == 'humidity':
				hasHumidity = True
		if hasTemp and hasHumidity:
			return 'environment'
		elif hasTemp:
			return 'thermometer'
		elif hasHumidity:
			return 'humidity'
		return ""


	@property
	def zigbeeStatus(self) -> str:
		if self.zigbeeType == 'switch':
			return self.getParam('state', "")
		if self.zigbeeType == 'window':
			return self.getParam('contact', "")
		if self.zigbeeType == 'environment':
			temp = self.getParam('temperature', "")
			ts = "OK"
			if temp > 22:
				ts = "HIGH"
			elif temp < 18:
				ts = "LOW"
			humi = self.getParam('humidity', "")
			hs = "OK"
			if humi > 60:
				hs = "WET"
			elif humi < 40:
				hs = "DRY"
			return ts + hs

		return ""


	def updateParamFromPayload(self, payload, param: str):
		state = payload.get(param, None)
		if state is not None:
			self.updateParams(param, state)
