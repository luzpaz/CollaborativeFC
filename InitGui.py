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

#handle basic logging first
#*******************************************************
import logging, txaio, sys
#txaio.use_asyncio()
#txaio.start_logging(level='error') 
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format="[%(levelname)8s] %(name)25s:   %(message)s")
logging.getLogger('asyncqt').setLevel(logging.ERROR)


#import the collaboration infrastructure
#*******************************************************
import FreeCAD, Collaboration, Commands, Test

#need to import Part::Gui to register the coin nodes, e.g. EdgeBrepSet
import PartGui


#setup the UI
#*******************************************************
if FreeCAD.GuiUp:
    import FreeCADGui
    FreeCADGui.addCommand('Collaborate', Commands.CommandCollaboration(Collaboration.widget))
    
# setup the toolbar
group = FreeCAD.ParamGet("User parameter:BaseApp/Workbench/Global/Toolbar")

# as the GUI for custom global toolbars always rename them to "Custom_X" we need to search if 
# a colaboration toolbar is already set up
alreadySetup = False
for i in range(1,1000):
    if group.HasGroup("Custom_" + str(i)):
        custom = group.GetGroup("Custom_" + str(i))
        if custom.GetBool("CollaborationAutoSetup", False):
            alreadySetup = True
        else:
            custom.RemBool("CollaborationAutoSetup")
    else:
        break

#if not already done add our global toolbar
if not alreadySetup:
    # add the toolbar and make it findable
    collab = group.GetGroup("Custom_" + str(i))
    collab.SetString("Name", "Collaboration Network")
    collab.SetBool("Active", True)
    collab.SetBool("CollaborationAutoSetup", True)
    
    # add the tools
    collab.SetString("Collaborate", "Command")
