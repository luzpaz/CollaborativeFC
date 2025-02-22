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

import asyncio
import Documents.Batcher as Batcher

class Task():
    # Wraps a function to be called as Task
    # Works for async and normal functions, with arbitrary arguments
    
    def __init__(self, fnc, args):
        self.Func = fnc 
        self.Args = args
        
    async def execute(self):
        
        if asyncio.iscoroutinefunction(self.Func):
            await self.Func(*self.Args)
        else:
            self.Func(*self.Args)
                
    def name(self):
        return self.Func.__self__.__class__.__name__ + "." + self.Func.__name__


class _TaskErrorHandler():
    # Base class for runners that unifies error handling of tasks
    
    def __init__(self):
        self.__handler = {}
    
    def registerErrorHandler(self, predicate, fnc, *args):
        self.__handler[predicate] = Task(fnc, args)
        
    async def _handleError(self, error):
        
        for predicate, task in self.__handler:
            if predicate(error):
                await task.execute
                return True
        
        return False


class DocumentRunner():
    #Generates sender and receiver DocumentBatchedOrderedRunner for a whole document where all actions on all 
    #individual runners are executed in order
    
    __sender   = {}
    __receiver = {}
    
    @classmethod
    def getSenderRunner(cls, docId, logger):
        if not docId in DocumentRunner.__sender:
            DocumentRunner.__sender[docId] = OrderedRunner(logger)
        
        return DocumentBatchedOrderedRunner(DocumentRunner.__sender[docId])
    
    @classmethod
    def getReceiverRunner(cls, docId, logger):
        if not docId in DocumentRunner.__receiver:
            DocumentRunner.__receiver[docId] = OrderedRunner(logger)
        
        return DocumentBatchedOrderedRunner(DocumentRunner.__receiver[docId])
            
    
class OrderedRunner(_TaskErrorHandler):
    #AsyncRunner which runs task in order
   
    #runs all tasks synchronous
    def __init__(self, logger):
        
        _TaskErrorHandler.__init__(self)
        
        self.__logger        = logger
        self.__tasks         = []
        self.__syncEvent     = asyncio.Event() 
        self.__finishEvent   = asyncio.Event()
        self.__current       = ""
        
        self.__maintask = asyncio.ensure_future(self.__run())

   
    async def waitTillCloseout(self, timeout = 10):
        try:
            await asyncio.wait_for(self.__finishEvent.wait(), timeout)
            
        except asyncio.TimeoutError as e:
            remaining = self.queued()
            self.__logger.error(f"Runner closeout timed out while working ({not self.__maintask.done()}) on {self.__current}. Remaining: \n{remaining}")     
         

    async def close(self):
        await self.waitTillCloseout()
        try:
            self.__shutdown = True
            if not self.__maintask.cancelled():
                self.__maintask.cancel()
                await self.__maintask
        except asyncio.CancelledError:
            pass
        
        self.__finishEvent.set()       

    async def __run(self):
        
        self.__finishEvent.set()
        while True:
            try:
                await self.__syncEvent.wait()
                self.__finishEvent.clear()
                        
                #work the tasks synchronous
                task = self.__tasks.pop(0)
                while task:
                    self.__current = task.name()
                    try:
                        await task.execute()
                        
                    except Exception as e:
                        if self._handleError(e):
                            # Remove all remaining tasks
                            self.__tasks = []
                        else:
                            raise e
                    
                    if self.__tasks:
                        task = self.__tasks.pop(0)
                    else:
                        task = None
                    
                self.__finishEvent.set()
                self.__syncEvent.clear()
                
            except Exception as e:
                self.__logger.error(f"{e}")
                
        if not self.__shutdown:
            self.__logger.error(f"Main loop of sync runner closed unexpectedly: {e}")
        
           
    def run(self, fnc, *args):
        
        self.__tasks.append(Task(fnc, args))
        self.__syncEvent.set()
        
        
    def queued(self):
        #returns the names of all currently queued tasks
        return [task.name() for task in self.__tasks]
    
    
    def sync(self, syncer):
        self.run(syncer.execute)


class BatchedOrderedRunner(_TaskErrorHandler):
    #batched ordered execution of tasks
    #Normally run received a function object of an async function and its arguments.
    #The functions are than processed in order one by one (each one awaited). If functions can be batched
    #together, this can be done in the following way:
    #1. register batch handler. This is a async function which is called after all batchable functions are executed
    #2. run functions that have a batchhandler assigned. Those functions must not be awaitables, but default functions.

    #runs all tasks synchronous and batches tasks together if possible
    def __init__(self, logger):
        
        _TaskErrorHandler.__init__(self)

        self.__logger        = logger
        self.__tasks         = []
        self.__syncEvent     = asyncio.Event() 
        self.__finishEvent   = asyncio.Event()
        self.__batcher       = []
        self.__shutdown      = False

        self.__maintask = asyncio.ensure_future(self.__run())


    def registerBatcher(self, batcher):        
        self.__batcher.append(batcher)


    async def waitTillCloseout(self, timeout = 10):     
        try:
            await asyncio.wait_for(self.__finishEvent.wait(), timeout)
            
        except asyncio.TimeoutError as e:
            remaining = self.queued()
            self.__logger.error(f"Runner closeout timed out while working ({not self.__maintask.done()}). Remaining: \n{remaining}")     


    async def close(self):
               
        await self.waitTillCloseout()
        try:
            self.__shutdown = True
            if not self.__maintask.cancelled():
                self.__maintask.cancel()
                await self.__maintask
        except asyncio.CancelledError:
            pass
        
        self.__finishEvent.set()
        

    async def __run(self):
                  
        #initially we have no work
        self.__finishEvent.set()
            
        while True:
            
            try:
                #wait till new tasks are given.
                await self.__syncEvent.wait()
                
                #inform that we are working
                self.__finishEvent.clear()            
                    
                #work the tasks in order
                while self.__tasks:
                                       
                    try:
                        executed  = await Batcher.executeBatchersOnTasks(self.__batcher, self.__tasks, )
                        if executed > 0:
                            self.__tasks = self.__tasks[executed:]
                        else:                       
                            #not batchable, execute normal operation
                            await self.__tasks.pop(0).execute()

                    except Exception as e:
                        
                        if self._handleError(e):
                            # Remove all tasks now
                            self.__tasks = []
                        else:
                            raise e
                
                self.__finishEvent.set()
                self.__syncEvent.clear()


            except Exception as e:
                self.logger.error(f"Unexpected exception in BatchedOrderedRunner: {e}")
                
        if not self.__shutdown:            
            self.logger.error(f"Unexpected shutdown in BatchedOrderedRunner: {e}")
        
           
    def run(self, fnc, *args):
        
        self.__tasks.append(Task(fnc, args))
        self.__syncEvent.set()
        
    def queued(self):
        #returns the names of all currently queued tasks
        return [task.name() for task in self.__tasks]
        
    def sync(self, syncer):
        self.run(syncer.execute)
        

class DocumentBatchedOrderedRunner():
    #A Async runner that synchronizes over the whole document, and has the same API as the BatchedOrderedRunner to be 
    #compatible replacement
    
    def __init__(self, runner):
        self.__docRunner = runner
        self.__batchHandler = {}
        
        
    def registerBatchHandler(self, fncName, batchFnc):        
        self.__batchHandler[fncName] = batchFnc;
        
    
    def run(self, fnc, *args):
        
        #check if this function needs to be handled by batch function, and 
        #build a wrapper if so
        if fnc.__name__ in self.__batchHandler:
            
            handler = self.__batchHandler[fnc.__name__ ]
            
            async def wrapper(*args):
                fnc(*args)
                await handler()
                
            self.__docRunner.run(wrapper, *args)
            
        else:
            self.__docRunner.run(fnc, *args)
                
                
    def queued(self):
        #returns the names of all currently queued tasks
        return self.__docRunner.queued()
        
    def sync(self, syncer):
        #syncronisation: provide a syncer. The runner calls done() when all currently 
        #available work is done and afterwards wait for the restart till new things are processed
        return self.__docRunner.sync(syncer)
                
                
    async def waitTillCloseout(self, timeout = 10):
        #Returns when all active tasks are finished. Also waits for tasks added after the call to this function
        return await self.__docRunner.waitTillCloseout(timeout)


    async def close(self):
        return await self.__docRunner.close()
           

