from core.device.model.DeviceType import DeviceType
import sqlite3
from core.device.model.Device import Device
from core.dialog.model.DialogSession import DialogSession
from core.util.model.TelemetryType import TelemetryType
from core.device.model.DeviceAbility import DeviceAbility
from core.webui.model.DeviceClickReactionAction import DeviceClickReactionAction
from core.webui.model.OnDeviceClickReaction import OnDeviceClickReaction

from typing import Union, Dict

class Zigbee(Device):

	def __init__(self, data: Union[sqlite3.Row, Dict]):
		super().__init__(data)

	@classmethod
	def getDeviceTypeDefinition(cls) -> dict:
		return { 'deviceTypeName'        : 'Zigbee',
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

		return OnDeviceClickReaction(action=DeviceClickReactionAction.NONE.value).toDict()


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
		if True or self.devSettings['storeTelemetry']:
			#exploded = [excl.strip() for excl in device.devSettings['excludedTelemetry'].split(',')]
			for key, val in payload.items():
				#if not key in exploded:
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


		self.parentSkillInstance.publish(   topic=self.parentSkillInstance.TOPIC_RENAME_DEVICE,
						payload={   'old': device.name,
									'new': newName })

		#todo wait for rename done message

		return True
