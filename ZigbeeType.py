from enum import Flag, auto


class ZigbeeType(Flag):
	generic = 0
	light = auto()
	switch = auto()
	fan = auto()
	cover = auto()
	lock = auto()
	climate = auto()
	window = auto()
	contact = window
	temperature = auto()
	humidity = auto()

	environment = temperature | humidity


	def simplify(self):
		if self.environment in self:
			return self.environment
		if self.climate in self:
			return self.climate
		if self.light in self:
			return self.light
		if self.fan in self:
			return self.fan
		if self.cover in self:
			return self.cover
		if self.contact in self:
			return self.window
		if self.switch in self:
			return self.switch
		if self.lock in self:
			return self.lock
		if self.temperature in self:
			return self.temperature
		if self.humidity in self:
			return self.humidity
		return self.generic
