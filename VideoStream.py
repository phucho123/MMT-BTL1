class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		self.dataArray = []
		self.curlen = 0
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		
	def nextFrame(self):
		"""Get next frame."""
		data = self.file.read(5) # Get the framelength from the first 5 bits
		if data: 
			framelength = int(data)
			
			# Read the current frame
			data = self.file.read(framelength)
			self.frameNum += 1

			if self.curlen < self.frameNum:
				self.dataArray.append(framelength)
				self.curlen = self.frameNum
		return data
		
	def nextNFrame(self,numFrame):
		for i in range(0,numFrame):
			data = self.file.read(5) # Get the framelength from the first 5 bits
			if data:
				framelength = int(data)
								
				# Read the current frame
				data = self.file.read(framelength)
				self.frameNum += 1

				if self.curlen < self.frameNum:
					self.dataArray.append(framelength)
					self.curlen = self.frameNum
		return data
	
	def goBackward(self):
		# print(self.dataArray)
		for i in range(0,90):
			if self.frameNum > 0:
				self.file.seek(-(5+self.dataArray[self.frameNum-1]),1)
				self.frameNum-=1
		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
	