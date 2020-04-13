# ************************************************************************
# *   Copyright (c) Stefan Troeger (stefantroeger@gmx.net) 2019          *
# *                                                                      *
# *   This library is free software; you can redistribute it and/or      *
# *   modify it under the terms of the GNU Library General Public        *
# *   License as published by the Free Software Foundation; either       *
# *   version 2 of the License, or (at your option) any later version.   *
# *                                                                      *
# *   This library  is distributed in the hope that it will be useful,   *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of     *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the      *
# *   GNU Library General Public License for more details.               *
# *                                                                      *
# *   You should have received a copy of the GNU Library General Public  *
# *   License along with this library; see the file COPYING.LIB. If not, *
# *   write to the Free Software Foundation, Inc., 59 Temple Place,      *
# *   Suite 330, Boston, MA  02111-1307, USA                             *
# ************************************************************************


import asyncio, txaio, subprocess, os
from autobahn.asyncio.component import Component
from autobahn.wamp.serializer import MsgPackSerializer
from asyncqt import QEventLoop
from PySide import QtCore

#Helper class to call the running node via CLI
class OCPNode():
    
    def __init__(self):
        self.ocp = '/home/stefan/Projects/Go/CollaborationNode/CollaborationNode'
        self.test = False
        
        #for testing we need to connect to a dedicated node       
        if os.getenv('OCP_TEST_RUN', "0") == "1":
            #we are in testing mode! check out the required node to connect to
            print("OCP test mode detected")
            self.test = True
            self.conf = os.getenv("OCP_TEST_NODE_CONFIG", "none")
            
            if self.conf == "none":
                raise("Testmode is set, but no config file name provided")

    async def init(self):

        if self.test:
            #no initialisation needed in test run!
            print("Test mode: no initialization required")
            return
        
        #check if init is required
        process = await asyncio.create_subprocess_shell(self.ocp, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await process.communicate()
        
        if not out:
            raise Exception("Unable to call OCP network")
        
        if "OCP directory not configured" in out.decode():
        
            process = await asyncio.create_subprocess_shell(self.ocp + ' init', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await process.communicate()
        
            if not out:
                raise Exception("Unable to call OCP network")
        
            if err and err.decode() != "":
                raise Exception("Unable to initialize OCP node:", err.decode())
            
            if "Node directory was initialized" not in out.decode():
                raise Exception("Unable to initialize OCP node:", out.decode())


    async def port(self):
        
        args = self.ocp + ' config -o connection.port'
        if self.test:
            args += " --config " + self.conf
         
        process = await asyncio.create_subprocess_shell(args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await process.communicate()
        
        if not out:
            raise Exception("Unable to call OCP network")
        
        if err and err.decode() != "":
            raise Exception("Unable to get Port from OCP node:", err.decode())
        
        if "No node is currently running" in out.decode():
            raise Exception("No node running: cannot read port")

        return out.decode().rstrip()
    
      
    async def uri(self):
        
        args = self.ocp + ' config -o connection.uri'
        if self.test:
            args += " --config " + self.conf
            
        process = await asyncio.create_subprocess_shell(args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await process.communicate()
        
        if not out:
            raise Exception("Unable to call OCP network")
        
        if err and err.decode() != "":
            raise Exception("Unable to get URI from OCP node:", err.decode())
        
        if "No node is currently running" in out.decode():
            raise Exception("No node running: cannot read port")
                            
        return out.decode().rstrip()
    
    
    async def start(self):
        
        if self.test:
            #in test mode we do not start our own node!
            print("Test mode: no own node startup!")
            return
        
        process = await asyncio.create_subprocess_shell(self.ocp, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await process.communicate()
        
        if not out:
            raise Exception("Unable to call OCP network")
        
        if err and err.decode() != "":
            raise Exception("Unable to start OCP node:", err.decode())
        
        if "No node is currently running" in out.decode():
            await asyncio.create_subprocess_shell(self.ocp, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            

    async def setup(self):
        await self.init()
        await self.start()
      

#Class to handle all connection matters to the ocp node
# must be provided all components that need to use this connection
class OCPConnection():
        
    def __init__(self, *argv):
        
        self.node = OCPNode()
        self.session = None 
        self.components = list(argv)        
        
        #make sure asyncio and qt work together
        app = QtCore.QCoreApplication.instance()
        loop = QEventLoop(app)
        txaio.config.loop = loop
        asyncio.set_event_loop(loop)       
        asyncio.ensure_future(self._startup())
   
   
    async def _startup(self):

        #setup the node
        await self.node.setup()
        print("Node setup done!")
        
        #make the OCP node connection!            
        uri = "ws://" + await self.node.uri() + ":" + await self.node.port() + "/ws"          
        self.wamp = Component(transports=uri, realm = "ocp")
        self.wamp.on('join', self.onJoin)
        self.wamp.on('leave', self.onLeave)

        coros = [self.wamp.start()]
            
        if os.getenv('OCP_TEST_RUN', "0") == "1":
            uri = os.getenv('OCP_TEST_SERVER_URI', '')
            self.test = Component(transports=uri, realm = "ocptest")
            self.test.on('join', self.testOnJoin)
            self.test.on('leave', self.testOnLeave)
            coros.append(self.test.start())

        #blocks till all wamp handling is finsihed
        await asyncio.wait(coros)

        
        
    async def onJoin(self, session, details):
        print("Connection to OCP node established")
        self.session = session
        #startup all relevant components
        for comp in self.components:
            comp.setConnection(self)
            
            
    async def onLeave(self, session, reason):
        print("Connection to OCP node lost: ", reason)
        #stop all relevant components
        for comp in self.components:
            comp.removeConnection()
            
            
    async def testOnJoin(self, session, details):
        print("Connection to OCP test server established")
        self.testSession = session
            
            
    async def testOnLeave(self, session, reason):
        print("Connection to OCP test server lost: ", reason)
 
