from core.device.model.DeviceType import DeviceType
import sqlite3
from core.device.model.Device import Device
from core.dialog.model.DialogSession import DialogSession
from core.util.model.TelemetryType import TelemetryType

from typing import Union, Dict

class Zigbee(Device):
	DEV_SETTINGS = {
		'storeTelemetry': True,
		'excludedTelmetry': ''  #define csv which should not be added to telemetry, e.g. battery,linkquality
	}
	LOC_SETTINGS = {}

	def __init__(self, data: Union[sqlite3.Row, Dict]):
		super().__init__(data)


	def discover(self, device: Device, uid: str, replyOnSiteId: str = "", session: DialogSession = None) -> bool:
		self.parentSkillInstance.allowNewDeviceJoining(limitToOne=True, device=device)

		def later():
			self.blockNewDeviceJoining()
			self.publish(topic=self.TOPIC_QUERY_DEVICE_LIST)

		self.ThreadManager.doLater(interval=60, func=later)

	def toggle(self, device: Device):
		pass

	def onZigbeeMessage(self, device: Device, payload):
		if True or device.devSettings['storeTelemetry']:
			#exploded = [excl.strip() for excl in device.devSettings['excludedTelemetry'].split(',')]
			self.parentSkillInstance.logInfo(payload)
			for key, val in payload.items():
				#if not key in exploded:
				try:
					ttype = TelemetryType(key)
					self.TelemetryManager.storeData(siteId=device.uid, locationID=device.getMainLocation().id, service=self.name, ttype=ttype, value=val)
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

	def getDeviceIcon(self) -> str:
		#todo figure out a concept for getting the correct icon for that kind of device
		return 'Zigbee.png'
