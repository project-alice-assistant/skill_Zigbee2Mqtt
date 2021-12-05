import sqlite3
from core.device.model.Device import Device
from core.device.model.DeviceAbility import DeviceAbility
from core.device.model.DeviceType import DeviceType
from core.dialog.model.DialogSession import DialogSession
from core.util.model.TelemetryType import TelemetryType
from core.webui.model.DeviceClickReactionAction import DeviceClickReactionAction
from core.webui.model.OnDeviceClickReaction import OnDeviceClickReaction
from datetime import datetime
from pathlib import Path
from skills.Zigbee2Mqtt.ZigbeeType import ZigbeeType
from typing import Dict, Optional, Union


class Zigbee(Device):

	def __init__(self, data: Union[sqlite3.Row, Dict]):
		super().__init__(data)
		self.zigbeeType = ZigbeeType.generic


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

		if self.zigbeeType.simplify() == ZigbeeType.switch:
			# Toggle that switch
			self.skillInstance.publish(topic=f'zigbee2mqtt/{self.getConfig("ieee")}/set', payload={'state': 'TOGGLE'})
		elif self.zigbeeType.simplify() == ZigbeeType.environment:
			# Info Output of current temperature and humidity
			temp = str(self.getParam("temperature", "unknown")) + "°C"
			humidity = str(self.getParam("humidity", "unknown")) + "%"
			return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
			                             data={'body': self.skillInstance.randomTalk('GUI_env_reporting', [temp, humidity], self.skillInstance.name)}).toDict()
		elif self.zigbeeType.simplify() == ZigbeeType.window:
			# Info Output of current state and time since this state was taken
			lastChanged = self.getParam("lastChange", "unknown")
			return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
			                             data={'body': self.skillInstance.randomTalk('GUI_window_reporting_closed' if self.getParam("contact") else 'GUI_window_reporting_open', [lastChanged], self.skillInstance.name)}).toDict()

		elif self.zigbeeType.simplify() == ZigbeeType.climate:
			# toggle auto off + set target temp + HOT
			if self.getParam("system_mode") == 'auto':
				self.skillInstance.publish(topic=f'zigbee2mqtt/{self.getConfig("ieee")}/set', payload={'system_mode': 'heat'})
				self.skillInstance.publish(topic=f'zigbee2mqtt/{self.getConfig("ieee")}/set', payload={'current_heating_setpoint': '24'})  # todo device config value
				return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
				                             data={'body': self.skillInstance.randomTalk('GUI_climtate_set_temp', [24], self.skillInstance.name)}).toDict()
			if self.getParam("system_mode") == 'heat':
				self.skillInstance.publish(topic=f'zigbee2mqtt/{self.getConfig("ieee")}/set', payload={'system_mode': 'off'})
				return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
				                             data={'body': self.skillInstance.randomTalk('GUI_climtate_set_temp', ["off"], self.skillInstance.name)}).toDict()
			else:
				# toggle auto on == unset current temp
				self.skillInstance.publish(topic=f'zigbee2mqtt/{self.getConfig("ieee")}/set', payload={'system_mode': 'auto'})
				return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
				                             data={'body': self.skillInstance.randomTalk('GUI_climtate_set_temp', ["automatic mode"], self.skillInstance.name)}).toDict()
		elif self.zigbeeType.simplify() == ZigbeeType.light:
			# toggle light on/off
			self.skillInstance.publish(topic=f'zigbee2mqtt/{self.getConfig("ieee")}/set', payload={'state': 'TOGGLE'})
			return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
			                             data={'body': self.skillInstance.randomTalk('GUI_light_toggle', [], self.skillInstance.name)}).toDict()

		return OnDeviceClickReaction(action=DeviceClickReactionAction.NONE.value).toDict()


	def getDeviceIcon(self, path: Optional[Path] = None) -> Path:
		"""
		Return the path of the icon representing the current status of the device
		e.g. a light bulb can be on or off and display its status
		:return: the icon file path
		"""
		base = self._typeName
		typ = self.zigbeeType.simplify().name
		status = self.zigbeeStatus
		icon = Path(f'{self.Commons.rootDir()}/skills/{self.skillName}/devices/img/{base}'
		            f'{f"_{typ}" if type else ""}'
		            f'{f"_{status}" if status else ""}.png')
		return super().getDeviceIcon(icon)


	def discover(self, replyOnSiteId: str = '', session: DialogSession = None) -> bool:
		self.skillInstance.allowNewDeviceJoining(limitToOne=True, device=self)

		def later():
			self.skillInstance.blockNewDeviceJoining()
			self.skillInstance.publish(topic=self.skillInstance.TOPIC_QUERY_DEVICE_LIST)

		self.ThreadManager.doLater(interval=60, func=later)
		return True


	def onZigbeeMessage(self, payload):
		if self.zigbeeType.simplify() == ZigbeeType.switch or self.zigbeeType.simplify() == ZigbeeType.light:
			self.updateParamFromPayload(payload, 'state')
		elif self.zigbeeType.simplify() == ZigbeeType.window:
			old = self.getParam('contact')
			new = payload.get('contact', None)
			self.updateParamFromPayload(payload, 'contact')

			if old != new:
				self.updateParam('lastChange', datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))

		elif self.zigbeeType.simplify() == ZigbeeType.environment:
			self.updateParamFromPayload(payload, 'temperature')
			self.updateParamFromPayload(payload, 'humidity')

		elif self.zigbeeType.simplify() == ZigbeeType.climate:
			self.updateParamFromPayload(payload, 'local_temperature')
			self.updateParamFromPayload(payload, 'current_heating_setpoint')
			self.updateParamFromPayload(payload, 'local_temperature_calibration')
			self.updateParamFromPayload(payload, 'running_state')
			self.updateParamFromPayload(payload, 'away_mode')
			self.updateParamFromPayload(payload, 'system_mode')

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
	def zigbeeStatus(self) -> str:
		if self.zigbeeType.simplify() == ZigbeeType.switch or self.zigbeeType.simplify() == ZigbeeType.light:
			return self.getParam('state', "")
		if self.zigbeeType.simplify() == ZigbeeType.window:
			return self.getParam('contact', "")
		if self.zigbeeType.simplify() == ZigbeeType.environment:
			temp = int(self.getParam('temperature', ""))
			ts = "OK"
			if temp > 22:
				ts = "HIGH"
			elif temp < 18:
				ts = "LOW"
			humi = int(self.getParam('humidity', ""))
			hs = "OK"
			if humi > 60:
				hs = "WET"
			elif humi < 40:
				hs = "DRY"
			return ts + hs
		if self.zigbeeType.simplify() == ZigbeeType.climate:
			bottom = ""
			top = ""
			if self.getParam('away_mode') == "ON":
				bottom = "away"
			else:
				bottom = self.getParam('system_mode')
			if float(self.getParam('local_temperature')) > float(self.getParam('current_heating_setpoint')):
				top = "OFF"
			else:
				top = "ON"
			return top + bottom

		return ""


	def updateParamFromPayload(self, payload, param: str):
		state = payload.get(param, None)
		if state is not None:
			self.updateParam(param, state)


	def updateType(self):
		exposes = self.getParam('exposes')
		for exposure in exposes:
			if exposure['type'] in ['light', 'switch', 'fan', 'cover', 'lock', 'climate']:
				self.zigbeeType = self.zigbeeType | ZigbeeType[exposure['type']]
			else:
				try:
					self.zigbeeType = self.zigbeeType | ZigbeeType[exposure['property']]
				except KeyError:
					pass
