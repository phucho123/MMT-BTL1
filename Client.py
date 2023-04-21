import tkinter.messagebox as tkMessageBox
from tkinter import *
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    DESCRIBE = 4
    FORWARD = 5
    BACKWARD = 6
    SWITCH = 7


    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0
        self.movies = ["movie.Mjpeg","video.mjpeg"]
        self.movieIndex = 0

    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        self.setup = Button(self.master, width=20, padx=3, pady=3,bg='green')
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        # Create Play button
        self.start = Button(self.master, width=20, padx=3, pady=3,background='blue')
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, padx=2, pady=2)

        # Create Pause button
        self.pause = Button(self.master, width=20, padx=3, pady=3,background='orange')
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3,bg='red')
        self.teardown["text"] = "Teardown"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        #Create Describe button
        self.describe = Button(self.master, width=20, padx=3, pady=3,bg='yellow')
        self.describe["text"] = "Describe"
        self.describe["command"] = self.sendDescribe
        self.describe.grid(row=2, column=0, padx=2, pady=2)

        #Create Backward button
        self.backward = Button(self.master, width=20, padx=3, pady=3,bg='red')
        self.backward["text"] = "Backward"
        self.backward["command"] = self.backwarding
        self.backward.grid(row=2, column=1, padx=2, pady=2)

        #Create Forward button
        self.forward = Button(self.master, width=20, padx=3, pady=3,bg='blue')
        self.forward["text"] = "Forward"
        self.forward["command"] = self.forwarding
        self.forward.grid(row=2, column=2, padx=2, pady=2)

        #Create Switch button
        self.switch = Button(self.master, width=20, padx=3, pady=3,bg='violet')
        self.switch["text"] = "Switch"
        self.switch["command"] = self.switching
        self.switch.grid(row=2, column=3, padx=2, pady=2)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W + E + N + S, padx=5, pady=5)

        self.text_box = Text(self.master, height=5, width=50)
        self.text_box.grid(row=3, column=0, columnspan=4, padx=2, pady=2)

    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()  # Close the gui window
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)  # Delete the cache image from video

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)

    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            # Create a new thread to listen for RTP packets
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)

    def forwarding(self):
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.FORWARD)
    def backwarding(self):
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.BACKWARD)
    def switching(self):
        self.sendRtspRequest(self.SWITCH)
    def sendDescribe(self):
        self.sendRtspRequest(self.DESCRIBE)

    def listenRtp(self):
        """Listen for RTP packets."""
        while True:
            try:
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)

                    currFrameNbr = rtpPacket.seqNum()
                    print("Current Seq Num: " + str(currFrameNbr))

                    if self.requestSent == self.BACKWARD or currFrameNbr >= self.frameNbr:  # Discard the late packet
                        self.frameNbr = currFrameNbr
                        self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
                        self.requestSent = self.PLAY
            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.playEvent.isSet():
                    break

                # Upon receiving ACK for TEARDOWN request,
                # close the RTP socket
                if self.teardownAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break

    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()

        return cachename

    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        photo = ImageTk.PhotoImage(Image.open(imageFile))
        self.label.configure(image=photo, height=288)
        self.label.image = photo

    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)

    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""
        # -------------
        # TO COMPLETE
        # -------------

        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply).start()
            # Update RTSP sequence number.
            self.rtspSeq = 1

            # Write the RTSP request to be sent.
            request = ( "SETUP " + str(self.fileName) + " RTSP/1.0 " + "\n"
                        "CSeq: " + str(self.rtspSeq) + "\n"
                        "Transport: RTP/UDP; client_port= " + str(self.rtpPort))

            # Keep track of the sent request.
            self.requestSent = self.SETUP

        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            # Update RTSP sequence number.
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            request = ("PLAY " + str(self.fileName) + " RTSP/1.0 " + "\n" +
                        "CSeq: " + str(self.rtspSeq) + "\n" +
                        "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            self.requestSent = self.PLAY

        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            # Update RTSP sequence number.
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            request = ( "PAUSE " + str(self.fileName) + " RTSP/1.0 " + "\n" +
                        "CSeq: " + str(self.rtspSeq) + "\n" +
                        "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            self.requestSent = self.PAUSE

        # Teardown request
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            # Update RTSP sequence number.
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            request = ( "TEARDOWN " + str(self.fileName) + " RTSP/1.0" + "\n"
                        "CSeq: " + str(self.rtspSeq) + "\n"
                        "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            self.requestSent = self.TEARDOWN
        elif requestCode == self.FORWARD:
            # Update RTSP sequence number.
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            request = ( "FORWARD " + str(self.fileName) + " RTSP/1.0" + "\n"
                        "CSeq: " + str(self.rtspSeq) + "\n"
                        "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            self.requestSent = self.FORWARD
        elif requestCode == self.BACKWARD:
            # Update RTSP sequence number.
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            request = ( "BACKWARD " + str(self.fileName) + " RTSP/1.0" + "\n"
                        "CSeq: " + str(self.rtspSeq) + "\n"
                        "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            self.requestSent = self.BACKWARD
        elif requestCode == self.SWITCH:
            # Update RTSP sequence number.
            self.rtspSeq = self.rtspSeq + 1
            self.movieIndex = (self.movieIndex+1)%len(self.movies)
            self.fileName = self.movies[self.movieIndex]
            self.frameNbr = 0
            # Write the RTSP request to be sent.
            request = ( "SWITCH " + str(self.fileName) + " RTSP/1.0" + "\n"
                        "CSeq: " + str(self.rtspSeq) + "\n"
                        "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            self.requestSent = self.SWITCH
        elif requestCode == self.DESCRIBE:
            # Update RTSP sequence number.
            self.rtspSeq = self.rtspSeq + 1
            # Write the RTSP request to be sent.
            request = ( "DESCRIBE " + str(self.fileName) + " RTSP/1.0" + "\n"
                        "CSeq: " + str(self.rtspSeq) + "\n"
                        "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            self.requestSent = self.DESCRIBE
        else:
            return

        # Send the RTSP request using rtspSocket.
        self.rtspSocket.send(request.encode("utf-8"))

        print('\nData sent:\n' + request)

    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(1024)

            if reply:
                self.parseRtspReply(reply.decode("utf-8"))
                if self.requestSent == self.DESCRIBE: 
                   self.text_box.insert(END,reply.decode("utf-8")+"\n")
                   self.requestSent = self.PLAY

            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break

    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])

        # Process only if the server reply's sequence number is the same as the request's
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            # New RTSP session ID
            if self.sessionId == 0:
                self.sessionId = session

            # Process only if the session ID is the same
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200:
                    if self.requestSent == self.SETUP:
                        # -------------
                        # TO COMPLETE
                        # -------------
                        # Update RTSP state.
                        self.state = self.READY

                        # Open RTP port.
                        self.openRtpPort()
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY

                        # The play thread exits. A new thread is created on resume.
                        self.playEvent.set()
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT

                        # Flag the teardownAcked to close the socket.
                        self.teardownAcked = 1



    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        # -------------
        # TO COMPLETE
        # -------------
        # Create a new datagram socket to receive RTP packets from the server
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set the timeout value of the socket to 0.5sec
        self.rtpSocket.settimeout(0.5)

        try:
            # Bind the socket to the address using the RTP port given by the client user
            self.state = self.READY
            self.rtpSocket.bind(('', self.rtpPort))
        except:
            tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:  # When the user presses cancel, resume playing.
            self.playMovie()