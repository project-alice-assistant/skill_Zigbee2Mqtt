from typing import Dict, Union

from core.base.model.AliceSkill import AliceSkill
from core.base.model.ProjectAliceObject import ProjectAliceObject


class ZigbeeDeviceHandler(ProjectAliceObject):

	def __init__(self, skillInstance, modelId: str):
		super().__init__()
		self._skillInstance = skillInstance
		self._modelId = modelId
		self._devices = dict()
		self._linkQuality = None


	def onBooted(self):
		server = self.SkillManager.getSkillInstance('Zigbee2Mqtt')
		if not server:
			return

		server.subscribeForDevices(self, self._modelId)


	def onDeviceListReceived(self, listing: dict):
		for device in listing:
			if device['modelIID'] != self._modelId:
				continue

			self._devices = device


	def onDeviceMessage(self, message: Union[str, Dict]):
		self._skillInstance(message)


	@property
	def linkQuality(self) -> int:
		return self._linkQuality
